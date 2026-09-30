"""Filtro One Euro (Casiez et al., 2012) para landmarks.

Por que este e não uma média móvel: a média suaviza o tremor MAS atrasa o movimento rápido, e atraso é o que
faz o arrastar parecer "borracha". O One Euro adapta o corte à velocidade: parado, filtra forte (sem tremor);
rápido, filtra pouco (sem atraso). O atraso que ele acrescenta é medido em `tests/test_espacial_filtro.py`."""
from __future__ import annotations
import math


class _LowPass:
    def __init__(self):
        self.y: float | None = None

    def __call__(self, x: float, alpha: float) -> float:
        self.y = x if self.y is None else alpha * x + (1 - alpha) * self.y
        return self.y


class OneEuro:
    def __init__(self, min_cutoff: float = 1.5, beta: float = 1.0, d_cutoff: float = 1.0):
        # calibrado para coordenadas normalizadas (0..1) a 30 fps: parado corta ~70% do tremor; num degrau
        # brusco anda >85% do caminho em 5 frames (tests/test_espacial_servico.py)
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self._x, self._dx = _LowPass(), _LowPass()
        self._t: float | None = None
        self._prev: float | None = None

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x: float, t: float) -> float:
        if self._t is None or t <= self._t:
            self._t, self._prev = t, x
            self._dx(0.0, 1.0)
            return self._x(x, 1.0)
        dt = t - self._t; self._t = t
        dx = (x - self._prev) / dt; self._prev = x
        edx = self._dx(dx, self._alpha(self.d_cutoff, dt))
        cutoff = self.min_cutoff + self.beta * abs(edx)
        return self._x(x, self._alpha(cutoff, dt))


class FiltroPonto:
    """Um One Euro por eixo de um ponto 3D."""
    def __init__(self, **kw):
        self.eixos = [OneEuro(**kw) for _ in range(3)]

    def __call__(self, p: tuple[float, float, float], t: float) -> tuple[float, float, float]:
        return tuple(f(v, t) for f, v in zip(self.eixos, p))  # type: ignore[return-value]


class FiltroMao:
    """Filtra só os pontos que o gesto usa (polegar, indicador, base dos dedos): 21×3 filtros por frame seria
    custo sem ganho — o resto dos landmarks só serve para desenhar a mão no HUD."""
    USADOS = (0, 4, 5, 8, 17)

    def __init__(self, **kw):
        self.kw = kw
        self.filtros: dict[str, dict[int, FiltroPonto]] = {}

    def __call__(self, chave: str, landmarks: list[tuple[float, float, float]], t: float) -> list[tuple[float, float, float]]:
        fs = self.filtros.setdefault(chave, {i: FiltroPonto(**self.kw) for i in self.USADOS})
        out = list(landmarks)
        for i, f in fs.items():
            if i < len(out):
                out[i] = f(out[i], t)
        return out

    def esquecer(self, chave: str) -> None:
        self.filtros.pop(chave, None)
