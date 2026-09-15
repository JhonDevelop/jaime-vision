"""Telegram — o canal rápido do celular. Bot próprio (@BotFather), long polling com httpx, sem biblioteca extra.

Só `JAIME_OWNER_TELEGRAM_ID` conversa com ele: qualquer outro remetente recebe silêncio e vira uma linha no diário.
Respostas curtas (canal `telegram`), sem markdown, no máximo ~3500 caracteres por mensagem."""
from __future__ import annotations
import asyncio
import httpx
from ..hud.events import bus

API = "https://api.telegram.org/bot{token}/{metodo}"
MAX = 3500

class Telegram:
    def __init__(self, token: str, dono: str, jaime, http: httpx.AsyncClient | None = None):
        self.token, self.dono, self.jaime = token, str(dono).strip(), jaime
        self.http = http
        self.offset = 0
        self.ativo = bool(token and dono)

    async def _api(self, metodo: str, **dados):
        cliente = self.http or httpx.AsyncClient(timeout=40)
        try:
            r = await cliente.post(API.format(token=self.token, metodo=metodo), json=dados)
            r.raise_for_status()
            return r.json()
        finally:
            if cliente is not self.http:
                await cliente.aclose()

    async def enviar(self, chat_id: str | int, texto: str) -> None:
        for i in range(0, max(len(texto), 1), MAX):
            await self._api("sendMessage", chat_id=chat_id, text=texto[i:i + MAX] or "…")

    async def tratar(self, update: dict) -> str | None:
        """Devolve o texto respondido, ou None se ignorado. Separado do loop para ser testável."""
        msg = update.get("message") or update.get("edited_message") or {}
        texto = (msg.get("text") or "").strip()
        de = str((msg.get("from") or {}).get("id", ""))
        chat = (msg.get("chat") or {}).get("id")
        if not texto or not chat:
            return None
        if de != self.dono:
            self.jaime.vault.diario(f"Telegram de desconhecido {de}: {texto[:80]}", "Log")
            return None
        resposta = await self.jaime.ask(texto, canal="telegram")
        await self.enviar(chat, resposta)
        return resposta

    async def rodar(self):
        if not self.ativo:
            return
        bus.emitir("conexoes_canal", canal="telegram", ligado=True)
        while True:
            try:
                r = await self._api("getUpdates", offset=self.offset, timeout=30, allowed_updates=["message", "edited_message"])
                for u in r.get("result", []):
                    self.offset = u["update_id"] + 1
                    try:
                        await self.tratar(u)
                    except Exception as e:
                        bus.emitir("conexoes_canal", canal="telegram", erro=f"{type(e).__name__}: {e}"[:120])
            except Exception as e:
                bus.emitir("conexoes_canal", canal="telegram", erro=f"{type(e).__name__}: {e}"[:120])
                await asyncio.sleep(10)
