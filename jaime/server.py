"""API do Jaime — para n8n, WhatsApp (Evolution API) e qualquer outro canal externo.

POST /ask               {"texto": "...", "canal": "n8n"}     header: X-Jaime-Token
POST /webhook/whatsapp  payload da Evolution API (messages.upsert)
GET  /health
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Request
from .config import settings
from .orchestrator.jaime import Jaime
from .channels.whatsapp import Evolution, extrair_mensagem
from .channels.telephony import router as telephony_router

jaime = Jaime(settings)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await jaime.start()
    yield
    await jaime.stop()

app = FastAPI(title="Jaime", lifespan=lifespan)
app.include_router(telephony_router)

def _auth(token: str | None):
    if token != settings.server_token:
        raise HTTPException(401, "token inválido")

@app.get("/health")
async def health():
    return {"ok": True, "modelo": settings.model}

@app.post("/ask")
async def ask(body: dict, x_jaime_token: str | None = Header(default=None)):
    _auth(x_jaime_token)
    return {"resposta": await jaime.ask(body.get("texto", ""), canal=body.get("canal", "n8n"))}

@app.post("/webhook/whatsapp")
async def whatsapp(req: Request, x_jaime_token: str | None = Header(default=None)):
    _auth(x_jaime_token)
    msg = extrair_mensagem(await req.json())
    if not msg:
        return {"ignorado": True}
    numero, texto = msg
    if settings.owner_phone and not numero.startswith(settings.owner_phone):
        # terceiros não dão ordens; o maester-comms pode só resumir para o João
        jaime.vault.diario(f"WhatsApp de {numero}: {texto[:120]}", "Log")
        return {"registrado": True}
    resposta = await jaime.ask(texto, canal="whatsapp")
    await Evolution(settings).enviar(numero, resposta)
    return {"ok": True}
