"""Fala: ElevenLabs em streaming. Sem chave → imprime no terminal (útil para testar o resto)."""
from __future__ import annotations
from ..config import Settings
from ..hud.events import bus

class TTS:
    def __init__(self, s: Settings):
        self.s = s
        self._client = None
        if s.elevenlabs_key:
            from elevenlabs.client import ElevenLabs
            self._client = ElevenLabs(api_key=s.elevenlabs_key)

    def falar(self, texto: str):
        texto = texto.strip()
        if not texto:
            return
        bus.emitir("voz", falando=True)
        try:
            if not self._client:
                print(f"🔈 {texto}")
                return
            from elevenlabs import stream
            audio = self._client.text_to_speech.convert_as_stream(
                text=texto, voice_id=self.s.elevenlabs_voice or "JBFqnCBsd6RMkjVDRZzb",
                model_id="eleven_multilingual_v2", output_format="mp3_22050_32",
            )
            stream(audio)
        finally:
            bus.emitir("voz", falando=False)
