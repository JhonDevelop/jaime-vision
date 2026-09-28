"""Fase 9 — autoevolução MEDIDA da camada espacial.

    hipótese → candidato → replay (mesmos cenários, mesma semente) → métricas vs. baseline → gate numérico
      → classe autorizada? → promove com snapshot  |  rejeita com motivo  → registro → rollback a qualquer hora

Classes:
- `parametro` (limiares da pinça, dwell, cooldown…): pode se promover SOZINHO, dentro das faixas abaixo e só se
  passar no gate (sem regressão de acerto, falsas ativações nem latência). Snapshot antes; rollback restaura.
- `codigo_acao_so`, `vigia`, `acesso`, `modelo`, `dependencia`, `egress`: nunca se promovem sozinhas — viram
  proposta para o João (o fluxo de PR já existente em jaime/evolucao.py, agora com o mesmo gate).

Nada aqui escreve no vault: parâmetros e experimentos ficam em ~/Jaime/espacial/.
"""
from __future__ import annotations
import json, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from uuid import uuid4
from .benchmark import Metrics, assess

FAIXAS = {"close_ratio": (0.15, 0.35), "open_ratio": (0.35, 0.60), "dwell_s": (0.04, 0.25),
          "click_max_s": (0.20, 0.60), "cooldown_s": (0.10, 0.50)}
PADRAO = {"close_ratio": 0.28, "open_ratio": 0.42, "dwell_s": 0.09, "click_max_s": 0.35, "cooldown_s": 0.20}
CLASSES_AUTO = frozenset({"parametro"})
CLASSES_HUMANAS = frozenset({"codigo_acao_so", "vigia", "acesso", "modelo", "dependencia", "egress"})

# cenários de replay e o que DEVE acontecer em cada um (eventos discretos no alvo)
ESPERADO = {
    "pinca": {"gesture.grab": 1, "gesture.release": 1, "gesture.click": 0},
    "clique": {"gesture.grab": 1, "gesture.release": 1, "gesture.click": 1},
    "perda": {"gesture.grab": 1, "gesture.cancel": 1, "gesture.release": 0},
    "parcial": {"gesture.grab": 0, "gesture.click": 0},
    "tremor": {"gesture.grab": 0, "gesture.click": 0},
}
NEGATIVOS = ("parcial", "tremor")


class Parametros:
    def __init__(self, arquivo: Path | None = None):
        self.arquivo = Path(arquivo).expanduser() if arquivo else None
        self.valores = dict(PADRAO); self.versao = 0; self.historico: list[dict] = []
        if self.arquivo and self.arquivo.exists():
            d = json.loads(self.arquivo.read_text(encoding="utf-8"))
            self.valores.update(d.get("valores", {})); self.versao = d.get("versao", 0); self.historico = d.get("historico", [])

    def _salvar(self) -> None:
        if self.arquivo:
            self.arquivo.parent.mkdir(parents=True, exist_ok=True)
            self.arquivo.write_text(json.dumps({"valores": self.valores, "versao": self.versao, "historico": self.historico[-50:]},
                                               indent=1), encoding="utf-8")

    def aplicar(self, novos: dict, motivo: str) -> int:
        self.historico.append({"versao": self.versao, "valores": dict(self.valores), "motivo": motivo, "t": time.strftime("%Y-%m-%d %H:%M")})
        self.valores.update(novos); self.versao += 1; self._salvar()
        return self.versao

    def rollback(self, para_versao: int | None = None) -> int:
        if not self.historico:
            raise ValueError("nada para reverter")
        alvo = self.historico[-1] if para_versao is None else next(h for h in self.historico if h["versao"] == para_versao)
        self.valores = dict(alvo["valores"]); self.versao += 1
        self.historico.append({"versao": self.versao, "valores": dict(self.valores), "motivo": f"rollback para v{alvo['versao']}",
                               "t": time.strftime("%Y-%m-%d %H:%M")})
        self._salvar()
        return self.versao


def _cenario_tremor():
    from .simulador import Quadro
    return [Quadro(i / 30, 0.2, 0.35, 0.26 if i % 2 else 0.45) for i in range(90)]


def medir(params: dict, repeticoes: int = 20, semente: int = 5) -> Metrics:
    """Replay determinístico (semente) de todos os cenários, `repeticoes` vezes com ruído diferente, pela MESMA
    máquina de gestos do serviço. acurácia = cenários com exatamente os eventos esperados; falsas ativações/hora
    = grabs/cliques nos cenários negativos, pelo tempo total deles; p95 = custo por frame."""
    from .core import SpatialCore
    from .filtro import FiltroMao
    from .gestures import HandSample, PinchMachine
    from .landmarks import INDICADOR, POLEGAR, alvo_em, cursor as cursor_de, largura_palma
    from .simulador import cenario, objetos_demo, poses
    from .core import Vec3
    from .metricas import percentil
    acertos = total = falsos = 0
    tempo_neg = 0.0
    custos: list[float] = []
    for rep in range(repeticoes):
        for nome, esperado in ESPERADO.items():
            core = SpatialCore()
            for o in objetos_demo():
                core.add(o)
            qs = _cenario_tremor() if nome == "tremor" else cenario(nome, core)
            seq = poses(qs, ruido=0.002, semente=semente * 1000 + rep)
            m = PinchMachine(core, **params); f = FiltroMao()
            cont: dict[str, int] = {}
            visto: dict[str, float] = {}
            for t, maos in seq:
                t0 = time.perf_counter()
                evs = []
                vistas = set()
                for p in maos:
                    k = f"demo:{p.hand_id}"; vistas.add(k); visto[k] = t
                    lm = f(k, p.landmarks, t)
                    cur = cursor_de(lm)
                    alvo = alvo_em(core, cur.x, cur.y)
                    evs += m.update(HandSample("demo", Vec3(*lm[POLEGAR]), Vec3(*lm[INDICADOR]), largura_palma(lm), t, p.confidence,
                                               alvo.id if alvo else None, p.hand_id, cur))
                for k, tt in list(visto.items()):
                    if k not in vistas and t - tt > 0.25:
                        evs += m.lost("demo", k.split(":")[1], "saiu"); visto.pop(k)
                custos.append((time.perf_counter() - t0) * 1000)
                for e in evs:
                    cont[e.kind] = cont.get(e.kind, 0) + 1
            total += 1
            acertos += all(cont.get(k, 0) == v for k, v in esperado.items())
            if nome in NEGATIVOS:
                falsos += cont.get("gesture.grab", 0) + cont.get("gesture.click", 0)
                tempo_neg += seq[-1][0] - seq[0][0]
    return Metrics(accuracy=acertos / total, false_activations_per_hour=falsos / max(tempo_neg / 3600, 1e-9),
                   p95_ms=percentil(custos, .95) or 0.0, sample_count=total)


@dataclass
class Experimento:
    hipotese: str
    classe: str
    mudancas: dict
    decisao: str = "pendente"         # promovido | rejeitado | revisao_humana
    motivo: str = ""
    base: dict = field(default_factory=dict)
    cand: dict = field(default_factory=dict)
    versao_antes: int = 0
    versao_depois: int = 0
    id: str = field(default_factory=lambda: uuid4().hex[:8])
    quando: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M"))


class Laboratorio:
    def __init__(self, parametros: Parametros, registro: Path | None = None, repeticoes: int = 20):
        self.p, self.registro, self.repeticoes = parametros, (Path(registro).expanduser() if registro else None), repeticoes

    def _registrar(self, e: Experimento) -> Experimento:
        if self.registro:
            self.registro.parent.mkdir(parents=True, exist_ok=True)
            with self.registro.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(e), ensure_ascii=False) + "\n")
        return e

    def testar(self, hipotese: str, mudancas: dict, classe: str = "parametro") -> Experimento:
        e = Experimento(hipotese, classe, dict(mudancas), versao_antes=self.p.versao)
        if classe not in CLASSES_AUTO:
            e.decisao = "revisao_humana"
            e.motivo = f"classe '{classe}' nunca se promove sozinha — vira proposta para o João"
            return self._registrar(e)
        for k, v in mudancas.items():
            if k not in FAIXAS:
                e.decisao, e.motivo = "rejeitado", f"parâmetro desconhecido: {k}"; return self._registrar(e)
            lo, hi = FAIXAS[k]
            if not lo <= float(v) <= hi:
                e.decisao, e.motivo = "rejeitado", f"{k}={v} fora da faixa autorizada [{lo}, {hi}]"; return self._registrar(e)
        cand_params = {**self.p.valores, **mudancas}
        if cand_params["close_ratio"] >= cand_params["open_ratio"]:
            e.decisao, e.motivo = "rejeitado", "quebra a histerese (close ≥ open)"; return self._registrar(e)
        base = medir(self.p.valores, self.repeticoes); cand = medir(cand_params, self.repeticoes)
        e.base, e.cand = asdict(base), asdict(cand)
        # latência de um frame é sub-milissegundo e ruidosa: o gate de p95 ganha uma folga absoluta de 0,05 ms
        base_lat = Metrics(base.accuracy, base.false_activations_per_hour, max(base.p95_ms, 0.05), base.sample_count)
        ok, motivo = assess(base_lat, cand, min_samples=min(100, base.sample_count), max_p95_regression=1.0)
        if not ok:
            e.decisao, e.motivo = "rejeitado", motivo
            return self._registrar(e)
        e.versao_depois = self.p.aplicar(mudancas, f"experimento {e.id}: {hipotese}")
        e.decisao, e.motivo = "promovido", motivo
        return self._registrar(e)

    def reverter(self) -> int:
        return self.p.rollback()


def gate_para_evolucao(metricas_base: Metrics, metricas_cand: Metrics) -> tuple[bool, str]:
    """O mesmo gate numérico, para o fluxo de PR de jaime/evolucao.py (código candidato medido em replay)."""
    return assess(metricas_base, metricas_cand, min_samples=min(100, metricas_base.sample_count))
