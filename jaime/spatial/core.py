"""Núcleo espacial: objetos virtuais, seleção e eventos. Intenção espacial NÃO executa ação no SO.

Veio do pacote de expansão (commit base 0948e37) e foi adaptado à casa:
- o histórico de eventos é limitado (`deque`): a 30 fps um `list` crescia sem fim e virava vazamento;
- a seleção guarda QUANDO aconteceu, para o resolvedor de "isso" aplicar TTL (fase 2);
- `to_dict()` é o formato que vai ao bus/HUD — IDs e deltas, nunca frames.

Coordenadas: enquanto não há calibração (fase 4/5), `Vec3` é o espaço normalizado do HUD
(x e y em 0..1 da tela do cockpit, z = profundidade relativa). Nunca é metro sem calibração."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field, asdict
from time import monotonic
from typing import Any, Callable
from uuid import uuid4

SCHEMA_VERSION = 1          # versão do contrato de eventos; consumidor antigo ignora tipos desconhecidos
PALAVRAS_ISSO = frozenset({"isso", "esse", "essa", "aqui", "isto", "este", "esta", "aquilo", "aquele", "aquela"})


@dataclass(frozen=True)
class Vec3:
    x: float
    y: float
    z: float

    def distance(self, other: "Vec3") -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2) ** 0.5

    def tupla(self) -> tuple[float, float, float]:
        return (round(self.x, 4), round(self.y, 4), round(self.z, 4))


@dataclass
class SpatialObject:
    id: str
    kind: str
    position: Vec3
    label: str = ""
    display_id: str | None = None
    resource_ref: str | None = None      # um objeto virtual NÃO implica que o arquivo existe (resolver com segurança antes)
    metadata: dict[str, Any] = field(default_factory=dict)
    scale: float = 1.0
    rotation: float = 0.0                # graus, no plano do HUD
    owner: str = "joao"
    radius: float = 0.06                 # raio de acerto no espaço normalizado do HUD

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "label": self.label or self.id, "pos": self.position.tupla(),
                "display_id": self.display_id, "resource_ref": self.resource_ref, "scale": round(self.scale, 3),
                "rotation": round(self.rotation, 1), "radius": self.radius}


@dataclass(frozen=True)
class SpatialEvent:
    kind: str
    object_id: str | None
    actor: str
    timestamp: float
    confidence: float
    data: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex[:12])

    def to_dict(self) -> dict:
        d = {"id": self.id, "kind": self.kind, "object_id": self.object_id, "actor": self.actor,
             "confidence": round(self.confidence, 3), "v": SCHEMA_VERSION}
        if self.data:
            d["data"] = self.data
        return d


@dataclass
class Selecao:
    object_id: str
    quando: float
    confianca: float
    origem: str = "gesto"       # gesto | voz | hud | ferramenta


class SpatialCore:
    def __init__(self, max_eventos: int = 512, relogio: Callable[[], float] = monotonic):
        self.objects: dict[str, SpatialObject] = {}
        self.selected: dict[str, str] = {}                  # actor → object_id (compatível com o pacote)
        self.selecoes: dict[str, deque[Selecao]] = {}       # actor → últimas seleções (para "esses" e TTL)
        self.events: deque[SpatialEvent] = deque(maxlen=max_eventos)
        self.relogio = relogio
        self.versao = 0                                    # sobe a cada mudança de cena (HUD reconstrói por ela)

    # ── objetos ─────────────────────────────────────
    def add(self, obj: SpatialObject) -> None:
        if obj.id in self.objects:
            raise ValueError("duplicate spatial object")
        self.objects[obj.id] = obj; self.versao += 1

    def remove(self, object_id: str) -> SpatialObject | None:
        obj = self.objects.pop(object_id, None)
        if obj:
            self.versao += 1
            for actor, oid in list(self.selected.items()):
                if oid == object_id:
                    self.selected.pop(actor, None)
            for fila in self.selecoes.values():
                for s in [s for s in fila if s.object_id == object_id]:
                    fila.remove(s)
        return obj

    def move(self, object_id: str, pos: Vec3) -> None:
        obj = self.objects[object_id]
        obj.position = Vec3(min(1.0, max(0.0, pos.x)), min(1.0, max(0.0, pos.y)), pos.z)
        self.versao += 1

    def cena(self) -> dict:
        return {"versao": self.versao, "objetos": [o.to_dict() for o in self.objects.values()],
                "selecionado": dict(self.selected)}

    # ── seleção ─────────────────────────────────────
    def select(self, actor: str, object_id: str, confidence: float = 1.0, origem: str = "gesto") -> SpatialEvent:
        if object_id not in self.objects:
            raise KeyError(object_id)
        self.selected[actor] = object_id
        fila = self.selecoes.setdefault(actor, deque(maxlen=8))
        fila.append(Selecao(object_id, self.relogio(), confidence, origem))
        return self.emit("spatial.select", actor, object_id, confidence, origem=origem)

    def deselect(self, actor: str) -> SpatialEvent | None:
        oid = self.selected.pop(actor, None)
        return self.emit("spatial.deselect", actor, oid) if oid else None

    def resolve(self, actor: str, word: str) -> SpatialObject | None:
        """Resolução mínima (a do pacote). A fase 2 usa `referencias.Resolvedor`, com TTL e ambiguidade."""
        if word.lower().strip() not in PALAVRAS_ISSO:
            return None
        return self.objects.get(self.selected.get(actor, ""))

    # ── eventos ─────────────────────────────────────
    def emit(self, kind: str, actor: str, object_id: str | None = None,
             confidence: float = 1.0, **data: Any) -> SpatialEvent:
        if not 0 <= confidence <= 1:
            raise ValueError("confidence out of range")
        evt = SpatialEvent(kind, object_id, actor, self.relogio(), confidence, data)
        self.events.append(evt)
        return evt


def objeto_de_dict(d: dict) -> SpatialObject:
    """Para criar objetos a partir do HUD/ferramenta, validando o mínimo."""
    pos = d.get("pos") or d.get("position") or (0.5, 0.5, 0.0)
    if len(pos) == 2:
        pos = (*pos, 0.0)
    oid = str(d.get("id") or uuid4().hex[:8])[:64]
    return SpatialObject(oid, str(d.get("kind") or "nota")[:32], Vec3(*(float(p) for p in pos)),
                         label=str(d.get("label") or "")[:80], resource_ref=d.get("resource_ref"),
                         radius=float(d.get("radius") or 0.06))


__all__ = ["SpatialCore", "SpatialEvent", "SpatialObject", "Vec3", "Selecao", "objeto_de_dict", "asdict"]
