"""Relações semânticas de uma cena. Sem acesso ao filesystem."""
from __future__ import annotations
from dataclasses import dataclass
from .core import SpatialCore

@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    relation: str
    evidence: str

class SceneGraph:
    def __init__(self, core: SpatialCore):
        self.core = core
        self.edges: set[Edge] = set()
        self.version = 0

    def link(self, source: str, target: str, relation: str, evidence: str) -> Edge:
        if source not in self.core.objects or target not in self.core.objects:
            raise KeyError("node missing")
        if not relation or not evidence or source == target:
            raise ValueError("relation and evidence required; self link forbidden")
        edge=Edge(source,target,relation,evidence)
        self.edges.add(edge); self.version += 1
        return edge

    def snapshot(self) -> dict:
        return {"version": self.version,
                "nodes": [{"id": o.id, "kind": o.kind, "label": o.label}
                          for o in self.core.objects.values()],
                "edges": [{"source": e.source, "target": e.target,
                           "relation": e.relation, "evidence": e.evidence}
                          for e in sorted(self.edges, key=lambda x:(x.source,x.target,x.relation))]}
