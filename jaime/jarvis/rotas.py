"""Rotas da tela Jarvis (/hud/jarvis), do rosto, do holograma e do webhook de saúde.

- tela e arquivos: livres na própria máquina (o middleware do servidor já exige token de fora);
- rosto: só da própria máquina e do próprio HUD (Origin); cadastrar só com o cérebro destrancado e depois do
  "aprende meu rosto" (a página sozinha não cadastra ninguém);
- saúde: `POST /webhook/saude` exige o X-Jaime-Token (é o celular do João mandando pela rede/túnel).
"""
from __future__ import annotations
import hmac
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from ..blocos.rotas import _so_local
from ..hud.events import bus
from . import holograma as holo
from . import saude as sd

router = APIRouter()
ESTATICO = Path(__file__).resolve().parent.parent / "hud" / "static"
ESTADO: dict = {"jarvis": None, "jaime": None}
ARQUIVOS = {"jarvis.js", "jarvis.css", "holograma.js", "orbe.js"}
SEM_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}


def _jarvis():
    j = ESTADO.get("jarvis")
    if j is None:
        raise HTTPException(409, "cenas do Jarvis desligadas (JAIME_JARVIS=off)")
    return j


@router.get("/hud/jarvis")
async def tela_jarvis():
    return FileResponse(ESTATICO / "jarvis.html", headers=SEM_CACHE)


@router.get("/hud/jarvis/{arquivo}")
async def arquivo_jarvis(arquivo: str):
    if arquivo not in ARQUIVOS:
        raise HTTPException(404)
    return FileResponse(ESTATICO / "jarvis" / arquivo, headers=SEM_CACHE)


@router.get("/hud/jarvis/vendor/{nome:path}")
async def vendor_jarvis(nome: str):
    """face-api e MediaPipe guardados nesta máquina (`python -m jaime jarvis baixar`); sem eles a tela usa o CDN."""
    from .vendor import arquivo
    p = arquivo(nome)
    if p is None:
        raise HTTPException(404)
    tipo = {".mjs": "text/javascript", ".js": "text/javascript", ".wasm": "application/wasm", ".json": "application/json"}.get(p.suffix, "application/octet-stream")
    return FileResponse(p, media_type=tipo, headers={"Cache-Control": "max-age=86400"})


@router.get("/jarvis/holograma/{slug}.glb")
async def holograma_glb(slug: str, request: Request):
    _so_local(request)
    p = holo.arquivo_glb(slug)
    if p is None:
        raise HTTPException(404)
    return FileResponse(p, media_type="model/gltf-binary")


@router.get("/jarvis/briefing")
async def ultimo_briefing(request: Request):
    _so_local(request)
    return {"segmentos": _jarvis().briefing.ultimo}


@router.post("/jarvis/rosto/verificar")
async def rosto_verificar(body: dict, request: Request):
    """A tela manda o descritor (ou {'status': 'sem_camera'|'sem_rosto'}); o servidor compara e responde só o status."""
    _so_local(request)
    j = _jarvis()
    if "descritor" in body:
        res = j.rostos.verificar(body.get("descritor"))
    else:
        st = str(body.get("status", ""))
        res = {"status": st if st in ("sem_camera", "sem_rosto") else "invalido", "distancia": None}
    j.monitor.receber_rosto(res)
    bus.emitir("rosto", acao="resultado", status=res["status"])
    return {"status": res["status"]}


@router.post("/jarvis/rosto/cadastrar")
async def rosto_cadastrar(body: dict, request: Request):
    _so_local(request)
    j = _jarvis()
    jaime = ESTADO.get("jaime")
    if jaime is not None and not getattr(getattr(jaime, "acesso", None), "liberado", False):
        raise HTTPException(403, "cérebro trancado")
    if not j.cadastrando:
        raise HTTPException(409, "peça 'aprende meu rosto' antes")
    try:
        n = j.rostos.cadastrar(body.get("descritores") or [])
    except ValueError as e:
        raise HTTPException(400, str(e))
    j.cadastrando = False
    bus.emitir("rosto", acao="cadastrado", amostras=n)
    frase = "Aprendi o seu rosto."
    bus.emitir("fala", texto=frase); bus.emitir("fala_fim")
    falar = ESTADO.get("falar")
    if callable(falar):
        falar(frase)
    return {"amostras": n}


@router.post("/webhook/saude")
async def webhook_saude(body: dict, x_jaime_token: str | None = Header(default=None)):
    from ..config import settings
    if not x_jaime_token or not hmac.compare_digest(x_jaime_token, settings.server_token):
        raise HTTPException(401, "token inválido")
    r = sd.salvar(body)
    bus.emitir("saude", recebido=True, observacoes=len(r.observacoes))
    return JSONResponse({"ok": True, "observacoes": len(r.observacoes)})
