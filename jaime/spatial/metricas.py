"""Medição do caminho quente: p50/p95 por etapa, frames descartados, fps. Metas não são resultados —
só vale o que este módulo mediu (docs/espacial/RELATORIO.md registra os números com a origem)."""
from __future__ import annotations
import time
from collections import Counter, deque


def percentil(valores, p: float) -> float | None:
    xs = sorted(valores)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo = int(k); hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


class Metricas:
    ETAPAS = ("fila_ms", "landmarks_ms", "gesto_ms", "captura_evento_ms", "evento_render_ms")

    def __init__(self, janela: int = 3000):
        self.lat: dict[str, deque[float]] = {e: deque(maxlen=janela) for e in self.ETAPAS}
        self.frames = 0
        self.descartados = 0
        self.eventos: Counter[str] = Counter()
        self.duplicados_bloqueados = 0
        self._ts_frames: deque[float] = deque(maxlen=120)
        self.inicio = time.monotonic()

    def frame(self, t: float) -> None:
        self.frames += 1; self._ts_frames.append(t)

    def registrar(self, etapa: str, ms: float) -> None:
        if etapa in self.lat and ms >= 0:
            self.lat[etapa].append(ms)

    def fps(self) -> float:
        ts = self._ts_frames
        if len(ts) < 2 or ts[-1] <= ts[0]:
            return 0.0
        return round((len(ts) - 1) / (ts[-1] - ts[0]), 1)

    def resumo(self) -> dict:
        r = {"frames": self.frames, "descartados": self.descartados, "fps": self.fps(),
             "eventos": dict(self.eventos), "duplicados_bloqueados": self.duplicados_bloqueados}
        for e, v in self.lat.items():
            if v:
                r[e] = {"p50": round(percentil(v, .5), 2), "p95": round(percentil(v, .95), 2), "n": len(v)}
        return r
