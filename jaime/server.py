"""API + HUD do Jaime.

Local por padrão (127.0.0.1). O HUD (/) não usa token porque só é alcançável na própria máquina;
/ask e /webhook/* exigem X-Jaime-Token e só fazem sentido expostos via túnel (JAIME_BIND=0.0.0.0)."""
from __future__ import annotations
import asyncio, ipaddress, json
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from .config import settings
from .orchestrator.jaime import Jaime
from .brain.estado import maquina
from .channels.whatsapp import Evolution, extrair_mensagem
from .channels.telephony import router as telephony_router
from .hud.events import bus
from .hud.monitor import loop_monitor

jaime = Jaime(settings)
STATIC = Path(__file__).parent / "hud" / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    monitor = asyncio.create_task(loop_monitor())
    await jaime.start(apresentar=True)
    yield
    monitor.cancel()
    await jaime.stop()

app = FastAPI(title="Jaime", lifespan=lifespan)
app.include_router(telephony_router)

@app.middleware("http")
async def so_local(request: Request, call_next):
    if settings.bind == "127.0.0.1":
        host = request.client.host if request.client else ""
        if not ipaddress.ip_address(host).is_loopback:
            return JSONResponse({"erro": "Jaime só aceita conexões locais"}, status_code=403)
    return await call_next(request)

def _auth(token: str | None):
    if token != settings.server_token:
        raise HTTPException(401, "token inválido")

# ── HUD ────────────────────────────────────────────────
@app.get("/")
async def hud():
    return FileResponse(STATIC / "index.html")

@app.get("/hud/stream")
async def hud_stream():
    async def gen():
        q = bus.assinar()
        try:
            for evt in list(bus.historico)[-60:]:
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
            while True:
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            bus.cancelar(q)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.get("/hud/estado")
async def hud_estado():
    return {"liberado": jaime.acesso.liberado, "fase": jaime.estado.fase(), "maquina": maquina(),
            "situacao": jaime.estado.secao("Situação agora"), "proximos": jaime.estado.secao("Próximos passos"),
            "apresentacao": jaime.apresentacao, "notion": jaime.notion.ativo, "modelo": settings.model}

@app.post("/hud/falar")
async def hud_falar(body: dict):
    texto = (body.get("texto") or "").strip()
    if not texto:
        raise HTTPException(400, "texto vazio")
    asyncio.create_task(jaime.ask(texto, canal="hud"))   # resposta chega pelo /hud/stream
    return {"ok": True}

@app.post("/hud/trancar")
async def hud_trancar():
    jaime.acesso.trancar(); bus.emitir("acesso", liberado=False); return {"ok": True}

# ── canais externos ────────────────────────────────────
@app.get("/health")
async def health():
    return {"ok": True, "modelo": settings.model, "fase": jaime.estado.fase(), "maquina": maquina()["host"]}

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
        jaime.vault.diario(f"WhatsApp de {numero}: {texto[:120]}", "Log")
        return {"registrado": True}
    resposta = await jaime.ask(texto, canal="whatsapp")
    await Evolution(settings).enviar(numero, resposta)
    return {"ok": True}
