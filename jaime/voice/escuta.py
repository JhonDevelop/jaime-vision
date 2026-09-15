"""Ouvidoria: escuta contínua. Roda dentro do servidor — abrir o HUD já liga o microfone.

microfone ─► frames de 32 ms ─► Silero VAD (probabilidade de voz) ─► Segmentador ─► STT ─► ativação por nome
           ─► Jaime.ask_stream ─► TTS frase a frase

Por que Silero e não energia: ventoinha, ar-condicionado e a própria caixa de som têm energia alta e constante;
o VAD aprende o que é voz humana e ignora o resto (custa ~1 ms por frame). Já vem dentro do faster-whisper.

Ativação (JAIME_ATIVACAO):
- `nome` (padrão): ele só responde quando a frase contém "Jaime" ("Jaime, está aí?", "Jaime, abre o Finder").
  Depois disso fica ativo por JAIME_JANELA_ATIVA_S segundos — dá para continuar a conversa sem repetir o nome.
- `sempre`: responde a tudo que ouvir.

Regras que evitam o Jaime se ouvir e responder a si mesmo: o microfone fica mudo enquanto ele fala, e
transcrições curtas demais ou iguais às "alucinações" clássicas do Whisper em silêncio são descartadas."""
from __future__ import annotations
import asyncio, random, re, threading, time
from collections import deque
from ..config import Settings
from ..hud.events import bus

SR = 16000
FRAME = 512                 # 32 ms — o tamanho de janela do Silero
FRAME_MS = FRAME * 1000 // SR
PRE_ROLL_MS = 320           # áudio guardado antes da voz começar, para não cortar a primeira sílaba
SILENCIO_MS = 700           # fim de fala
MIN_FALA_MS = 300           # menos que isso é ruído (porta batendo, tosse)
MAX_FALA_S = 20
VAD_INICIO = 0.5            # probabilidade para começar a gravar
VAD_FIM = 0.35              # abaixo disto conta como silêncio (histerese)
JANELA_VAD = 8              # frames de contexto para o Silero (256 ms)
MULETA_S = 3.0              # só em tarefas com ferramenta: silêncio máximo antes de "deixa eu ver…"
MULETAS = ["Deixa eu ver…", "Só um segundo.", "Hmm… deixa eu olhar isso.", "Peraí, já te digo."]

LIXO_WHISPER = re.compile(r"(legendas? pela comunidade|amara\.org|obrigad[oa] por assistir|tchau tchau|^\W*$|^\.+$)", re.I)
PEDIDOS_TECLADO = {"teclado", "abre o teclado", "abrir teclado", "deixa eu escrever", "quero escrever",
                   "vou escrever", "deixa eu digitar", "quero digitar"}
# o nome (e como o STT costuma escrevê-lo) vem de vault/00-Jaime/Identidade.md — ver jaime/identidade.py
NOME_RX = re.compile(r"\b(jaime|jayme|jaimi|jaimy|jamie|jaine|jaim|jaimes|jaimin|jardim|gênio|genio|jay me)\b[,.!?…\s]*", re.I)

def usar_nome(variantes: list[str]) -> None:
    """Recompila a detecção do nome (chamado no boot e após renomear)."""
    global NOME_RX
    NOME_RX = re.compile(r"\b(" + "|".join(re.escape(v) for v in variantes) + r")\b[,.!?…\s]*", re.I)
CHAMADA_RX = re.compile(r"^(ô|oi|ei|hey|olá|ola|e aí|eai|alô|alo|fala)[,\s]*$|^(você\s+)?(tá|ta|está|esta)\s+a[íi]\??$|^(me\s+)?(ouve|escuta|ouvindo|escutando)\??$|^acorda\??$", re.I)

DISPENSA_RX = re.compile(r"\b(encerrad[oa]|por enquanto (é|e) s[oó] isso|s[oó] isso por enquanto|pode descansar|descansa|pode ir|(até|ate) (mais|logo|depois)|"
                         r"obrigad[oa],? (é|e) s[oó]|(era|é|e) s[oó] isso|pode dormir|tchau|fica (à|a) vontade|t[aá] liberado)\b", re.I)

def quer_descansar(texto: str) -> bool:
    """'encerrado', 'por enquanto é só isso', 'pode descansar' → ele volta a esperar o nome."""
    return bool(DISPENSA_RX.search(texto or ""))

def quer_teclado(texto: str) -> bool:
    return texto.strip().lower().rstrip(".!") in PEDIDOS_TECLADO

def frases(buffer: str):
    """Corta o texto em frases prontas para o TTS; devolve (frases, resto)."""
    prontas = []
    while (m := re.search(r"(.+?[.!?…])(\s+|$)", buffer)):
        prontas.append(m.group(1).strip()); buffer = buffer[m.end():]
        if not m.group(2):
            break
    return prontas, buffer

def interpretar_chamada(texto: str, modo: str = "nome") -> tuple[str, str]:
    """Devolve (decisao, texto_limpo). decisao ∈ {"chamou", "pediu", "sem_nome"}.

    "Jaime, está aí?"      → ("chamou", "")           só quer saber se ele está
    "Jaime, abre o Finder" → ("pediu", "abre o Finder")
    "abre o Finder"        → ("sem_nome", "abre o Finder")  vale se a janela ativa estiver aberta
    modo "sempre": tudo é "pediu"."""
    t = texto.strip()
    if modo == "sempre":
        return "pediu", NOME_RX.sub("", t, count=1).strip() or t
    if not NOME_RX.search(t):
        return "sem_nome", t
    resto = NOME_RX.sub("", t, count=1).strip()
    # sobra de vocativo antes ou depois do nome: "Ô Jaime", "O jardim está aí" → "está aí"
    resto = re.sub(r"^(o|ô|oi|ei|hey|olá|ola|e aí|eai|alô|alo|fala)\b[,\s]*", "", resto, flags=re.I).strip()
    if not resto or CHAMADA_RX.match(resto.rstrip(".!?…")):
        return "chamou", ""
    return "pediu", resto

class Segmentador:
    """Máquina de estados pura (testável): recebe (probabilidade de voz, frame) e devolve a fala quando termina."""
    def __init__(self, inicio: float = VAD_INICIO, fim: float = VAD_FIM, silencio_ms: int = SILENCIO_MS,
                 min_fala_ms: int = MIN_FALA_MS, max_s: float = MAX_FALA_S, frame_ms: int = FRAME_MS):
        self.inicio, self.fim, self.silencio_ms, self.min_fala_ms, self.max_s, self.frame_ms = inicio, fim, silencio_ms, min_fala_ms, max_s, frame_ms
        self.pre = deque(maxlen=max(1, PRE_ROLL_MS // frame_ms))
        self.gravando = False
        self._chunks: list[bytes] = []
        self._ms_voz = self._ms_silencio = self._ms_total = 0

    def alimentar(self, prob: float, frame: bytes) -> bytes | None:
        if not self.gravando:
            if prob < self.inicio:
                self.pre.append(frame); return None
            self.gravando = True
            self._chunks = list(self.pre); self.pre.clear()
            self._ms_voz = self._ms_silencio = self._ms_total = 0
        self._chunks.append(frame); self._ms_total += self.frame_ms
        if prob >= self.fim:
            self._ms_voz += self.frame_ms; self._ms_silencio = 0
        else:
            self._ms_silencio += self.frame_ms
        if self._ms_silencio >= self.silencio_ms or self._ms_total >= self.max_s * 1000:
            self.gravando = False
            fala = b"".join(self._chunks); self._chunks = []
            return fala if self._ms_voz >= self.min_fala_ms else None
        return None

    def cancelar(self):
        self.gravando = False; self._chunks = []

class VAD:
    """Silero em janela deslizante: probabilidade de voz do frame mais recente."""
    def __init__(self):
        from faster_whisper.vad import get_vad_model
        import numpy as np
        self._np = np
        self._modelo = get_vad_model()
        self._janela: deque = deque(maxlen=JANELA_VAD)

    def prob(self, pcm16) -> float:
        np = self._np
        self._janela.append(pcm16.astype(np.float32) / 32768.0)
        if len(self._janela) < 2:
            return 0.0
        probs = np.asarray(self._modelo(np.concatenate(self._janela), num_samples=FRAME)).ravel()
        return float(probs[-2:].mean())

class Ouvido:
    """Thread do microfone + pipeline assíncrono. `start()` no lifespan do servidor; `stop()` ao sair."""
    def __init__(self, jaime, s: Settings, loop: asyncio.AbstractEventLoop | None = None):
        self.jaime, self.s = jaime, s
        self.loop = loop or asyncio.get_event_loop()
        self.seg = Segmentador()
        self.ativo = True          # False = microfone mudo (botão do HUD)
        self.mudo = False          # True enquanto o Jaime fala (evita eco)
        self.ocupado = False       # True enquanto transcreve/pensa
        self.ativo_ate = 0.0       # janela em que responde sem precisar do nome
        self.observador = None     # jaime/ops/observador.py, ligado pelo servidor
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self._stt = None
        self._tts = None
        self._vad = None
        self.erro = ""

    # ── ciclo de vida ────────────────────────────────────
    def start(self):
        self._thread = threading.Thread(target=self._rodar, name="ouvido", daemon=True)
        self._thread.start()

    def stop(self):
        self._parar.set()

    @property
    def janela_ativa(self) -> bool:
        return time.time() < self.ativo_ate

    def _carregar(self):
        from .stt import STT
        from .tts import TTS
        bus.emitir("voz", estado="carregando", falando=False)
        self._tts = TTS(self.s)
        self._vad = VAD()
        self._stt = STT(self.s)   # Whisper local: baixa o modelo na primeira vez
        # quem fala (resemblyzer/torch): carga de ~1 min no Intel — em segundo plano, o ouvido não espera.
        # JAIME_FALANTES=off desliga (torch no mesmo processo do onnxruntime deu segfault em 15/09; ver falantes_worker)
        self.falantes = None
        import os
        if os.environ.get("JAIME_FALANTES", "off") == "off":
            return
        def carregar_falantes():
            try:
                from .falantes import Falantes
                f = Falantes(); f._encoder(); self.falantes = f
                bus.emitir("voz", estado="ouvindo", falando=False, aviso=f"reconhecimento de voz pronto ({', '.join(f.conhecidos()) or 'nenhuma voz cadastrada'})")
            except Exception as e:
                bus.emitir("voz", estado="ouvindo", falando=False, aviso=f"reconhecimento de voz indisponível: {type(e).__name__}")
        threading.Thread(target=carregar_falantes, name="falantes", daemon=True).start()

    def _rodar(self):
        try:
            import numpy as np, sounddevice as sd
            self._carregar()
        except Exception as e:
            self.erro = f"{type(e).__name__}: {e}"
            bus.emitir("voz", estado="erro", erro=self.erro[:200], falando=False); return
        ultimo_nivel = 0.0
        try:
            with sd.RawInputStream(samplerate=SR, blocksize=FRAME, dtype="int16", channels=1) as mic:
                bus.emitir("voz", estado="ouvindo", falando=False, ativacao=self.s.ativacao, nome=self.s.nome)
                while not self._parar.is_set():
                    frame, _ = mic.read(FRAME)
                    frame = bytes(frame)
                    pcm = np.frombuffer(frame, dtype=np.int16)
                    if not self.ativo or self.mudo or self.ocupado:
                        self.seg.cancelar(); self._vad._janela.clear(); continue
                    prob = self._vad.prob(pcm)
                    agora = time.time()
                    if agora - ultimo_nivel > 0.1:
                        ultimo_nivel = agora
                        rms = float(np.sqrt(np.mean(pcm.astype(np.float32) ** 2)))
                        bus.emitir("escuta", nivel=round(min(1.0, rms / 2500), 3), voz=round(prob, 2),
                                   gravando=self.seg.gravando, janela_ativa=self.janela_ativa)
                    fala = self.seg.alimentar(prob, frame)
                    if fala:
                        self.ocupado = True
                        asyncio.run_coroutine_threadsafe(self._processar(fala), self.loop)
        except Exception as e:
            self.erro = f"{type(e).__name__}: {e}"
            bus.emitir("voz", estado="erro", erro=self.erro[:200], falando=False)

    # ── pipeline ─────────────────────────────────────────
    async def _processar(self, pcm: bytes):
        try:
            bus.emitir("voz", estado="transcrevendo", falando=False)
            texto = (await self._stt.transcrever(pcm, SR)).strip()
            if len(texto) < 3 or LIXO_WHISPER.search(texto):
                return
            # quem falou? (cadastro em andamento consome a fala; senão identifica)
            falante, conf = "", 0.0
            if getattr(self, "falantes", None):
                from .falantes import interpretar as falantes_interpretar
                if (fim := await asyncio.to_thread(self.falantes.alimentar_cadastro, pcm, SR)):
                    bus.emitir("ouvido", texto=texto, ignorado=False); await asyncio.to_thread(self._falar, fim); return
                if self.falantes.cadastrando:
                    n = len(self.falantes.cadastrando[1]); bus.emitir("ouvido", texto=f"(voz {n}/5 guardada) {texto}", ignorado=False); return
                falante, conf = await asyncio.to_thread(self.falantes.identificar, pcm, SR)
                if (cmd := falantes_interpretar(texto)):
                    if cmd[0] == "aprender":
                        await asyncio.to_thread(self._falar, self.falantes.comecar_cadastro(cmd[1])); return
                    resposta = (f"É você, {falante}." if falante and falante != "desconhecido" else
                                "Ainda não conheço essa voz. Diga 'aprende a minha voz' ou 'essa é a voz do Gabriel'.")
                    await asyncio.to_thread(self._falar, resposta); return
                if falante:
                    bus.emitir("falante", nome=falante, confianca=round(conf, 2))
            self.jaime.falante_atual = falante
            decisao, limpo = interpretar_chamada(texto, self.s.ativacao)
            # resposta a uma oferta de ajuda do observador ("sim" / "deixa")
            if self.observador and (oferta := self.observador.responder_oferta(limpo or texto)) is not None:
                bus.emitir("ouvido", texto=texto, ignorado=False)
                if oferta == "":
                    await asyncio.to_thread(self._falar, "Beleza, sigo de olho."); return
                decisao, texto, limpo = "pediu", oferta, oferta
            if decisao == "sem_nome" and not self.janela_ativa and self.jaime.acesso.liberado:
                # ouviu, mas não era com ele — aparece apagado no HUD e vai para o ouvido passivo (consolidado às 22h)
                bus.emitir("ouvido", texto=texto, ignorado=True)
                from ..brain.ouvido_passivo import guardar
                if getattr(self.jaime, "vault", None) is not None:
                    guardar(self.jaime.vault, texto); return
            print(f"🎙 você › {texto}")
            if quer_descansar(limpo or texto):
                # dispensado: volta a responder só quando chamado pelo nome
                self.ativo_ate = 0.0
                bus.emitir("ouvido", texto=texto, ignorado=False); bus.emitir("voz", estado="ouvindo", falando=False, ativo=False)
                await asyncio.to_thread(self._falar, "Certo, João. Estou aqui se precisar."); return
            self.ativo_ate = time.time() + self.s.janela_ativa_s
            if decisao == "chamou":
                # "Jaime, está aí?" liga a conversa até o João dispensar ("encerrado", "pode descansar"…)
                self.ativo_ate = float("inf")
                bus.emitir("ouvido", texto=texto, ignorado=False); bus.emitir("voz", estado="ouvindo", falando=False, ativo=True)
                await asyncio.to_thread(self._falar, "Estou aqui, senhor." if self.jaime.acesso.liberado else "Estou aqui. Palavra-passe, por favor.")
                if self.jaime.acesso.liberado and (aviso := self.jaime.avisos_do_dia()):
                    await asyncio.to_thread(self._falar, aviso)
                if getattr(self.jaime, "aguardando_nome", False):
                    await asyncio.to_thread(self._falar, f"Meu nome é {self.jaime.identidade.nome} — confirma?")
                return
            # trancado: a palavra-passe pode vir sem o nome
            texto = limpo if decisao == "pediu" else texto
            if quer_teclado(texto):
                bus.emitir("teclado", aberto=True, motivo="você pediu")
                await asyncio.to_thread(self._falar, "Pode escrever."); return
            bus.emitir("voz", estado="pensando", falando=False)
            buffer = ""
            contexto = self.observador.contexto() if self.observador else ""
            if falante and falante != "João":
                contexto = (contexto + "; " if contexto else "") + f"falante={falante}"
            # narrador: em tarefas longas ele diz o que está fazendo ("lendo os arquivos…"), como o Jarvis
            from .narrador import Narrador
            narrador = Narrador(self._enfileirar); narrador.comecar()
            fila_eventos = bus.assinar()
            async def narrar():
                try:
                    while True:
                        ev = await fila_eventos.get()
                        if ev.get("tipo") in ("producao", "raciocinio") and ev.get("ferramenta") and not primeira.is_set():
                            usou_ferramenta.set()
                            narrador.evento(ev["ferramenta"], ev.get("alvo", ""))
                except asyncio.CancelledError:
                    pass
            tarefa_narrar = asyncio.create_task(narrar())
            # "deixa eu ver…" só quando ele está de fato TRABALHANDO (usou ferramenta) e a resposta ainda não veio
            # depois de MULETA_S — conversa curta responde direto, sem muleta
            primeira = asyncio.Event(); usou_ferramenta = asyncio.Event()
            async def muleta():
                try:
                    await asyncio.wait_for(usou_ferramenta.wait(), MULETA_S)
                except asyncio.TimeoutError:
                    return
                await asyncio.sleep(max(0.0, MULETA_S - 1.0))
                if not primeira.is_set():
                    self._enfileirar(random.choice(MULETAS))
            asyncio.create_task(muleta())
            # Cada frase entra na fila do TTS assim que fica pronta, sem bloquear: o sintetizador
            # prepara a próxima enquanto a atual toca, e a resposta sai emendada em vez de picotada.
            async for trecho in self.jaime.ask_stream(texto, canal="voice", contexto=contexto):
                buffer += trecho
                prontas, buffer = frases(buffer)
                for f in prontas:
                    primeira.set(); self._enfileirar(f)
            if buffer.strip():
                self._enfileirar(buffer)
            narrador.parar(); tarefa_narrar.cancel(); bus.cancelar(fila_eventos)
            await asyncio.to_thread(self._aguardar_fala)
            self.ativo_ate = time.time() + self.s.janela_ativa_s
        except Exception as e:
            bus.emitir("voz", estado="erro", erro=f"{type(e).__name__}: {e}"[:200], falando=False)
        finally:
            self.ocupado = False
            bus.emitir("voz", estado="ouvindo", falando=False)

    def _enfileirar(self, texto: str):
        """Manda a frase para a fila do TTS e cala o microfone; quem espera é `_aguardar_fala`."""
        if not self._tts:
            return
        humor = getattr(self.jaime, "humor", None)
        if humor is not None:
            from ..emocao.prosodia import prosodia
            p = prosodia(humor, "voice")
            self._tts.ajustes = p["eleven"]          # ElevenLabs: estabilidade/estilo
            self._tts.instrucoes = p["instructions"]  # OpenAI: instrução de estilo
        self.mudo = True
        self._tts.enfileirar(texto)

    def _aguardar_fala(self):
        """Espera a fila de fala esvaziar; volta a ouvir 250 ms depois (cauda do alto-falante)."""
        try:
            if self._tts:
                self._tts.aguardar()
        finally:
            time.sleep(0.25); self.mudo = False

    def _falar(self, texto: str):
        """Microfone mudo enquanto fala; volta a ouvir 250 ms depois (cauda do alto-falante)."""
        self.mudo = True
        try:
            self._tts.falar(texto)
        finally:
            time.sleep(0.25); self.mudo = False

    def falar(self, texto: str):
        """Para o servidor falar algo fora de um turno (apresentação, avisos)."""
        if self._tts:
            self._falar(texto)
