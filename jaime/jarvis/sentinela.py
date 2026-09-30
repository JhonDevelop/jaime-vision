"""Sentinela — "monitorar sistemas críticos e gerenciar servidores e APIs" (vídeo da esfera de partículas), de verdade.

O João lista o que importa em `JAIME_SENTINELA="BUB|https://bubapp.com.br;API BUB|https://api.bubapp.com.br/health"`.
A cada `JAIME_SENTINELA_S` (padrão 60 s) o Jaime bate em cada um, mede a latência e guarda o histórico curto.
- caiu (2 falhas seguidas) → avisa uma vez: evento na tela, linha no diário e, se a voz estiver ligada, fala;
- voltou → avisa quanto tempo ficou fora;
- lento (latência > 3× a mediana dele) → vira observação, sem alarme;
- o briefing do bom dia conta o que aconteceu de madrugada ("o site da BUB ficou fora 12 minutos às 03:10").
Só HTTPS (ou http na própria máquina). Nada aqui muda nada nos servidores: é só olhar.
"""
from __future__ import annotations
import asyncio, os, statistics, time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlsplit

import httpx

from ..hud.events import bus

LOCAIS = {"127.0.0.1", "localhost", "::1"}


@dataclass
class Alvo:
    nome: str
    url: str
    ok: bool | None = None
    falhas: int = 0
    desde: float = 0.0                        # desde quando está no estado atual
    ultima_ms: float | None = None
    status: int | None = None
    erro: str = ""
    latencias: deque = field(default_factory=lambda: deque(maxlen=60))
    checagens: int = 0
    sucessos: int = 0
    eventos: list = field(default_factory=list)   # (quando, texto) das últimas quedas/voltas

    def dados(self) -> dict:
        med = statistics.median(self.latencias) if self.latencias else None
        return {"nome": self.nome, "url": self.url, "ok": self.ok, "status": self.status, "ms": self.ultima_ms,
                "mediana_ms": round(med) if med else None, "erro": self.erro,
                "disponibilidade": round(100 * self.sucessos / self.checagens, 1) if self.checagens else None,
                "desde": datetime.fromtimestamp(self.desde).strftime("%H:%M") if self.desde else ""}


def alvos_do_ambiente(env=None) -> list[Alvo]:
    e = os.environ if env is None else env
    out = []
    for parte in (e.get("JAIME_SENTINELA", "") or "").split(";"):
        nome, _, url = parte.partition("|")
        nome, url = nome.strip(), url.strip()
        u = urlsplit(url)
        if nome and u.hostname and (u.scheme == "https" or (u.scheme == "http" and u.hostname in LOCAIS)):
            out.append(Alvo(nome, url))
    return out


def _dur(s: float) -> str:
    m = int(s // 60)
    return f"{m // 60} h {m % 60} min" if m >= 60 else f"{max(1, m)} minuto{'s' if m != 1 else ''}"


class Sentinela:
    def __init__(self, alvos: list[Alvo], http: httpx.AsyncClient | None = None, emitir=None, falar=None, diario=None,
                 intervalo: float = 60.0, relogio=time.time):
        self.alvos, self.http, self.intervalo, self.relogio = alvos, http, intervalo, relogio
        self.emitir, self.falar, self.diario = emitir or bus.emitir, falar, diario

    @classmethod
    def do_ambiente(cls, env=None, **kw) -> "Sentinela":
        e = os.environ if env is None else env
        try:
            intervalo = max(15.0, float(e.get("JAIME_SENTINELA_S", "60")))
        except ValueError:
            intervalo = 60.0
        return cls(alvos_do_ambiente(e), intervalo=intervalo, **kw)

    async def _checar(self, c: httpx.AsyncClient, a: Alvo) -> None:
        t0 = time.perf_counter()
        try:
            r = await c.get(a.url, timeout=10, follow_redirects=True)
            a.status, a.erro = r.status_code, ""
            bom = r.status_code < 500
        except Exception as ex:
            a.status, a.erro, bom = None, type(ex).__name__, False
        ms = (time.perf_counter() - t0) * 1000
        a.checagens += 1
        agora = self.relogio()
        if bom:
            a.sucessos += 1; a.ultima_ms = round(ms); a.latencias.append(ms)
            if a.ok is False:
                fora = agora - a.desde
                self._avisar(a, f"{a.nome} voltou, depois de {_dur(fora)} fora.", "voltou", _dur(fora))
            if a.ok is not True:
                a.desde = agora
            a.ok, a.falhas = True, 0
        else:
            a.falhas += 1
            if a.falhas >= 2 and a.ok is not False:
                a.ok, a.desde = False, agora
                self._avisar(a, f"{a.nome} está fora do ar ({a.erro or f'HTTP {a.status}'}).", "caiu")

    def _avisar(self, a: Alvo, texto: str, tipo: str, duracao: str = "") -> None:
        quando = datetime.fromtimestamp(self.relogio()).strftime("%H:%M")
        a.eventos = (a.eventos + [{"quando": quando, "tipo": tipo, "texto": texto, "duracao": duracao, "t": self.relogio()}])[-5:]
        self.emitir("sentinela", alvo=a.nome, tipo=tipo, texto=texto)
        if self.diario:
            try:
                self.diario(f"Sentinela: {texto}")
            except Exception:
                pass
        if self.falar and tipo == "caiu":
            try:
                self.falar(texto)
            except Exception:
                pass

    async def rodada(self) -> list[dict]:
        if not self.alvos:
            return []
        dono = self.http is None
        c = self.http or httpx.AsyncClient(headers={"User-Agent": "J.A.I.M.E sentinela"})
        try:
            await asyncio.gather(*(self._checar(c, a) for a in self.alvos))
        finally:
            if dono:
                await c.aclose()
        return self.estado()

    def estado(self) -> list[dict]:
        return [a.dados() for a in self.alvos]

    def desvios(self, desde_h: float = 14.0) -> list[str]:
        """O que o briefing precisa contar: fora agora, ou caiu e voltou na madrugada."""
        out = []
        for a in self.alvos:
            if a.ok is False:
                out.append(f"{a.nome} está fora do ar desde {datetime.fromtimestamp(a.desde).strftime('%H:%M')}")
            else:
                voltas = [e for e in a.eventos if e["tipo"] == "voltou" and self.relogio() - e["t"] <= desde_h * 3600]
                if voltas:
                    out.append(f"{a.nome} ficou fora {voltas[-1]['duracao']} e voltou às {voltas[-1]['quando']}")
        return out

    def lentos(self) -> list[str]:
        out = []
        for a in self.alvos:
            if a.ok and len(a.latencias) >= 5 and a.ultima_ms and a.ultima_ms > 3 * statistics.median(a.latencias):
                out.append(f"{a.nome} está lento ({a.ultima_ms} ms, costuma {round(statistics.median(a.latencias))} ms)")
        return out

    def resumo_falado(self) -> str:
        if not self.alvos:
            return "Ainda não tenho sistemas para vigiar. Coloque os endereços em JAIME_SENTINELA e eu fico de olho."
        fora = [a for a in self.alvos if a.ok is False]
        if a_checar := [a for a in self.alvos if a.ok is None]:
            if len(a_checar) == len(self.alvos):
                return f"Estou vigiando {len(self.alvos)} sistemas; a primeira checagem ainda está em andamento."
        if not fora:
            lentos = self.lentos()
            base = f"Os {len(self.alvos)} sistemas estão no ar" if len(self.alvos) > 1 else f"{self.alvos[0].nome} está no ar"
            return base + (f"; atenção: {lentos[0]}." if lentos else ", respondendo normal.")
        return "Fora do ar: " + "; ".join(f"{a.nome} desde {datetime.fromtimestamp(a.desde).strftime('%H:%M')}" for a in fora) + "."

    async def rodar(self) -> None:
        while True:
            try:
                await self.rodada()
                self.emitir("sentinela", estado=self.estado(), _efemero=True)
            except Exception:
                pass
            await asyncio.sleep(self.intervalo)
