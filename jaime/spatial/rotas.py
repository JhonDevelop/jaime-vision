"""Rotas HTTP da camada espacial (locais, como o resto do HUD — o middleware do servidor já barra fora da máquina).

Nenhuma rota liga a câmera se o João não configurou `JAIME_SPATIAL=camera`: `/espacial/ligar` só religa o modo
que está no .env depois de um kill switch."""
from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from .integracao import ESTADO

router = APIRouter()
JS = Path(__file__).resolve().parent.parent / "hud" / "static" / "espacial.js"


def _s():
    return ESTADO.get("servico")


@router.get("/hud/espacial.js")
async def espacial_js():
    r = FileResponse(JS, media_type="application/javascript")
    r.headers["Cache-Control"] = "no-store"
    return r


@router.get("/espacial/estado")
async def estado():
    s = _s()
    if not s:
        return {"ativo": False, "modo": "off", "dica": "JAIME_SPATIAL=sim no .env para a demo sem câmera"}
    return {"ativo": True, **s.estado()}


@router.post("/espacial/desligar")
async def desligar():
    s = _s()
    if not s:
        return {"ativo": False}
    return {"ativo": True, **(await s.desligar_rastreamento("desligado no HUD"))}


@router.post("/espacial/ligar")
async def ligar():
    s = _s()
    if not s:
        raise HTTPException(409, "JAIME_SPATIAL=off — ligar a expansão é decisão de configuração, não de clique")
    await s.iniciar()
    return {"ativo": True, **s.estado()}


@router.post("/espacial/latencia")
async def latencia(body: dict):
    s = _s()
    if s:
        s.registrar_render(list(body.get("amostras") or []))
    return {"ok": bool(s)}


@router.get("/espacial/cena")
async def cena():
    s = _s()
    return s.core.cena() if s else {"versao": 0, "objetos": [], "selecionado": {}}


@router.post("/espacial/selecionar")
async def selecionar(body: dict):
    """Alternativa sem mão (mouse/teclado/acessibilidade): selecionar pelo HUD vale como seleção do dono."""
    s = _s()
    if not s:
        raise HTTPException(409, "espacial desligado")
    oid = str(body.get("id") or "")
    if oid not in s.core.objects:
        raise HTTPException(404, "objeto não existe")
    ator = "joao" if s.dono_ok() else "desconhecido"
    s._publicar(s.core.select(ator, oid, 1.0, origem="hud"))
    return {"ok": True, "selecionado": oid, "ator": ator}
