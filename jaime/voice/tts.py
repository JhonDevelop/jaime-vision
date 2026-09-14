"""Fala: ElevenLabs em PCM streaming direto na placa de som (sounddevice). Sem mpv, sem arquivo.

Ordem de tentativa:
1. ElevenLabs → PCM 22 kHz → sounddevice (streaming real: começa a soar no primeiro chunk).
2. ElevenLabs falhou (voz de biblioteca no plano grátis = HTTP 402, cota, rede) → `say` do macOS em pt-BR.
3. Sem `say` → texto no terminal. O Jaime nunca fica mudo em silêncio.

Cada frase emite `voz: falando=true/false` — é o que faz o cérebro do HUD pulsar."""
from __future__ import annotations
import os, shutil, subprocess, threading
from ..config import Settings
from ..hud.events import bus

PCM_SR = 24000                       # pcm_24000 existe no plano gratuito (44100 é só Pro)
PRE_BUFFER_S = 0.4                   # acumula isto antes de começar a tocar: absorve os soluços da rede
VOZ_PADRAO = "JBFqnCBsd6RMkjVDRZzb"  # premade (George) — fala pt-BR com sotaque; troque em ELEVENLABS_VOICE_ID

class TTS:
    def __init__(self, s: Settings):
        self.s = s
        self._client = None
        self._lock = threading.Lock()   # uma frase por vez, sem sobreposição
        self._falhas = 0
        if s.elevenlabs_key:
            from elevenlabs.client import ElevenLabs
            self._client = ElevenLabs(api_key=s.elevenlabs_key)

    # ── saídas ────────────────────────────────────────────
    def _tocar_pcm(self, chunks) -> None:
        """Rede e placa de som desacoplados: a rede enche um buffer; um callback da placa consome.
        Começa a tocar com PRE_BUFFER_S acumulado (ou quando a rede terminar). Underruns são contados
        e impressos — se aparecerem, o problema é rede/CPU, não o código."""
        import sounddevice as sd
        buf = bytearray(); lock = threading.Lock()
        fim = threading.Event(); pronto = threading.Event()
        underruns = 0

        def encher():
            nonlocal buf
            try:
                for c in chunks:
                    if not c:
                        continue
                    with lock:
                        buf += c
                        if len(buf) >= int(PCM_SR * 2 * PRE_BUFFER_S):
                            pronto.set()
            finally:
                fim.set(); pronto.set()

        def callback(outdata, frames, tempo, status):
            nonlocal underruns
            n = frames * 2
            if status.output_underflow:
                underruns += 1
            with lock:
                pedaco = bytes(buf[:n]); del buf[:n]
            outdata[:len(pedaco)] = pedaco
            if len(pedaco) < n:
                outdata[len(pedaco):] = b"\x00" * (n - len(pedaco))
                if fim.is_set():
                    raise sd.CallbackStop

        threading.Thread(target=encher, daemon=True).start()
        pronto.wait(timeout=15)
        acabou = threading.Event()
        with sd.RawOutputStream(samplerate=PCM_SR, channels=1, dtype="int16", blocksize=1024,
                                latency="high", callback=callback, finished_callback=acabou.set):
            acabou.wait(timeout=120)
        if underruns:
            print(f"⚠ áudio: {underruns} underruns nesta frase")

    def _say_nativo(self, texto: str) -> bool:
        """macOS: voz local em pt-BR. Grátis, offline, sotaque pior que a ElevenLabs."""
        if not shutil.which("say"):
            return False
        subprocess.run(["say", "-v", os.environ.get("JAIME_SAY_VOZ", "Luciana"), "-r", "185", texto],
                       check=False, stderr=subprocess.DEVNULL)
        return True

    def _elevenlabs(self, texto: str) -> None:
        from elevenlabs import VoiceSettings
        # Emoção: estabilidade baixa e "style" alto deixam a voz seguir a pontuação — exclamação sobe,
        # reticências hesitam, pergunta entoa. O prompt do Jaime escreve pensando nisso quando fala.
        ajustes = VoiceSettings(stability=float(os.environ.get("JAIME_VOZ_ESTABILIDADE", "0.5")),
                                similarity_boost=0.8,
                                style=float(os.environ.get("JAIME_VOZ_ESTILO", "0.3")),
                                use_speaker_boost=True)
        audio = self._client.text_to_speech.stream(
            text=texto, voice_id=self.s.elevenlabs_voice or VOZ_PADRAO,
            model_id=os.environ.get("JAIME_TTS_MODELO", "eleven_flash_v2_5"),   # flash: menor latência
            output_format=f"pcm_{PCM_SR}", voice_settings=ajustes,
        )
        self._tocar_pcm(audio)

    # ── API ───────────────────────────────────────────────
    def falar(self, texto: str) -> None:
        texto = texto.strip()
        if not texto:
            return
        with self._lock:
            bus.emitir("voz", falando=True, estado="falando", texto=texto)
            try:
                if self._client and self._falhas < 3:
                    try:
                        self._elevenlabs(texto); self._falhas = 0; return
                    except Exception as e:
                        # depois de 3 falhas seguidas para de tentar nesta sessão (não gasta latência à toa)
                        self._falhas += 1
                        print(f"⚠ ElevenLabs falhou ({type(e).__name__}); usando a voz local")
                if not self._say_nativo(texto):
                    print(f"🔈 {texto}")
            finally:
                bus.emitir("voz", falando=False, estado="ouvindo")
