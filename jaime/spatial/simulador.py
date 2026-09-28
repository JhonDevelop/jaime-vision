"""Simulador e replay de landmarks — a fase 0/1 inteira roda sem câmera.

Gera mãos sintéticas de 21 pontos na convenção do MediaPipe a partir de quadros-chave (onde o cursor está no HUD,
quão fechada está a pinça, confiança, se a mão está visível) e grava/lê sequências em JSONL. JSONL de landmarks
é o formato de replay dos testes: SÓ landmarks, nunca imagem — dá para gravar uma sessão real e reproduzi-la
nos testes sem guardar nada privado."""
from __future__ import annotations
import json, random
from dataclasses import dataclass
from pathlib import Path
from .core import SpatialCore, SpatialObject, Vec3
from .landmarks import HandPose

PALMA = 0.09        # largura da palma no quadro (≈ mão a 60 cm de uma webcam 720p)


@dataclass(frozen=True)
class Quadro:
    t: float                     # segundos desde o início
    x: float                     # cursor no HUD (0..1), já no referencial espelhado
    y: float
    gap: float                   # razão polegar–indicador / palma (0,1 fechada · 0,6 aberta)
    conf: float = 0.97
    visivel: bool = True
    mao: str = "right"


def mao_sintetica(x_hud: float, y_hud: float, gap: float, palma: float = PALMA, espelhar: bool = True,
                  rng: random.Random | None = None, ruido: float = 0.0) -> list[tuple[float, float, float]]:
    """21 landmarks cujo ponto de mira (meio polegar–indicador) cai em (x_hud, y_hud) e cuja razão de pinça é `gap`."""
    mx = (1.0 - x_hud) if espelhar else x_hud
    my = y_hud
    W = palma
    idx_tip = (mx - gap * W / 2, my)
    thb_tip = (mx + gap * W / 2, my)
    # a mão "pendura" abaixo da ponta do indicador: base do indicador 1 palma abaixo, punho 2 palmas abaixo
    b5 = (idx_tip[0], my + W)
    b17 = (idx_tip[0] + W, my + W)
    b9 = (idx_tip[0] + W / 3, my + W * 0.98)
    b13 = (idx_tip[0] + 2 * W / 3, my + W * 0.97)
    punho = (idx_tip[0] + W / 2, my + 2 * W)
    pts = [None] * 21
    pts[0] = punho
    # polegar: do punho até a ponta, em 4 segmentos
    for i, f in zip((1, 2, 3, 4), (0.25, 0.5, 0.75, 1.0)):
        pts[i] = (punho[0] + (thb_tip[0] - punho[0]) * f, punho[1] + (thb_tip[1] - punho[1]) * f)
    for base, ini in ((5, b5), (9, b9), (13, b13), (17, b17)):
        pts[base] = ini
        topo = idx_tip if base == 5 else (ini[0], ini[1] - W * 0.9)
        for j, f in zip((1, 2, 3), (0.33, 0.66, 1.0)):
            pts[base + j] = (ini[0] + (topo[0] - ini[0]) * f, ini[1] + (topo[1] - ini[1]) * f)
    rng = rng or random.Random(0)
    return [(p[0] + (rng.gauss(0, ruido) if ruido else 0.0), p[1] + (rng.gauss(0, ruido) if ruido else 0.0), 0.0)
            for p in pts]  # type: ignore[index]


def interpolar(quadros: list[Quadro], fps: float = 30.0) -> list[Quadro]:
    """Quadros-chave → um quadro por frame, interpolando posição e pinça linearmente."""
    qs = sorted(quadros, key=lambda q: q.t)
    out: list[Quadro] = []
    passo = 1.0 / fps
    t = qs[0].t
    i = 0
    while t <= qs[-1].t + 1e-9:
        while i + 1 < len(qs) and qs[i + 1].t < t:
            i += 1
        a = qs[i]; b = qs[min(i + 1, len(qs) - 1)]
        f = 0.0 if b.t == a.t else min(1.0, max(0.0, (t - a.t) / (b.t - a.t)))
        lerp = lambda u, v: u + (v - u) * f
        out.append(Quadro(round(t, 4), lerp(a.x, b.x), lerp(a.y, b.y), lerp(a.gap, b.gap), lerp(a.conf, b.conf),
                          a.visivel and b.visivel if f not in (0.0, 1.0) else (a.visivel if f == 0 else b.visivel), a.mao))
        t += passo
    return out


def poses(quadros: list[Quadro], fps: float = 30.0, ruido: float = 0.0, semente: int = 7) -> list[tuple[float, list[HandPose]]]:
    """Sequência de frames: (t, poses visíveis). Várias mãos: quadros com `mao` diferente no mesmo t se somam."""
    rng = random.Random(semente)
    por_mao: dict[str, list[Quadro]] = {}
    for q in quadros:
        por_mao.setdefault(q.mao, []).append(q)
    frames: dict[float, list[HandPose]] = {}
    for mao, qs in por_mao.items():
        for q in interpolar(qs, fps):
            frames.setdefault(q.t, [])
            if q.visivel:
                frames[q.t].append(HandPose(mao_sintetica(q.x, q.y, q.gap, rng=rng, ruido=ruido), mao, q.conf))
    return sorted(frames.items())


# ── cenários prontos (fase 0/1: demo e testes) ──────────────────────────────
def objetos_demo(nomes: list[str] | None = None) -> list[SpatialObject]:
    nomes = (nomes or ["BUB", "SeventyOne", "GearHead", "Oldsen"])[:6]
    n = len(nomes)
    objs = [SpatialObject(f"projeto:{nm.lower()}", "projeto", Vec3(0.2 + 0.6 * i / max(n - 1, 1), 0.35, 0.0), label=nm)
            for i, nm in enumerate(nomes)]
    objs.append(SpatialObject("zona:lixeira", "lixeira", Vec3(0.9, 0.85, 0.0), label="lixeira (virtual)", radius=0.07))
    return objs


def cenario(nome: str, core: SpatialCore | None = None) -> list[Quadro]:
    """Cenários com alvo nos objetos da demo (use `objetos_demo()` na mesma ordem)."""
    a = (0.2, 0.35); b = (0.4, 0.35)
    if core and core.objects:
        objs = [o for o in core.objects.values() if o.kind != "lixeira"]
        if objs:
            a = (objs[0].position.x, objs[0].position.y)
            b = (objs[1].position.x, objs[1].position.y) if len(objs) > 1 else a
    ABERTA, FECHADA = 0.6, 0.12
    if nome == "pinca":       # aproxima de A, agarra, arrasta até embaixo, solta
        return [Quadro(0.0, 0.5, 0.7, ABERTA), Quadro(0.5, *a, ABERTA), Quadro(0.7, *a, ABERTA),
                Quadro(0.8, *a, FECHADA), Quadro(1.1, *a, FECHADA), Quadro(1.8, 0.5, 0.65, FECHADA),
                Quadro(1.9, 0.5, 0.65, ABERTA), Quadro(2.2, 0.5, 0.7, ABERTA)]
    if nome == "clique":      # pinça rápida e parada em B
        return [Quadro(0.0, 0.5, 0.7, ABERTA), Quadro(0.4, *b, ABERTA), Quadro(0.5, *b, FECHADA),
                Quadro(0.7, *b, FECHADA), Quadro(0.75, *b, ABERTA), Quadro(1.0, *b, ABERTA)]
    if nome == "perda":       # agarra A, arrasta e a mão some no meio
        return [Quadro(0.0, *a, ABERTA), Quadro(0.1, *a, FECHADA), Quadro(0.4, *a, FECHADA),
                Quadro(0.7, 0.45, 0.55, FECHADA), Quadro(0.72, 0.45, 0.55, FECHADA, visivel=False),
                Quadro(1.5, 0.45, 0.55, FECHADA, visivel=False)]
    if nome == "parcial":     # fecha até a zona morta da histerese e volta: nada acontece
        return [Quadro(0.0, *a, ABERTA), Quadro(0.3, *a, 0.35), Quadro(0.8, *a, 0.35), Quadro(1.0, *a, ABERTA)]
    if nome == "duas_maos":   # as duas mãos agarram A e se afastam: escala
        return [Quadro(0.0, a[0] - 0.02, a[1], ABERTA, mao="left"), Quadro(0.1, a[0] - 0.02, a[1], FECHADA, mao="left"),
                Quadro(1.2, a[0] - 0.15, a[1], FECHADA, mao="left"), Quadro(1.3, a[0] - 0.15, a[1], ABERTA, mao="left"),
                Quadro(0.0, a[0] + 0.02, a[1], ABERTA, mao="right"), Quadro(0.1, a[0] + 0.02, a[1], FECHADA, mao="right"),
                Quadro(1.2, a[0] + 0.15, a[1], FECHADA, mao="right"), Quadro(1.3, a[0] + 0.15, a[1], ABERTA, mao="right")]
    if nome == "demo":        # pinça + clique, em sequência
        p = cenario("pinca", core); c = cenario("clique", core)
        return p + [Quadro(q.t + 2.4, q.x, q.y, q.gap, q.conf, q.visivel, q.mao) for q in c]
    raise ValueError(f"cenário desconhecido: {nome} (pinca | clique | perda | parcial | duas_maos | demo)")


CENARIOS = ("pinca", "clique", "perda", "parcial", "duas_maos", "demo")


# ── replay (JSONL de landmarks) ─────────────────────────────────────────────
def gravar(frames: list[tuple[float, list[HandPose]]], caminho: Path) -> Path:
    caminho = Path(caminho); caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"formato": "jaime.spatial.landmarks", "v": 1}) + "\n")
        for t, ps in frames:
            f.write(json.dumps({"t": round(t, 4), "maos": [p.to_dict() for p in ps]}) + "\n")
    return caminho


def ler(caminho: Path) -> list[tuple[float, list[HandPose]]]:
    out = []
    with Path(caminho).open(encoding="utf-8") as f:
        cab = json.loads(f.readline() or "{}")
        if cab.get("formato") != "jaime.spatial.landmarks":
            raise ValueError("arquivo não é um replay de landmarks do Jaime")
        for linha in f:
            if not linha.strip():
                continue
            d = json.loads(linha)
            ps = [HandPose([tuple(p) for p in m["lm"]], m.get("hand", "right"), float(m.get("conf", 1.0))) for m in d.get("maos", [])]
            out.append((float(d["t"]), [p for p in ps if p.valida()]))
    return out
