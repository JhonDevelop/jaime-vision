"""Rotas da tela Jarvis (/hud/jarvis), do rosto, do holograma e do webhook de saúde.

- tela e arquivos: livres na própria máquina (o middleware do servidor já exige token de fora);
- rosto: só da própria máquina e do próprio HUD (Origin); cadastrar só com o cérebro destrancado e depois do
  "aprende meu rosto" (a página sozinha não cadastra ninguém);
- saúde: `POST /webhook/saude` exige o X-Jaime-Token (é o celular do João mandando pela rede/túnel).
"""
from __future__ import annotations
import hmac
from pathlib import Path
import asyncio, json
from fastapi import APIRouter, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from ..blocos.rotas import _so_local, _loopback, origem_ok
from ..hud.events import bus
from . import holograma as holo
from . import saude as sd

router = APIRouter()
ESTATICO = Path(__file__).resolve().parent.parent / "hud" / "static"
ESTADO: dict = {"jarvis": None, "jaime": None}
ARQUIVOS = {"jarvis.js", "jarvis.css", "holograma.js", "orbe.js", "sentidos.js"}
SEM_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}


def _jarvis():
    j = ESTADO.get("jarvis")
    if j is None:
        raise HTTPException(409, "cenas do Jarvis desligadas (JAIME_JARVIS=off)")
    return j


def _versao() -> str:
    """Muda quando os arquivos da tela mudam (deploy): a aba aberta se recarrega sozinha."""
    import hashlib
    h = hashlib.sha1()
    for p in sorted([ESTATICO / "jarvis.html", *(ESTATICO / "jarvis").glob("*")]):
        try:
            h.update(p.name.encode()); h.update(str(p.stat().st_mtime_ns).encode())
        except OSError:
            pass
    return h.hexdigest()[:12]


@router.get("/jarvis/versao")
async def versao():
    return {"versao": _versao()}


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


@router.post("/jarvis/holograma/cena")
async def holograma_cena(body: dict, request: Request):
    """A tela conta o que está aberto: título, peças (nome, centro, tamanho, visível) e a peça selecionada."""
    _so_local(request)
    _jarvis().estudio.receber_cena(body)
    return {"ok": True}


@router.post("/jarvis/holograma/tracos")
async def holograma_tracos(body: dict, request: Request):
    _so_local(request)
    return {"tracos": _jarvis().estudio.receber_tracos(body.get("tracos"))}


@router.post("/jarvis/holograma/malhas")
async def holograma_malhas(body: dict, request: Request):
    """Resposta da tela ao pedido de exportação: as malhas como o João deixou."""
    _so_local(request)
    _jarvis().estudio.receber_malhas(body)
    return {"ok": True}


@router.post("/jarvis/holograma/fechado")
async def holograma_fechado(request: Request):
    _so_local(request)
    _jarvis().estudio.fechar()
    return {"ok": True}


@router.websocket("/jarvis/maos/ws")
async def maos_ws(ws: WebSocket):
    """A aba do Jarvis manda os pontos das mãos (~30/s); o servidor move o mouse do computador (controle_maos.py).
    Só da própria máquina e do próprio HUD — o serviço pode estar em 0.0.0.0, e mouse remoto seria um buraco."""
    host = ws.client.host if ws.client else ""
    j = ESTADO.get("jarvis")
    if not _loopback(host) or not origem_ok(ws.headers.get("origin") or "") or j is None:
        await ws.close(code=4403)
        return
    c = j.controle
    await ws.accept()
    try:
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_text(), 0.25)
            except asyncio.TimeoutError:
                c.vigiar()
                continue
            if len(msg) > 20000:
                continue
            try:
                d = json.loads(msg)
            except json.JSONDecodeError:
                continue
            if not c.nativo:                  # com o rastreador nativo ligado, ele manda; o navegador só observa
                c.receber(d.get("maos") or [])
    except WebSocketDisconnect:
        pass
    finally:
        c.soltar_tudo()


@router.get("/jarvis/maos/estado")
async def maos_estado(request: Request):
    _so_local(request)
    return _jarvis().controle.estado()


@router.post("/jarvis/tela/viva")
async def tela_viva(request: Request):
    """A tela Jarvis avisa que está aberta (a cada 10 s): as cenas não abrem outra por cima."""
    _so_local(request)
    from .tela import sinal_de_vida
    sinal_de_vida()
    return {"ok": True}


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
    j.receber_rosto(res)
    # a página só fica sabendo do status e do nome de quem já é conhecido (nunca do descritor guardado)
    bus.emitir("rosto", acao="resultado", status=res["status"], nome=res.get("nome") or "")
    return {"status": res["status"], "nome": res.get("nome") or ""}


@router.post("/jarvis/rosto/cadastrar")
async def rosto_cadastrar(body: dict, request: Request):
    _so_local(request)
    j = _jarvis()
    jaime = ESTADO.get("jaime")
    if jaime is not None and not getattr(getattr(jaime, "acesso", None), "liberado", False):
        raise HTTPException(403, "cérebro trancado")
    c = j.cadastrando
    if not c:
        raise HTTPException(409, "peça 'aprende meu rosto' (ou 'aprende o rosto da Ana') antes")
    try:
        n = j.rostos.cadastrar(body.get("descritores") or [], pessoa=c["pessoa"], nome=c["nome"], dono=c["dono"], relacao=c["relacao"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    frase = j.cadastrado(n)
    bus.emitir("rosto", acao="cadastrado", amostras=n, nome=c["nome"] if not c["dono"] else "")
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
