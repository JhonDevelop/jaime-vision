"""Scheduler próprio (APScheduler dentro do processo do servidor) — substitui o n8n.

Rotinas: `vault/30-Tarefas/Rotinas.md`, linhas `- <cron> · <ordem>`; lidas no boot e recarregadas quando o
arquivo muda. Cada rotina vira `jaime.ask(ordem, canal="rotina")` e a resposta é falada (se houver voz) e vai
para o HUD. Lembretes: `30-Tarefas/Lembretes.md`, agendados como jobs de data única."""
from __future__ import annotations
import asyncio, re
from datetime import datetime
from pathlib import Path
from ..hud.events import bus
from . import lembretes as lem
from .relogio import FUSO

ROTINAS_REL = "30-Tarefas/Rotinas.md"
LINHA_RX = re.compile(r"^\s*-\s*([^·]+?)\s*·\s*(.+?)\s*$")
CRON_RX = re.compile(r"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$")
VIGIA_ARQUIVO_S = 30

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

    # ── ciclo de vida ────────────────────────────────────
    def start(self):
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        self._sched = AsyncIOScheduler(timezone=FUSO)
        self._sched.start()
        self.recarregar()
        for quando, o_que in lem.pendentes(self.vault.read(lem.ARQUIVO)):
            self._agendar_lembrete(quando, o_que)
        asyncio.get_event_loop().create_task(self._vigiar_arquivo())

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
                self._sched.add_job(self._rodar_ordem, CronTrigger(**cron, timezone=FUSO), args=[ordem, "rotina"], id=f"rotina:{i}", replace_existing=True)
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
        if ordem.lower().startswith("consolida o que ouvi"):
            # ouvido passivo: à noite, silencioso — o resultado aparece no primeiro "está aí" do dia seguinte
            from ..brain.ouvido_passivo import prompt_consolidar
            await self.jaime.ask(prompt_consolidar(self.jaime.vault), canal=canal); return
        resposta = await self.jaime.ask(ordem, canal=canal)
        if self.ouvido:
            await asyncio.to_thread(self.ouvido.falar, resposta)

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
                            id=f"lembrete:{quando:%Y%m%d%H%M}:{o_que[:20]}", replace_existing=True)

    async def _disparar_lembrete(self, quando: datetime, o_que: str):
        frase = f"João, lembrete: {o_que}."
        bus.emitir("lembrete", texto=o_que, quando=quando.strftime("%H:%M"))
        bus.emitir("fala", texto=frase); bus.emitir("fala_fim")
        self.vault.write(lem.ARQUIVO, lem.marcar_feito(self.vault.read(lem.ARQUIVO), quando, o_que))
        self.vault.diario(f"Lembrete disparado: {o_que}", "Log")
        if self.ouvido:
            await asyncio.to_thread(self.ouvido.falar, frase)
