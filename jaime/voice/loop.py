"""Loop de voz: wake word → grava até silêncio → STT → Jaime → TTS (frase a frase)."""
from __future__ import annotations
import asyncio, re, time
from ..config import Settings

SILENCIO_MS = 900      # fim de fala
MAX_FALA_S = 20
LIMIAR_RMS = 500       # ajuste ao seu microfone

class VoiceLoop:
    def __init__(self, jaime, s: Settings):
        self.jaime, self.s = jaime, s

    async def run(self):
        import numpy as np, sounddevice as sd
        from .wake import WakeWord
        from .stt import STT
        from .tts import TTS
        wake, stt, tts = WakeWord(self.s), STT(self.s), TTS(self.s)
        sr, fl = wake.sample_rate, wake.frame_length
        print(f"🎙️  Jaime ouvindo. Diga '{self.s.wake_word}'…")
        with sd.RawInputStream(samplerate=sr, blocksize=fl, dtype="int16", channels=1) as stream:
            while True:
                frame, _ = stream.read(fl)
                pcm = np.frombuffer(frame, dtype=np.int16)
                if not wake.detectou(pcm):
                    continue
                tts.falar("Oi.")
                audio = self._gravar(stream, fl, sr)
                texto = await stt.transcrever(audio, sr)
                if not texto:
                    continue
                print(f"você › {texto}")
                buffer = ""
                async for trecho in self.jaime.ask_stream(texto, canal="voice"):
                    buffer += trecho
                    # fala frase a frase para reduzir latência
                    while (m := re.search(r"(.+?[.!?])\s", buffer)):
                        tts.falar(m.group(1)); buffer = buffer[m.end():]
                tts.falar(buffer)

    def _gravar(self, stream, fl: int, sr: int) -> bytes:
        import numpy as np
        chunks, ultimo_som, inicio = [], time.time(), time.time()
        while True:
            frame, _ = stream.read(fl)
            pcm = np.frombuffer(frame, dtype=np.int16)
            chunks.append(pcm.tobytes())
            if np.sqrt(np.mean(pcm.astype(np.float32) ** 2)) > LIMIAR_RMS:
                ultimo_som = time.time()
            if (time.time() - ultimo_som) * 1000 > SILENCIO_MS and len(chunks) > 10:
                break
            if time.time() - inicio > MAX_FALA_S:
                break
        return b"".join(chunks)
