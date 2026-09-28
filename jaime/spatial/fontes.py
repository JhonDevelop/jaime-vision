"""Fontes de frames e rastreadores de mão — plugáveis, para o serviço não saber se é câmera, simulação ou replay.

- `FonteSimulada` / `FonteReplay`: entregam frames que JÁ trazem landmarks (o rastreador é a identidade).
- `FonteOpenCV`: webcam real via OpenCV, lida numa thread (o `read()` bloqueia) — import preguiçoso: o Jaime
  sobe sem OpenCV instalado e só a fonte real reclama.
- `RastreadorMediaPipe`: MediaPipe Hands, import preguiçoso. Roda fora do event loop (`asyncio.to_thread`).

Nenhuma fonte grava imagem: o frame vive um ciclo e some."""
from __future__ import annotations
import asyncio, time
from typing import AsyncIterator, Protocol
from .landmarks import CameraFrame, HandPose


class FrameSource(Protocol):
    camera_id: str
    def frames(self) -> AsyncIterator[CameraFrame]: ...
    def fechar(self) -> None: ...


class HandTracker(Protocol):
    def detect(self, frame: CameraFrame) -> list[HandPose]: ...
    def fechar(self) -> None: ...


class RastreadorIdentidade:
    """Para fontes que já entregam landmarks (simulação/replay)."""
    nome = "identidade"

    def detect(self, frame: CameraFrame) -> list[HandPose]:
        return list(frame.poses or [])

    def fechar(self) -> None:
        pass


class FonteSequencia:
    """Reproduz uma sequência (t, poses) — sintética ou lida de JSONL. `tempo_real=False` entrega o mais rápido
    possível (testes e benchmark); `True` respeita o relógio (demo no HUD)."""
    def __init__(self, sequencia: list[tuple[float, list[HandPose]]], camera_id: str = "sim",
                 tempo_real: bool = True, repetir: bool = False, relogio=time.monotonic):
        self.seq, self.camera_id, self.tempo_real, self.repetir, self.relogio = sequencia, camera_id, tempo_real, repetir, relogio
        self._fechada = False

    async def frames(self) -> AsyncIterator[CameraFrame]:
        n = 0
        volta = 0
        dur = (self.seq[-1][0] - self.seq[0][0] + 1 / 30) if self.seq else 0.0
        while not self._fechada:
            t0 = self.relogio()
            base = self.seq[0][0] if self.seq else 0.0
            for t, ps in self.seq:
                if self._fechada:
                    return
                if self.tempo_real:
                    espera = (t - base) - (self.relogio() - t0)
                    if espera > 0:
                        await asyncio.sleep(espera)
                else:
                    await asyncio.sleep(0)
                n += 1
                yield CameraFrame(self.camera_id, n, self.relogio(), poses=ps, wall_ms=time.time() * 1000,
                                  media_ts=(t - base) + volta * dur)
            volta += 1
            if not self.repetir:
                return

    def fechar(self) -> None:
        self._fechada = True


FonteSimulada = FonteSequencia


def FonteReplay(caminho, **kw) -> FonteSequencia:
    from .simulador import ler
    return FonteSequencia(ler(caminho), camera_id=kw.pop("camera_id", "replay"), **kw)


class FonteOpenCV:
    """Webcam real. Só é construída com JAIME_SPATIAL=camera — ligar câmera é decisão do João."""
    def __init__(self, indice: int = 0, largura: int = 640, altura: int = 480, fps: int = 30):
        try:
            import cv2  # noqa: F401
        except ImportError as e:
            raise RuntimeError("OpenCV ausente: `pip install opencv-python` (decisão do João; não instalo sozinho)") from e
        import threading
        self.camera_id, self.indice, self.largura, self.altura, self.fps = str(indice), indice, largura, altura, fps
        self._cap = None
        self._fechada = False
        self._lendo = threading.Lock()     # release() nunca durante um read() de outra thread (OpenCV não é thread-safe)

    def _abrir(self):
        import cv2
        cap = cv2.VideoCapture(self.indice)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.largura); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.altura)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)     # buffer do driver com 1 frame: senão lemos o passado
        except Exception:
            pass
        if not cap.isOpened():
            raise RuntimeError(f"câmera {self.indice} não abriu (permissão de Câmera? outra app usando?)")
        return cap

    def _ler(self):
        with self._lendo:
            if self._cap is None:
                return False, None
            return self._cap.read()

    async def frames(self) -> AsyncIterator[CameraFrame]:
        self._cap = await asyncio.to_thread(self._abrir)
        n = 0
        try:
            while not self._fechada:
                ok, img = await asyncio.to_thread(self._ler)
                ts = time.monotonic()
                if not ok:
                    raise RuntimeError("câmera parou de entregar frames")
                n += 1
                yield CameraFrame(self.camera_id, n, ts, pixels=img, wall_ms=time.time() * 1000)
        finally:
            self.fechar()

    def fechar(self) -> None:
        """Pede para parar e solta a câmera numa thread que ESPERA o read() em curso terminar."""
        import threading
        self._fechada = True

        def soltar():
            with self._lendo:
                cap, self._cap = self._cap, None
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass
        threading.Thread(target=soltar, name="espacial:soltar-camera", daemon=True).start()


class RastreadorMediaPipe:
    nome = "mediapipe"

    def __init__(self, max_maos: int = 2, conf_min: float = 0.6):
        try:
            import mediapipe as mp
        except ImportError as e:
            raise RuntimeError("MediaPipe ausente: `pip install mediapipe` (decisão do João; no Mac Intel verificar wheel)") from e
        self._hands = mp.solutions.hands.Hands(static_image_mode=False, max_num_hands=max_maos,
                                               min_detection_confidence=conf_min, min_tracking_confidence=conf_min)

    def detect(self, frame: CameraFrame) -> list[HandPose]:
        import cv2
        if frame.pixels is None:
            return []
        rgb = cv2.cvtColor(frame.pixels, cv2.COLOR_BGR2RGB)
        r = self._hands.process(rgb)
        out: list[HandPose] = []
        for lms, lado in zip(r.multi_hand_landmarks or [], r.multi_handedness or []):
            c = lado.classification[0]
            # o MediaPipe assume imagem espelhada (selfie); a webcam crua vem sem espelho → a lateralidade inverte
            mao = "left" if c.label.lower() == "right" else "right"
            out.append(HandPose([(p.x, p.y, p.z) for p in lms.landmark], mao, float(c.score), camera_id=frame.camera_id))
        return out

    def fechar(self) -> None:
        try:
            self._hands.close()
        except Exception:
            pass
