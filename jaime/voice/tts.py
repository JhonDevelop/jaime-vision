"""Fala: ElevenLabs/OpenAI → PCM → placa de som. Feito para não engasgar — e para calar em < 100 ms.

Por que é assim (medido nesta máquina, 14/09/2026):
- A ElevenLabs não entrega o áudio em fluxo contínuo: espera ~0,3 s e despeja a frase inteira em
  ~0,2 s. Tocar "em streaming" não ganhava nada e ainda deixava a placa de som sem dado — era daí
  que vinha a voz picotada. Agora a frase é sintetizada inteira em memória e só então tocada.
- O que realmente travava a conversa eram as pausas ENTRE frases: cada uma abria uma requisição nova
  e o João ouvia ~0,5 s de silêncio a cada ponto final. Agora um sintetizador vai na frente,
  preparando as próximas frases enquanto a atual toca — a fala sai emendada.
- A saída é UM stream de saída aberto para a resposta inteira, com escrita em blocos de ~100 ms:
  assim `parar()` (barge-in) corta no meio da frase em < 100 ms. `afplay` fica de reserva.
- O PCM é reamostrado aqui para a taxa nativa do aparelho (24 kHz → 44,1 kHz), em vez de deixar a
  conversão para o PortAudio — é de lá que vinham os estalos.

Fase 3 (docs/FASE-3-TEMPO-REAL.md): `pre_sintetizar()` prepara a 1ª frase enquanto o João ainda fala,
`tocar_pronto()` toca esse cache em ~0 ms, `parar()` mata tudo (barge-in), `velocidade` 1.15× por padrão
(JAIME_VOZ_VELOCIDADE) e `t_inicio_audio` marca quando a resposta começou a soar (métrica de latência).

Ordem de tentativa: ElevenLabs → OpenAI gpt-4o-mini-tts → `say` do macOS em pt-BR → texto no terminal. Nunca fica mudo.
`voz: falando=true` sai quando a primeira frase começa e só volta a false quando a fila esvazia."""
from __future__ import annotations
import os, queue, re, shutil, subprocess, tempfile, threading, time, wave
from ..config import Settings
from ..hud.events import bus
from .cache_frases import CacheFrases

PCM_SR = 24000                       # pcm_24000 existe no plano gratuito (44100 é só Pro)
VOZ_PADRAO = "JBFqnCBsd6RMkjVDRZzb"  # premade (George) — fala pt-BR com sotaque; troque em ELEVENLABS_VOICE_ID
ADIANTAR = 2                         # quantas frases o sintetizador prepara à frente da que está tocando
BLOCO_S = 0.05                       # escrita na placa em blocos de 50 ms: é o tempo máximo que parar() espera para calar

def limpar_para_fala(texto: str) -> str:
    """O modelo às vezes manda markdown mesmo por voz; o TTS leria os símbolos. Tira tudo que não se fala."""
    t = re.sub(r"```.*?```", " ", texto, flags=re.S)          # blocos de código
    t = re.sub(r"`([^`]*)`", r"\1", t)                        # `código` → código
    t = re.sub(r"https?://\S+", "link", t)                     # URLs não se leem
    t = re.sub(r"^\s*(#{1,6}\s*|[-*•]\s+|\d+[.)]\s+)", "", t, flags=re.M)   # títulos e marcadores de lista
    t = re.sub(r"[*_~#>|]+", "", t)                             # ênfases, tabelas, citações
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)             # [texto](url) → texto
    t = re.sub(r"\s*\n+\s*", ". ", t)                          # quebra de linha vira pausa
    t = re.sub(r"\.\s*\.", ".", t)
    return re.sub(r"[ \t]{2,}", " ", t).strip()

class TTS:
    def __init__(self, s: Settings, ao_tocar=None):
        self.s = s
        self._client = None
        self._falhas = 0
        self._ultima_falha = 0.0
        self._afplay = shutil.which("afplay")
        self._stream = None          # stream de saída, aberto enquanto durar a resposta
        self._taxa = PCM_SR          # taxa nativa do aparelho, descoberta ao abrir
        self._anterior = ""          # última frase sintetizada (previous_text da ElevenLabs)
        self.ajustes: dict | None = None   # {"stability", "style"} vindos da prosódia (humor); None = .env
        self.instrucoes: str = ""          # instrução de estilo (prosódia) para o gpt-4o-mini-tts
        self.motor = os.environ.get("JAIME_TTS", "auto")   # elevenlabs | openai | auto
        self.velocidade = float(os.environ.get("JAIME_VOZ_VELOCIDADE", "1.15"))
        self.t_inicio_audio = 0.0    # quando a resposta atual começou a soar (0 = ainda não)
        self.t_fim_audio = 0.0
        self.interrompida = False    # a última fala foi cortada por parar()
        self._openai = None
        # Recebe PCM mono int16 a 24 kHz imediatamente antes de cada bloco ir
        # para a placa. É opcional para não alterar os chamadores existentes.
        self.ao_tocar = ao_tocar
        self._cache_frases = CacheFrases(motor=self.motor, voz=self._voz_cache(), velocidade=self.velocidade,
                                         instrucoes=self.instrucoes)
        if s.openai_key:
            from openai import OpenAI
            self._openai = OpenAI(api_key=s.openai_key)
        if s.elevenlabs_key:
            from elevenlabs.client import ElevenLabs
            self._client = ElevenLabs(api_key=s.elevenlabs_key)
        # pipeline: enfileirar() → [sintetizador] → _prontos → [reprodutor] → placa de som
        self._pedidos: queue.Queue = queue.Queue()
        self._prontos: queue.Queue = queue.Queue(maxsize=ADIANTAR)
        self._pendentes = 0
        self._cond = threading.Condition()
        self._geracao = 0            # parar() avança a geração: itens antigos são descartados
        self._parando = threading.Event()
        # O PortAudio não aguenta abort()/close() numa thread enquanto write() roda em outra (segfault em
        # PaUtil_WriteRingBuffer, 15/09 14:06). Todo acesso ao stream passa por este lock, bloco a bloco.
        self._lock_stream = threading.RLock()
        threading.Thread(target=self._sintetizador, daemon=True).start()
        threading.Thread(target=self._reprodutor, daemon=True).start()

    # ── API ───────────────────────────────────────────────
    def _preparar(self, texto: str) -> str:
        from .persona import aplicar as persona
        return persona(limpar_para_fala(texto))

    def _voz_cache(self) -> str:
        """Inclui as duas vozes possíveis quando o motor automático escolhe o provedor."""
        eleven = getattr(self.s, "elevenlabs_voice", "") or VOZ_PADRAO
        openai = os.environ.get("JAIME_OPENAI_VOZ", "onyx")
        return openai if self.motor == "openai" else (eleven if self.motor == "elevenlabs" else f"{eleven}|{openai}")

    def _cache_atualizar(self) -> None:
        self._cache_frases.configurar(motor=self.motor, voz=self._voz_cache(), velocidade=self.velocidade,
                                      instrucoes=self.instrucoes)

    def _sintetizar_com_cache(self, texto: str, *, guardar_anterior: bool = True, streaming: bool = False):
        self._cache_atualizar()
        if pcm := self._cache_frases.get(texto):
            return pcm
        pcm = self._sintetizar(texto, guardar_anterior=guardar_anterior, streaming=streaming)
        if pcm is None:
            return None
        if not streaming or isinstance(pcm, (bytes, bytearray)):
            self._cache_frases.put(texto, pcm)
            return pcm
        return self._acumular_para_cache(texto, pcm)

    def _acumular_para_cache(self, texto: str, blocos):
        """Grava depois do último bloco em thread própria: a placa nunca espera o disco."""
        def fluxo():
            pcm = bytearray()
            for bloco in blocos:
                pcm += bloco
                yield bloco
            if pcm:
                threading.Thread(target=self._cache_frases.put, args=(texto, bytes(pcm)), daemon=True).start()
        return fluxo()

    def enfileirar(self, texto: str) -> None:
        """Manda falar sem esperar. Use durante a resposta em fluxo: cada frase entra assim que fica
        pronta e o sintetizador já vai preparando a seguinte."""
        texto = self._preparar(texto)
        if not texto:
            return
        with self._cond:
            if self._pendentes == 0:
                self.t_inicio_audio = 0.0; self.interrompida = False
                bus.emitir("voz", falando=True, estado="falando", texto=texto)
            self._pendentes += 1
            g = self._geracao
        self._pedidos.put((g, texto))

    def pre_sintetizar(self, texto: str) -> bytes | None:
        """Sintetiza AGORA, sem tocar (rascunho do antecipador). Devolve o PCM ou None se nenhum motor respondeu."""
        texto = self._preparar(texto)
        if not texto:
            return None
        return self._sintetizar_com_cache(texto, guardar_anterior=False)

    def tocar_pronto(self, texto: str, pcm: bytes | None) -> None:
        """Toca um áudio já sintetizado (cache do antecipador) na frente de tudo."""
        texto = self._preparar(texto) or texto
        with self._cond:
            if self._pendentes == 0:
                self.t_inicio_audio = 0.0; self.interrompida = False
                bus.emitir("voz", falando=True, estado="falando", texto=texto)
            self._pendentes += 1
            g = self._geracao
        self._anterior = texto
        self._prontos.put((g, texto, pcm if pcm else None))

    def parar(self) -> int:
        """Barge-in: cala em < 100 ms. Esvazia as filas, corta o bloco em curso e fecha o aparelho.
        Devolve quantas frases ficaram por dizer."""
        with self._cond:
            self._geracao += 1
            restantes = self._pendentes
            self._parando.set()
            for q in (self._pedidos, self._prontos):
                while True:
                    try: q.get_nowait()
                    except queue.Empty: break
            self._pendentes = 0
            self.interrompida = restantes > 0
            self._cond.notify_all()
        self._fechar_stream()
        self._parando.clear()
        self._anterior = ""
        if restantes:
            bus.emitir("voz", falando=False, estado="ouvindo", interrompida=True)
        return restantes

    def aguardar(self, timeout: float = 300) -> None:
        """Bloqueia até a fila esvaziar."""
        with self._cond:
            self._cond.wait_for(lambda: self._pendentes == 0, timeout=timeout)

    def falar(self, texto: str) -> None:
        """Fala uma coisa só e espera terminar (apresentação, avisos)."""
        self.enfileirar(texto)
        self.aguardar()

    @property
    def ocupado(self) -> bool:
        with self._cond:
            return self._pendentes > 0

    # ── pipeline ──────────────────────────────────────────
    def _sintetizar(self, texto: str, guardar_anterior: bool = True, streaming: bool = False):
        """PCM inteiro (bytes) ou, com `streaming`, um iterador de blocos que já vem com o 1º bloco baixado —
        o reprodutor começa a tocar no primeiro byte em vez de esperar a frase inteira (medido 15/09: 0,5–1,4 s
        até o 1º byte contra 1,3–2,4 s pela frase toda no gpt-4o-mini-tts)."""
        pcm = None
        # 3 falhas seguidas desligam a ElevenLabs por 10 min (cota, rede); depois tenta de novo sozinho
        if self._falhas >= 3 and time.time() - self._ultima_falha > 600:
            self._falhas = 0
        usar_eleven = self._client and self._falhas < 3 and self.motor in ("auto", "elevenlabs")
        if usar_eleven:
            try:
                pcm = self._elevenlabs(texto, guardar_anterior, streaming)
                self._falhas = 0
            except Exception as e:
                self._falhas += 1; self._ultima_falha = time.time()
                print(f"⚠ ElevenLabs falhou ({type(e).__name__}: {str(e)[:80]}); tentando OpenAI/voz local")
        if pcm is None and self._openai and self.motor in ("auto", "openai"):
            try:
                pcm = self._openai_tts(texto, streaming)
            except Exception as e:
                print(f"⚠ OpenAI TTS falhou ({type(e).__name__}: {str(e)[:80]}); usando a voz local")
        return pcm

    @staticmethod
    def _primeiro_e_resto(blocos):
        """Puxa o 1º bloco agora (absorve a latência de rede à frente) e devolve um iterador com ele + o resto."""
        import itertools
        it = iter(blocos)
        primeiro = next(it, None)
        if not primeiro:
            return None
        return itertools.chain([primeiro], it)

    def medir_primeiro_byte(self, texto: str) -> float | None:
        """Segundos até o 1º bloco de áudio da frase (o que o João espera quando não há cache)."""
        texto = self._preparar(texto)
        if not texto:
            return None
        ini = time.time()
        r = self._sintetizar(texto, guardar_anterior=False, streaming=True)
        if r is None:
            return None
        t = time.time() - ini
        for _ in r:                     # esgota (fecha a conexão) sem tocar
            pass
        return t

    def _sintetizador(self) -> None:
        """Vai na frente: busca o áudio da próxima frase enquanto a atual ainda toca."""
        while True:
            g, texto = self._pedidos.get()
            if g != self._geracao:
                continue                        # parar() passou por aqui: frase descartada
            pcm = self._sintetizar_com_cache(texto, streaming=True)
            if g != self._geracao:
                continue
            self._prontos.put((g, texto, pcm))

    def _reprodutor(self) -> None:
        while True:
            g, texto, pcm = self._prontos.get()
            if g != self._geracao:
                continue
            try:
                if pcm is not None:
                    self._tocar(pcm, g)
                elif not self._say_nativo(texto):
                    print(f"🔈 {texto}")
            except Exception as e:
                print(f"⚠ áudio falhou ({type(e).__name__}); {texto}")
            finally:
                with self._cond:
                    if g == self._geracao and self._pendentes > 0:
                        self._pendentes -= 1
                    vazio = self._pendentes == 0
                    self._cond.notify_all()
                if vazio and g == self._geracao:
                    self.t_fim_audio = time.time()
                    self._fechar_stream()   # libera o aparelho entre uma resposta e outra
                    bus.emitir("voz", falando=False, estado="ouvindo")

    # ── saídas ────────────────────────────────────────────
    def _elevenlabs(self, texto: str, guardar_anterior: bool = True, streaming: bool = False):
        from elevenlabs import VoiceSettings
        # Emoção: estabilidade baixa e "style" alto deixam a voz seguir a pontuação — exclamação sobe,
        # reticências hesitam, pergunta entoa. O prompt do Jaime escreve pensando nisso quando fala.
        a = self.ajustes or {}
        kw = dict(stability=float(a.get("stability", os.environ.get("JAIME_VOZ_ESTABILIDADE", "0.5"))),
                  similarity_boost=0.8,
                  style=float(a.get("style", os.environ.get("JAIME_VOZ_ESTILO", "0.3"))),
                  use_speaker_boost=True)
        try:
            ajustes = VoiceSettings(speed=self.velocidade, **kw)
        except TypeError:                       # SDK antigo sem `speed`
            ajustes = VoiceSettings(**kw)
        fluxo = self._client.text_to_speech.stream(
            text=texto, voice_id=self.s.elevenlabs_voice or VOZ_PADRAO,
            model_id=os.environ.get("JAIME_TTS_MODELO", "eleven_flash_v2_5"),   # flash: menor latência
            output_format=f"pcm_{PCM_SR}", voice_settings=ajustes,
            optimize_streaming_latency=3,   # ~0,1 s a menos até o primeiro byte
            previous_text=self._anterior[-300:] or None,   # continuidade de entonação entre frases
        )
        if guardar_anterior:
            self._anterior = texto
        if streaming:
            return self._primeiro_e_resto(c for c in fluxo if c)
        return b"".join(c for c in fluxo if c)

    def _openai_kw(self, texto: str) -> dict:
        base = os.environ.get("JAIME_VOZ_ESTILO_BASE",
                              "Voz masculina grave e calma, dicção precisa, sotaque brasileiro neutro, tom seco e educado, "
                              "leve textura de assistente de inteligência artificial — um mordomo britânico falando português.")
        return dict(model=os.environ.get("JAIME_OPENAI_TTS_MODELO", "gpt-4o-mini-tts"), voice=os.environ.get("JAIME_OPENAI_VOZ", "onyx"),
                    input=texto, instructions=(base + " " + self.instrucoes).strip(), response_format="pcm", speed=self.velocidade)

    def _openai_blocos(self, texto: str):
        """Blocos de ~100 ms conforme chegam da rede; para no barge-in."""
        with self._openai.audio.speech.with_streaming_response.create(**self._openai_kw(texto)) as resp:
            for ch in resp.iter_bytes(PCM_SR * 2 // 10):
                if self._parando.is_set():
                    return
                yield ch

    def _openai_tts(self, texto: str, streaming: bool = False):
        """gpt-4o-mini-tts: voz masculina (JAIME_OPENAI_VOZ, padrão onyx) + instrução de estilo vinda da prosódia.
        PCM 24 kHz, a mesma taxa da ElevenLabs — cai no mesmo reprodutor."""
        if streaming:
            return self._primeiro_e_resto(self._openai_blocos(texto))
        with self._openai.audio.speech.with_streaming_response.create(**self._openai_kw(texto)) as resp:
            return b"".join(resp.iter_bytes())

    def _tocar(self, pcm, g: int | None = None) -> None:
        """`pcm`: bytes inteiros ou iterador de blocos (streaming). Escreve em blocos de ~50 ms; `parar()` corta no próximo.
        `g` é a geração da frase: se `parar()` avançou a geração, o resto é descartado mesmo que `_parando` já tenha baixado."""
        if isinstance(pcm, (bytes, bytearray)):
            blocos = [bytes(pcm)]
        else:
            blocos = pcm
        if g is None:
            g = self._geracao
        cortada = lambda: self._parando.is_set() or g != self._geracao
        tocado = bytearray()
        try:
            bloco = int(self._taxa * BLOCO_S) * 2          # bytes por bloco (int16 mono)
            bloco_pcm = int(PCM_SR * BLOCO_S) * 2
            for trecho in blocos:
                if cortada():
                    return                                  # barge-in: cala no próximo bloco
                for inicio in range(0, len(trecho), bloco_pcm):
                    if cortada():
                        return
                    pcm_24k = bytes(trecho[inicio:inicio + bloco_pcm])
                    if self.ao_tocar:
                        try:
                            self.ao_tocar(pcm_24k)          # referência para o supressor de eco (voice/eco.py)
                        except Exception:
                            pass                            # observador não pode derrubar a reprodução
                    dados = self._na_taxa_do_aparelho(pcm_24k)
                    tocado += pcm_24k
                    for i in range(0, len(dados), bloco):
                        # Abrir e escrever sob o mesmo lock: parar() nunca fecha o aparelho no meio de um write(),
                        # e uma frase antiga nunca reabre o aparelho depois de parar().
                        with self._lock_stream:
                            if cortada():
                                return
                            st = self._abrir_stream()
                            if not self.t_inicio_audio:
                                self.t_inicio_audio = time.time()
                            st.write(dados[i:i + bloco])
        except Exception as e:
            if cortada():
                return
            print(f"⚠ placa de som falhou ({type(e).__name__}); tocando pelo afplay")
            self._fechar_stream()
            resto = b"".join(bytes(t) for t in blocos) if not isinstance(pcm, (bytes, bytearray)) else b""
            self._tocar_afplay(bytes(tocado) + resto if tocado or resto else bytes(pcm))

    def _abrir_stream(self):
        """Um stream por resposta, não por frase: abrir custa 0,09 s e é o que emenda as frases."""
        import sounddevice as sd
        with self._lock_stream:
            if self._stream is None:
                self._taxa = int(sd.query_devices(kind="output")["default_samplerate"]) or PCM_SR
                self._stream = sd.RawOutputStream(samplerate=self._taxa, channels=1, dtype="int16",
                                                  blocksize=0, latency="low")
                self._stream.start()
            return self._stream

    def _fechar_stream(self) -> None:
        with self._lock_stream:                             # espera o bloco em curso (≤ 50 ms) terminar
            st, self._stream = self._stream, None
            if st is not None:
                try: st.abort() if self._parando.is_set() else st.stop(); st.close()
                except Exception: pass

    def _na_taxa_do_aparelho(self, pcm: bytes) -> bytes:
        """Reamostragem linear 24 kHz → taxa do aparelho. Fazer aqui evita os estalos do PortAudio."""
        if self._taxa == PCM_SR:
            return pcm
        import numpy as np
        x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        n = int(len(x) * self._taxa / PCM_SR)
        return np.interp(np.arange(n) * PCM_SR / self._taxa,
                         np.arange(len(x)), x).astype(np.int16).tobytes()

    def _tocar_afplay(self, pcm: bytes) -> None:
        """Reserva: WAV temporário. Confiável, mas cobra ~1 s por frase — só quando o stream falha."""
        if not self._afplay:
            return
        caminho = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                caminho = f.name
            with wave.open(caminho, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(PCM_SR); w.writeframes(pcm)
            subprocess.run([self._afplay, caminho], check=False, stderr=subprocess.DEVNULL)
        finally:
            if caminho:
                try: os.unlink(caminho)
                except OSError: pass

    def _say_nativo(self, texto: str) -> bool:
        """macOS: voz local em pt-BR. Grátis, offline, sotaque pior que a ElevenLabs."""
        if not shutil.which("say"):
            return False
        # Eddy é masculina pt-BR; a Luciana (feminina) era o padrão antigo — o João estranhou "voz feminina às vezes"
        subprocess.run(["say", "-v", os.environ.get("JAIME_SAY_VOZ", "Eddy (Português (Brasil))"), "-r", str(int(185 * self.velocidade)), texto],
                       check=False, stderr=subprocess.DEVNULL)
        return True
