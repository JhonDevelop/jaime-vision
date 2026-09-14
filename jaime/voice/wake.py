"""Wake word com Porcupine (Picovoice). "jarvis" é built-in; "jaime" precisa de um .ppn treinado no console."""
from __future__ import annotations
from ..config import Settings

class WakeWord:
    def __init__(self, s: Settings):
        import pvporcupine
        kw = dict(access_key=s.picovoice_key)
        if s.wake_ppn:
            kw["keyword_paths"] = [s.wake_ppn]
        else:
            kw["keywords"] = [s.wake_word]
        self._p = pvporcupine.create(**kw)
        self.frame_length = self._p.frame_length
        self.sample_rate = self._p.sample_rate

    def detectou(self, frame) -> bool:
        return self._p.process(frame) >= 0

    def close(self):
        self._p.delete()
