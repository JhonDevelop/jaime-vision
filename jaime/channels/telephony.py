"""Ligações via Twilio — esqueleto. Fluxo: Twilio <Gather speech> → /voz/twilio → Jaime → <Say> (ou stream ElevenLabs).

Última etapa do roadmap. Requer número Twilio e webhook público (ngrok/cloudflared em dev)."""
from __future__ import annotations
from fastapi import APIRouter, Form
from fastapi.responses import Response

router = APIRouter()

def twiml(texto: str, proximo: str = "/voz/twilio") -> Response:
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" language="pt-BR" action="{proximo}" speechTimeout="auto">
    <Say language="pt-BR">{texto}</Say>
  </Gather>
</Response>"""
    return Response(content=xml, media_type="application/xml")

@router.post("/voz/twilio")
async def voz_twilio(SpeechResult: str = Form(default="")):
    from .. import server
    if not SpeechResult:
        return twiml("Oi, aqui é o Jaime. Pode falar.")
    resposta = await server.jaime.ask(SpeechResult, canal="voice")
    return twiml(resposta)
