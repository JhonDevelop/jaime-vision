"""A tela do Jarvis aparece quando é chamada (vídeo do monitor: "ativar monitor" acorda o monitor e o painel surge).

- a página /hud/jarvis manda um sinal de vida a cada 10 s (`POST /jarvis/tela/viva`);
- uma cena que precisa da tela (monitor, holograma, briefing) chama `garantir()`: acorda o monitor e, se nenhuma
  tela Jarvis deu sinal nos últimos 25 s, abre a página no navegador padrão;
- macOS: `caffeinate -u` acorda o monitor, `open` abre; Windows: um toque de mouse acorda, `start` abre;
  Linux: `xset dpms force on` + `xdg-open`.
`JAIME_JARVIS_ABRIR_TELA=off` desliga a abertura automática. Nada disso mexe em arquivo ou configuração.
"""
from __future__ import annotations
import os, platform, subprocess, time

URL = os.environ.get("JAIME_JARVIS_URL", "http://127.0.0.1:8787/hud/jarvis")
_ultimo_sinal = 0.0


def sinal_de_vida(agora: float | None = None) -> None:
    global _ultimo_sinal
    _ultimo_sinal = agora if agora is not None else time.time()


def aberta(janela_s: float = 25.0, agora: float | None = None) -> bool:
    return ((agora if agora is not None else time.time()) - _ultimo_sinal) <= janela_s


def comandos(sistema: str, url: str) -> list[list[str]]:
    if sistema == "Darwin":
        return [["caffeinate", "-u", "-t", "2"], ["open", url]]
    if sistema == "Windows":
        toque = ("Add-Type -Name U -Namespace W -MemberDefinition '[DllImport(\"user32.dll\")] public static extern void "
                 "mouse_event(int f,int x,int y,int d,int i);'; [W.U]::mouse_event(1,0,1,0,0)")
        return [["powershell", "-NoProfile", "-Command", toque], ["cmd", "/c", "start", "", url]]
    return [["xset", "dpms", "force", "on"], ["xdg-open", url]]


def garantir(rodar=None, sistema: str | None = None, env=None) -> str:
    """'aberta' | 'abri' | 'desligado' | 'falhou'. Acorda o monitor sempre; abre a página só se não houver uma viva."""
    e = os.environ if env is None else env
    if (e.get("JAIME_JARVIS_ABRIR_TELA", "on") or "on").lower() in ("off", "0", "false"):
        return "desligado"
    rodar = rodar or (lambda c: subprocess.Popen(c, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    acordar, abrir = comandos(sistema or platform.system(), e.get("JAIME_JARVIS_URL", URL))
    try:
        rodar(acordar)
    except Exception:
        pass
    if aberta():
        return "aberta"
    try:
        rodar(abrir)
        return "abri"
    except Exception:
        return "falhou"
