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

def _cortex(acao: str, texto: str) -> int:
    """`jaime cortex explicar "<tarefa>"`: tipo, modelo escolhido e porquê, com o placar atual."""
    from .cortex.placar import Placar
    from .cortex.roteador import Roteador
    if acao != "explicar" or not texto:
        print('uso: python -m jaime cortex explicar "<tarefa>"'); return 2
    r = Roteador({"decisao": settings.model_decisao, "codigo": settings.model_codigo,
                  "padrao": settings.model_padrao, "rotina": settings.model_rotina},
                 Placar(settings.vault), exploracao=0.0)
    print(r.explicar(texto)); return 0

SKILLS_OFICIAIS = ("pdf", "docx", "xlsx", "pptx")

def _skills(acao: str) -> int:
    """`jaime skills instalar`: baixa as skills oficiais de documentos (anthropics/skills) para .claude/skills/."""
    import io, urllib.request, zipfile, shutil
    if acao != "instalar":
        print("uso: python -m jaime skills instalar"); return 2
    destino = settings.root / ".claude" / "skills"; destino.mkdir(parents=True, exist_ok=True)
    print("▶ baixando anthropics/skills…")
    dados = urllib.request.urlopen("https://github.com/anthropics/skills/archive/refs/heads/main.zip", timeout=120).read()
    z = zipfile.ZipFile(io.BytesIO(dados)); raiz = z.namelist()[0].split("/")[0]
    for nome in SKILLS_OFICIAIS:
        alvo = destino / nome
        if alvo.exists():
            shutil.rmtree(alvo)
        membros = [n for n in z.namelist() if n.startswith(f"{raiz}/skills/{nome}/")]
        for n in membros:
            rel = n[len(f"{raiz}/skills/"):]
            if n.endswith("/"):
                (destino / rel).mkdir(parents=True, exist_ok=True); continue
            (destino / rel).parent.mkdir(parents=True, exist_ok=True)
            (destino / rel).write_bytes(z.read(n))
        print(f"  ✔ {nome} ({len(membros)} arquivos)" if membros else f"  ✘ {nome} não encontrada no repositório")
    print(f"skills em {destino}"); return 0

def main(argv=None):
    ap = argparse.ArgumentParser(prog="jaime")
    ap.add_argument("modo", choices=["chat", "voice", "hud", "serve", "senha", "cerebro", "cortex", "skills"])
    ap.add_argument("acao", nargs="?", default="check")
    ap.add_argument("texto", nargs="*")
    args = ap.parse_args(argv); m = args.modo
    if m == "cerebro": return _cerebro(args.acao)
    if m == "cortex": return _cortex(args.acao, " ".join(args.texto))
    if m == "skills": return _skills(args.acao)
    if m == "chat": asyncio.run(_chat())
    elif m == "voice": asyncio.run(_voice())
    elif m == "hud": _serve(abrir_hud=True)
    elif m == "serve": _serve(abrir_hud=False)
    else: return _senha()

if __name__ == "__main__":
    sys.exit(main())
