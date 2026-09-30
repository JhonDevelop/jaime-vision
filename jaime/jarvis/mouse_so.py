"""O mouse de verdade do sistema (fora do navegador): mover, apertar, soltar, clicar, rolar.

- macOS: Quartz (CGEvent) — já instalado no .venv do João (pyobjc). Exige que o Python do Jaime tenha permissão de
  **Acessibilidade** (Ajustes do Sistema › Privacidade e Segurança › Acessibilidade); sem ela o macOS ignora os
  eventos em silêncio, por isso `permitido()` pergunta antes e o controle fica em ensaio;
- Windows: user32 via ctypes (SetCursorPos, mouse_event) — sem dependência;
- resto: pyautogui, se existir.
`rolar(dy)`: dy > 0 rola para CIMA (como girar a roda para a frente). Coordenadas em pontos LÓGICOS no espaço global de todas as telas (o que o Quartz/Win32 usam). `area()` devolve a
união das telas, para a mão alcançar os dois monitores.
"""
from __future__ import annotations
import platform


class MouseNulo:
    """Dublê: registra o que faria (testes e ensaio)."""
    nome = "nulo"

    def __init__(self, area=(0, 0, 1920, 1080)):
        self._area = area
        self.log: list[tuple] = []
        self.pos = (area[0] + area[2] / 2, area[1] + area[3] / 2)

    def permitido(self) -> bool:
        return True

    def area(self) -> tuple[float, float, float, float]:
        return self._area

    def mover(self, x, y, arrastando=False):
        self.pos = (x, y); self.log.append(("mover", round(x), round(y), arrastando))

    def apertar(self, botao="esquerdo", cliques=1):
        self.log.append(("apertar", botao, cliques))

    def soltar(self, botao="esquerdo", cliques=1):
        self.log.append(("soltar", botao, cliques))

    def rolar(self, dy, dx=0):
        self.log.append(("rolar", round(dy), round(dx)))


class MouseMac:
    nome = "quartz"

    def __init__(self):
        import Quartz  # noqa: F401  (pyobjc; falha cedo se não houver)
        self.Q = Quartz
        self.pos = self._pos_atual()

    def _pos_atual(self):
        ev = self.Q.CGEventCreate(None)
        p = self.Q.CGEventGetLocation(ev)
        return (p.x, p.y)

    def permitido(self) -> bool:
        try:
            from ApplicationServices import AXIsProcessTrusted
            return bool(AXIsProcessTrusted())
        except Exception:
            return True       # sem como saber: tenta; o HUD mostra se o cursor não se mexer

    def area(self):
        Q = self.Q
        err, ids, n = Q.CGGetActiveDisplayList(16, None, None)
        caixas = [Q.CGDisplayBounds(i) for i in (ids or [])[:n]] or [Q.CGDisplayBounds(Q.CGMainDisplayID())]
        x0 = min(b.origin.x for b in caixas); y0 = min(b.origin.y for b in caixas)
        x1 = max(b.origin.x + b.size.width for b in caixas); y1 = max(b.origin.y + b.size.height for b in caixas)
        return (x0, y0, x1 - x0, y1 - y0)

    def _evento(self, tipo, botao, cliques=1):
        Q = self.Q
        ev = Q.CGEventCreateMouseEvent(None, tipo, self.pos, botao)
        if cliques > 1:
            Q.CGEventSetIntegerValueField(ev, Q.kCGMouseEventClickState, cliques)
        Q.CGEventPost(Q.kCGHIDEventTap, ev)

    def mover(self, x, y, arrastando=False):
        Q = self.Q
        self.pos = (x, y)
        self._evento(Q.kCGEventLeftMouseDragged if arrastando else Q.kCGEventMouseMoved, Q.kCGMouseButtonLeft)

    def apertar(self, botao="esquerdo", cliques=1):
        Q = self.Q
        if botao == "direito":
            self._evento(Q.kCGEventRightMouseDown, Q.kCGMouseButtonRight, cliques)
        else:
            self._evento(Q.kCGEventLeftMouseDown, Q.kCGMouseButtonLeft, cliques)

    def soltar(self, botao="esquerdo", cliques=1):
        Q = self.Q
        if botao == "direito":
            self._evento(Q.kCGEventRightMouseUp, Q.kCGMouseButtonRight, cliques)
        else:
            self._evento(Q.kCGEventLeftMouseUp, Q.kCGMouseButtonLeft, cliques)

    def rolar(self, dy, dx=0):
        Q = self.Q
        ev = Q.CGEventCreateScrollWheelEvent(None, Q.kCGScrollEventUnitPixel, 2, int(dy), int(dx))
        Q.CGEventPost(Q.kCGHIDEventTap, ev)


class MouseWindows:
    nome = "win32"

    def __init__(self):
        import ctypes
        self.u = ctypes.windll.user32
        try:
            self.u.SetProcessDPIAware()
        except Exception:
            pass
        self.pos = (0, 0)

    def permitido(self) -> bool:
        return True

    def area(self):
        g = self.u.GetSystemMetrics
        return (g(76), g(77), g(78), g(79))      # tela virtual: todas as telas

    def mover(self, x, y, arrastando=False):
        self.pos = (x, y); self.u.SetCursorPos(int(x), int(y))

    def apertar(self, botao="esquerdo", cliques=1):
        self.u.mouse_event(0x0008 if botao == "direito" else 0x0002, 0, 0, 0, 0)

    def soltar(self, botao="esquerdo", cliques=1):
        self.u.mouse_event(0x0010 if botao == "direito" else 0x0004, 0, 0, 0, 0)

    def rolar(self, dy, dx=0):
        if dy:
            self.u.mouse_event(0x0800, 0, 0, int(dy), 0)
        if dx:
            self.u.mouse_event(0x1000, 0, 0, int(dx), 0)


class MousePyAutoGUI:
    nome = "pyautogui"

    def __init__(self):
        import pyautogui
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0
        self.p = pyautogui
        self.pos = tuple(pyautogui.position())

    def permitido(self) -> bool:
        return True

    def area(self):
        w, h = self.p.size()
        return (0, 0, w, h)

    def mover(self, x, y, arrastando=False):
        self.pos = (x, y); self.p.moveTo(x, y, _pause=False)

    def apertar(self, botao="esquerdo", cliques=1):
        self.p.mouseDown(button="right" if botao == "direito" else "left", _pause=False)

    def soltar(self, botao="esquerdo", cliques=1):
        self.p.mouseUp(button="right" if botao == "direito" else "left", _pause=False)

    def rolar(self, dy, dx=0):
        if dy:
            self.p.scroll(int(dy / 10), _pause=False)
        if dx:
            try:
                self.p.hscroll(int(dx / 10), _pause=False)
            except Exception:
                pass


def do_sistema(sistema: str | None = None):
    s = sistema or platform.system()
    tentativas = [MouseMac] if s == "Darwin" else [MouseWindows] if s == "Windows" else []
    for c in tentativas + [MousePyAutoGUI]:
        try:
            return c()
        except Exception:
            continue
    return None
