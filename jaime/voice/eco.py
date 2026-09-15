"""Referência de saída e supressão de eco para o barge-in.

O AEC do WebRTC é opcional: nem todo macOS/venv tem um binding compatível. A
correlação normalizada continua sendo um caminho local, determinístico e sem
dependência nativa.
"""
from __future__ import annotations

from collections import deque
import threading

import numpy as np

SR_TTS = 24_000
SR_MIC = 16_000
ATRASO_MAX_MS = 300
LIMIAR_SIMILARIDADE = 0.80


class ReferenciaEco:
    """Mantém os últimos 300 ms do PCM que efetivamente vai para a placa."""
    def __init__(self, atraso_max_ms: int = ATRASO_MAX_MS):
        self.max_amostras = SR_TTS * atraso_max_ms // 1000
        self._amostras: deque[np.ndarray] = deque()
        self._total = 0
        self._lock = threading.Lock()

    def adicionar(self, bloco_pcm_24k: bytes) -> None:
        amostras = np.frombuffer(bloco_pcm_24k, dtype=np.int16).copy()
        if not len(amostras):
            return
        with self._lock:
            self._amostras.append(amostras)
            self._total += len(amostras)
            while self._amostras and self._total > self.max_amostras:
                excesso = self._total - self.max_amostras
                primeiro = self._amostras[0]
                if excesso >= len(primeiro):
                    self._amostras.popleft(); self._total -= len(primeiro)
                else:
                    self._amostras[0] = primeiro[excesso:]; self._total -= excesso

    def recente_16k(self) -> np.ndarray:
        with self._lock:
            if not self._amostras:
                return np.empty(0, dtype=np.float32)
            pcm = np.concatenate(tuple(self._amostras)).astype(np.float32)
        # 24 kHz -> 16 kHz. A interpolação preserva a duração, inclusive para
        # blocos cujo tamanho não seja múltiplo de 3 amostras.
        n = round(len(pcm) * SR_MIC / SR_TTS)
        if n < 2:
            return np.empty(0, dtype=np.float32)
        return np.interp(np.arange(n) * SR_TTS / SR_MIC, np.arange(len(pcm)), pcm).astype(np.float32)


class _WebRTCAEC:
    """Adaptador defensivo para bindings compatíveis com webrtc-audio-processing.

    O binding não é obrigatório e suas APIs variam entre wheels; qualquer
    incompatibilidade desabilita somente este acelerador, nunca a voz.
    """
    def __init__(self):
        try:
            import webrtc_audio_processing as webrtc  # type: ignore[import-not-found]
            cls = getattr(webrtc, "AudioProcessingModule")
            self._apm = cls(enable_aec=True, enable_ns=False, enable_agc=False)
        except Exception:
            self._apm = None

    @property
    def disponivel(self) -> bool:
        return self._apm is not None

    def alimentar_referencia(self, pcm_24k: bytes) -> None:
        # A maioria dos bindings APM trabalha em 16 kHz PCM int16.
        if not self._apm:
            return
        try:
            referencia = _reamostrar_pcm(pcm_24k, SR_TTS, SR_MIC)
            self._apm.process_reverse_stream(referencia.tobytes())
        except Exception:
            self._apm = None

    def eh_eco(self, frame_mic_16k: bytes) -> tuple[bool, float] | None:
        if not self._apm:
            return None
        try:
            antes = np.frombuffer(frame_mic_16k, dtype=np.int16).astype(np.float32)
            saida = self._apm.process_stream(frame_mic_16k)
            depois = np.frombuffer(saida if isinstance(saida, bytes) else frame_mic_16k, dtype=np.int16).astype(np.float32)
            energia_antes = float(np.linalg.norm(antes))
            residual = float(np.linalg.norm(depois)) / max(energia_antes, 1.0)
            return residual < 0.35, max(0.0, min(1.0, 1.0 - residual))
        except Exception:
            self._apm = None
            return None


def _reamostrar_pcm(pcm: bytes, origem: int, destino: int) -> np.ndarray:
    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    n = round(len(x) * destino / origem)
    if len(x) < 2 or n < 2:
        return np.empty(0, dtype=np.int16)
    return np.interp(np.arange(n) * origem / destino, np.arange(len(x)), x).astype(np.int16)


class SupressorDeEco:
    """Classifica um frame do microfone usando referência recente do TTS."""
    def __init__(self, limiar: float = LIMIAR_SIMILARIDADE, atraso_max_ms: int = ATRASO_MAX_MS):
        self.limiar = limiar
        self.referencia = ReferenciaEco(atraso_max_ms)
        self._webrtc = _WebRTCAEC()

    def ao_tocar(self, bloco_pcm_24k: bytes) -> None:
        """Callback compatível com ``TTS(ao_tocar=...)``."""
        self.referencia.adicionar(bloco_pcm_24k)
        self._webrtc.alimentar_referencia(bloco_pcm_24k)

    def eh_eco(self, frame_mic_16k: bytes) -> tuple[bool, float]:
        """Devolve ``(eh_eco, similaridade)`` para um frame PCM mono int16."""
        aec = self._webrtc.eh_eco(frame_mic_16k)
        if aec is not None:
            return aec
        mic = np.frombuffer(frame_mic_16k, dtype=np.int16).astype(np.float32)
        referencia = self.referencia.recente_16k()
        if len(mic) < 2 or len(referencia) < len(mic):
            return False, 0.0
        mic -= mic.mean()
        norma_mic = float(np.linalg.norm(mic))
        if norma_mic < 1.0:
            return False, 0.0
        # Cada posição representa um atraso possível dentro da janela de 300 ms.
        # Como ``mic`` já tem média zero, o numerador não muda ao centralizar
        # cada trecho da referência. As energias são calculadas por somas
        # acumuladas para a thread do microfone não fazer milhares de loops Python.
        n = len(mic)
        numeradores = np.abs(np.correlate(referencia, mic, mode="valid"))
        referencia64 = referencia.astype(np.float64)
        soma = np.concatenate(([0.0], np.cumsum(referencia64)))
        soma2 = np.concatenate(([0.0], np.cumsum(referencia64 * referencia64)))
        energia = soma2[n:] - soma2[:-n] - (soma[n:] - soma[:-n]) ** 2 / n
        similares = numeradores / np.maximum(norma_mic * np.sqrt(np.maximum(energia, 0.0)), 1.0)
        melhor = float(similares.max(initial=0.0))
        return melhor >= self.limiar, min(1.0, melhor)
