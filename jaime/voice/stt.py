"""Transcrição: Deepgram (nuvem, rápido) se houver chave; senão faster-whisper local."""
from __future__ import annotations
import io, wave
import httpx
from ..config import Settings

def _wav_bytes(pcm16: bytes, sr: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm16)
    return buf.getvalue()

class STT:
    def __init__(self, s: Settings):
        self.s = s
        self._whisper = None
        if not s.deepgram_key:
            from faster_whisper import WhisperModel
            # small: bom pt-BR em CPU (1-3 s por frase). base: mais rápido, erra mais. Ver JAIME_WHISPER_MODELO.
            self._whisper = WhisperModel(s.whisper_modelo, device="auto", compute_type="int8")

    async def transcrever(self, pcm16: bytes, sr: int = 16000) -> str:
        if self.s.deepgram_key:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post("https://api.deepgram.com/v1/listen?model=nova-3&language=pt-BR&smart_format=true",
                                 headers={"Authorization": f"Token {self.s.deepgram_key}", "Content-Type": "audio/wav"},
                                 content=_wav_bytes(pcm16, sr))
                r.raise_for_status()
                return r.json()["results"]["channels"][0]["alternatives"][0]["transcript"].strip()
        import asyncio
        return await asyncio.to_thread(self._whisper_sync, pcm16)   # não trava o servidor enquanto transcreve

    def _whisper_sync(self, pcm16: bytes) -> str:
        import numpy as np
        audio = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        segs, _ = self._whisper.transcribe(audio, language="pt", vad_filter=True, beam_size=1)
        return " ".join(s.text.strip() for s in segs).strip()
