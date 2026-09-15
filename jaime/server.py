"""API + HUD do Jaime.

Local por padrão (127.0.0.1). O HUD (/) não usa token porque só é alcançável na própria máquina;
/ask e /webhook/* exigem X-Jaime-Token e só fazem sentido expostos via túnel (JAIME_BIND=0.0.0.0)."""
from __future__ import annotations
import asyncio, ipaddress, json, os
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
from .hud.conexoes import Conexoes
from .voice.escuta import Ouvido
from .ops.observador import Observador

jaime = Jaime(settings)
conexoes = Conexoes(settings, jaime)
observador = Observador(jaime)
ouvido: Ouvido | None = None
STATIC = Path(__file__).parent / "hud" / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    global ouvido
    monitor = asyncio.create_task(loop_monitor())
    sonda = asyncio.create_task(conexoes.sondar())
    await jaime.start(apresentar=True)
    if settings.voz != "off" and settings.voz_modo == "conversa" and settings.openai_key:
        # fase 3: fala-para-fala pelo Realtime; o Ouvido (pipeline) fica de fora
        from .voice.tempo_real import Conversa
        ouvido = Conversa(jaime, settings, asyncio.get_running_loop(), observador)
        observador.ouvido = ouvido
        ouvido.start()
        if jaime.apresentacao:
            asyncio.get_running_loop().call_later(3, ouvido.falar, jaime.apresentacao)
    elif settings.voz != "off":
        # o microfone vive no servidor: abrir o HUD já é estar ouvindo
        # fase 3: `duplex` (padrão) = STT em streaming + antecipador + barge-in; `pipeline` = turno a turno
        if settings.voz_modo == "duplex":
            from .voice.duplex import OuvidoDuplex
            ouvido = OuvidoDuplex(jaime, settings, asyncio.get_running_loop())
        else:
            ouvido = Ouvido(jaime, settings, asyncio.get_running_loop())
        ouvido.observador = observador; observador.ouvido = ouvido
        ouvido.start()
        if jaime.apresentacao:
            asyncio.get_running_loop().run_in_executor(None, _falar_quando_pronto, jaime.apresentacao)
    vigilancia = asyncio.create_task(observador.rodar())   # de olho no que o João faz na máquina
    # gravador de processos usa o observador (app/janela) e a captura de tela a cada clique
    from .maos import computador
    jaime.gravador.observador = observador; jaime.gravador.capturador = computador.capturar
    # notificações do Mac (Central de Notificações): avisa por voz as importantes
    from .ops.notificacoes import Notificacoes
    notificacoes = Notificacoes(jaime, ouvido)
    notif_t = asyncio.create_task(notificacoes.rodar())
    app.state.notificacoes = notificacoes
    jaime.agenda.ouvido = ouvido; jaime.agenda.start()      # rotinas e lembretes, no processo (sem n8n)
    # mente contínua (mínima): estuda um problema em aberto a cada 30 min, só quando ninguém está falando com ele
    ocioso = lambda: jaime.acesso.liberado and not (ouvido and ouvido.ocupado) and not jaime._lock.locked()
    estudo_t = asyncio.create_task(jaime.estudo.rodar_em_ciclos(ocioso))
    jaime.estudo.emitir()
    # fase 3 — E: vontades (impulsos ouvem o bus), Mente (impulso × janela × orçamento) e noite criativa/Vitrine
    from .vontade import ligar as ligar_vontade
    app.state.vontade = ligar_vontade(jaime, ocioso, orcamento=getattr(app.state, "orcamento", None))   # orçamento do D, se já ligado
    # Telegram: canal do celular, só o dono (JAIME_OWNER_TELEGRAM_ID)
    from .conexoes.telegram import Telegram
    telegram = Telegram(settings.telegram_token, settings.owner_telegram_id, jaime)
    telegram_t = asyncio.create_task(telegram.rodar())
    if telegram.ativo:
        jaime.conexoes.registrar("Telegram", "mensagens do dono (canal telegram)", "token do @BotFather no .env", "@BotFather /revoke ou apagar TELEGRAM_BOT_TOKEN")
    yield
    monitor.cancel(); sonda.cancel(); vigilancia.cancel(); estudo_t.cancel(); telegram_t.cancel(); notif_t.cancel(); jaime.agenda.stop()
    app.state.vontade.parar()   # fase 3 — E
    if ouvido:
        ouvido.stop()
    await jaime.stop()

def _falar_quando_pronto(texto: str):
    """A apresentação é falada assim que o TTS carregar (o Whisper demora alguns segundos a subir)."""
    import time
    for _ in range(120):
        if ouvido and ouvido._tts:
            ouvido.falar(texto); return
        time.sleep(0.5)

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

@app.get("/hud/vendor/{arquivo}")
async def hud_vendor(arquivo: str):
    p = (STATIC / "vendor" / arquivo).resolve()
    if p.parent != (STATIC / "vendor").resolve() or not p.is_file():
        raise HTTPException(404)
    return FileResponse(p)

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
            "apresentacao": jaime.apresentacao, "notion": jaime.notion.ativo, "modelo": jaime.modelo_atual,
            "voz": _voz_estado(), "conexoes": conexoes.estado(), "nome": jaime.identidade.nome,
            "contexto": {"app": observador.atual[0], "janela": observador.atual[1]}}

def _voz_estado() -> dict:
    if settings.voz == "off":
        return {"disponivel": False, "ativa": False, "motivo": "JAIME_VOZ=off"}
    if not ouvido:
        return {"disponivel": False, "ativa": False, "motivo": "iniciando"}
    return {"disponivel": not ouvido.erro, "ativa": ouvido.ativo, "motivo": ouvido.erro,
            "stt": "deepgram" if settings.deepgram_key else f"whisper:{settings.whisper_modelo}",
            "tts": {"openai": "openai:" + os.environ.get("JAIME_OPENAI_VOZ", "onyx"), "elevenlabs": "elevenlabs"}.get(os.environ.get("JAIME_TTS", "auto"), "auto") if (settings.openai_key or settings.elevenlabs_key) else "say"}

@app.get("/hud/tela")
async def hud_tela():
    """Última captura de tela do computer use (só local)."""
    from .maos.computador import ULTIMA
    if not ULTIMA.exists():
        raise HTTPException(404)
    return FileResponse(ULTIMA, headers={"Cache-Control": "no-store"})

@app.get("/hud/vault")
async def hud_vault():
    """O cérebro real: notas do vault como nós, [[links]] como arestas — o HUD desenha e acende o que ele toca."""
    import re as _re
    raiz = settings.vault; nos, arestas = [], []
    idx = {}
    for p in sorted(raiz.rglob("*.md")):
        if ".obsidian" in p.parts or "templates" in p.parts:
            continue
        rel = str(p.relative_to(raiz)); pasta = rel.split("/")[0]
        idx[p.stem] = rel; idx[rel] = rel
        nos.append({"id": rel, "nome": p.stem, "pasta": pasta, "kb": round(p.stat().st_size / 1024, 1)})
    for n in nos:
        try:
            txt = (raiz / n["id"]).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for alvo in set(_re.findall(r"\[\[([^\]|#]+)", txt)):
            alvo = alvo.strip(); dest = idx.get(alvo) or idx.get(alvo.split("/")[-1])
            if dest and dest != n["id"]:
                arestas.append([n["id"], dest])
    return {"nos": nos, "arestas": arestas, "total": len(nos)}

@app.get("/hud/busca")
async def hud_busca(q: str):
    """Cérebro interativo: busca semântica no vault (FTS5) para o painel do HUD."""
    try:
        jaime.indice.atualizar()
        return {"q": q, "hits": [{"rel": c, "trecho": t} for c, t, _ in jaime.indice.buscar(q, 12)]}
    except Exception as e:
        return {"q": q, "hits": [], "erro": str(e)[:120]}

@app.get("/hud/mente")
async def hud_mente():
    """O que ele sabe de você e o que está pensando: pessoas, vínculo, humor, problemas em aberto, propostas, lembretes."""
    try:
        return {"pessoas": jaime.vinculo.pessoas(), "vinculo": jaime.vinculo.dados(), "humor": jaime.humor.dados(),
                "problemas": [{"id": p.id, "titulo": p.titulo, "tentativas": len(p.tentativas)} for p in jaime.estudo.problemas.abertos()],
                "propostas": [{"id": p.id, "titulo": p.titulo, "estado": p.estado} for p in jaime.evolucao.propostas()][-5:],
                "lembrar": __import__("jaime.brain.ouvido_passivo", fromlist=["pendentes"]).pendentes(jaime.vault)[:5],
                "estado": {"fase": jaime.estado.fase(), "situacao": jaime.estado.secao("Situação agora"), "andamento": jaime.estado.secao("Em andamento")}}
    except Exception as e:
        return {"erro": str(e)[:160]}

# fase 3 — E: Vitrine (criações da noite criativa) + níveis das vontades; o voto realimenta os impulsos pelo bus
@app.get("/hud/vitrine")
async def hud_vitrine():
    v = getattr(app.state, "vontade", None)
    if not v:
        return {"itens": [], "vontades": {}, "escolha": None}
    return {"itens": v.criacoes.listar(), "vontades": v.impulsos.dados(), "escolha": v.mente.ultima.dados() if v.mente.ultima else None}

@app.post("/hud/vitrine/{id_}/voto")
async def hud_vitrine_voto(id_: str, body: dict):
    """body: {"gostei": true|false}"""
    v = getattr(app.state, "vontade", None)
    if not v:
        raise HTTPException(409, "vontades indisponíveis")
    item = v.criacoes.votar(id_, bool(body.get("gostei", body.get("gostou", True))))
    if not item:
        raise HTTPException(404, "criação não encontrada")
    return item

@app.get("/hud/nota")
async def hud_nota(rel: str):
    """Conteúdo de uma nota (só local), para o painel do cérebro."""
    try:
        return {"rel": rel, "texto": jaime.vault.read(rel)[:6000]}
    except Exception:
        raise HTTPException(404)

@app.get("/hud/conexoes")
async def hud_conexoes():
    return conexoes.estado()

@app.post("/hud/voz")
async def hud_voz(body: dict):
    """Liga/desliga o microfone a partir do HUD."""
    if not ouvido:
        raise HTTPException(409, "voz indisponível")
    ouvido.ativo = bool(body.get("ativa", True))
    bus.emitir("voz", estado="ouvindo" if ouvido.ativo else "mudo", falando=False)
    return _voz_estado()

@app.post("/hud/teclado")
async def hud_teclado(body: dict):
    """O HUD avisa que o teclado abriu/fechou (para o histórico e outros clientes)."""
    bus.emitir("teclado", aberto=bool(body.get("aberto")), motivo=str(body.get("motivo") or "")[:120])
    return {"ok": True}

@app.post("/hud/falar")
async def hud_falar(body: dict):
    texto = (body.get("texto") or "").strip()
    if not texto:
        raise HTTPException(400, "texto vazio")
    asyncio.create_task(jaime.ask(texto, canal="hud", contexto=observador.contexto()))   # resposta chega pelo /hud/stream
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
    return {"resposta": await jaime.ask(body.get("texto", ""), canal=body.get("canal", "api"))}

@app.get("/webhook/meta")
async def meta_verificar(request: Request):
    """Handshake do webhook da Meta (hub.mode/verify_token/challenge)."""
    from .conexoes.meta import handshake
    desafio = handshake(dict(request.query_params), settings.meta_verify_token)
    if desafio is None:
        raise HTTPException(403, "verify_token inválido")
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(desafio)

@app.post("/webhook/meta")
async def meta_receber(request: Request):
    """WhatsApp Cloud API e Instagram Messaging: assinatura verificada com o app secret; terceiros viram rascunho."""
    from .conexoes.meta import verificar_assinatura
    corpo = await request.body()
    if not verificar_assinatura(settings.meta_app_secret, corpo, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(403, "assinatura inválida")
    asyncio.create_task(jaime.meta.receber(json.loads(corpo or b"{}")))
    return {"ok": True}

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
