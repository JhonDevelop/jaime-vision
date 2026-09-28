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
