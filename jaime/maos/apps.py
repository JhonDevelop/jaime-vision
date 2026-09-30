"""Apps de criação do João: abrir, e mexer por dentro quando o app deixa (scripts oficiais do próprio app).

- abrir qualquer app conhecido (Photoshop, Premiere, Illustrator, After Effects, Blender, DaVinci, CapCut, Figma,
  Bambu Studio…) com ou sem arquivo; Canva e Figma também pela web;
- Photoshop: roda ExtendScript (.jsx) — o jeito oficial de automatizar o Photoshop — no macOS por AppleScript
  (`do javascript`), no Windows por COM (`DoJavaScriptFile`). Script que salva por cima, apaga ou fecha sem salvar
  passa pelo Vigia;
- Premiere: monta uma SEQUÊNCIA (XML do Final Cut 7, que o Premiere importa nativamente) com os cortes pedidos e
  abre no Premiere — cortar, ordenar e montar a timeline sem clicar;
- Canva: o servidor MCP oficial (https://mcp.canva.com/mcp) quando `JAIME_CANVA=on` (login uma vez); senão, abre
  o Canva no navegador.
Nada aqui instala app, compra licença ou publica: abrir e montar arquivo local.
"""
from __future__ import annotations
import glob, os, platform, re, subprocess, time
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

PASTA = Path(os.environ.get("JAIME_APPS", "~/Jaime/apps")).expanduser()
WEB = {"canva": "https://www.canva.com/", "figma": "https://www.figma.com/files", "whatsapp web": "https://web.whatsapp.com/",
       "gmail": "https://mail.google.com/"}
APPS = {  # nome → (padrões macOS em /Applications, padrões Windows)
    "photoshop": (["Adobe Photoshop*/Adobe Photoshop*.app", "Adobe Photoshop*.app"], [r"C:\Program Files\Adobe\Adobe Photoshop*\Photoshop.exe"]),
    "premiere": (["Adobe Premiere Pro*/Adobe Premiere Pro*.app", "Adobe Premiere Pro*.app"], [r"C:\Program Files\Adobe\Adobe Premiere Pro*\Adobe Premiere Pro.exe"]),
    "illustrator": (["Adobe Illustrator*/Adobe Illustrator*.app"], [r"C:\Program Files\Adobe\Adobe Illustrator*\Support Files\Contents\Windows\Illustrator.exe"]),
    "after effects": (["Adobe After Effects*/Adobe After Effects*.app"], [r"C:\Program Files\Adobe\Adobe After Effects*\Support Files\AfterFX.exe"]),
    "blender": (["Blender.app"], [r"C:\Program Files\Blender Foundation\Blender*\blender.exe"]),
    "davinci resolve": (["DaVinci Resolve/DaVinci Resolve.app", "DaVinci Resolve.app"], [r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"]),
    "capcut": (["CapCut.app"], [os.path.expandvars(r"%LOCALAPPDATA%\CapCut\Apps\CapCut.exe")]),
    "figma": (["Figma.app"], [os.path.expandvars(r"%LOCALAPPDATA%\Figma\Figma.exe")]),
    "canva": (["Canva.app"], [os.path.expandvars(r"%LOCALAPPDATA%\Programs\Canva\Canva.exe")]),
    "whatsapp": (["WhatsApp.app"], [os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe")]),
    "bambu studio": (["BambuStudio.app"], [r"C:\Program Files\Bambu Studio\bambu-studio.exe"]),
    "mail": (["Mail.app", "/System/Applications/Mail.app"], []),
}
APELIDOS = {"ps": "photoshop", "premier": "premiere", "premiere pro": "premiere", "ai": "illustrator", "ae": "after effects",
            "davinci": "davinci resolve", "resolve": "davinci resolve", "zap": "whatsapp", "whats": "whatsapp", "e-mail": "mail",
            "email": "mail", "bambu": "bambu studio"}
PERIGOSO_JSX = re.compile(r"\.saveAs\s*\(|\.save\s*\(|\.remove\s*\(|SaveOptions\.DONOTSAVECHANGES|Folder\s*\(|\.execute\s*\(|system\s*\(|app\.system", re.I)


def _nome(nome: str) -> str:
    n = (nome or "").strip().lower()
    return APELIDOS.get(n, n)


def localizar(nome: str, sistema: str | None = None, raizes=("/Applications", os.path.expanduser("~/Applications"))) -> str | None:
    n, s = _nome(nome), sistema or platform.system()
    if n not in APPS:
        return None
    mac, win = APPS[n]
    if s == "Darwin":
        for r in raizes:
            for padrao in mac:
                achados = sorted(glob.glob(padrao if padrao.startswith("/") else os.path.join(r, padrao)))
                if achados:
                    return achados[-1]          # a versão mais nova (ordem alfabética: 2024 < 2025)
        return None
    if s == "Windows":
        for padrao in win:
            achados = sorted(glob.glob(padrao))
            if achados:
                return achados[-1]
    return None


def abrir(nome: str, arquivo: str = "", rodar=subprocess.Popen, sistema: str | None = None, localizar_fn=localizar) -> dict:
    n, s = _nome(nome), sistema or platform.system()
    caminho = localizar_fn(n, s)
    if arquivo and not Path(arquivo).expanduser().exists():
        return {"ok": False, "erro": f"arquivo não existe: {arquivo}"}
    arq = [str(Path(arquivo).expanduser())] if arquivo else []
    if caminho:
        cmd = (["open", "-a", caminho] + arq) if s == "Darwin" else ([caminho] + arq)
    elif n in WEB and not arq:
        cmd = ["open", WEB[n]] if s == "Darwin" else (["cmd", "/c", "start", "", WEB[n]] if s == "Windows" else ["xdg-open", WEB[n]])
    else:
        return {"ok": False, "erro": f"{nome} não está instalado nesta máquina"}
    rodar(cmd)
    return {"ok": True, "app": n, "como": "web" if not caminho else "app"}


def instalados(sistema: str | None = None, localizar_fn=localizar) -> list[str]:
    return [n for n in APPS if localizar_fn(n, sistema)]


# ── Photoshop ─────────────────────────────────────────
def photoshop_jsx(jsx: str, rodar=subprocess.run, sistema: str | None = None, timeout: int = 180) -> dict:
    PASTA.mkdir(parents=True, exist_ok=True)
    arq = PASTA / f"ps-{time.strftime('%Y%m%d-%H%M%S')}.jsx"
    arq.write_text(jsx, encoding="utf-8")
    s = sistema or platform.system()
    if s == "Darwin":
        cmd = ["osascript", "-e", f'tell application id "com.adobe.Photoshop" to do javascript (POSIX file "{arq}")']
    elif s == "Windows":
        cmd = ["powershell", "-NoProfile", "-Command", f"$ps = New-Object -ComObject Photoshop.Application; $ps.DoJavaScriptFile('{arq}')"]
    else:
        return {"ok": False, "erro": "Photoshop só no macOS ou Windows", "script": str(arq)}
    try:
        r = rodar(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "erro": "o Photoshop não respondeu a tempo", "script": str(arq)}
    ok = r.returncode == 0
    return {"ok": ok, "saida": (r.stdout or "")[-800:], "erro": "" if ok else (r.stderr or "")[-400:], "script": str(arq)}


# ── Premiere (sequência em XML do Final Cut 7, importado nativamente) ────────────────
def premiere_xml(nome: str, clipes: list[dict], fps: int = 30, pasta: Path | None = None) -> str:
    """clipes: [{"caminho": "/…/a.mp4", "inicio": s, "fim": s}] na ordem da timeline. Devolve o caminho do .xml."""
    fps = max(1, int(fps))
    itens, t, arquivos = [], 0, {}
    for i, c in enumerate(clipes[:300]):
        p = Path(str(c.get("caminho", ""))).expanduser()
        ini, fim = float(c.get("inicio", 0) or 0), float(c.get("fim", 0) or 0)
        if fim <= ini:
            raise ValueError(f"clipe {i + 1}: fim precisa ser depois do início")
        a, b = int(round(ini * fps)), int(round(fim * fps))
        fid = arquivos.setdefault(str(p), f"arquivo-{len(arquivos) + 1}")
        itens.append((i + 1, p, fid, a, b, t, t + (b - a)))
        t += b - a
    rate = f"<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>"

    def arquivo(p, fid, primeira):
        if not primeira:
            return f'<file id="{fid}"/>'
        return (f'<file id="{fid}"><name>{escape(p.name)}</name><pathurl>file://localhost{quote(str(p))}</pathurl>{rate}'
                f"<media><video/><audio/></media></file>")
    vistos: set = set()
    vid, aud = [], []
    for n, p, fid, a, b, ini, fim in itens:
        primeira = fid not in vistos; vistos.add(fid)
        corpo = f"<name>{escape(p.name)}</name><duration>{b}</duration>{rate}<start>{ini}</start><end>{fim}</end><in>{a}</in><out>{b}</out>"
        vid.append(f'<clipitem id="v{n}">{corpo}{arquivo(p, fid, primeira)}</clipitem>')
        aud.append(f'<clipitem id="a{n}">{corpo}<file id="{fid}"/><sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack></clipitem>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="seq-jaime">'
           f"<name>{escape(nome)}</name><duration>{t}</duration>{rate}<media><video><track>{''.join(vid)}</track></video>"
           f"<audio><track>{''.join(aud)}</track></audio></media></sequence></xmeml>\n")
    pasta = pasta or PASTA
    pasta.mkdir(parents=True, exist_ok=True)
    base = re.sub(r"[^\w-]+", "-", nome.lower()).strip("-") or "sequencia"
    arq = pasta / f"{base}-{time.strftime('%Y%m%d-%H%M%S')}.xml"
    arq.write_text(xml, encoding="utf-8")
    return str(arq)
