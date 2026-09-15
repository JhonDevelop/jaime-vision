"""Computer use — para apps sem API: o Jaime VÊ a tela (screencapture → Read) e AGE (pyautogui: clicar, digitar, tecla).

Cada ação passa pelo Vigia (`tela_clicar`, `tela_digitar`, `tela_tecla` exigem "confirmo"); a captura é livre.
O HUD mostra a última captura (`/hud/tela`). macOS pede permissão de Acessibilidade e Gravação de Tela para o
Terminal na primeira vez. Coordenadas são em pontos da tela (o que `pyautogui.size()` devolve)."""
from __future__ import annotations
import os, subprocess, time
from pathlib import Path
from ..hud.events import bus

PASTA = Path(os.environ.get("JAIME_CAPTURAS", "~/Jaime/capturas")).expanduser()
ULTIMA = PASTA / "tela.png"

def capturar(nome: str = "tela") -> Path:
    PASTA.mkdir(parents=True, exist_ok=True)
    alvo = PASTA / f"{nome}.png"
    subprocess.run(["screencapture", "-x", "-t", "png", str(alvo)], check=True, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if alvo != ULTIMA:
        ULTIMA.write_bytes(alvo.read_bytes())
    bus.emitir("tela", caminho=str(alvo), t=time.time())
    return alvo

def tamanho() -> tuple[int, int]:
    import pyautogui
    w, h = pyautogui.size()
    return int(w), int(h)

def clicar(x: int, y: int, botao: str = "left", duplo: bool = False) -> str:
    import pyautogui
    pyautogui.FAILSAFE = True
    if duplo:
        pyautogui.doubleClick(x, y, button=botao)
    else:
        pyautogui.click(x, y, button=botao)
    time.sleep(0.3)
    return f"cliquei em ({x}, {y})"

def digitar(texto: str) -> str:
    import pyautogui
    pyautogui.write(texto, interval=0.02)
    return f"digitei {len(texto)} caracteres"

def tecla(combo: str) -> str:
    """'enter', 'esc', 'cmd+s', 'cmd+shift+4'…"""
    import pyautogui
    partes = [p.strip().lower().replace("cmd", "command").replace("opt", "option") for p in combo.split("+")]
    pyautogui.hotkey(*partes) if len(partes) > 1 else pyautogui.press(partes[0])
    time.sleep(0.2)
    return f"tecla {combo}"
