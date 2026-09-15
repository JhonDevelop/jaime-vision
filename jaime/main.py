"""Entrada: `python -m jaime chat | voice | hud | serve | senha`."""
from __future__ import annotations
import argparse, asyncio, sys, webbrowser
from .config import settings

async def _chat():
    from .orchestrator.jaime import Jaime
    j = Jaime(settings)
    print("jaime ›", await j.start(), "\n")
    try:
        while True:
            texto = await asyncio.to_thread(input, "você › ")
            if texto.strip():
                print("jaime ›", await j.ask(texto, canal="cli"), "\n")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        await j.stop()

async def _voice():
    """Só voz, sem HUD: escuta contínua no terminal (mesmo ouvido que o servidor usa)."""
    from .orchestrator.jaime import Jaime
    from .voice.escuta import Ouvido
    j = Jaime(settings)
    apresentacao = await j.start()
    ouvido = Ouvido(j, settings, asyncio.get_running_loop())
    ouvido.start()
    print("🎙️  Jaime ouvindo — fale normalmente (Ctrl+C para sair).")
    await asyncio.to_thread(lambda: (_esperar_tts(ouvido), ouvido.falar(apresentacao)))
    try:
        while not ouvido.erro:
            await asyncio.sleep(0.5)
        print("voz indisponível:", ouvido.erro)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        ouvido.stop(); await j.stop()

def _esperar_tts(ouvido, s: float = 60):
    import time
    fim = time.time() + s
    while not ouvido._tts and time.time() < fim:
        time.sleep(0.25)

def _serve(abrir_hud: bool):
    import uvicorn
    url = f"http://{settings.bind}:{settings.port}"
    print(f"Jaime em {url}  (HUD em / · API em /ask · bind={settings.bind})")
    if abrir_hud:
        webbrowser.open(url if settings.bind != "0.0.0.0" else f"http://127.0.0.1:{settings.port}")
    uvicorn.run("jaime.server:app", host=settings.bind, port=settings.port, reload=False, log_level="warning")

def _senha():
    from .vigia.acesso import hash_senha
    import getpass
    s1 = getpass.getpass("Nova palavra-passe (dígitos ou por extenso): ")
    s2 = getpass.getpass("Repita: ")
    if s1 != s2:
        print("Não confere."); return 1
    print(f"\nColoque no .env:\nJAIME_PASSPHRASE_HASH={hash_senha(s1)}")

def _cerebro(acao: str) -> int:
    """`jaime cerebro check`: saúde do vault + índices. Código de saída 1 se houver erro."""
    from .brain.saude import verificar, gerar_indices, relatorio
    if acao != "check":
        print("uso: python -m jaime cerebro check"); return 2
    probs = verificar(settings.vault, settings.root)
    print(relatorio(probs))
    print("índices:", ", ".join(gerar_indices(settings.vault)))
    return 1 if any(p.nivel == "erro" for p in probs) else 0

def main(argv=None):
    ap = argparse.ArgumentParser(prog="jaime")
    ap.add_argument("modo", choices=["chat", "voice", "hud", "serve", "senha", "cerebro"])
    ap.add_argument("acao", nargs="?", default="check")
    args = ap.parse_args(argv); m = args.modo
    if m == "cerebro": return _cerebro(args.acao)
    if m == "chat": asyncio.run(_chat())
    elif m == "voice": asyncio.run(_voice())
    elif m == "hud": _serve(abrir_hud=True)
    elif m == "serve": _serve(abrir_hud=False)
    else: return _senha()

if __name__ == "__main__":
    sys.exit(main())
