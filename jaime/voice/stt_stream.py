"""STT em streaming — a transcrição cresce enquanto o João fala (docs/FASE-3-TEMPO-REAL.md §2.1).

Três motores, mesma interface (`FluxoSTT`): `iniciar()` uma vez; `enviar(pcm16)` a cada frame; `finalizar()` no fim
do turno devolve o texto final e zera; `on_parcial(texto)` é chamado a cada parcial (texto acumulado do turno).
- DeepgramAoVivo: WebSocket `v1/listen` (nova-3, pt-BR, interim_results). Conexão persistente com KeepAlive;
  `Finalize` no fim do turno força os resultados finais do que ficou no buffer.
- OpenAIRealtimeTranscricao: `realtime?intent=transcription` (gpt-realtime-whisper / gpt-4o-mini-transcribe).
- WhisperLocalPseudo: sem chave, o faster-whisper local reprocessa o turno inteiro a cada ~1 s — parcial de verdade,
  só que com 1 s de atraso. Também é o motor dos testes (transcritor injetável)."""
from __future__ import annotations
import asyncio, base64, json, time
from typing import Callable

SR = 16000

class FluxoSTT:
    on_parcial: Callable[[str], None] | None = None
    nome = "base"

    async def iniciar(self) -> None: ...
    async def enviar(self, pcm16: bytes) -> None: ...
    async def finalizar(self) -> str: return ""
    async def fechar(self) -> None: ...
    @property
    def conectado(self) -> bool: return True

    def _parcial(self, texto: str) -> None:
        if self.on_parcial and texto:
            try: self.on_parcial(texto)
            except Exception: pass

# ── Deepgram ──────────────────────────────────────────────────────────────────
class DeepgramAoVivo(FluxoSTT):
    nome = "deepgram"
    URL = ("wss://api.deepgram.com/v1/listen?model=nova-3&language=pt-BR&encoding=linear16&sample_rate={sr}&channels=1"
           "&interim_results=true&smart_format=true&punctuate=true&endpointing=300&keyterm=Jaime")

    def __init__(self, api_key: str, sr: int = SR, ws_factory=None):
        self.api_key, self.sr, self.ws_factory = api_key, sr, ws_factory
        self.ws = None
        self._finais: list[str] = []
        self._interim = ""
        self._leitor: asyncio.Task | None = None
        self._keepalive: asyncio.Task | None = None
        self._finalizado = asyncio.Event()
        self._ultimo_envio = 0.0
        self.erro = ""

    @property
    def conectado(self) -> bool:
        return self.ws is not None

    @property
    def texto(self) -> str:
        return (" ".join(self._finais + ([self._interim] if self._interim else []))).strip()

    async def iniciar(self) -> None:
        if self.ws_factory:
            self.ws = await self.ws_factory()
        else:
            import websockets
            self.ws = await websockets.connect(self.URL.format(sr=self.sr), additional_headers={"Authorization": f"Token {self.api_key}"}, max_size=None)
        self._leitor = asyncio.create_task(self._ler())
        self._keepalive = asyncio.create_task(self._manter())

    async def _manter(self):
        try:
            while self.ws:
                await asyncio.sleep(3)
                if time.time() - self._ultimo_envio > 3 and self.ws:
                    await self.ws.send(json.dumps({"type": "KeepAlive"}))
        except Exception:
            pass

    async def _ler(self):
        try:
            async for raw in self.ws:
                self.tratar(json.loads(raw))
        except Exception as e:
            self.erro = f"{type(e).__name__}: {e}"
        finally:
            self.ws = None
            self._finalizado.set()

    def tratar(self, ev: dict) -> None:
        """Evento do Deepgram (testável). Finais acumulam; interim substitui o último trecho."""
        if ev.get("type") != "Results":
            return
        alt = ((ev.get("channel") or {}).get("alternatives") or [{}])[0]
        t = (alt.get("transcript") or "").strip()
        if ev.get("is_final"):
            self._interim = ""
            if t:
                self._finais.append(t)
        else:
            self._interim = t
        if ev.get("from_finalize") or ev.get("speech_final"):
            self._finalizado.set()
        self._parcial(self.texto)

    async def enviar(self, pcm16: bytes) -> None:
        if self.ws:
            self._ultimo_envio = time.time()
            await self.ws.send(pcm16)

    async def finalizar(self) -> str:
        """Força o que está no buffer a virar final e devolve o texto do turno."""
        if self.ws:
            self._finalizado.clear()
            try:
                await self.ws.send(json.dumps({"type": "Finalize"}))
                await asyncio.wait_for(self._finalizado.wait(), 1.5)
            except (asyncio.TimeoutError, Exception):
                pass
        texto = self.texto
        self._finais = []; self._interim = ""
        return texto

    async def fechar(self) -> None:
        ws, self.ws = self.ws, None
        for t in (self._leitor, self._keepalive):
            if t: t.cancel()
        if ws:
            try: await ws.send(json.dumps({"type": "CloseStream"})); await ws.close()
            except Exception: pass

# ── OpenAI Realtime (transcrição) ─────────────────────────────────────────────
class OpenAIRealtimeTranscricao(FluxoSTT):
    nome = "openai-realtime"
    URL = "wss://api.openai.com/v1/realtime?intent=transcription"

    def __init__(self, api_key: str, modelo: str = "gpt-4o-mini-transcribe", sr: int = SR, ws_factory=None):
        self.api_key, self.modelo, self.sr, self.ws_factory = api_key, modelo, sr, ws_factory
        self.ws = None
        self._finais: list[str] = []
        self._delta = ""
        self._leitor = None
        self._completo = asyncio.Event()
        self.erro = ""

    @property
    def conectado(self) -> bool:
        return self.ws is not None

    @property
    def texto(self) -> str:
        return (" ".join(self._finais + ([self._delta] if self._delta else []))).strip()

    async def iniciar(self) -> None:
        if self.ws_factory:
            self.ws = await self.ws_factory()
        else:
            import websockets
            self.ws = await websockets.connect(self.URL, additional_headers={"Authorization": f"Bearer {self.api_key}"}, max_size=None)
        await self.ws.send(json.dumps({"type": "transcription_session.update", "session": {
            "input_audio_format": "pcm16", "input_audio_transcription": {"model": self.modelo, "language": "pt"},
            "turn_detection": None}}))
        self._leitor = asyncio.create_task(self._ler())

    async def _ler(self):
        try:
            async for raw in self.ws:
                self.tratar(json.loads(raw))
        except Exception as e:
            self.erro = f"{type(e).__name__}: {e}"
        finally:
            self.ws = None; self._completo.set()

    def tratar(self, ev: dict) -> None:
        t = ev.get("type", "")
        if t == "conversation.item.input_audio_transcription.delta":
            self._delta += ev.get("delta", ""); self._parcial(self.texto)
        elif t == "conversation.item.input_audio_transcription.completed":
            self._delta = ""
            if (tx := (ev.get("transcript") or "").strip()):
                self._finais.append(tx)
            self._completo.set(); self._parcial(self.texto)

    async def enviar(self, pcm16: bytes) -> None:
        if self.ws:
            # o Realtime espera 24 kHz; reamostra 16 → 24 (linear) antes de mandar
            import numpy as np
            x = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32)
            n = int(len(x) * 24000 / self.sr)
            y = np.interp(np.arange(n) * self.sr / 24000, np.arange(len(x)), x).astype(np.int16).tobytes()
            await self.ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": base64.b64encode(y).decode()}))

    async def finalizar(self) -> str:
        if self.ws:
            self._completo.clear()
            try:
                await self.ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
                await asyncio.wait_for(self._completo.wait(), 2.5)
            except (asyncio.TimeoutError, Exception):
                pass
        texto = self.texto
        self._finais = []; self._delta = ""
        return texto

    async def fechar(self) -> None:
        ws, self.ws = self.ws, None
        if self._leitor: self._leitor.cancel()
        if ws:
            try: await ws.close()
            except Exception: pass

# ── Whisper local (pseudo-streaming) ──────────────────────────────────────────
class WhisperLocalPseudo(FluxoSTT):
    """Reprocessa o áudio acumulado do turno a cada `cada_s`. `transcritor(pcm16, sr) -> str` é injetável."""
    nome = "whisper-local"

    def __init__(self, transcritor: Callable[[bytes, int], str], sr: int = SR, cada_s: float = 1.0):
        self.transcritor, self.sr, self.cada_s = transcritor, sr, cada_s
        self._buf = bytearray()
        self._ultimo = 0.0
        self._tarefa: asyncio.Task | None = None
        self.texto = ""

    async def enviar(self, pcm16: bytes) -> None:
        self._buf += pcm16
        agora = time.time()
        if agora - self._ultimo >= self.cada_s and (self._tarefa is None or self._tarefa.done()):
            self._ultimo = agora
            trecho = bytes(self._buf)
            self._tarefa = asyncio.create_task(self._reprocessar(trecho))

    async def _reprocessar(self, pcm: bytes) -> None:
        try:
            t = (await asyncio.to_thread(self.transcritor, pcm, self.sr) or "").strip()
        except Exception:
            return
        if t:
            self.texto = t; self._parcial(t)

    async def finalizar(self) -> str:
        if self._tarefa and not self._tarefa.done():
            try: await self._tarefa
            except Exception: pass
        pcm = bytes(self._buf); self._buf = bytearray()
        try:
            t = (await asyncio.to_thread(self.transcritor, pcm, self.sr) or "").strip() if pcm else ""
        except Exception:
            t = self.texto
        self.texto = ""
        return t

def escolher(s, transcritor_local=None) -> FluxoSTT:
    """Pelo .env: JAIME_STT_STREAM = deepgram | openai | local | auto (Deepgram se houver chave, senão OpenAI, senão local)."""
    import os
    modo = os.environ.get("JAIME_STT_STREAM", "auto").lower()
    if modo in ("deepgram", "auto") and getattr(s, "deepgram_key", ""):
        return DeepgramAoVivo(s.deepgram_key)
    if modo in ("openai", "auto") and getattr(s, "openai_key", ""):
        return OpenAIRealtimeTranscricao(s.openai_key, os.environ.get("JAIME_STT_STREAM_MODELO", "gpt-4o-mini-transcribe"))
    if transcritor_local is None:
        raise RuntimeError("sem STT em streaming: defina DEEPGRAM_API_KEY/OPENAI_API_KEY ou passe o Whisper local")
    return WhisperLocalPseudo(transcritor_local)
