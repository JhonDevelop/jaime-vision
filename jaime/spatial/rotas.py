"""Rotas HTTP da camada espacial (locais, como o resto do HUD — o middleware do servidor já barra fora da máquina).

Nenhuma rota liga a câmera se o João não configurou `JAIME_SPATIAL=camera`: `/espacial/ligar` só religa o modo
que está no .env depois de um kill switch."""
from __future__ import annotations
from pathlib import Path
import ipaddress
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from .integracao import ESTADO

router = APIRouter()
JS = Path(__file__).resolve().parent.parent / "hud" / "static" / "espacial.js"


def _s():
    return ESTADO.get("servico")


def _so_local(request: Request) -> None:
    """Confirmar/desfazer ação no SO só da PRÓPRIA máquina — mesmo com JAIME_BIND aberto para convidados com token."""
    host = request.client.host if request.client else ""
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        if host in ("testclient", "localhost"):
            return
    raise HTTPException(403, "ação no computador só se confirma na própria máquina")


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


# ── fase 3: prévias, confirmação no HUD, recibos e Undo ─────────────────────
@router.get("/espacial/acoes")
async def acoes_estado():
    a = ESTADO.get("acoes")
    if not a:
        return {"ativo": False}
    return {"ativo": True, "dry_run": a.dry_run, "duplicados_bloqueados": a.duplicados_bloqueados,
            "previas": [pv.to_dict() for _, pv in list(a.previas.values())[-20:]],
            "recibos": [r.to_dict() | {"undo_dados": bool(r.undo_dados)} for r in list(a.por_recibo.values())[-20:]],
            "telas": ESTADO["telas"].estado() if ESTADO.get("telas") else None}


@router.post("/espacial/acoes/{proposta_id}/confirmar")
async def acoes_confirmar(proposta_id: str, request: Request):
    """O botão do HUD é confirmação explícita do João (só da própria máquina, com o cérebro destrancado)."""
    _so_local(request)
    a = ESTADO.get("acoes")
    if not a:
        raise HTTPException(409, "espacial desligado")
    return (await a.executar(proposta_id, confirmado=True)).to_dict()


@router.post("/espacial/recibos/{recibo_id}/desfazer")
async def recibo_desfazer(recibo_id: str, request: Request):
    _so_local(request)
    a = ESTADO.get("acoes")
    if not a:
        raise HTTPException(409, "espacial desligado")
    ok, msg = await a.desfazer(recibo_id)
    return {"ok": ok, "msg": msg}


@router.post("/espacial/descartes/{token}/desfazer")
async def descarte_desfazer(token: str):
    i = ESTADO.get("intencoes")
    return {"ok": bool(i and i.desfazer_descarte(token))}


@router.post("/espacial/telas/validar")
async def telas_validar():
    """Depois de um hotplug, o João confere o apontamento e libera as ações de janela de novo."""
    t = ESTADO.get("telas")
    if not t:
        raise HTTPException(409, "espacial desligado")
    t.validar()
    return t.estado()
