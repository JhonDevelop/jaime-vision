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
    import socket, uvicorn
    # instância única: dois Jaimes disputando o mesmo microfone e alto-falante já causaram "pensar e falar duas vezes"
    with socket.socket() as s:
        if s.connect_ex((settings.bind if settings.bind != "0.0.0.0" else "127.0.0.1", settings.port)) == 0:
            print(f"Já existe um Jaime em {settings.bind}:{settings.port}. Use o HUD dele ou pare-o (bash jaime/ops/servico.sh parar)."); return 1
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

def _conectar(servico: str) -> int:
    """`jaime conectar google`: OAuth do seu projeto → token local + registro em 01-Estado/Conexoes.md."""
    if servico != "google":
        print("uso: python -m jaime conectar google"); return 2
    from .conexoes.google import conectar
    from .conexoes.registro import Registro
    from .brain.vault import Vault
    from datetime import date
    email = conectar(settings.google_client_secret, settings.google_token)
    Registro(Vault(settings.vault)).registrar("Google Gmail", "ler, rascunhar, enviar (Vigia), marcar", f"OAuth {date.today():%d/%m/%Y} ({email})", "myaccount.google.com › Segurança › Acesso de terceiros")
    Registro(Vault(settings.vault)).registrar("Google Calendar", "ler e criar eventos", f"OAuth {date.today():%d/%m/%Y} ({email})", "idem; ou apagar ~/Jaime/google-token.json")
    Registro(Vault(settings.vault)).registrar("Google Drive", "somente leitura", f"OAuth {date.today():%d/%m/%Y} ({email})", "idem")
    print(f"✔ Google conectado como {email}. Token em {settings.google_token}"); return 0

VOZES_TESTE = ("onyx", "ash", "echo", "verse", "ballad")

def _voz(acao: str) -> int:
    """`jaime voz testar`: a mesma frase em 5 vozes masculinas do gpt-4o-mini-tts; você escolhe e fica no .env.
    `jaime voz latencia`: 10 turnos sintéticos (say → STT streaming → antecipador → TTS) e as medianas no diário."""
    if acao == "latencia":
        from .voice.latencia import medir, registrar_no_diario
        from .brain.vault import Vault
        resumo = asyncio.run(medir(settings))
        registrar_no_diario(Vault(settings.vault), resumo)
        return 0 if resumo.get("meta_ok") else 1
    if acao != "testar":
        print("uso: python -m jaime voz testar | latencia"); return 2
    if not settings.openai_key:
        print("OPENAI_API_KEY ausente."); return 1
    import numpy as np, sounddevice as sd, re
    from openai import OpenAI
    c = OpenAI(api_key=settings.openai_key)
    frase = "Bom dia, João. O build da BUB terminou sem erros e a agenda está livre até as duas. Deseja que eu prossiga?"
    instr = ("Voz masculina grave e calma, dicção precisa, sotaque brasileiro neutro, tom seco e educado, "
             "leve textura de assistente de inteligência artificial — um mordomo britânico falando português.")
    for i, voz in enumerate(VOZES_TESTE, 1):
        print(f"{i}. {voz}…", end=" ", flush=True)
        with c.audio.speech.with_streaming_response.create(model="gpt-4o-mini-tts", voice=voz, input=frase, instructions=instr, response_format="pcm") as r:
            pcm = b"".join(r.iter_bytes())
        sd.play(np.frombuffer(pcm, dtype=np.int16), 24000); sd.wait(); print("ok")
    esc = input(f"Qual fica? [1-{len(VOZES_TESTE)}, Enter = manter] ").strip()
    if esc.isdigit() and 1 <= int(esc) <= len(VOZES_TESTE):
        voz = VOZES_TESTE[int(esc) - 1]
        env = settings.root / ".env"; t = env.read_text(encoding="utf-8")
        t = re.sub(r"^JAIME_OPENAI_VOZ=.*$", f"JAIME_OPENAI_VOZ={voz}", t, flags=re.M) if "JAIME_OPENAI_VOZ=" in t else t + f"\nJAIME_OPENAI_VOZ={voz}\n"
        env.write_text(t, encoding="utf-8")
        from .brain.vault import Vault
        Vault(settings.vault).diario(f"Voz escolhida: gpt-4o-mini-tts/{voz}", "Decisões")
        print(f"✔ JAIME_OPENAI_VOZ={voz} — reinicie o servidor.")
    return 0

def main(argv=None):
    ap = argparse.ArgumentParser(prog="jaime")
    ap.add_argument("modo", choices=["chat", "voice", "hud", "serve", "senha", "cerebro", "cortex", "skills", "conectar", "voz", "permissoes"])
    ap.add_argument("acao", nargs="?", default="check")
    ap.add_argument("texto", nargs="*")
    args = ap.parse_args(argv); m = args.modo
    if m == "cerebro": return _cerebro(args.acao)
    if m == "cortex": return _cortex(args.acao, " ".join(args.texto))
    if m == "skills": return _skills(args.acao)
    if m == "conectar": return _conectar(args.acao)
    if m == "voz": return _voz(args.acao)
    if m == "permissoes":
        from .ops.permissoes import rodar
        return rodar()
    if m == "chat": asyncio.run(_chat())
    elif m == "voice": asyncio.run(_voice())
    elif m == "hud": return _serve(abrir_hud=True)
    elif m == "serve": return _serve(abrir_hud=False)
    else: return _senha()

if __name__ == "__main__":
    sys.exit(main())
