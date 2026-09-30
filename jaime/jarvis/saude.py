"""Dados de treino e saúde que o João manda do celular — o "monitor" do vídeo (passos, pico de batimento, estresse,
recuperação) e as "observações" do briefing.

Entrada: `POST /webhook/saude` (X-Jaime-Token) com o JSON do app **Health Auto Export** (iPhone, formato
`{"data": {"metrics": [...], "workouts": [...]}}`) ou um JSON simples `{"distancia_km":…, "duracao_min":…,
"fc_pico":…, "estresse":…, "recuperacao":…}` (Whoop/Garmin/atalho próprio). Fica só nesta máquina
(`~/Jaime/saude/`, 0600). Nada aqui é diagnóstico: são números do próprio relógio, falados como estão.
"""
from __future__ import annotations
import json, os, time
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path

PASTA = Path(os.environ.get("JAIME_SAUDE_DIR", "~/Jaime/saude")).expanduser()

# nomes de métrica do Health Auto Export → nosso campo
MAPA = {
    "walking_running_distance": "distancia_km", "distance_walking_running": "distancia_km",
    "step_count": "passos", "active_energy": "calorias", "heart_rate": "fc",
    "resting_heart_rate": "fc_repouso", "heart_rate_variability": "vfc", "apple_exercise_time": "exercicio_min",
    "sleep_analysis": "sono_h",
}
BASE_CAMPOS = ("distancia_km", "passos", "fc_repouso", "vfc", "sono_h", "calorias")


@dataclass
class Resumo:
    dia: str = ""
    distancia_km: float | None = None
    duracao_min: float | None = None
    passos: float | None = None
    calorias: float | None = None
    fc_pico: float | None = None
    fc_repouso: float | None = None
    vfc: float | None = None
    estresse: float | None = None
    recuperacao: float | None = None
    habitual_km: float | None = None
    sono_h: float | None = None
    base: dict = field(default_factory=dict)          # médias dos últimos 14 dias (sem hoje), por campo
    observacoes: list[str] = field(default_factory=list)

    def dados(self) -> dict:
        return asdict(self)


def _num(v) -> float | None:
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _km(qty, unidade: str) -> float | None:
    q = _num(qty)
    if q is None:
        return None
    u = (unidade or "km").lower()
    return round(q * 1.609344, 2) if u.startswith("mi") else round(q / 1000, 2) if u in ("m", "meter", "meters") else q


def interpretar(corpo: dict, hoje: date | None = None) -> Resumo:
    hoje = hoje or date.today()
    r = Resumo(dia=hoje.isoformat())
    if not isinstance(corpo, dict):
        return r
    simples = {k: corpo.get(k) for k in ("distancia_km", "duracao_min", "passos", "calorias", "fc_pico", "fc_repouso",
                                          "vfc", "estresse", "recuperacao", "habitual_km", "sono_h")}
    for k, v in simples.items():
        if v is not None:
            setattr(r, k, _num(v))
    dados = corpo.get("data") if isinstance(corpo.get("data"), dict) else {}
    for m in dados.get("metrics", []) or []:
        campo = MAPA.get(str(m.get("name", "")).lower())
        pontos = [p for p in (m.get("data") or []) if str(p.get("date", ""))[:10] in ("", hoje.isoformat())] or (m.get("data") or [])
        if not campo or not pontos:
            continue
        if campo == "sono_h":
            p = pontos[-1]
            h = _num(p.get("asleep") or p.get("totalSleep") or p.get("qty"))
            if h is not None:
                r.sono_h = round(h / 60, 1) if h > 24 else h          # alguns exports mandam minutos
            continue
        if campo == "fc":
            picos = [_num(p.get("Max") or p.get("max") or p.get("qty")) for p in pontos]
            picos = [x for x in picos if x is not None]
            if picos:
                r.fc_pico = max(picos + ([r.fc_pico] if r.fc_pico else []))
        elif campo == "distancia_km":
            r.distancia_km = round(sum(_km(p.get("qty"), m.get("units", "km")) or 0 for p in pontos), 2)
        else:
            vals = [_num(p.get("qty")) for p in pontos]
            vals = [x for x in vals if x is not None]
            if vals:
                setattr(r, campo, round(sum(vals), 2) if campo in ("passos", "calorias", "exercicio_min") else vals[-1])
    for w in dados.get("workouts", []) or []:
        if (d := w.get("distance")) and r.distancia_km is None:
            r.distancia_km = _km(d.get("qty"), d.get("units", "km"))
        ini, fim = w.get("start"), w.get("end")
        if ini and fim and r.duracao_min is None:
            try:
                f = "%Y-%m-%d %H:%M:%S %z"
                r.duracao_min = round((datetime.strptime(fim, f) - datetime.strptime(ini, f)).total_seconds() / 60)
            except ValueError:
                pass
        mx = w.get("maxHeartRate") or w.get("heartRateMax")
        if isinstance(mx, dict):
            mx = mx.get("qty")
        if (v := _num(mx)) and (r.fc_pico is None or v > r.fc_pico):
            r.fc_pico = v
    r.observacoes = observacoes(r)
    return r


def observacoes(r: Resumo) -> list[str]:
    """O que vale dizer: comparado com a SUA média dos últimos 14 dias quando ela existe, não com tabela genérica."""
    b, obs = r.base or {}, []
    hab = r.habitual_km or b.get("distancia_km")
    if r.distancia_km is not None and hab:
        obs.append(f"distância {'abaixo' if r.distancia_km < hab else 'acima'} do habitual ({r.distancia_km} vs {round(hab, 2)} km)")
    if r.passos is not None and b.get("passos") and r.passos < 0.6 * b["passos"]:
        obs.append(f"passos bem abaixo da média ({r.passos:.0f} vs {b['passos']:.0f})")
    if r.fc_pico and r.fc_pico >= 185:
        obs.append(f"pico de {r.fc_pico:.0f} bpm")
    if r.fc_repouso is not None and b.get("fc_repouso") and r.fc_repouso - b["fc_repouso"] >= 5:
        obs.append(f"frequência de repouso {r.fc_repouso - b['fc_repouso']:.0f} bpm acima da sua média")
    if r.vfc is not None and b.get("vfc") and r.vfc < 0.8 * b["vfc"]:
        obs.append(f"VFC {100 - 100 * r.vfc / b['vfc']:.0f}% abaixo da sua média")
    elif r.vfc is not None:
        obs.append(f"VFC {r.vfc:.0f} ms")
    if r.sono_h is not None and r.sono_h < 6:
        obs.append(f"dormiu {r.sono_h:.1f} h".replace(".", ","))
    if r.recuperacao is not None and r.recuperacao < 40:
        obs.append(f"recuperação baixa antes da atividade ({r.recuperacao:.0f}%)")
    if r.estresse is not None:
        obs.append(f"estresse em {r.estresse}")
    return obs


def _historico(pasta: Path) -> list[dict]:
    try:
        return [json.loads(l) for l in (pasta / "historico.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception:
        return []


def base_de(historico: list[dict], hoje: str, dias: int = 14) -> dict:
    anteriores = [h["resumo"] for h in historico if h.get("dia", "") < hoje][-dias:]
    base = {}
    for c in BASE_CAMPOS:
        vals = [a.get(c) for a in anteriores if isinstance(a.get(c), (int, float))]
        if len(vals) >= 3:
            base[c] = round(sum(vals) / len(vals), 2)
    return base


def salvar(corpo: dict, pasta: Path | None = None) -> Resumo:
    pasta = pasta or PASTA
    pasta.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(pasta, 0o700)
    except OSError:
        pass
    r = interpretar(corpo)
    hist = _historico(pasta)
    r.base = base_de(hist, r.dia)
    anterior = carregar(pasta)
    if r.habitual_km is None:
        r.habitual_km = r.base.get("distancia_km") or (anterior.distancia_km if anterior and anterior.distancia_km is not None else None)
    r.observacoes = observacoes(r)
    hist = [h for h in hist if h.get("dia") != r.dia] + [{"dia": r.dia, "resumo": {c: getattr(r, c) for c in BASE_CAMPOS}}]
    arq_h = pasta / "historico.jsonl"
    arq_h.write_text("\n".join(json.dumps(h, ensure_ascii=False) for h in hist[-120:]) + "\n", encoding="utf-8")
    os.chmod(arq_h, 0o600)
    alvo = pasta / "ultimo.json"
    alvo.write_text(json.dumps({"recebido": time.time(), "resumo": r.dados()}, ensure_ascii=False), encoding="utf-8")
    os.chmod(alvo, 0o600)
    return r


def carregar(pasta: Path | None = None) -> Resumo | None:
    try:
        d = json.loads(((pasta or PASTA) / "ultimo.json").read_text(encoding="utf-8"))["resumo"]
        return Resumo(**{k: v for k, v in d.items() if k in Resumo.__dataclass_fields__})
    except Exception:
        return None


def _br(x: float, casas: int = 1) -> str:
    return (f"{x:.{casas}f}".rstrip("0").rstrip(".") if casas else f"{x:.0f}").replace(".", ",")


def falas_do_monitor(r: Resumo) -> list[dict]:
    """Os segmentos do "ativar monitor": ícone holográfico + dado + frase, na ordem do vídeo."""
    out = []
    if r.distancia_km is not None:
        f = f"O senhor caminhou {_br(r.distancia_km)} km hoje"
        if r.duracao_min:
            f += f" em {_br(r.duracao_min, 0)} minutos"
        if r.habitual_km:
            f += f", {'abaixo' if r.distancia_km < r.habitual_km else 'acima'} dos {_br(r.habitual_km)} habituais"
        out.append({"icone": "passos", "cor": "laranja", "fala": f + ".",
                    "callouts": [["DISTÂNCIA", f"{_br(r.distancia_km, 2)} km"], ["DURAÇÃO", f"{_br(r.duracao_min or 0, 0)} min"],
                                 ["HABITUAL", f"{_br(r.habitual_km or 0)} km"]]})
    if r.fc_pico:
        out.append({"icone": "chama", "cor": "laranja", "fala": f"O pico foi de {r.fc_pico:.0f} batimentos.",
                    "callouts": [["PICO", f"{r.fc_pico:.0f} bpm"], ["CALORIAS", f"{_br(r.calorias or 0, 0)} kcal"],
                                 ["REPOUSO", f"{_br(r.fc_repouso or 0, 0)} bpm"]]})
    if r.estresse is not None:
        out.append({"icone": "chama", "cor": "laranja", "fala": f"O stress ficou em {_br(r.estresse)}.",
                    "callouts": [["ESTRESSE", _br(r.estresse)]]})
    if r.recuperacao is not None:
        out.append({"icone": "bateria", "cor": "verde",
                    "fala": f"Sua recuperação antes desta atividade estava em {r.recuperacao:.0f}%.",
                    "callouts": [["RECUPERAÇÃO", f"{r.recuperacao:.0f}%"]] + ([["VFC", f"{r.vfc:.0f} ms"]] if r.vfc else [])})
    return out
