"""Fase 7 — gestos ensináveis: "Jaime, aprende gesto: arquivar".

Fluxo: nomear + escolher contexto e ação → 5–12 demonstrações + ≥3 negativos → validação SEPARADA (hold-out) →
métricas (precisão, recall, falsas ativações/hora num fluxo de movimentos comuns, separação dos gestos que já
existem) → só ativa se passar → removível a qualquer momento (apaga os exemplos do disco).

Regras de segurança:
- gesto novo NUNCA concede privilégio: só pode ser ligado a verbo reversível (policy.REVERSIBLE) ou a um comando
  do HUD; lixeira/editar/rodar/instalar/enviar/publicar/apagar são recusados na hora de ensinar;
- e mesmo ligado, a ação passa pelo AdaptadorAcoes (política + Vigia + recibo) como qualquer outra;
- guarda SÓ trajetórias de landmarks normalizadas (nada de vídeo), com consentimento explícito para gravar.
"""
from __future__ import annotations
import json, random, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from .learner import GestureLibrary, dtw, normalize
from .policy import REVERSIBLE, SENSITIVE

MIN_POS, MAX_POS, MIN_NEG = 5, 12, 3
CRITERIOS = {"recall": 0.8, "precisao": 0.95, "fp_hora": 1.0}


@dataclass
class Gesto:
    nome: str
    acao: str
    contexto: list[str] = field(default_factory=lambda: ["hud"])
    positivos: list[list[list[float]]] = field(default_factory=list)
    negativos: list[list[list[float]]] = field(default_factory=list)
    ativo: bool = False
    metricas: dict = field(default_factory=dict)
    criado: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M"))


def acao_permitida(acao: str) -> tuple[bool, str]:
    if acao.startswith("hud:"):
        return True, ""
    if acao in SENSITIVE or acao in ("delete_forever", "run_command", "send", "publish", "install", "pay"):
        return False, f"'{acao}' é sensível: gesto não concede esse privilégio"
    if acao in REVERSIBLE:
        return True, ""
    return False, f"ação desconhecida '{acao}' (use um verbo reversível ou hud:<comando>)"


class Treinador:
    def __init__(self, arquivo: Path | None = None, semente: int = 7):
        self.arquivo = Path(arquivo).expanduser() if arquivo else None
        self.gestos: dict[str, Gesto] = {}
        self.rng = random.Random(semente)
        if self.arquivo and self.arquivo.exists():
            d = json.loads(self.arquivo.read_text(encoding="utf-8"))
            self.gestos = {g["nome"]: Gesto(**g) for g in d.get("gestos", [])}

    # ── persistência (com consentimento) ───────────────
    def _salvar(self) -> None:
        if not self.arquivo:
            return
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self.arquivo.write_text(json.dumps({"formato": "jaime.spatial.gestos", "v": 1,
                                            "gestos": [asdict(g) for g in self.gestos.values()]}), encoding="utf-8")

    # ── ensinar ────────────────────────────────────────
    def iniciar(self, nome: str, acao: str, contexto: list[str] | None = None, consentimento: bool = False) -> Gesto:
        if not consentimento:
            raise PermissionError("preciso do seu ok para guardar os exemplos (só landmarks, nada de vídeo)")
        nome = (nome or "").strip().lower()
        if not nome:
            raise ValueError("gesto precisa de nome")
        ok, motivo = acao_permitida(acao)
        if not ok:
            raise PermissionError(motivo)
        g = Gesto(nome, acao, list(contexto or ["hud"]))
        self.gestos[nome] = g
        self._salvar()
        return g

    def exemplo(self, nome: str, trajetoria: list[tuple[float, ...]], negativo: bool = False) -> int:
        g = self.gestos[nome]
        normalize([tuple(p) for p in trajetoria])                  # valida já (levanta se inconsistente)
        lista = g.negativos if negativo else g.positivos
        if not negativo and len(lista) >= MAX_POS:
            raise ValueError(f"já tenho {MAX_POS} demonstrações; chega")
        lista.append([list(map(float, p)) for p in trajetoria])
        g.ativo = False; g.metricas = {}                           # mudou o conjunto: precisa reavaliar
        self._salvar()
        return len(lista)

    def remover(self, nome: str) -> bool:
        """Apaga o gesto E os exemplos gravados."""
        ok = self.gestos.pop(nome, None) is not None
        self._salvar()
        return ok

    # ── avaliar e ativar ───────────────────────────────
    def _biblioteca(self, excluir: str | None = None, so_ativos: bool = True, com: dict | None = None) -> GestureLibrary:
        lib = GestureLibrary()
        for g in self.gestos.values():
            if g.nome == excluir or (so_ativos and not g.ativo):
                continue
            if len(g.positivos) >= 3:
                lib.teach(g.nome, [[tuple(p) for p in t] for t in g.positivos])
            if len(g.negativos) >= 3:
                lib.teach(g.nome, [[tuple(p) for p in t] for t in g.negativos], negative=True)
        for nome, (pos, neg) in (com or {}).items():
            lib.teach(nome, pos)
            if len(neg) >= 3:
                lib.teach(nome, neg, negative=True)
        return lib

    def avaliar(self, nome: str, fluxo_comum: list[list[tuple[float, ...]]] | None = None, horas_fluxo: float = 0.0) -> dict:
        g = self.gestos[nome]
        if len(g.positivos) < MIN_POS or len(g.negativos) < MIN_NEG:
            m = {"pronto": False, "motivo": f"preciso de ≥{MIN_POS} demonstrações e ≥{MIN_NEG} negativos "
                                           f"(tenho {len(g.positivos)} e {len(g.negativos)})"}
            g.metricas = m; return m
        pos = [[tuple(p) for p in t] for t in g.positivos]
        neg = [[tuple(p) for p in t] for t in g.negativos]
        idx = list(range(len(pos))); self.rng.shuffle(idx)
        n_val = max(1, len(pos) // 4)
        val, treino = [pos[i] for i in idx[:n_val]], [pos[i] for i in idx[n_val:]]
        lib = self._biblioteca(excluir=nome, com={nome: (treino, neg)})
        ctx = set(lib.positives)
        vp = sum(1 for t in val if lib.recognize(t, ctx)[0] == nome)
        # negativos: os dele + as demonstrações dos OUTROS gestos (não pode confundir com eles)
        outros = [[tuple(p) for p in t] for o in self.gestos.values() if o.nome != nome for t in o.positivos]
        fp = sum(1 for t in neg + outros if lib.recognize(t, ctx)[0] == nome)
        recall = vp / len(val)
        precisao = vp / (vp + fp) if vp + fp else 0.0
        # separação: protótipo deste × protótipo dos gestos já ativos
        parecido = ""
        for o in self.gestos.values():
            if o.nome == nome or not o.ativo or len(o.positivos) < 3:
                continue
            d = min(dtw(normalize(a), normalize([tuple(p) for p in b])) for a in treino[:4] for b in o.positivos[:4])
            if d < lib.threshold + lib.margin:
                parecido = o.nome
        fp_hora = None
        if fluxo_comum:
            disparos = sum(1 for t in fluxo_comum if lib.recognize(t, ctx)[0] == nome)
            fp_hora = round(disparos / max(horas_fluxo, 1e-6), 2)
        m = {"pronto": True, "recall": round(recall, 3), "precisao": round(precisao, 3), "fp_hora": fp_hora,
             "validacao": len(val), "treino": len(treino), "negativos": len(neg) + len(outros), "parecido_com": parecido}
        g.metricas = m; self._salvar()
        return m

    def ativar(self, nome: str) -> tuple[bool, str]:
        g = self.gestos[nome]
        m = g.metricas
        if not m.get("pronto"):
            return False, m.get("motivo") or "avalie antes de ativar"
        if m.get("parecido_com"):
            return False, f"ambíguo: parecido demais com '{m['parecido_com']}' — mostre de outro jeito"
        if m["recall"] < CRITERIOS["recall"]:
            return False, f"reconheci só {m['recall']:.0%} das demonstrações de validação — preciso de mais exemplos"
        if m["precisao"] < CRITERIOS["precisao"]:
            return False, f"precisão {m['precisao']:.0%}: ele dispara em movimentos que não são ele"
        if m.get("fp_hora") is None:
            return False, "falta medir falsas ativações num fluxo de movimentos comuns"
        if m["fp_hora"] > CRITERIOS["fp_hora"]:
            return False, f"{m['fp_hora']} falsas ativações por hora — acima do limite de {CRITERIOS['fp_hora']}"
        g.ativo = True; self._salvar()
        return True, f"Aprendi '{nome}' para {', '.join(g.contexto)} → {g.acao}. Diga 'esquece o gesto {nome}' para desfazer."

    # ── uso ────────────────────────────────────────────
    def reconhecer(self, trajetoria: list[tuple[float, ...]], contexto: str = "hud") -> tuple[str | None, float, str]:
        """(gesto, confiança, ação) — só entre ATIVOS daquele contexto."""
        validos = {g.nome for g in self.gestos.values() if g.ativo and contexto in g.contexto}
        if not validos:
            return None, 0.0, ""
        nome, conf = self._biblioteca().recognize([tuple(p) for p in trajetoria], validos)
        return (nome, conf, self.gestos[nome].acao) if nome else (None, 0.0, "")
