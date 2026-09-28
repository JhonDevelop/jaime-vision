"""Expansão espacial do J.A.I.M.E — gestos, cena virtual, voz contextual e (por fases) ações no SO.

Desligada por padrão (`JAIME_SPATIAL=off`). Veja docs/ESPACIAL.md. Nada aqui age no computador sozinho:
efeitos reais passam por `acoes.py` → política → Vigia → recibo/Undo, e começam em dry-run."""
from .core import SpatialCore, SpatialEvent, SpatialObject, Vec3

__all__ = ["SpatialCore", "SpatialEvent", "SpatialObject", "Vec3"]
