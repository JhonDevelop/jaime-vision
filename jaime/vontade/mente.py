"""Mente — escolhe a próxima atividade por impulso × janela da rotina × orçamento (fase 3, §5 e §6).

Janelas (§5): `atento` 08–18h com fala nos últimos 15 min (só demandas); `noite` 21h–06h (noite criativa);
`ocioso` no resto. Regras: Utilidade sempre vence quando há demanda pendente; criar só na noite criativa; conhecer
o João só de dia; nada passa por cima do orçamento. Cada escolha vira um pensamento "quero … porque …" no diário
e no bus — vontade registrada, não escondida.

`orcamento` é injetável: o do Prompt D (jaime/cortex/orcamento.py, `.pode(tipo)`), ou `OrcamentoLivre`.
`modo_atento(ultima_fala_ts, agora)` vem do Prompt D se existir; senão, 15 min sem fala."""
from __future__ import annotations
import asyncio, time
from dataclasses import dataclass, asdict
from datetime import datetime
from .impulsos import Impulsos, ROTULO, NOMES
from ..hud.events import bus

ATIVIDADE = {"utilidade": "atender", "curiosidade": "estudar", "maestria": "praticar",
             "criacao": "criar", "ordem": "organizar", "vinculo": "conhecer"}
ORCAMENTO_DE = {"atender": "demanda", "estudar": "estudo", "praticar": "estudo",
                "criar": "criacao", "organizar": "estudo", "conhecer": "estudo"}
VERBO = {"atender": "atender o João", "estudar": "estudar um problema em aberto", "praticar": "praticar onde estou errando",
         "criar": "criar algo meu", "organizar": "organizar o vault", "conhecer": "conhecer melhor o João"}
PERMITIDO = {"atento": {"atender"},
             "ocioso": {"atender", "estudar", "praticar", "organizar", "conhecer", "criar"},   # criar: só com CRIACAO_DIA_*
             "noite": {"atender", "estudar", "praticar", "criar"}}
LIMIAR = 0.30                  # abaixo disso nada me puxa
CRIACAO_DIA_MIN = 0.60         # M-38: de dia, na 1ª janela ociosa longa, Criação ≥ isto pode criar (o Mac dorme à noite)
CRIACAO_DIA_OCIOSO_S = 30 * 60 # ... se o João não fala há 30 min
BONUS_NOITE_CRIACAO = 0.15     # noite criativa: Criação ganha vantagem
ATENTO_S = 15 * 60
INTERVALO_S = 10 * 60

class OrcamentoLivre:
    """Stub injetável enquanto o Prompt D não entrega jaime/cortex/orcamento.py."""
    def pode(self, tipo: str) -> bool:
        return True
    def gastar(self, tipo: str, usd: float) -> None:
        pass

def _modo_atento(ultima_fala_ts: float, agora: float) -> bool:
    try:
        from ..agenda.scheduler import modo_atento          # type: ignore
        return bool(modo_atento(ultima_fala_ts, agora))
    except Exception:
        pass
    try:
        from ..telemetria.uso import modo_atento            # type: ignore
        return bool(modo_atento(ultima_fala_ts, agora))
    except Exception:
        return (agora - ultima_fala_ts) < ATENTO_S

def janela(agora: datetime, ultima_fala_ts: float = 0.0) -> str:
    """'noite' 21–06 · 'atento' 08–18 com fala recente · 'ocioso' no resto."""
    h = agora.hour
    if h >= 21 or h < 6:
        return "noite"
    if 8 <= h < 18 and _modo_atento(ultima_fala_ts, agora.timestamp()):
        return "atento"
    return "ocioso"

@dataclass
class Escolha:
    atividade: str
    impulso: str
    nivel: float
    janela: str
    pensamento: str

    def dados(self) -> dict:
        return asdict(self)

class Mente:
    def __init__(self, impulsos: Impulsos, vault=None, orcamento=None, executores: dict | None = None,
                 agora=datetime.now, pode_criar=lambda: True):
        self.impulsos, self.vault, self.orcamento = impulsos, vault, orcamento or OrcamentoLivre()
        self.executores = executores or {}
        self.agora, self.pode_criar = agora, pode_criar
        self.ultima_fala_ts = 0.0
        self.ultima: Escolha | None = None
        self.ocupado = False
        self._criacao_dia = None        # data da criação diurna já feita (uma por dia)
        self._adiada: str | None = None # atividade escolhida mas adiada pelo cérebro trancado (registrada uma vez)

    # ── decisão ───────────────────────────────────────
    def decidir(self, registrar: bool = True) -> Escolha | None:
        imp = self.impulsos
        jan = janela(self.agora(), self.ultima_fala_ts)
        candidatos: list[tuple[str, float]] = []
        if imp.demanda_pendente:
            candidatos.append(("utilidade", 1.0))            # regra 1: Utilidade sempre ganha com demanda
        for nome, nivel in imp.ranking():
            if nome == "utilidade" and not imp.demanda_pendente:
                continue                                    # sem demanda, "atender" não é uma atividade
            if jan == "noite" and nome == "criacao":
                nivel = min(1.0, nivel + BONUS_NOITE_CRIACAO)
            candidatos.append((nome, nivel))
        candidatos.sort(key=lambda c: -c[1])
        for nome, nivel in candidatos:
            atividade = ATIVIDADE[nome]
            if atividade not in PERMITIDO[jan] or (nivel < LIMIAR and atividade != "atender"):
                continue
            if atividade == "criar" and jan == "ocioso":
                # M-38 (Vigília 20/09): 0 criações em 4 noites — o Mac dorme 21h–06h. Uma criação de dia quando
                # Criação está alta e o João não fala há 30 min; uma por dia.
                agora = self.agora()
                ocioso_s = agora.timestamp() - self.ultima_fala_ts if self.ultima_fala_ts else 10 ** 9
                if nivel < CRIACAO_DIA_MIN or ocioso_s < CRIACAO_DIA_OCIOSO_S or self._criacao_dia == agora.date():
                    continue
            if atividade == "criar" and not self.pode_criar():
                continue
            if atividade != "atender" and not self.orcamento.pode(ORCAMENTO_DE[atividade]):
                continue
            e = Escolha(atividade, nome, round(nivel, 2), jan, self._pensamento(nome, nivel, jan))
            if registrar:
                self._registrar(e)
            self.ultima = e
            return e
        self.ultima = None
        return None

    def _pensamento(self, nome: str, nivel: float, jan: str) -> str:
        motivo = self.impulsos.motivo(nome)
        if nome == "utilidade" and self.impulsos.demanda_pendente:
            motivo = motivo or "há demanda pendente"
            return f"quero {VERBO['atender']} porque {motivo} — e Utilidade sempre vem primeiro"
        porque = f"{ROTULO[nome]} está em {nivel:.0%}" + (f" ({motivo})" if motivo else "")
        if jan == "noite" and nome == "criacao":
            porque += ", e a noite é minha"
        return f"quero {VERBO[ATIVIDADE[nome]]} porque {porque}"

    def _registrar(self, e: Escolha) -> None:
        bus.emitir("vontade", escolha=e.dados(), niveis={k: round(v, 2) for k, v in self.impulsos.niveis.items()})
        if self.vault and (not self.ultima or self.ultima.pensamento != e.pensamento):
            try:
                self.vault.diario(f"Vontade: {e.pensamento}", "Log")
            except Exception:
                pass

    # ── execução ──────────────────────────────────────
    async def ciclo(self) -> Escolha | None:
        """Um passo da Mente: tique dos impulsos, decisão, execução (se houver executor). Devolve a escolha."""
        if self.ocupado:
            return None
        self.impulsos.tique()
        e = self.decidir()
        if not e or e.atividade == "atender":
            return e                                          # atender é o orquestrador quem faz
        fn = self.executores.get(e.atividade)
        if not fn:
            return e
        self.ocupado = True
        try:
            r = fn()
            if asyncio.iscoroutine(r):
                r = await r
            if e.atividade == "criar" and e.janela == "ocioso":
                self._criacao_dia = self.agora().date()        # a criação de dia conta quando EXECUTA (não quando é só escolhida/adiada)
            return e
        except Exception as ex:
            bus.emitir("vontade", erro=f"{e.atividade} falhou: {type(ex).__name__}: {ex}"[:160])
            if self.vault:
                self.vault.diario(f"Vontade: tentei {e.atividade} e falhou ({type(ex).__name__})", "Pendente")
            return e
        finally:
            self.ocupado = False

    async def passo(self, pode_rodar=lambda: True, motivo=lambda: "") -> Escolha | None:
        """Um tique do loop. Bloqueado (cérebro trancado etc.), a ESCOLHA ainda é registrada e a execução fica adiada com
        linha no diário — 21/09: Criação 0,86, 33 min ocioso, e nada no diário, porque o bloqueio era silencioso (M-43)."""
        if pode_rodar():
            self._adiada = None
            return await self.ciclo()
        m = motivo() or "bloqueado"
        if m != "cérebro trancado" or self.ocupado:
            return None                                       # conversa em curso / orquestrador ocupado: só espera
        e = self.decidir(registrar=self._adiada is None)      # o "quero … porque …" aparece uma vez por período trancado
        if e and e.atividade != "atender" and self._adiada != e.atividade:
            self._adiada = e.atividade
            if self.vault:
                self.vault.diario(f"{VERBO[e.atividade].capitalize()}: adiado (cérebro trancado), faço quando destrancar", "Log")
            bus.emitir("vontade", adiada=e.atividade, motivo=m)
        return None

    async def rodar(self, pode_rodar=lambda: True, intervalo: int = INTERVALO_S, motivo=lambda: "") -> None:
        """Loop: a cada `intervalo`, se estiver liberado e ocioso, um ciclo. Marca a última fala pelo bus."""
        q = bus.assinar()
        proximo = time.time() + intervalo
        try:
            while True:
                # O passo é pelo RELÓGIO, não pelo silêncio do bus: antes o `wait_for(q.get())` só expirava se o bus
                # ficasse quieto o intervalo inteiro — com o ouvido vivo (~10 eventos 'escuta'/s) a Mente nunca decidia
                # nada e só "funcionava" com o microfone morto (Vigília 21/09 12:13: Criação 0,86, 40 min ociosa, nada).
                restante = proximo - time.time()
                if restante <= 0:
                    proximo = time.time() + intervalo
                    try:
                        await self.passo(pode_rodar, motivo)
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        bus.emitir("vontade", erro=f"ciclo falhou: {type(e).__name__}: {e}"[:160])
                    continue
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=restante)
                    if evt.get("tipo") in ("conversa", "ouvido", "transcricao_viva"):
                        self.ultima_fala_ts = time.time()
                except asyncio.TimeoutError:
                    pass
        finally:
            bus.cancelar(q)
