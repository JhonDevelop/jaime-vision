"""Fila de demandas — nada se perde quando o João interrompe o Jaime (docs/FASE-3-TEMPO-REAL.md §2.3).

Cada pedido por voz vira uma Demanda: nova → em andamento → concluída, ou interrompida (barge-in) com o que já foi
dito, o que foi gerado e não dito, e se o modelo chegou a terminar. Depois de atender a demanda nova:
- se a antiga tinha terminado de gerar e faltavam ≤ 2 frases → retoma sozinho ("Voltando: …");
- senão → UMA pergunta: "Continuo o que eu dizia sobre X?"; "sim" retoma, "não/deixa" descarta.
A fila aparece no HUD (evento `fila`)."""
from __future__ import annotations
import re, time
from dataclasses import dataclass, field
from ..hud.events import bus

RETOMAR_SOZINHO_ATE = 2      # frases restantes para retomar sem perguntar
NEGATIVA_RX = re.compile(r"^\s*(n[aã]o|deixa|esquece|depois|deixa pra l[aá]|n[aã]o precisa|para|chega)\b", re.I)
POSITIVA_RX = re.compile(r"^\s*(sim|pode|continua|continue|vai|isso|claro|por favor|manda|segue)\b", re.I)

@dataclass
class Demanda:
    id: int
    texto: str
    estado: str = "nova"                      # nova | em_andamento | interrompida | concluida | descartada
    t_inicio: float = field(default_factory=time.time)
    t_fim: float = 0.0
    ditas: list[str] = field(default_factory=list)       # frases que chegaram a soar
    pendentes: list[str] = field(default_factory=list)   # geradas mas não ditas (cortadas pelo barge-in)
    gerou_tudo: bool = False                  # o modelo terminou a resposta?
    interrompida_por: int | None = None       # id da demanda que a interrompeu

    @property
    def resumo(self) -> str:
        t = re.sub(r"\s+", " ", self.texto).strip()
        return (t[:40] + "…") if len(t) > 40 else t

    def dados(self) -> dict:
        return {"id": self.id, "resumo": self.resumo, "estado": self.estado, "ditas": len(self.ditas), "pendentes": len(self.pendentes), "gerou_tudo": self.gerou_tudo}

class FilaDemandas:
    def __init__(self, maximo: int = 30):
        self.itens: list[Demanda] = []
        self.maximo = maximo
        self.atual: Demanda | None = None
        self.aguardando: Demanda | None = None    # esperando o João dizer se retoma
        self._seq = 0

    # ── transições ─────────────────────────────────────
    def nova(self, texto: str) -> Demanda:
        self._seq += 1
        d = Demanda(self._seq, texto)
        self.itens.append(d); self.itens = self.itens[-self.maximo:]
        self._emitir(); return d

    def comecar(self, d: Demanda) -> None:
        d.estado = "em_andamento"; self.atual = d; self._emitir()

    def gerada(self, d: Demanda, frase: str) -> None:
        d.pendentes.append(frase)

    def dita(self, d: Demanda, frase: str | None = None) -> None:
        """Uma frase saiu do alto-falante (a primeira pendente, ou a indicada)."""
        if frase is None and d.pendentes:
            frase = d.pendentes.pop(0)
        elif frase in d.pendentes:
            d.pendentes.remove(frase)
        if frase:
            d.ditas.append(frase)

    def interromper(self, d: Demanda, nao_ditas: int | None = None, por: Demanda | None = None) -> None:
        """Barge-in. `nao_ditas` = quantas das frases geradas ficaram por dizer (o TTS sabe); as outras contam como ditas."""
        if nao_ditas is not None:
            geradas = d.ditas + d.pendentes
            corte = max(0, len(geradas) - nao_ditas)
            d.ditas, d.pendentes = geradas[:corte], geradas[corte:]
        d.estado = "interrompida"; d.interrompida_por = por.id if por else None
        if self.atual is d:
            self.atual = None
        self._emitir()

    def concluir(self, d: Demanda) -> None:
        d.ditas += d.pendentes; d.pendentes = []
        d.gerou_tudo = True; d.estado = "concluida"; d.t_fim = time.time()
        if self.atual is d:
            self.atual = None
        self._emitir()

    def descartar(self, d: Demanda) -> None:
        d.estado = "descartada"; d.t_fim = time.time()
        if self.aguardando is d:
            self.aguardando = None
        self._emitir()

    # ── retomada ───────────────────────────────────────
    def interrompidas(self) -> list[Demanda]:
        return [d for d in self.itens if d.estado == "interrompida"]

    def plano_de_retomada(self, d: Demanda) -> tuple[str, str]:
        """("automatica", texto a falar) quando é curto; ("perguntar", pergunta) quando não."""
        if d.gerou_tudo and len(d.pendentes) <= RETOMAR_SOZINHO_ATE:
            return "automatica", ("Voltando: " + " ".join(d.pendentes)).strip() if d.pendentes else ("automatica", "")
        return "perguntar", f"Continuo o que eu dizia sobre {d.resumo}?"

    def pedir_retomada(self, d: Demanda) -> None:
        self.aguardando = d; self._emitir()

    def responder_retomada(self, texto: str) -> str | None:
        """Só vale quando há pergunta pendente: "sim" | "nao" | None (não era resposta)."""
        if not self.aguardando:
            return None
        t = (texto or "").strip().lower()
        if NEGATIVA_RX.match(t):
            return "nao"
        if POSITIVA_RX.match(t):
            return "sim"
        return None

    def texto_de_continuacao(self, d: Demanda) -> str:
        dito = " ".join(d.ditas)[-240:]
        return (f"Continue a resposta anterior sobre «{d.resumo}» exatamente de onde parou, sem repetir o que já disse"
                + (f" (você tinha dito: «{dito}»)" if dito else "") + ".")

    # ── HUD ────────────────────────────────────────────
    def dados(self) -> list[dict]:
        return [d.dados() for d in self.itens[-8:]]

    def _emitir(self) -> None:
        bus.emitir("fila", itens=self.dados(), atual=self.atual.id if self.atual else None,
                   aguardando=self.aguardando.id if self.aguardando else None)
