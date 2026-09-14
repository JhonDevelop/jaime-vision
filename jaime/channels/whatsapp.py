"""WhatsApp via Evolution API (número pessoal) — troque por Meta Cloud API para número comercial."""
from __future__ import annotations
import httpx
from ..config import Settings

def extrair_mensagem(payload: dict) -> tuple[str, str] | None:
    """Evolution API, evento messages.upsert → (numero, texto) ou None."""
    data = payload.get("data") or {}
    key = data.get("key") or {}
    if key.get("fromMe"):
        return None
    numero = (key.get("remoteJid") or "").split("@")[0]
    m = data.get("message") or {}
    texto = m.get("conversation") or (m.get("extendedTextMessage") or {}).get("text") or ""
    return (numero, texto) if numero and texto else None

class Evolution:
    def __init__(self, s: Settings):
        self.s = s

    async def enviar(self, numero: str, texto: str):
        if not self.s.evolution_url:
            return
        url = f"{self.s.evolution_url}/message/sendText/{self.s.evolution_instance}"
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(url, headers={"apikey": self.s.evolution_key},
                             json={"number": numero, "text": texto})
            r.raise_for_status()
