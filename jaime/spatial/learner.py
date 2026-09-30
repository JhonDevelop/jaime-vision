"""Aprendizado pessoal por exemplos positivos e negativos, sem vídeo bruto."""
from __future__ import annotations
from dataclasses import dataclass, field
from math import inf

Point = tuple[float, ...]

def normalize(points: list[Point], steps: int = 24) -> tuple[Point, ...]:
    if len(points) < 2 or steps < 2:
        raise ValueError("gesture needs at least two samples")
    dims = len(points[0])
    if not dims or any(len(p) != dims for p in points):
        raise ValueError("inconsistent dimensions")
    origin = points[0]
    scale = max(max(abs(p[d] - origin[d]) for p in points) for d in range(dims)) or 1.0
    centered = [tuple((p[d] - origin[d]) / scale for d in range(dims)) for p in points]
    out = []
    for i in range(steps):
        pos = i * (len(points) - 1) / (steps - 1)
        lo = int(pos); hi = min(lo + 1, len(points)-1); t = pos-lo
        out.append(tuple(centered[lo][d]*(1-t)+centered[hi][d]*t for d in range(dims)))
    return tuple(out)

def dtw(a: tuple[Point, ...], b: tuple[Point, ...]) -> float:
    if not a or not b or len(a[0]) != len(b[0]):
        raise ValueError("invalid gesture")
    old = [inf] * (len(b)+1); old[0] = 0
    for x in a:
        new = [inf] * (len(b)+1)
        for j, y in enumerate(b, 1):
            distance = sum((u-v)**2 for u,v in zip(x,y)) ** .5
            new[j] = distance + min(new[j-1], old[j], old[j-1])
        old = new
    return old[-1] / max(len(a), len(b))

@dataclass
class GestureLibrary:
    positives: dict[str, list[tuple[Point, ...]]] = field(default_factory=dict)
    negatives: dict[str, list[tuple[Point, ...]]] = field(default_factory=dict)
    threshold: float = .14
    margin: float = .06

    def teach(self, name: str, samples: list[list[Point]], negative: bool = False) -> None:
        if not name or len(samples) < 3:
            raise ValueError("name and at least three demonstrations required")
        dest = self.negatives if negative else self.positives
        dest.setdefault(name, []).extend(normalize(s) for s in samples)

    def recognize(self, points: list[Point], context: set[str] | None = None) -> tuple[str | None, float]:
        item = normalize(points)
        scores = sorted((min(dtw(item, x) for x in examples), name)
                        for name, examples in self.positives.items()
                        if examples and (context is None or name in context))
        if not scores:
            return None, 0.0
        best, name = scores[0]
        runner = scores[1][0] if len(scores) > 1 else inf
        negative = min((dtw(item, n) for n in self.negatives.get(name, [])), default=inf)
        if best > self.threshold or runner-best < self.margin or negative-best < self.margin:
            return None, 0.0
        return name, max(0.0, 1.0-best/self.threshold)
