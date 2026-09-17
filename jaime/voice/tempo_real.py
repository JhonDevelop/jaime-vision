"""Modo conversa — OpenAI Realtime (gpt-realtime-2) fala-para-fala, com as mãos do Jaime como ferramenta.

Ver docs/FASE-3.md § Etapa 1. Ligado com `JAIME_VOZ_MODO=conversa` (o padrão `pipeline` usa Deepgram + Opus + TTS).
As partes puras (gate "é comigo?", tratamento de eventos, ferramentas) são testáveis com um WebSocket falso."""
from __future__ import annotations
from .idiomas import IDIOMA_REALTIME
import asyncio, base64, json, queue, threading, time
from ..hud.events import bus
from .escuta import interpretar_chamada, quer_teclado, quer_descansar, LIXO_WHISPER

SR = 24000
BLOCO = 480                      # 20 ms
BLOCO_VAD = 768                  # 32 ms a 24 kHz = 512 amostras a 16 kHz (janela do Silero)
CAUDA_S = 0.5                    # microfone volta a ouvir 500 ms depois do último áudio dele
URL = "wss://api.openai.com/v1/realtime?model={modelo}"

FERRAMENTAS = [
    {"type": "function", "name": "jaime", "description": "Delega ao Jaime completo (memória no vault, mãos no computador, browser, e-mail, agenda, projetos, "
                                                          "imagens). Use para QUALQUER pedido que exija agir, lembrar ou consultar. Passe o pedido do João como está.",
     "parameters": {"type": "object", "properties": {"texto": {"type": "string"}}, "required": ["texto"]}},
    {"type": "function", "name": "hora", "description": "Data e hora atuais.", "parameters": {"type": "object", "properties": {}}},
    {"type": "function", "name": "clima", "description": "Clima agora e previsão do dia.", "parameters": {"type": "object", "properties": {"amanha": {"type": "boolean"}}}},
    {"type": "function", "name": "lembrete", "description": "Cria um lembrete: quando ('em 20 min', 'às 15h', 'amanhã às 9') e o quê.",
     "parameters": {"type": "object", "properties": {"quando": {"type": "string"}, "o_que": {"type": "string"}}, "required": ["quando", "o_que"]}},
]

def instrucoes(nome: str, prosodia: str = "") -> str:
    return (f"Você é {nome}, assistente pessoal e operacional do João (Franca/SP). Fale português do Brasil, frases curtas, "
            f"seco e leal, sem 'como posso ajudar', sem se apresentar. Chame-o de João ou de senhor. Nunca invente o que não sabe: "
            f"para agir, lembrar ou consultar qualquer coisa use a ferramenta `jaime`; para hora/clima/lembrete use as ferramentas próprias. "
            f"Quando a ferramenta devolver texto, diga-o com naturalidade em até 3 frases. {prosodia}").strip()

class Gate:
    """Decide se uma transcrição é com ele (mesma regra da fase 2) e mantém a janela ativa."""
    def __init__(self, modo: str = "nome", janela_s: int = 25):
        self.modo, self.janela_s, self.ativo_ate = modo, janela_s, 0.0

    def avaliar(self, texto: str, liberado: bool) -> tuple[bool, str]:
        """(responder?, texto para o modelo). Trancado: tudo vai ao Jaime (palavra-passe)."""
        if not texto or len(texto.strip()) < 3 or LIXO_WHISPER.search(texto):
            return False, ""
        if not liberado:
            return True, texto
        decisao, limpo = interpretar_chamada(texto, self.modo)
        if decisao == "sem_nome" and time.time() >= self.ativo_ate:
            return False, ""
        if quer_descansar(limpo or texto):
            self.ativo_ate = 0.0
            return True, "__descansar__"
        self.ativo_ate = float("inf") if decisao == "chamou" else max(self.ativo_ate, time.time() + self.janela_s)
        return True, (limpo if decisao == "pediu" else texto)

class Conversa:
    def __init__(self, jaime, s, loop: asyncio.AbstractEventLoop, observador=None, ws_factory=None):
        self.jaime, self.s, self.loop, self.observador = jaime, s, loop, observador
        self.gate = Gate(s.ativacao, s.janela_ativa_s)
        self.ws_factory = ws_factory          # injetável (teste)
        self.ws = None
        self.ativo = True
        self.mudo = False
        self.ocupado = False
        self._ultimo_audio = 0.0
        self._mic: queue.Queue = queue.Queue(maxsize=200)
        self._saida: queue.Queue = queue.Queue()
        self._parar = threading.Event()
        self.erro = ""
        self._fala_atual = ""

    # ── ciclo de vida ────────────────────────────────
    def start(self):
        threading.Thread(target=self._thread_mic, name="mic-rt", daemon=True).start()
        threading.Thread(target=self._thread_saida, name="som-rt", daemon=True).start()
        self.loop.create_task(self.rodar())

    def stop(self):
        self._parar.set()

    def falar(self, texto: str):
        """Fala fora de um turno (apresentação): pede ao Realtime que diga exatamente o texto."""
        if self.ws:
            asyncio.run_coroutine_threadsafe(self._dizer(texto), self.loop)

    # ── áudio ────────────────────────────────────────
    def _thread_mic(self):
        """Só manda áudio para o Realtime quando o Silero (local, grátis) diz que há voz humana — com pré-roll e cauda.
        Sem isso o microfone aberto o dia inteiro seria cobrado como entrada de áudio (~US$ 3,6/h parado)."""
        try:
            import numpy as np, sounddevice as sd
            from collections import deque
            from .escuta import VAD, VAD_INICIO, VAD_FIM
            vad = VAD(); pre = deque(maxlen=8); falando = False; cauda = 0.0
            with sd.RawInputStream(samplerate=SR, blocksize=BLOCO_VAD, dtype="int16", channels=1) as mic:
                while not self._parar.is_set():
                    frame, _ = mic.read(BLOCO_VAD)
                    frame = bytes(frame)
                    if not (self.ativo and not self.mudo and not self.ocupado):
                        vad._janela.clear(); pre.clear(); falando = False; continue
                    pcm24 = np.frombuffer(frame, dtype=np.int16)
                    pcm16 = np.interp(np.arange(512) * (len(pcm24) / 512), np.arange(len(pcm24)), pcm24).astype(np.int16)
                    prob = vad.prob(pcm16)
                    if prob >= VAD_INICIO:
                        falando = True; cauda = time.time() + 0.8
                    elif falando and prob < VAD_FIM and time.time() > cauda:
                        falando = False
                    if falando:
                        for f in pre: self._enfileirar_mic(f)
                        pre.clear(); self._enfileirar_mic(frame)
                    else:
                        pre.append(frame)
        except Exception as e:
            self.erro = f"{type(e).__name__}: {e}"; bus.emitir("voz", estado="erro", erro=self.erro[:200], falando=False)

    def _enfileirar_mic(self, frame: bytes):
        try: self._mic.put_nowait(frame)
        except queue.Full: pass

    def _thread_saida(self):
        try:
            import sounddevice as sd
            with sd.RawOutputStream(samplerate=SR, channels=1, dtype="int16", blocksize=0, latency="high") as out:
                buf = bytearray()
                while not self._parar.is_set():
                    try:
                        pcm = self._saida.get(timeout=0.2)
                    except queue.Empty:
                        if buf:                                   # fim da resposta: toca o que sobrou
                            out.write(bytes(buf)); buf.clear()
                        if self.mudo and self._saida.empty() and time.time() - self._ultimo_audio > CAUDA_S:
                            self.mudo = False; bus.emitir("voz", falando=False, estado="ouvindo")
                        continue
                    self.mudo = True; self._ultimo_audio = time.time()
                    buf += pcm
                    # junta ~0,25 s antes de escrever: a rede solta o áudio em rajadas e a placa não pode ficar sem dado
                    if len(buf) >= SR * 2 // 4:
                        out.write(bytes(buf)); buf.clear()
        except Exception as e:
            self.erro = f"{type(e).__name__}: {e}"

    # ── websocket ────────────────────────────────────
    async def _conectar(self):
        if self.ws_factory:
            return await self.ws_factory()
        import websockets
        return await websockets.connect(URL.format(modelo=self.s.realtime_model),
                                        additional_headers={"Authorization": f"Bearer {self.s.openai_key}"}, max_size=None)

    async def _enviar(self, ev: dict):
        await self.ws.send(json.dumps(ev))

    def _sessao(self) -> dict:
        pros = ""
        try:
            from ..emocao.prosodia import prosodia
            pros = prosodia(self.jaime.humor, "voice")["instructions"]
        except Exception:
            pass
        return {"type": "session.update", "session": {
            "type": "realtime", "instructions": instrucoes(self.jaime.identidade.nome, pros), "tools": FERRAMENTAS,
            "audio": {"input": {"format": {"type": "audio/pcm", "rate": SR}, "turn_detection": {"type": "server_vad", "create_response": False, "interrupt_response": False, "silence_duration_ms": 700, "prefix_padding_ms": 300},
                                "transcription": {"model": "gpt-4o-mini-transcribe", "language": IDIOMA_REALTIME}},
                      "output": {"format": {"type": "audio/pcm", "rate": SR}, "voice": self.s.realtime_voz}}}}

    async def rodar(self):
        while not self._parar.is_set():
            try:
                self.ws = await self._conectar()
                await self._enviar(self._sessao())
                bus.emitir("voz", estado="ouvindo", falando=False, ativacao=self.s.ativacao, nome=self.jaime.identidade.nome, modo="conversa")
                bombeia = asyncio.create_task(self._bombear_mic())
                try:
                    async for raw in self.ws:
                        await self.tratar(json.loads(raw))
                finally:
                    bombeia.cancel()
            except asyncio.CancelledError:
                return
            except Exception as e:
                self.erro = f"{type(e).__name__}: {e}"
                bus.emitir("voz", estado="erro", erro=self.erro[:200], falando=False)
                await asyncio.sleep(5)

    async def _bombear_mic(self):
        ultimo = 0.0
        while True:
            try:
                frame = self._mic.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.01); continue
            await self._enviar({"type": "input_audio_buffer.append", "audio": base64.b64encode(frame).decode()})
            if time.time() - ultimo > 0.1:
                ultimo = time.time()
                import numpy as np
                rms = float(np.sqrt(np.mean(np.frombuffer(frame, dtype=np.int16).astype(np.float32) ** 2)))
                bus.emitir("escuta", nivel=round(min(1.0, rms / 2500), 3), voz=0.0, gravando=False, janela_ativa=time.time() < self.gate.ativo_ate)

    # ── eventos ──────────────────────────────────────
    async def tratar(self, ev: dict):
        t = ev.get("type", "")
        if t == "response.created":
            # mudo já na criação da resposta (antes do 1º áudio): o eco do começo não vira "fala do João"
            self.mudo = True; self._ultimo_audio = time.time() + 2.0
            await self._enviar({"type": "input_audio_buffer.clear"})
        elif t == "response.done":
            self._ultimo_audio = time.time()          # a cauda conta a partir do fim da resposta
        elif t == "input_audio_buffer.speech_started":
            bus.emitir("escuta", nivel=0.5, voz=0.9, gravando=True, janela_ativa=time.time() < self.gate.ativo_ate)
        elif t == "conversation.item.input_audio_transcription.completed":
            await self._transcricao(ev.get("transcript", ""))
        elif t == "response.output_audio.delta":
            self._saida.put(base64.b64decode(ev["delta"]))
        elif t == "response.output_audio_transcript.delta":
            if not self._fala_atual:
                bus.emitir("voz", falando=True, estado="falando")
            self._fala_atual += ev.get("delta", ""); bus.emitir("fala", texto=ev.get("delta", ""))
        elif t == "response.output_audio_transcript.done":
            bus.emitir("fala_fim"); self._fala_atual = ""
        elif t == "response.function_call_arguments.done":
            await self._ferramenta(ev.get("name", ""), ev.get("arguments", "{}"), ev.get("call_id", ""))
        elif t == "error":
            bus.emitir("voz", estado="erro", erro=json.dumps(ev.get("error"))[:200], falando=False)

    async def _transcricao(self, texto: str):
        texto = (texto or "").strip()
        liberado = self.jaime.acesso.liberado
        responder, limpo = self.gate.avaliar(texto, liberado)
        if not responder:
            if texto and liberado:
                bus.emitir("ouvido", texto=texto, ignorado=True)
                from ..brain.ouvido_passivo import guardar
                if getattr(self.jaime, "vault", None) is not None:
                    guardar(self.jaime.vault, texto)
            return
        chamou = self.gate.ativo_ate == float("inf") and (limpo == texto)
        from ..maos.gravador import interpretar as gravador_interpretar
        from .escuta import interpretar_chamada
        if liberado and (gravador_interpretar(limpo) or interpretar_chamada(texto, self.gate.modo)[0] == "chamou"):
            # gravador de processos, "para" e "está aí" passam pelo Jaime (sem modelo) e o Realtime só repete
            r = await self.jaime.ask(limpo or texto, canal="voice")
            await self._dizer(r)
            if interpretar_chamada(texto, self.gate.modo)[0] == "chamou" and (aviso := self.jaime.avisos_do_dia()):
                await self._dizer(aviso)
            return
        print(f"🎙 você › {texto}")
        bus.emitir("ouvido", texto=texto, ignorado=False)
        if limpo == "__descansar__":
            bus.emitir("voz", estado="ouvindo", falando=False, ativo=False)
            await self._dizer("Certo, João. Estou aqui se precisar."); return
        bus.emitir("voz", estado="ouvindo", falando=False, ativo=self.gate.ativo_ate == float("inf"))
        if not liberado or quer_teclado(limpo):
            # palavra-passe, tranca, teclado, renomear: o Jaime decide sem modelo e o Realtime só repete
            r = await self.jaime.ask(limpo or texto, canal="voice")
            await self._dizer(r); return
        await self._enviar({"type": "response.create"})

    async def _dizer(self, texto: str):
        await self._enviar({"type": "response.create", "response": {"instructions": f"Diga exatamente, sem acrescentar nada: {texto}"}})

    async def _ferramenta(self, nome: str, args_json: str, call_id: str):
        try:
            args = json.loads(args_json or "{}")
        except json.JSONDecodeError:
            args = {}
        self.ocupado = True
        bus.emitir("voz", estado="pensando", falando=False)
        try:
            if nome == "jaime":
                contexto = self.observador.contexto() if self.observador else ""
                saida = await self.jaime.ask(str(args.get("texto", "")), canal="voice", contexto=contexto)
            elif nome == "hora":
                from ..agenda import relogio
                dt = relogio.agora(); saida = f"{relogio.texto_data(dt)}, {relogio.texto_hora(dt)}"
            elif nome == "clima":
                from ..agenda import clima
                saida = await clima.responder("amanhã" if args.get("amanha") else "hoje", self.s.lat, self.s.lon)
            elif nome == "lembrete":
                saida = await self.jaime._mundo(f"me lembra {args.get('quando', '')} de {args.get('o_que', '')}") or "não entendi o horário"
            else:
                saida = f"ferramenta desconhecida: {nome}"
        except Exception as e:
            saida = f"falhou: {type(e).__name__}: {str(e)[:120]}"
        finally:
            self.ocupado = False
        await self._enviar({"type": "conversation.item.create", "item": {"type": "function_call_output", "call_id": call_id, "output": str(saida)[:6000]}})
        await self._enviar({"type": "response.create"})
