"""Barramento de eventos do HUD — tudo que o Jaime faz vira um evento que a interface desenha.

Tipos: fala, fala_fim, raciocinio, producao, resultado, conversa, acesso, estado, sistema, apresentacao, voz."""
from __future__ import annotations
import asyncio, time
from collections import deque

class Bus:
    def __init__(self):
        self._subs: set[asyncio.Queue] = set()
        self.historico: deque = deque(maxlen=300)

    def emitir(self, tipo: str, _efemero: bool = False, **dados) -> None:
        """`_efemero=True`: vai aos assinantes, mas não ao histórico (cursor/arrasto da mão a 30 Hz apagariam
        em segundos os 300 eventos que o HUD recarrega ao abrir)."""
        evt = {"t": round(time.time(), 3), "tipo": tipo, **dados}
        if not _efemero:
            self.historico.append(evt)
        for q in list(self._subs):
            try:
                q.put_nowait(evt)
            except asyncio.QueueFull:
                pass

    def assinar(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subs.add(q)
        return q

    def cancelar(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

bus = Bus()
