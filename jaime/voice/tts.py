"""Fala: ElevenLabs → PCM → placa de som. Feito para não engasgar.

Por que é assim (medido nesta máquina, 14/09/2026):
- A ElevenLabs não entrega o áudio em fluxo contínuo: espera ~0,3 s e despeja a frase inteira em
  ~0,2 s. Tocar "em streaming" não ganhava nada e ainda deixava a placa de som sem dado — era daí
  que vinha a voz picotada. Agora a frase é sintetizada inteira em memória e só então tocada.
- O que realmente travava a conversa eram as pausas ENTRE frases: cada uma abria uma requisição nova
  e o João ouvia ~0,5 s de silêncio a cada ponto final. Agora um sintetizador vai na frente,
  preparando as próximas frases enquanto a atual toca — a fala sai emendada.
- A saída é UM stream de saída aberto para a resposta inteira, com escrita bloqueante. Medido:
  `afplay` cobrava ~1,1 s por frase só para abrir e fechar o aparelho — voltava o efeito picotado.
  O stream persistente custa 0,09 s uma vez e emenda as frases sem folga nenhuma.
- O PCM é reamostrado aqui para a taxa nativa do aparelho (24 kHz → 44,1 kHz), em vez de deixar a
  conversão para o PortAudio — é de lá que vinham os estalos. `afplay` fica de reserva.

Ordem de tentativa: ElevenLabs → `say` do macOS em pt-BR → texto no terminal. Nunca fica mudo em silêncio.
`voz: falando=true` sai quando a primeira frase começa e só volta a false quando a fila esvazia —
o cérebro do HUD pulsa durante a resposta toda, não a cada ponto final."""
from __future__ import annotations
import os, queue, re, shutil, subprocess, tempfile, threading, wave
from ..config import Settings
from ..hud.events import bus

PCM_SR = 24000                       # pcm_24000 existe no plano gratuito (44100 é só Pro)
VOZ_PADRAO = "JBFqnCBsd6RMkjVDRZzb"  # premade (George) — fala pt-BR com sotaque; troque em ELEVENLABS_VOICE_ID
ADIANTAR = 2                         # quantas frases o sintetizador prepara à frente da que está tocando

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
    def __init__(self, s: Settings):
        self.s = s
        self._client = None
        self._falhas = 0
        self._afplay = shutil.which("afplay")
        self._stream = None          # stream de saída, aberto enquanto durar a resposta
        self._taxa = PCM_SR          # taxa nativa do aparelho, descoberta ao abrir
        self._anterior = ""          # última frase sintetizada (previous_text da ElevenLabs)
        self.ajustes: dict | None = None   # {"stability", "style"} vindos da prosódia (humor); None = .env
        if s.elevenlabs_key:
            from elevenlabs.client import ElevenLabs
            self._client = ElevenLabs(api_key=s.elevenlabs_key)
        # pipeline: enfileirar() → [sintetizador] → _prontos → [reprodutor] → placa de som
        self._pedidos: queue.Queue = queue.Queue()
        self._prontos: queue.Queue = queue.Queue(maxsize=ADIANTAR)
        self._pendentes = 0
        self._cond = threading.Condition()
        threading.Thread(target=self._sintetizador, daemon=True).start()
        threading.Thread(target=self._reprodutor, daemon=True).start()

    # ── API ───────────────────────────────────────────────
    def enfileirar(self, texto: str) -> None:
        """Manda falar sem esperar. Use durante a resposta em fluxo: cada frase entra assim que fica
        pronta e o sintetizador já vai preparando a seguinte."""
        texto = limpar_para_fala(texto)
        if not texto:
            return
        with self._cond:
            if self._pendentes == 0:
                bus.emitir("voz", falando=True, estado="falando", texto=texto)
            self._pendentes += 1
        self._pedidos.put(texto)

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
    def _sintetizador(self) -> None:
        """Vai na frente: busca o áudio da próxima frase enquanto a atual ainda toca."""
        while True:
            texto = self._pedidos.get()
            pcm = None
            if self._client and self._falhas < 3:
                try:
                    pcm = self._elevenlabs(texto)
                    self._falhas = 0
                except Exception as e:
                    # depois de 3 falhas seguidas para de tentar nesta sessão (não gasta latência à toa)
                    self._falhas += 1
                    print(f"⚠ ElevenLabs falhou ({type(e).__name__}); usando a voz local")
            self._prontos.put((texto, pcm))

    def _reprodutor(self) -> None:
        while True:
            texto, pcm = self._prontos.get()
            try:
                if pcm:
                    self._tocar(pcm)
                elif not self._say_nativo(texto):
                    print(f"🔈 {texto}")
            except Exception as e:
                print(f"⚠ áudio falhou ({type(e).__name__}); {texto}")
            finally:
                with self._cond:
                    self._pendentes -= 1
                    vazio = self._pendentes == 0
                    self._cond.notify_all()
                if vazio:
                    self._fechar_stream()   # libera o aparelho entre uma resposta e outra
                    bus.emitir("voz", falando=False, estado="ouvindo")

    # ── saídas ────────────────────────────────────────────
    def _elevenlabs(self, texto: str) -> bytes:
        from elevenlabs import VoiceSettings
        # Emoção: estabilidade baixa e "style" alto deixam a voz seguir a pontuação — exclamação sobe,
        # reticências hesitam, pergunta entoa. O prompt do Jaime escreve pensando nisso quando fala.
        a = self.ajustes or {}
        ajustes = VoiceSettings(stability=float(a.get("stability", os.environ.get("JAIME_VOZ_ESTABILIDADE", "0.5"))),
                                similarity_boost=0.8,
                                style=float(a.get("style", os.environ.get("JAIME_VOZ_ESTILO", "0.3"))),
                                use_speaker_boost=True)
        fluxo = self._client.text_to_speech.stream(
            text=texto, voice_id=self.s.elevenlabs_voice or VOZ_PADRAO,
            model_id=os.environ.get("JAIME_TTS_MODELO", "eleven_flash_v2_5"),   # flash: menor latência
            output_format=f"pcm_{PCM_SR}", voice_settings=ajustes,
            optimize_streaming_latency=3,   # ~0,1 s a menos até o primeiro byte
            previous_text=self._anterior[-300:] or None,   # continuidade de entonação entre frases
        )
        self._anterior = texto
        return b"".join(c for c in fluxo if c)

    def _tocar(self, pcm: bytes) -> None:
        try:
            self._abrir_stream().write(self._na_taxa_do_aparelho(pcm))
        except Exception as e:
            print(f"⚠ placa de som falhou ({type(e).__name__}); tocando pelo afplay")
            self._fechar_stream()
            self._tocar_afplay(pcm)

    def _abrir_stream(self):
        """Um stream por resposta, não por frase: abrir custa 0,09 s e é o que emenda as frases."""
        import sounddevice as sd
        if self._stream is None:
            self._taxa = int(sd.query_devices(kind="output")["default_samplerate"]) or PCM_SR
            self._stream = sd.RawOutputStream(samplerate=self._taxa, channels=1, dtype="int16",
                                              blocksize=0, latency="low")
            self._stream.start()
        return self._stream

    def _fechar_stream(self) -> None:
        st, self._stream = self._stream, None
        if st is not None:
            try: st.stop(); st.close()
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
        subprocess.run(["say", "-v", os.environ.get("JAIME_SAY_VOZ", "Luciana"), "-r", "185", texto],
                       check=False, stderr=subprocess.DEVNULL)
        return True
