"""Monitores: descoberta, geometria lógica, impressão digital do layout e hotplug (fase 4).

Pixel LÓGICO é o que a API de janelas/cursor do SO usa: pontos no macOS (um Retina 2560×1600 é 1280×800 pontos,
escala 2), pixels com DPI-awareness por monitor no Windows. `pyautogui.size()` só enxerga o principal — por isso
este módulo existe. Monitores com escalas diferentes convivem no mesmo espaço global de coordenadas.

Backends: macOS (Quartz/pyobjc — já instalado no .venv do João), Windows (ctypes, sem dependência), Linux
(xrandr). Sem backend: lista vazia e ações de janela ficam suspensas (nunca "adivinha" a geometria).

Mudou o layout (plugou/desplugou, girou, mudou escala/resolução, espelhou) → evento `workspace.displays_changed`
e as ações no SO ficam suspensas até a próxima validação (`VigiaTelas.suspenso`)."""
from __future__ import annotations
import hashlib, platform, re, shutil, subprocess, time
from dataclasses import dataclass, asdict
from typing import Callable


@dataclass(frozen=True)
class Display:
    id: str                    # estável entre boots: hash de fabricante/modelo/unidade (nunca o serial cru)
    nome: str
    x: int                     # origem no espaço global LÓGICO do SO
    y: int
    largura: int               # em unidades lógicas
    altura: int
    escala: float = 1.0        # pixels físicos por unidade lógica
    rotacao: int = 0
    principal: bool = False
    embutido: bool = False

    def contem(self, x: float, y: float) -> bool:
        return self.x <= x < self.x + self.largura and self.y <= y < self.y + self.altura

    def centro(self) -> tuple[int, int]:
        return (self.x + self.largura // 2, self.y + self.altura // 2)

    def to_dict(self) -> dict:
        return asdict(self)


def _id(*partes) -> str:
    return hashlib.sha1("|".join(str(p) for p in partes).encode()).hexdigest()[:10]


# ── backends ─────────────────────────────────────────────────────────────────
def _macos() -> list[Display]:
    import Quartz  # pyobjc-framework-Quartz
    err, ids, n = Quartz.CGGetActiveDisplayList(16, None, None)
    if err:
        return []
    out = []
    for i, did in enumerate(ids[:n]):
        b = Quartz.CGDisplayBounds(did)
        w, h = int(b.size.width), int(b.size.height)
        px = Quartz.CGDisplayPixelsWide(did)
        modo = Quartz.CGDisplayCopyDisplayMode(did)
        if modo is not None:
            px = Quartz.CGDisplayModeGetPixelWidth(modo) or px
        escala = round(px / w, 2) if w else 1.0
        ident = _id(Quartz.CGDisplayVendorNumber(did), Quartz.CGDisplayModelNumber(did), Quartz.CGDisplayUnitNumber(did),
                    Quartz.CGDisplaySerialNumber(did))
        embutido = bool(Quartz.CGDisplayIsBuiltin(did))
        out.append(Display(ident, "embutido" if embutido else f"externo {i}", int(b.origin.x), int(b.origin.y), w, h,
                           escala, int(Quartz.CGDisplayRotation(did)), bool(Quartz.CGDisplayIsMain(did)), embutido))
    return out


def _windows() -> list[Display]:
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)      # por monitor: coordenadas reais em telas de escala mista
    except Exception:
        pass

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]
    out: list[Display] = []
    Proc = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def cb(hmon, hdc, rect, data):
        mi = MONITORINFOEXW(); mi.cbSize = ctypes.sizeof(MONITORINFOEXW)
        user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
        r = mi.rcMonitor
        dx, dy = ctypes.c_uint(), ctypes.c_uint()
        try:
            ctypes.windll.shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(dx), ctypes.byref(dy))
            escala = round(dx.value / 96, 2)
        except Exception:
            escala = 1.0
        out.append(Display(_id(mi.szDevice, r.right - r.left, r.bottom - r.top), mi.szDevice, r.left, r.top,
                           r.right - r.left, r.bottom - r.top, escala, 0, bool(mi.dwFlags & 1), False))
        return 1
    user32.EnumDisplayMonitors(None, None, Proc(cb), 0)
    return out


def _linux() -> list[Display]:
    if not shutil.which("xrandr"):
        return []
    r = subprocess.run(["xrandr", "--listmonitors"], capture_output=True, text=True, timeout=5)
    out = []
    for linha in r.stdout.splitlines()[1:]:
        m = re.search(r"(\d+):\s+\+?(\*?)(\S+)\s+(\d+)/\d+x(\d+)/\d+\+(-?\d+)\+(-?\d+)\s+(\S+)", linha)
        if m:
            _, prim, nome, w, h, x, y, saida = m.groups()
            out.append(Display(_id(saida, w, h), saida, int(x), int(y), int(w), int(h), 1.0, 0, prim == "*", saida.startswith("eDP")))
    return out


def listar(backend: Callable[[], list[Display]] | None = None) -> tuple[list[Display], str]:
    """(monitores, backend usado). Erro de backend vira lista vazia + motivo — nunca geometria inventada."""
    if backend is not None:
        return backend(), "injetado"
    so = platform.system()
    try:
        if so == "Darwin":
            return _macos(), "quartz"
        if so == "Windows":
            return _windows(), "win32"
        if so == "Linux":
            return _linux(), "xrandr"
    except Exception as e:
        return [], f"{so}: {type(e).__name__}: {str(e)[:80]}"
    return [], f"sem backend para {so}"


def impressao(displays: list[Display]) -> str:
    """Impressão digital do layout: qualquer mudança de conjunto, posição, tamanho, escala ou rotação muda o hash."""
    chave = sorted((d.id, d.x, d.y, d.largura, d.altura, d.escala, d.rotacao) for d in displays)
    return hashlib.sha1(repr(chave).encode()).hexdigest()[:12]


def display_em(displays: list[Display], x: float, y: float) -> Display | None:
    return next((d for d in displays if d.contem(x, y)), None)


def espelhados(displays: list[Display]) -> bool:
    vistos = set()
    for d in displays:
        k = (d.x, d.y, d.largura, d.altura)
        if k in vistos:
            return True
        vistos.add(k)
    return False


class VigiaTelas:
    """Observa o layout. Mudança → suspende ações de SO até `validar()` (o João confirma o apontamento)."""
    def __init__(self, backend: Callable[[], list[Display]] | None = None, ao_mudar: Callable[[dict], None] | None = None,
                 relogio: Callable[[], float] = time.monotonic):
        self.backend, self.ao_mudar, self.relogio = backend, ao_mudar, relogio
        self.displays, self.origem = listar(backend)
        self.hash = impressao(self.displays)
        self.suspenso = "" if self.displays else f"sem geometria de monitores ({self.origem})"
        self.mudancas = 0

    def checar(self) -> dict | None:
        novos, origem = listar(self.backend)
        h = impressao(novos)
        if h == self.hash:
            return None
        antes = {d.id for d in self.displays}; depois = {d.id for d in novos}
        evento = {"evento": "workspace.displays_changed", "entrou": sorted(depois - antes), "saiu": sorted(antes - depois),
                  "hash_antes": self.hash, "hash_depois": h, "espelhado": espelhados(novos), "total": len(novos)}
        self.displays, self.origem, self.hash = novos, origem, h
        self.mudancas += 1
        self.suspenso = "layout de monitores mudou — ações no SO suspensas até validar o apontamento"
        if self.ao_mudar:
            self.ao_mudar(evento)
        return evento

    def validar(self) -> None:
        if self.displays:
            self.suspenso = ""

    def estado(self) -> dict:
        return {"backend": self.origem, "hash": self.hash, "suspenso": self.suspenso,
                "displays": [d.to_dict() for d in self.displays]}


# ── alvo por monitor ("manda essa janela para o monitor da direita") ─────────
def escolher(displays: list[Display], qual: str, referencia: Display | None = None) -> Display | None:
    """qual: id | 'principal' | 'embutido' | 'direita' | 'esquerda' | 'cima' | 'baixo' (relativo à `referencia`)."""
    if not displays:
        return None
    q = (qual or "").strip().lower()
    por_id = next((d for d in displays if d.id == q or d.nome.lower() == q), None)
    if por_id:
        return por_id
    if q in ("principal", "main"):
        return next((d for d in displays if d.principal), displays[0])
    if q in ("embutido", "notebook", "do notebook"):
        return next((d for d in displays if d.embutido), None)
    ref = referencia or next((d for d in displays if d.principal), displays[0])
    cx, cy = ref.centro()
    eixo = {"direita": (1, 0), "esquerda": (-1, 0), "baixo": (0, 1), "cima": (0, -1)}.get(q)
    if not eixo:
        return None
    cands = []
    for d in displays:
        if d.id == ref.id:
            continue
        dx, dy = d.centro()[0] - cx, d.centro()[1] - cy
        proj = dx * eixo[0] + dy * eixo[1]
        perp = abs(dx * eixo[1]) + abs(dy * eixo[0])
        if proj > 0 and proj >= perp:          # "da direita" tem de estar MAIS à direita do que acima/abaixo
            cands.append((proj, d))
    return min(cands, key=lambda c: c[0])[1] if cands else None


def destino_janela(janela: tuple[int, int, int, int], origem: Display | None, destino: Display) -> tuple[int, int]:
    """Mantém a posição RELATIVA da janela ao trocar de monitor (escala mista: a conta é em unidades lógicas,
    que é o que a API de janelas usa) e garante que o canto fique dentro da tela de destino."""
    x, y, w, h = janela
    if origem:
        fx = (x - origem.x) / max(origem.largura, 1); fy = (y - origem.y) / max(origem.altura, 1)
    else:
        fx = fy = 0.1
    nx = destino.x + int(fx * destino.largura); ny = destino.y + int(fy * destino.altura)
    nx = min(max(nx, destino.x), destino.x + max(destino.largura - min(w, destino.largura), 0))
    ny = min(max(ny, destino.y), destino.y + max(destino.altura - min(h, destino.altura), 0))
    return nx, ny


# ── calibração física (monitor no espaço da sala, em metros) ────────────────
def salvar_calibracao(caminho, displays: list[Display], planos: dict) -> None:
    """planos: display_id → {"origem": [x,y,z], "direita": [x,y,z], "baixo": [x,y,z]} (metros, vetores do plano).
    Guarda junto a impressão do layout: calibração de outro layout não vale."""
    import json
    from pathlib import Path
    p = Path(caminho).expanduser(); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"v": 1, "layout": impressao(displays), "planos": planos}, indent=1), encoding="utf-8")


def carregar_calibracao(caminho, displays: list[Display]) -> tuple[dict, str]:
    """(DisplayPlane por id, motivo_se_inválida)."""
    import json
    from pathlib import Path
    from .core import Vec3
    from .geometry import DisplayPlane
    p = Path(caminho).expanduser() if caminho else None
    if not p or not p.exists():
        return {}, "sem arquivo de calibração"
    d = json.loads(p.read_text(encoding="utf-8"))
    if d.get("layout") != impressao(displays):
        return {}, "calibração é de outro layout de monitores — recalibrar"
    por_id = {x.id: x for x in displays}
    out = {}
    for did, pl in d.get("planos", {}).items():
        if did in por_id:
            disp = por_id[did]
            out[did] = DisplayPlane(did, Vec3(*pl["origem"]), Vec3(*pl["direita"]), Vec3(*pl["baixo"]),
                                    (disp.x, disp.y, disp.largura, disp.altura))
    return out, ""
