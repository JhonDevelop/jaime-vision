"""Fase 6 — Air Canvas: traços versionados → formas SUGERIDAS → nós/arestas confirmados → grafo semântico.

- Desenhar é um MODO explícito (voz "modo desenho" / HUD); fora dele, mexer o dedo não risca nada.
- Um traço é (x, y, z, t, confiança) com id, plano, autor e versão. Tudo é versionado com Undo.
- Reconhecer círculo/retângulo/linha/seta é SUGESTÃO até o João rotular ("isso é o banco de dados"): só então
  vira objeto da cena (nó) ou relação (aresta) com a evidência de onde veio.
- Exporta JSON versionado e Mermaid; "isso aguenta 100 mil usuários?" recebe o GRAFO e as premissas, não um print.
"""
from __future__ import annotations
import json, math
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4
from .core import SpatialCore, SpatialObject, Vec3
from .scene import SceneGraph

Pt = tuple[float, float, float, float, float]      # x, y, z, t, confiança


@dataclass
class Traco:
    id: str
    pontos: list[Pt]
    autor: str = "joao"
    plano: str = "hud"
    versao: int = 1

    def xy(self) -> list[tuple[float, float]]:
        return [(p[0], p[1]) for p in self.pontos]

    def to_dict(self) -> dict:
        return {"id": self.id, "autor": self.autor, "plano": self.plano, "versao": self.versao,
                "pontos": [[round(c, 4) for c in p] for p in self.pontos]}


@dataclass
class Sugestao:
    traco_id: str
    forma: str                      # circulo | retangulo | linha | seta | livre
    confianca: float
    centro: tuple[float, float]
    tamanho: float
    de: tuple[float, float] | None = None       # linhas/setas
    para: tuple[float, float] | None = None
    id: str = field(default_factory=lambda: uuid4().hex[:8])


def _comprimento(xy) -> float:
    return sum(math.dist(xy[i], xy[i + 1]) for i in range(len(xy) - 1))


def _angulos_fortes(xy, limiar_graus: float = 55) -> int:
    """Quantas quinas: mudança de direção grande entre segmentos reamostrados."""
    pts = _reamostrar(xy, 32)
    quinas, ultimo = 0, -99
    for i in range(2, len(pts) - 2):
        a = math.atan2(pts[i][1] - pts[i - 2][1], pts[i][0] - pts[i - 2][0])
        b = math.atan2(pts[i + 2][1] - pts[i][1], pts[i + 2][0] - pts[i][0])
        d = abs((b - a + math.pi) % (2 * math.pi) - math.pi)
        if math.degrees(d) > limiar_graus and i - ultimo > 3:
            quinas += 1; ultimo = i
    return quinas


def _reamostrar(xy, n: int):
    total = _comprimento(xy)
    if total == 0:
        return [xy[0]] * n
    passo = total / (n - 1); out = [xy[0]]; acum = 0.0; i = 0; prev = xy[0]
    while len(out) < n - 1 and i < len(xy) - 1:
        seg = math.dist(prev, xy[i + 1])
        if acum + seg >= passo and seg > 0:
            f = (passo - acum) / seg
            novo = (prev[0] + (xy[i + 1][0] - prev[0]) * f, prev[1] + (xy[i + 1][1] - prev[1]) * f)
            out.append(novo); prev = novo; acum = 0.0
        else:
            acum += seg; prev = xy[i + 1]; i += 1
    out.append(xy[-1])
    return out


def reconhecer(t: Traco) -> Sugestao:
    xy = t.xy()
    if len(xy) < 4:
        return Sugestao(t.id, "livre", 0.0, xy[0] if xy else (0, 0), 0.0)
    comp = _comprimento(xy)
    cx = sum(p[0] for p in xy) / len(xy); cy = sum(p[1] for p in xy) / len(xy)
    xs = [p[0] for p in xy]; ys = [p[1] for p in xy]
    diag = math.dist((min(xs), min(ys)), (max(xs), max(ys))) or 1e-9
    fechado = math.dist(xy[0], xy[-1]) < 0.2 * diag
    reta = math.dist(xy[0], xy[-1]) / comp if comp else 0
    if reta > 0.93:
        return Sugestao(t.id, "linha", round(min(1.0, (reta - 0.93) / 0.07 * 0.5 + 0.5), 2), (cx, cy), comp, xy[0], xy[-1])
    if fechado:
        raios = [math.dist(p, (cx, cy)) for p in xy]
        m = sum(raios) / len(raios)
        cv = (sum((r - m) ** 2 for r in raios) / len(raios)) ** 0.5 / (m or 1e-9)
        quinas = _angulos_fortes(xy)
        if 3 <= quinas <= 5 and cv > 0.06:
            return Sugestao(t.id, "retangulo", round(max(0.5, 1 - abs(quinas - 4) * 0.2), 2), (cx, cy), diag)
        if cv < 0.12:
            return Sugestao(t.id, "circulo", round(max(0.5, 1 - cv * 4), 2), (cx, cy), 2 * m)
    # seta: quase-reta até uma ponta onde volta em "V"
    pts = _reamostrar(xy, 40)
    corpo = pts[:28]
    if _comprimento(corpo) and math.dist(corpo[0], corpo[-1]) / _comprimento(corpo) > 0.93 and _angulos_fortes(pts) >= 1:
        return Sugestao(t.id, "seta", 0.6, (cx, cy), comp, corpo[0], corpo[-1])
    return Sugestao(t.id, "livre", 0.3, (cx, cy), diag)


class Canvas:
    def __init__(self, core: SpatialCore):
        self.core = core
        self.grafo = SceneGraph(core)
        self.tracos: dict[str, Traco] = {}
        self.sugestoes: dict[str, Sugestao] = {}
        self.modo_desenho = False
        self.versao = 0
        self._aberto: Traco | None = None
        self._historico: list[tuple[str, object]] = []     # para Undo: ("traco"|"no"|"aresta", dado)

    # ── desenho ────────────────────────────────────────
    def ligar(self, on: bool = True) -> None:
        self.modo_desenho = on
        if not on:
            self._aberto = None

    def ponto(self, x: float, y: float, t: float, conf: float = 1.0, z: float = 0.0, autor: str = "joao") -> None:
        if not self.modo_desenho or conf < 0.65:
            return
        if self._aberto is None:
            self._aberto = Traco(uuid4().hex[:8], [], autor)
        self._aberto.pontos.append((x, y, z, t, conf))

    def fechar_traco(self) -> Sugestao | None:
        tr, self._aberto = self._aberto, None
        if not tr or len(tr.pontos) < 2:
            return None
        return self.adicionar_traco(tr)

    def adicionar_traco(self, tr: Traco) -> Sugestao:
        self.tracos[tr.id] = tr; self.versao += 1; tr.versao = self.versao
        s = reconhecer(tr)
        self.sugestoes[s.id] = s
        self._historico.append(("traco", tr.id))
        return s

    # ── confirmação: sugestão → nó/aresta ──────────────
    def confirmar_no(self, sugestao_id: str, rotulo: str, tipo: str = "componente", fonte: str = "voz") -> SpatialObject:
        s = self.sugestoes.pop(sugestao_id)
        if s.forma not in ("circulo", "retangulo", "livre"):
            raise ValueError("nó vem de forma fechada")
        oid = f"no:{rotulo.lower().replace(' ', '-')}"[:48]
        base = oid; n = 2
        while oid in self.core.objects:
            oid = f"{base}-{n}"; n += 1
        o = SpatialObject(oid, tipo, Vec3(s.centro[0], s.centro[1], 0.0), label=rotulo,
                          metadata={"forma": s.forma, "traco": s.traco_id, "fonte": fonte}, radius=max(0.03, s.tamanho / 2))
        self.core.add(o); self.versao += 1
        self._historico.append(("no", oid))
        return o

    def _no_perto(self, p: tuple[float, float]) -> SpatialObject | None:
        cands = [(math.dist(p, (o.position.x, o.position.y)) - o.radius, o) for o in self.core.objects.values()
                 if o.id.startswith("no:")]
        cands = [c for c in cands if c[0] <= 0.06]
        return min(cands, key=lambda c: c[0])[1] if cands else None

    def sugerir_aresta(self, sugestao_id: str) -> tuple[str, str] | None:
        s = self.sugestoes.get(sugestao_id)
        if not s or s.forma not in ("linha", "seta") or not s.de or not s.para:
            return None
        a, b = self._no_perto(s.de), self._no_perto(s.para)
        return (a.id, b.id) if a and b and a.id != b.id else None

    def confirmar_aresta(self, sugestao_id: str, relacao: str, fonte: str = "voz"):
        par = self.sugerir_aresta(sugestao_id)
        if not par:
            raise ValueError("o traço não liga dois nós")
        s = self.sugestoes.pop(sugestao_id)
        e = self.grafo.link(par[0], par[1], relacao, f"desenho:{s.traco_id}+confirmação:{fonte}")
        self.versao += 1
        self._historico.append(("aresta", e))
        return e

    def desfazer(self) -> str:
        if not self._historico:
            return "nada a desfazer"
        tipo, dado = self._historico.pop()
        if tipo == "traco":
            self.tracos.pop(dado, None)
            for k in [k for k, s in self.sugestoes.items() if s.traco_id == dado]:
                self.sugestoes.pop(k)
        elif tipo == "no":
            self.core.remove(dado)
            self.grafo.edges = {e for e in self.grafo.edges if dado not in (e.source, e.target)}
        elif tipo == "aresta":
            self.grafo.edges.discard(dado)
        self.versao += 1
        return f"desfeito: {tipo}"

    # ── exportar / reabrir ─────────────────────────────
    def exportar(self) -> dict:
        nos = [o for o in self.core.objects.values() if o.id.startswith("no:")]
        return {"formato": "jaime.spatial.canvas", "v": 1, "versao": self.versao,
                "nos": [{**o.to_dict(), "metadata": o.metadata} for o in nos],
                "arestas": self.grafo.snapshot()["edges"],
                "tracos": [t.to_dict() for t in self.tracos.values()]}

    def salvar(self, caminho) -> Path:
        p = Path(caminho).expanduser(); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.exportar(), ensure_ascii=False, indent=1), encoding="utf-8")
        return p

    @classmethod
    def abrir(cls, caminho, core: SpatialCore | None = None) -> "Canvas":
        d = json.loads(Path(caminho).expanduser().read_text(encoding="utf-8"))
        if d.get("formato") != "jaime.spatial.canvas":
            raise ValueError("não é um canvas do Jaime")
        c = cls(core or SpatialCore())
        for n in d["nos"]:
            c.core.add(SpatialObject(n["id"], n["kind"], Vec3(*n["pos"]), label=n["label"], metadata=n.get("metadata", {}),
                                     radius=n.get("radius", 0.06)))
        for e in d["arestas"]:
            c.grafo.link(e["source"], e["target"], e["relation"], e["evidence"])
        for t in d.get("tracos", []):
            c.tracos[t["id"]] = Traco(t["id"], [tuple(p) for p in t["pontos"]], t.get("autor", "joao"), t.get("plano", "hud"), t.get("versao", 1))
        c.versao = d.get("versao", 0)
        return c

    def mermaid(self) -> str:
        nos = [o for o in self.core.objects.values() if o.id.startswith("no:")]
        ident = {o.id: f"n{i}" for i, o in enumerate(nos)}
        linhas = ["flowchart LR"]
        for o in nos:
            forma = ("((", "))") if o.metadata.get("forma") == "circulo" else ("[", "]")
            rot = (o.label or o.id).replace('"', "'")
            linhas.append(f'  {ident[o.id]}{forma[0]}"{rot}"{forma[1]}')
        for e in self.grafo.snapshot()["edges"]:
            if e["source"] in ident and e["target"] in ident:
                linhas.append(f'  {ident[e["source"]]} -->|"{e["relation"]}"| {ident[e["target"]]}')
        return "\n".join(linhas)

    def para_raciocinio(self, pergunta: str) -> str:
        """O que vai ao cérebro quando o João pergunta sobre o desenho: grafo + premissas, não pixels."""
        return (f"Pergunta do João sobre o diagrama desenhado no ar: {pergunta}\n"
                f"Grafo (confirmado por ele, versão {self.versao}):\n{self.mermaid()}\n"
                "Premissas: só os nós e relações acima foram confirmados; o que não está aqui é suposição — diga quais "
                "números (usuários, requisições/s, tamanho de dados) você está assumindo.")
