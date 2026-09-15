"""`python -m jaime permissoes` — toca cada API protegida do macOS para o sistema PEDIR a permissão ao binário do
Jaime (o python do .venv, o mesmo que o serviço usa), e abre o painel de Privacidade para as que não têm prompt.

Microfone e Câmera: o macOS pergunta na primeira vez. Gravação de Tela e Acessibilidade: pergunta e/ou exige marcar
no painel. Acesso Total ao Disco (notificações): só manual. O resultado sai como tabela; rode de novo depois de marcar."""
from __future__ import annotations
import ctypes, os, sqlite3, subprocess, sys, time
from pathlib import Path

PAINEIS = {"microfone": "Privacy_Microphone", "camera": "Privacy_Camera", "tela": "Privacy_ScreenCapture",
           "acessibilidade": "Privacy_Accessibility", "disco": "Privacy_AllFiles"}

def _microfone() -> tuple[bool, str]:
    try:
        import sounddevice as sd
        with sd.RawInputStream(samplerate=16000, blocksize=1600, dtype="int16", channels=1) as m:
            m.read(1600)
        return True, "ok"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:80]}"

def _camera() -> tuple[bool, str]:
    try:
        from ..casa.camera import quadro_webcam
        p = quadro_webcam("0", Path("/tmp/jaime-permissao-camera.png"))
        return p.exists(), "ok"
    except Exception as e:
        return False, str(e)[:100]

def _tela() -> tuple[bool, str]:
    try:
        subprocess.run(["screencapture", "-x", "-t", "png", "/tmp/jaime-permissao-tela.png"], check=True, timeout=10, capture_output=True)
        # sem permissão o macOS devolve uma imagem só do papel de parede; aqui só checamos que gerou
        return Path("/tmp/jaime-permissao-tela.png").exists(), "ok (confira se a captura mostra as janelas; senão marque Gravação de Tela)"
    except Exception as e:
        return False, str(e)[:100]

def _acessibilidade() -> tuple[bool, str]:
    try:
        AS = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        CF = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        AS.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
        # kAXTrustedCheckOptionPrompt = true → o sistema abre o pedido
        CF.CFStringCreateWithCString.restype = ctypes.c_void_p
        chave = CF.CFStringCreateWithCString(None, b"AXTrustedCheckOptionPrompt", 0x08000100)
        CF.kCFBooleanTrue = ctypes.c_void_p.in_dll(CF, "kCFBooleanTrue")
        CF.CFDictionaryCreate.restype = ctypes.c_void_p
        keys = (ctypes.c_void_p * 1)(chave); vals = (ctypes.c_void_p * 1)(CF.kCFBooleanTrue.value)
        d = CF.CFDictionaryCreate(None, keys, vals, 1, None, None)
        ok = AS.AXIsProcessTrustedWithOptions(ctypes.c_void_p(d))
        return bool(ok), "ok" if ok else "pedido enviado — marque o python na lista"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:80]}"

def _disco() -> tuple[bool, str]:
    db = Path("~/Library/Group Containers/group.com.apple.usernoted/db2/db").expanduser()
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True); con.execute("SELECT 1 FROM record LIMIT 1"); con.close()
        return True, "ok"
    except Exception as e:
        return False, "sem Acesso Total ao Disco (manual): " + str(e)[:60]

def rodar(abrir_paineis: bool = True) -> int:
    print(f"binário: {sys.executable}")
    checks = [("microfone", _microfone), ("camera", _camera), ("tela", _tela), ("acessibilidade", _acessibilidade), ("disco", _disco)]
    faltando = []
    for nome, fn in checks:
        ok, msg = fn()
        print(f"  {'✔' if ok else '✘'} {nome:15s} {msg}")
        if not ok:
            faltando.append(nome)
        time.sleep(0.5)
    if faltando and abrir_paineis:
        for nome in faltando:
            subprocess.run(["open", f"x-apple.systempreferences:com.apple.preference.security?{PAINEIS[nome]}"], check=False)
            time.sleep(1.5)
        print(f"\nAbri os painéis de: {', '.join(faltando)}. Adicione/marque: {sys.executable}\n(Ajustes › Privacidade e Segurança). Depois: python -m jaime permissoes")
    else:
        print("\n✔ todas as permissões concedidas ao binário do Jaime")
    return 0 if not faltando else 1
