"""Rotas dos blocos: REST para o cockpit/atalhos e WebSocket JBP para qualquer superfície.

Segurança:
- da própria máquina (loopback): entra direto, como superfície do dono;
- de fora (óculos/visor/tablet na rede, com JAIME_BIND aberto): só com o token DO DISPOSITIVO
  (`python -m jaime blocos parear <nome>`), e só se o JAIME_SERVER_TOKEN não for o padrão;
- mudar estado por REST (abrir/fechar/layout) só da própria máquina e do próprio HUD (Origin).
"""
from __future__ import annotations
import asyncio, hmac, ipaddress, json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from .integracao import ESTADO, token_dispositivo
from .modelo import BlocoInvalido
from .protocolo import FilaDeEnvio, codificar, sessao_de_ola, tratar_mensagem

router = APIRouter()
ESTATICO = Path(__file__).resolve().parent.parent / "hud" / "static"


def _g():
    g = ESTADO.get("g")
    if g is None:
        raise HTTPException(409, "blocos desligados (JAIME_BLOCOS=off)")
    return g


def _loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host in ("testclient", "localhost")


ORIGENS_LOCAIS = ("127.0.0.1", "localhost", "::1", "[::1]")


def origem_ok(origem: str) -> bool:
    """Sem Origin (cliente nativo) ou Origin da própria máquina. "null" (iframe sandbox de qualquer site) e
    DNS rebinding (evil.com apontando para 127.0.0.1 manda Origin evil.com) são recusados."""
    if not origem:
        return True
    if origem == "null":
        return False
    from urllib.parse import urlsplit
    return (urlsplit(origem).hostname or "") in ORIGENS_LOCAIS


def _so_local(request: Request) -> None:
    if not _loopback(request.client.host if request.client else ""):
        raise HTTPException(403, "isso só se faz na própria máquina")
    if not origem_ok(request.headers.get("origin") or ""):
        raise HTTPException(403, "pedido de outro site recusado")


def _segredo() -> str:
    try:
        from ..config import settings
        return settings.server_token
    except Exception:
        return ""


def dispositivo_autorizado(nome: str, token: str, segredo: str) -> bool:
    if not segredo or segredo == "troque-isto" or not nome or not token:
        return False
    return hmac.compare_digest(token_dispositivo(segredo, nome), token.strip())


@router.get("/hud/blocos.js")
async def blocos_js():
    r = FileResponse(ESTATICO / "blocos.js", media_type="application/javascript")
    r.headers["Cache-Control"] = "no-store"
    return r


@router.get("/blocos/leve")
async def leve():
    """Superfície leve (óculos, visor, celular, tablet): fundo preto — transparente em óculos see-through —
    e blocos empilhados. `?perfil=oculos|visor|janela`; de fora da máquina: `&dispositivo=<nome>&t=<token>`."""
    r = FileResponse(ESTATICO / "blocos_leve.html")
    r.headers["Cache-Control"] = "no-store"
    return r


@router.get("/blocos")
async def listar():
    g = ESTADO.get("g")
    if g is None:
        return {"ativo": False}
    m = ESTADO["modelos"]
    dono = g.dono_ok()
    return {"ativo": True,
            "abertos": [{"id": b.id, "titulo": b.titulo, "tipo": b.tipo, "fonte": b.fonte, "privado": b.privado}
                        for b in g.listar() if dono or not b.privado],
            "superficies": [{"perfil": s.perfil, "nome": s.nome} for s in g.sessoes.values()],
            "modelos": m.nomes(), "titulos": {n: m.receita(n).get("titulo", n) for n in m.nomes()}, "fontes": ESTADO["fontes"].listar(), "layouts": list(g.layouts())}


@router.post("/blocos")
async def abrir(body: dict, request: Request):
    _so_local(request)
    g, m = _g(), ESTADO["modelos"]
    try:
        d = m.instanciar(body["modelo"]) if body.get("modelo") else body
        b = g.abrir(d, origem="joao")
    except KeyError as e:
        raise HTTPException(404, f"modelo desconhecido: {e}")
    except BlocoInvalido as e:
        raise HTTPException(422, str(e))
    return {"ok": True, "id": b.id}


@router.post("/blocos/{bid}/fechar")
async def fechar(bid: str, request: Request):
    _so_local(request)
    return {"fechados": _g().fechar(bid, motivo="fechado em cockpit")}


@router.post("/blocos/desfazer")
async def desfazer(request: Request):
    _so_local(request)
    return {"msg": _g().desfazer()}


@router.post("/blocos/layout/{nome}")
async def layout(nome: str, body: dict, request: Request):
    _so_local(request)
    g = _g()
    try:
        if (body or {}).get("acao") == "abrir":
            return {"abertos": g.abrir_layout(nome)}
        return {"salvos": g.salvar_layout(nome)}
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.websocket("/blocos/ws")
async def ws(websocket: WebSocket):
    """Uma superfície. Primeira mensagem: {"op":"ola","perfil":…,"capacidades":…}. Depois, blocos adaptados."""
    g = ESTADO.get("g")
    host = websocket.client.host if websocket.client else ""
    local = _loopback(host)
    nome = websocket.query_params.get("dispositivo", "")
    token = websocket.query_params.get("t", "") or websocket.headers.get("x-jaime-token", "")
    origem = websocket.headers.get("origin") or ""
    if origem == "null" or (local and not origem_ok(origem)):
        await websocket.close(code=4403); return      # site de terceiros (ou iframe sandbox) não vira superfície do Jaime
    if g is None or not (local or dispositivo_autorizado(nome, token, _segredo())):
        await websocket.close(code=4401 if g is not None else 4409); return
    await websocket.accept()
    fila = FilaDeEnvio()
    try:
        ola = json.loads(await asyncio.wait_for(websocket.receive_text(), timeout=10))
        sessao = sessao_de_ola(ola, fila, confiavel=True)     # local ou dispositivo pareado = do dono
        if not local:
            sessao.nome = f"{sessao.nome} ({nome})"
    except Exception as e:
        await websocket.send_text(codificar({"op": "erro", "msg": f"handshake: {str(e)[:120]}"}))
        await websocket.close(code=4400); return
    await websocket.send_text(codificar(sessao.boas_vindas()))
    g.conectar(sessao)

    async def bombear():
        while True:
            try:
                msg = await asyncio.wait_for(fila.q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                msg = None
            if fila.estourou:                       # cliente lento: fecha, para ele não ficar mostrando tela velha
                await websocket.close(code=4408); return
            if msg is not None:
                await websocket.send_text(codificar(msg))

    envio = asyncio.create_task(bombear())
    jaime = ESTADO.get("jaime")

    async def executar(intencao: str):
        if jaime is not None:
            await jaime.ask(intencao, canal="hud")                # caminho normal: Vigia, orçamento, diário (já prefixada)

    try:
        while True:
            try:
                msg = json.loads(await websocket.receive_text())
            except json.JSONDecodeError:
                await websocket.send_text(codificar({"op": "erro", "msg": "json inválido"})); continue
            resp = await tratar_mensagem(g, sessao, msg, executar)
            if resp:
                await websocket.send_text(codificar(resp))
            if fila.estourou:
                break
    except WebSocketDisconnect:
        pass
    finally:
        envio.cancel()
        g.desconectar(sessao.id)
