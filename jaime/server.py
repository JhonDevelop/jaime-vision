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
    # fase 3 — D: telemetria local (janela ativa + pedidos), modo atento, orçamento diário e prioridades de estudo
    from .telemetria.uso import Telemetria
    from .telemetria import prioridades
    from .cortex.orcamento import Orcamento
    from .agenda.scheduler import Atencao
    orcamento = Orcamento(settings.vault, float(os.environ.get("JAIME_ORCAMENTO_DIA_USD", "0").strip() or 0))
    orcamento.ligar_ao_placar(jaime.placar)                 # todo custo de turno entra no orçamento (60/25/15)
    atencao = Atencao()                                      # última fala do João, pelo bus
    telemetria = Telemetria(jaime.vault, placar=jaime.placar)
    jaime.estudo.orcamento, jaime.estudo.atencao = orcamento, atencao
    jaime.agenda.ao("fecha o dia", lambda: prioridades.recalcular(jaime.vault, telemetria, jaime.placar))
    jaime.agenda.ao("fecha a semana", lambda: telemetria.escrever_uso())
    telemetria_t = asyncio.create_task(telemetria.rodar(observador))
    atencao_t = asyncio.create_task(atencao.escutar_bus())
    app.state.orcamento, app.state.telemetria, app.state.atencao = orcamento, telemetria, atencao
    jaime.agenda.ouvido = ouvido; jaime.agenda.start()      # rotinas e lembretes, no processo (sem n8n)
    # mente contínua (mínima): estuda um problema em aberto a cada 30 min, só quando ninguém está falando com ele
    ocioso = lambda: jaime.acesso.liberado and not (ouvido and ouvido.ocupado) and not jaime._lock.locked()
    estudo_t = asyncio.create_task(jaime.estudo.rodar_em_ciclos(ocioso))
    # raciocínio próprio: pensa sobre o mundo do João quando ocioso (respeita orçamento se houver)
    if getattr(jaime, "pensar", None) is not None:
        try: jaime.pensar.pode_gastar = (lambda: app.state.orcamento.pode("estudo")) if getattr(app.state, "orcamento", None) else (lambda: True)
        except Exception: pass
        pensar_t = asyncio.create_task(jaime.pensar.rodar(ocioso))
    else:
        pensar_t = None
    # fase 3: relatórios dos filhos (terminais no Maestri) chegam pela nota compartilhada; os importantes são falados
    equipe_t = asyncio.create_task(jaime.equipe.vigiar_relatorios(falar=(ouvido.falar if ouvido else None)))
    # os dois hemisférios não podem viver dormindo: este laço acorda e dá pauta própria a cada um
    from .cerebros.despertador import rodar as rodar_despertador
    despertador_t = asyncio.create_task(rodar_despertador(jaime, ocioso))
    jaime.estudo.emitir()
    # fase 3 — E: vontades (impulsos ouvem o bus), Mente (impulso × janela × orçamento) e noite criativa/Vitrine
    from .vontade import ligar as ligar_vontade
    app.state.vontade = ligar_vontade(jaime, ocioso, orcamento=getattr(app.state, "orcamento", None))   # orçamento do D, se já ligado
    jaime.vontade = app.state.vontade      # a autoconsciência (brain/eu.py) lê o impulso dominante daqui
    # Telegram: canal do celular, só o dono (JAIME_OWNER_TELEGRAM_ID)
    from .conexoes.telegram import Telegram
    telegram = Telegram(settings.telegram_token, settings.owner_telegram_id, jaime)
    telegram_t = asyncio.create_task(telegram.rodar())
    if telegram.ativo:
        jaime.conexoes.registrar("Telegram", "mensagens do dono (canal telegram)", "token do @BotFather no .env", "@BotFather /revoke ou apagar TELEGRAM_BOT_TOKEN")
    yield
    monitor.cancel(); sonda.cancel(); vigilancia.cancel(); estudo_t.cancel(); equipe_t.cancel(); telegram_t.cancel(); notif_t.cancel(); despertador_t.cancel(); jaime.agenda.stop()
    if pensar_t: pensar_t.cancel()
    app.state.vontade.parar()   # fase 3 — E
    telemetria_t.cancel(); atencao_t.cancel(); telemetria.salvar()      # fase 3 — D
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

# Rotas que podem ser abertas sem token: é por elas que o convidado PEDE o token.
ABERTAS = ("/entrar", "/favicon.ico")


@app.middleware("http")
async def porta_da_rede(request: Request, call_next):
    """Quem pode falar com o Jaime.

    Com `JAIME_BIND=127.0.0.1` (o padrão), só a própria máquina — é o desenho original e nada muda.
    Com o bind aberto (o João abriu em 17/09 para o Gabriel usar da máquina dele), a própria máquina
    continua entrando sem cerimônia, e quem vem de FORA precisa do token. Sem isso, qualquer aparelho
    no mesmo Wi-Fi conversaria com o Jaime, leria o painel de finanças e tentaria a palavra-passe à
    vontade — abrir a porta sem tranca não é autonomia, é descuido."""
    host = request.client.host if request.client else ""
    try:
        local = ipaddress.ip_address(host).is_loopback
    except ValueError:
        local = False
    if settings.bind == "127.0.0.1":
        if not local:
            return JSONResponse({"erro": "Jaime só aceita conexões locais"}, status_code=403)
        return await call_next(request)
    if local or request.url.path in ABERTAS:
        return await call_next(request)
    dado = (request.headers.get("x-jaime-token")
            or request.query_params.get("t")
            or request.cookies.get("jaime_token") or "")
    if dado != settings.server_token:
        return JSONResponse(
            {"erro": "preciso do token para falar com você de fora desta máquina",
             "como": "abra /entrar?t=SEU_TOKEN uma vez; eu guardo no navegador"}, status_code=401)
    return await call_next(request)


@app.get("/entrar")
async def entrar(t: str = ""):
    """O convidado abre isto UMA vez com o token na URL; o navegador guarda e o resto funciona sozinho."""
    from fastapi.responses import RedirectResponse
    if t != settings.server_token:
        return JSONResponse({"erro": "token inválido"}, status_code=401)
    r = RedirectResponse("/", status_code=302)
    r.set_cookie("jaime_token", t, max_age=60 * 60 * 24 * 90, httponly=True, samesite="lax")
    return r

def _auth(token: str | None):
    if token != settings.server_token:
        raise HTTPException(401, "token inválido")

# ── HUD ────────────────────────────────────────────────
@app.get("/")
async def hud():
    return FileResponse(STATIC / "cockpit.html")     # cockpit ATSMATRIX (principal)

@app.get("/classico")
async def hud_classico():
    return FileResponse(STATIC / "index.html")       # HUD 3D anterior (cérebro de pontos)

@app.get("/cockpit")
async def hud_cockpit():
    return FileResponse(STATIC / "cockpit.html")

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

@app.get("/hud/agentes")
async def hud_agentes():
    """O grafo COMPLETO do J.A.I.M.E (estilo ATSMATRIX): todas as peças reais como nós — orquestrador, maesters,
    ferramentas, loops, equipe, e o cérebro inteiro do vault (notas, cada linha do diário, problemas, pensamentos,
    música). Denso de verdade, sem inventar. Alimenta a vista central do cérebro no cockpit."""
    from .hud.grafo import montar
    return montar(jaime.vault, jaime)

@app.get("/hud/semana")
async def hud_semana():
    """A agenda física: sete dias, duas faixas por dia. A do João (compromissos, lembretes, prazos) e a do
    J.A.I.M.E (rotinas dele, estudo, criação, melhorias) — separadas, porque o que ele decide fazer sozinho
    não faz parte da agenda do João."""
    from .agenda.semana import montar
    return montar(jaime.vault, jaime)

@app.get("/hud/cerebros")
async def hud_cerebros():
    """Os três hemisférios: quem está acordado, forte em quê, e o placar de acertos e erros de cada um."""
    return {"hemisferios": jaime.cerebros.estado(), "resumo": jaime.cerebros.resumo()}

@app.get("/hud/universo")
async def hud_universo():
    """O universo do J.A.I.M.E: os mundos vivos dele (mente, vontade, estudo, memória, equipe, feitoria,
    vigilância, cuidado, serviço, mãos, consultoria, conexões), cada um com os corpos reais em órbita e o
    quanto está aceso agora. Alimenta a vista Universo do cockpit."""
    from .hud.universo import montar
    return montar(jaime.vault, jaime)

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

# fase 3 — HUD: fotografia dos subsistemas para o painel "Sistemas" (lote do Vigia, fila, filhos, estudo, rotina, orçamento)
@app.get("/hud/sistemas")
async def hud_sistemas():
    from .hud.sistemas import montar
    return montar(jaime, ouvido, app.state, settings)

@app.get("/hud/conexoes")
async def hud_conexoes():
    return conexoes.estado()

@app.get("/hud/financas")
async def hud_financas(mes: str = ""):
    """Painel Finanças: saldo, entradas/saídas, gastos por categoria e evolução por mês (para os gráficos)."""
    return jaime.financas.resumo(mes)

@app.get("/hud/musica")
async def hud_musica():
    """Painel Música: se conectado, o que toca e o gosto; senão, o card de conectar."""
    if not jaime.spotify.conectado:
        return {"conectado": False, "dica": "python -m jaime conectar spotify"}
    try:
        return {"conectado": True, "tocando": jaime.spotify.o_que_toca(), "top_artistas": jaime.spotify.top("artists")}
    except Exception as e:
        return {"conectado": True, "erro": f"{type(e).__name__}"}

@app.get("/hud/painel")
async def hud_painel():
    """Cockpit do J.A.I.M.E num JSON: finanças, afazeres (tarefas) e agenda (próximos lembretes/rotinas)."""
    from datetime import datetime
    tarefas = jaime.vault.tarefas_abertas()
    try:
        lembretes = [{"quando": q.strftime("%d/%m %H:%M"), "o_que": o} for q, o in sorted(jaime.agenda.lembretes())[:8]]
    except Exception:
        lembretes = []
    rotinas = [{"cron": " ".join(c.values()), "ordem": o} for c, o in getattr(jaime.agenda, "rotinas", [])][:12]
    import re as _re
    feitos = _re.findall(r"^-\s+\[[xX]\]\s+(.+)$", jaime.vault.read("30-Tarefas/Inbox.md") or "", _re.M)
    return {"financas": jaime.financas.resumo(), "afazeres": tarefas, "afazeres_total": len(tarefas),
            "afazeres_feitos": feitos[-12:],
            "agenda": {"lembretes": lembretes, "rotinas": rotinas}, "agora": datetime.now().strftime("%d/%m/%Y %H:%M")}

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

@app.post("/hud/dizer")
async def hud_dizer(body: dict):
    """Teclado do cockpit: o texto entra como um turno do João (canal hud). Local, sem token."""
    texto = str(body.get("texto") or "").strip()
    if not texto:
        return {"resposta": ""}
    return {"resposta": await jaime.ask(texto, canal="hud")}

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
