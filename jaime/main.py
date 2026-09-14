"""Entrada: `python -m jaime chat | voice | serve`."""
from __future__ import annotations
import argparse, asyncio, sys
from .config import settings

async def _chat():
    from .orchestrator.jaime import Jaime
    j = Jaime(settings)
    await j.start()
    print("Jaime online. (Ctrl+C para sair)\n")
    try:
        while True:
            texto = await asyncio.to_thread(input, "você › ")
            if not texto.strip():
                continue
            print("jaime ›", await j.ask(texto, canal="cli"), "\n")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        await j.stop()

async def _voice():
    from .orchestrator.jaime import Jaime
    from .voice.loop import VoiceLoop
    j = Jaime(settings)
    await j.start()
    try:
        await VoiceLoop(j, settings).run()
    finally:
        await j.stop()

def _serve():
    import uvicorn
    uvicorn.run("jaime.server:app", host="0.0.0.0", port=8787, reload=False)

def main(argv=None):
    ap = argparse.ArgumentParser(prog="jaime")
    ap.add_argument("modo", choices=["chat", "voice", "serve"])
    args = ap.parse_args(argv)
    if args.modo == "chat":
        asyncio.run(_chat())
    elif args.modo == "voice":
        asyncio.run(_voice())
    else:
        _serve()

if __name__ == "__main__":
    sys.exit(main())
