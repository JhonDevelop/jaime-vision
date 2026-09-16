"""Scheduler próprio (APScheduler dentro do processo do servidor) — substitui o n8n.

Rotinas: `vault/30-Tarefas/Rotinas.md`, linhas `- <cron> · <ordem>`; lidas no boot e recarregadas quando o
arquivo muda. Cada rotina vira `jaime.ask(ordem, canal="rotina")` e a resposta é falada (se houver voz) e vai
para o HUD. Lembretes: `30-Tarefas/Lembretes.md`, agendados como jobs de data única.

Fase 3 (§5): a tabela de Rotinas.md ganhou o dia inteiro (preparar o dia, briefing, revisão, fecha o dia/semana,
auto-avaliação, consolidação). O que NÃO é cron fica aqui como função pura, testável com relógio falso:
`modo_atento()` (nada de estudo/criação se houve fala nos últimos 15 min), `noite_criativa()` (janela 21h–06h) e
`pode_estudar()`/`pode_criar()` que juntam as duas com o orçamento. `Atencao` guarda a última fala ouvindo o bus.
Ganchos: `Agenda.ao("fecha o dia", fn)` roda `fn` antes de a ordem ir ao modelo (recalcular prioridades, Uso.md)."""
from __future__ import annotations
import asyncio, inspect, re, time
from datetime import datetime, timedelta
from pathlib import Path
from ..hud.events import bus
from . import lembretes as lem
from .relogio import FUSO

ROTINAS_REL = "30-Tarefas/Rotinas.md"
LINHA_RX = re.compile(r"^\s*-\s*([^·]+?)\s*·\s*(.+?)\s*$")
CRON_RX = re.compile(r"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$")
VIGIA_ARQUIVO_S = 30
# Tolerância de atraso dos jobs. O padrão do APScheduler é 1 s; no macOS o relógio monotônico do asyncio não conta o
# tempo em que o Mac dorme (medido 15/09: 876 s de parede em 6 s de loop), o timer acorda atrasado e o job é descartado
# como "perdido" — por isso NENHUMA rotina disparou em nenhum dia. Uma rotina horas atrasada ainda vale ser feita.
GRACE_ROTINA_S = 3 * 3600
GRACE_LEMBRETE_S = 30 * 60
ATENTO_JANELA_S = 15 * 60          # §5: nada de estudo/criação se houve fala nos últimos 15 min
NOITE_INICIO_H, NOITE_FIM_H = 21, 6   # §5: noite criativa 21h–06h (janela, não cron)
EVENTOS_FALA = ("conversa", "ouvido", "transcricao_viva")

# ── funções puras (fase 3, §5) ───────────────────────────────
def modo_atento(ultima_fala_ts: float | None, agora: float | None = None, janela_s: int = ATENTO_JANELA_S) -> bool:
    """True se o João falou (ou pediu algo) nos últimos `janela_s` segundos — aí é só demanda, nada de estudo/criação."""
    if not ultima_fala_ts:
        return False
    agora = time.time() if agora is None else agora
    return 0 <= agora - ultima_fala_ts < janela_s

def noite_criativa(agora: datetime) -> bool:
    """21h–06h: janela de projetos autônomos e criações próprias."""
    return agora.hour >= NOITE_INICIO_H or agora.hour < NOITE_FIM_H

def pode_estudar(ultima_fala_ts: float | None, agora: float | None = None, orcamento=None) -> tuple[bool, str]:
    """(pode, motivo). Estudo cabe fora do modo atento e enquanto a fatia 'estudo' do orçamento tiver saldo."""
    agora = time.time() if agora is None else agora
    if modo_atento(ultima_fala_ts, agora):
        return False, f"modo atento: fala há {int((agora - ultima_fala_ts) // 60)} min"
    if orcamento is not None and not orcamento.pode("estudo"):
        return False, "orçamento de estudo do dia esgotado"
    return True, ""

def pode_criar(ultima_fala_ts: float | None, agora: datetime, orcamento=None) -> tuple[bool, str]:
    """Criação: só na noite criativa, fora do modo atento e com saldo na fatia 'criacao'."""
    if not noite_criativa(agora):
        return False, "fora da noite criativa (21h–06h)"
    if modo_atento(ultima_fala_ts, agora.timestamp()):
        return False, "modo atento: o João falou há pouco"
    if orcamento is not None and not orcamento.pode("criacao"):
        return False, "orçamento de criação do dia esgotado"
    return True, ""

class Atencao:
    """Última vez que o João falou/pediu algo. `escutar_bus()` atualiza pelos eventos do HUD; `ouviu()` serve para
    quem tem o microfone (o servidor) e para os testes."""
    def __init__(self, agora=time.time):
        self.agora = agora
        self.ultima_fala: float = 0.0

    def ouviu(self, ts: float | None = None) -> None:
        self.ultima_fala = max(self.ultima_fala, self.agora() if ts is None else ts)

    def atento(self, agora: float | None = None) -> bool:
        return modo_atento(self.ultima_fala, self.agora() if agora is None else agora)

    def evento(self, evt: dict) -> bool:
        """True se o evento conta como fala do João (e atualiza a última fala)."""
        tipo = evt.get("tipo")
        if tipo not in EVENTOS_FALA or evt.get("ignorado") or evt.get("texto") == "•••":
            return False
        self.ouviu(evt.get("t"))
        return True

    async def escutar_bus(self) -> None:
        q = bus.assinar()
        try:
            while True:
                self.evento(await q.get())
        finally:
            bus.cancelar(q)

def parse_rotinas(texto: str) -> list[tuple[dict, str]]:
    """'- 0 7 * * 1-5 · briefing' → ({minute:'0', hour:'7', day:'*', month:'*', day_of_week:'1-5'}, 'briefing')"""
    out = []
    for l in (texto or "").splitlines():
        m = LINHA_RX.match(l)
        if not m:
            continue
        c = CRON_RX.match(m.group(1).strip())
        if not c:
            continue
        out.append(({"minute": c.group(1), "hour": c.group(2), "day": c.group(3), "month": c.group(4), "day_of_week": c.group(5)}, m.group(2)))
    return out

class Agenda:
    def __init__(self, jaime, ouvido=None):
        self.jaime, self.ouvido = jaime, ouvido
        self.vault = jaime.vault
        self._sched = None
        self._mtime = 0.0
        self.rotinas: list[tuple[dict, str]] = []
        self.ganchos: dict[str, list] = {}       # "fecha o dia" → [fn, ...] (fn sync ou async, sem argumentos)

    # ── ganchos (fase 3 — D) ─────────────────────────────
    def ao(self, chave: str, fn) -> None:
        """Registra `fn` para rodar antes de qualquer ordem que contenha `chave` (ex.: recalcular prioridades no fecha-dia)."""
        self.ganchos.setdefault(chave.lower(), []).append(fn)

    async def executar_ganchos(self, ordem: str) -> list[str]:
        """Roda os ganchos cuja chave aparece na ordem. Devolve as chaves disparadas; erro num gancho não derruba a rotina."""
        o = (ordem or "").lower(); disparadas = []
        for chave, fns in self.ganchos.items():
            if chave not in o:
                continue
            disparadas.append(chave)
            for fn in fns:
                try:
                    r = fn()
                    if inspect.isawaitable(r):
                        await r
                except Exception as e:
                    bus.emitir("agenda", erro=f"gancho '{chave}' falhou: {type(e).__name__}: {e}"[:160])
        return disparadas

    # ── ciclo de vida ────────────────────────────────────
    def start(self):
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        self._sched = AsyncIOScheduler(timezone=FUSO)
        self._sched.start()
        self.recarregar()
        for quando, o_que in lem.pendentes(self.vault.read(lem.ARQUIVO)):
            self._agendar_lembrete(quando, o_que)
        self.recuperar_perdidas()
        asyncio.get_event_loop().create_task(self._vigiar_arquivo())

    # ── rotinas perdidas enquanto o processo não existia (Vigília 16/09: 06:30 e 07:00 caíram no sono do Mac) ──
    def perdidas(self, agora: datetime | None = None, janela_s: int = GRACE_ROTINA_S) -> list[str]:
        """Ordens cujo último horário previsto caiu nas últimas `janela_s` e que ainda não constam no diário de hoje.
        misfire_grace_time só recupera com o processo VIVO; o jobstore é em memória, então o boot precisa olhar para trás."""
        from apscheduler.triggers.cron import CronTrigger
        agora = agora or datetime.now(FUSO)
        diario_hoje = self.vault.read(self.vault.daily_rel(agora.date())) or ""
        achadas = []
        for cron, ordem in self.rotinas:
            try:
                prev = CronTrigger(**cron, timezone=FUSO).get_next_fire_time(None, agora - timedelta(seconds=janela_s))
            except Exception:
                continue
            if prev is None or prev > agora:
                continue                                   # nada previsto dentro da janela
            if f"Rotina disparada: {ordem}" in diario_hoje or f"vou rodar agora: {ordem}" in diario_hoje:
                continue                                   # já rodou, ou outro boot (16/09 07:35: dois seguidos) já a agendou
            achadas.append(ordem)
        return achadas

    def recuperar_perdidas(self) -> list[str]:
        from apscheduler.triggers.date import DateTrigger
        ordens = self.perdidas()
        for i, ordem in enumerate(ordens):
            quando = datetime.now(FUSO) + timedelta(seconds=20 + 30 * i)   # depois de o serviço acabar de subir, uma por vez
            self._sched.add_job(self._rodar_ordem, DateTrigger(run_date=quando), args=[ordem, "rotina"],
                                id=f"recuperada:{i}", replace_existing=True, misfire_grace_time=GRACE_ROTINA_S)
            self.vault.diario(f"Rotina perdida enquanto eu estava desligado, vou rodar agora: {ordem}", "Log")
        return ordens

    def stop(self):
        if self._sched:
            self._sched.shutdown(wait=False)

    # ── rotinas ──────────────────────────────────────────
    def recarregar(self) -> int:
        from apscheduler.triggers.cron import CronTrigger
        for job in self._sched.get_jobs():
            if job.id.startswith("rotina:"):
                job.remove()
        self.rotinas = parse_rotinas(self.vault.read(ROTINAS_REL))
        for i, (cron, ordem) in enumerate(self.rotinas):
            try:
                self._sched.add_job(self._rodar_ordem, CronTrigger(**cron, timezone=FUSO), args=[ordem, "rotina"], id=f"rotina:{i}",
                                    replace_existing=True, misfire_grace_time=GRACE_ROTINA_S, coalesce=True)
            except Exception as e:
                bus.emitir("agenda", erro=f"rotina inválida '{ordem}': {e}"[:160])
        try:
            self._mtime = self.vault.path(ROTINAS_REL).stat().st_mtime
        except FileNotFoundError:
            self._mtime = 0.0
        bus.emitir("agenda", rotinas=[f"{' '.join(c.values())} · {o}" for c, o in self.rotinas], lembretes=len(self.lembretes()))
        return len(self.rotinas)

    async def _vigiar_arquivo(self):
        while True:
            await asyncio.sleep(VIGIA_ARQUIVO_S)
            try:
                mt = self.vault.path(ROTINAS_REL).stat().st_mtime
            except FileNotFoundError:
                continue
            if mt != self._mtime:
                self.recarregar()

    async def _rodar_ordem(self, ordem: str, canal: str = "rotina"):
        bus.emitir("agenda", disparo=ordem, quando=datetime.now(FUSO).strftime("%H:%M"))
        self.vault.diario(f"Rotina disparada: {ordem}", "Log")
        if not self.jaime.acesso.liberado:
            bus.emitir("fala", texto=f"Rotina '{ordem}' esperando: cérebro trancado."); bus.emitir("fala_fim"); return
        await self.executar_ganchos(ordem)     # fase 3 — D: prioridades/Uso.md prontos antes de o modelo fechar o dia
        if ordem.lower().startswith("consolida o que ouvi"):
            # ouvido passivo: à noite, silencioso — o resultado aparece no primeiro "está aí" do dia seguinte
            from ..brain.ouvido_passivo import prompt_consolidar
            await self.jaime.ask(prompt_consolidar(self.jaime.vault), canal=canal); return
        t0 = time.time()
        resposta = await self.jaime.ask(ordem, canal=canal)
        if getattr(self.jaime, "_rotina_cedida", "") == ordem:
            self.jaime._rotina_cedida = ""       # o João falou no meio: a rotina foi reagendada; não se fala o pedaço que sobrou
            return
        self.vault.diario(f"Rotina concluída em {time.time() - t0:.0f} s: {ordem[:60]}", "Log")
        if self.ouvido:
            await asyncio.to_thread(self.ouvido.falar, resposta)

    def reagendar(self, ordem: str, minutos: int = 10) -> datetime:
        """Volta a rodar `ordem` daqui a `minutos` (rotina interrompida por uma demanda do João)."""
        from apscheduler.triggers.date import DateTrigger
        quando = datetime.now(FUSO) + timedelta(minutes=minutos)
        if self._sched:
            self._sched.add_job(self._rodar_ordem, DateTrigger(run_date=quando), args=[ordem, "rotina"],
                                id=f"reagendada:{ordem[:30]}", replace_existing=True, misfire_grace_time=GRACE_ROTINA_S)
        return quando

    # ── lembretes ────────────────────────────────────────
    def lembretes(self) -> list[tuple[datetime, str]]:
        return lem.pendentes(self.vault.read(lem.ARQUIVO))

    def criar_lembrete(self, quando: datetime, o_que: str) -> str:
        if not self.vault.read(lem.ARQUIVO):
            self.vault.write(lem.ARQUIVO, "# Lembretes\n\n")
        self.vault.append(lem.ARQUIVO, lem.linha(quando, o_que))
        self._agendar_lembrete(quando, o_que)
        return f"Combinado: {quando:%d/%m às %H:%M} — {o_que}."

    def _agendar_lembrete(self, quando: datetime, o_que: str):
        from apscheduler.triggers.date import DateTrigger
        self._sched.add_job(self._disparar_lembrete, DateTrigger(run_date=quando), args=[quando, o_que],
                            id=f"lembrete:{quando:%Y%m%d%H%M}:{o_que[:20]}", replace_existing=True, misfire_grace_time=GRACE_LEMBRETE_S)

    async def _disparar_lembrete(self, quando: datetime, o_que: str):
        frase = f"João, lembrete: {o_que}."
        bus.emitir("lembrete", texto=o_que, quando=quando.strftime("%H:%M"))
        bus.emitir("fala", texto=frase); bus.emitir("fala_fim")
        self.vault.write(lem.ARQUIVO, lem.marcar_feito(self.vault.read(lem.ARQUIVO), quando, o_que))
        self.vault.diario(f"Lembrete disparado: {o_que}", "Log")
        if self.ouvido:
            await asyncio.to_thread(self.ouvido.falar, frase)
