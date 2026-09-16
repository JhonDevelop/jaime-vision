"""`python -m jaime voz latencia` — mede a latência da voz com turnos sintéticos (docs/FASE-3-TEMPO-REAL.md §2.5).

Para cada frase: o `say` do macOS gera o áudio (16 kHz), que entra no STT em streaming como se fosse o microfone;
o antecipador roda sobre o último parcial; ao fim, `finalizar()` dá o texto; o TTS pré-sintetiza o rascunho (ou uma
resposta padrão). Métricas: fala→texto, texto→1ª frase, fala→1ª frase (com e sem antecipação). Meta: mediana < 700 ms.
`gerar_audio`, `fluxo`, `antecipador` e `tts` são injetáveis (testes offline)."""
from __future__ import annotations
import asyncio, io, os, statistics, subprocess, tempfile, time, wave

FRASES = ["Jaime, que horas são?", "Jaime, abre o Finder.", "Jaime, qual a previsão do tempo para amanhã?",
          "Jaime, me lembra de beber água em vinte minutos.", "Jaime, o que tem na minha agenda hoje?",
          "Jaime, cria uma tarefa para ligar pro contador.", "Jaime, quanto está o dólar?", "Jaime, está aí?",
          "Jaime, manda um resumo do dia.", "Jaime, abre o site da Oldsen."]
RESPOSTA_PADRAO = "Sim, senhor."
SR = 16000
FRAME = 512

def gerar_audio_say(texto: str, sr: int = SR) -> bytes:
    """PCM16 mono via `say` (voz pt-BR). Vazio se o `say` não existir."""
    voz = os.environ.get("JAIME_SAY_VOZ", "Eddy (Português (Brasil))")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        caminho = f.name
    try:
        subprocess.run(["say", "-v", voz, "-o", caminho, f"--data-format=LEI16@{sr}", texto], check=True, stderr=subprocess.DEVNULL, timeout=30)
        with wave.open(caminho, "rb") as w:
            return w.readframes(w.getnframes())
    except Exception:
        return b""
    finally:
        try: os.unlink(caminho)
        except OSError: pass

async def medir_turno(pcm: bytes, fluxo, antecipador=None, tts=None, ritmo_real: bool = False) -> dict:
    parciais: list[tuple[float, str]] = []
    tarefas: list[asyncio.Task] = []
    loop = asyncio.get_running_loop()
    def chegou(t: str) -> None:
        # como o duplex: cada parcial é avaliado ao chegar (heurística já; modelo em segundo plano). Avaliar só o último
        # parcial deixava o benchmark cego quando os eventos chegavam durante o finalizar() (Vigília 16/09: 'nenhuma' 10/10).
        parciais.append((time.time(), t))
        if antecipador and antecipador.pode_avaliar(t):
            tarefas.append(loop.create_task(antecipador.avaliar(t, agora=time.time())))
    fluxo.on_parcial = chegou
    t0 = time.time()
    for i in range(0, len(pcm), FRAME * 2):
        await fluxo.enviar(pcm[i:i + FRAME * 2])
        if ritmo_real:
            await asyncio.sleep(FRAME / SR)
    t_fim_fala = time.time()
    texto = (await fluxo.finalizar()).strip()
    t_texto = time.time()
    antecip = None
    if antecipador:
        if texto and antecipador.pode_avaliar(texto):
            tarefas.append(loop.create_task(antecipador.avaliar(texto, agora=time.time())))
        for tf in tarefas:
            try: await tf
            except Exception: pass
        await antecipador.esperar_modelo()
        antecip = antecipador.confere(texto) or antecipador.ultima
    rascunho = antecip.rascunho if antecip and antecip.especulavel and antecipador.confere(texto) else ""
    t_tts = 0.0
    if tts:
        # sem cache, o que o João espera é o 1º byte do TTS em streaming (não a frase inteira)
        if hasattr(tts, "medir_primeiro_byte"):
            t_tts = tts.medir_primeiro_byte(rascunho or RESPOSTA_PADRAO) or 0.0
        else:
            ini = time.time(); tts.pre_sintetizar(rascunho or RESPOSTA_PADRAO); t_tts = time.time() - ini
    fala_texto = t_texto - t_fim_fala
    # com antecipação o áudio já está em cache: a 1ª frase sai logo após o texto; sem, espera a síntese
    fala_frase = fala_texto + (0.0 if rascunho else t_tts)
    return {"texto": texto, "parciais": len(parciais), "primeiro_parcial_s": (parciais[0][0] - t0) if parciais else None,
            "fala_texto": fala_texto, "texto_frase": t_tts, "fala_frase": fala_frase, "antecipado": bool(rascunho),
            "antecipador_s": antecip.latencia_s if antecip else None, "duracao_audio_s": len(pcm) / 2 / SR,
            # para a Vigília validar sem adivinhar: o que o antecipador viu e decidiu neste turno
            "antecipacao": (f"{antecip.origem} · especulável={'sim' if antecip.especulavel else 'não'} · completude {antecip.completude:.1f}"
                            f" · ação «{antecip.acao_prevista}» · rascunho «{antecip.rascunho}» · parcial «{antecip.texto[:40]}»"
                            f" · {len(parciais)} parciais") if antecip else f"nenhuma ({len(parciais)} parciais; último «{parciais[-1][1][:40] if parciais else ''}»)"}

def _med(vals):
    v = [x for x in vals if x is not None]
    return statistics.median(v) if v else None

async def medir(s, n: int = 10, frases: list[str] | None = None, gerar_audio=gerar_audio_say, fluxo=None, antecipador=None, tts=None,
                ritmo_real: bool = False, imprimir=print) -> dict:
    from . import stt_stream
    from .antecipador import Antecipador, modelo_openai
    frases = (frases or FRASES)[:n]
    if fluxo is None:
        fluxo = stt_stream.escolher(s)
    if antecipador is None:
        fn = None
        if getattr(s, "openai_key", "") and os.environ.get("JAIME_ANTECIPADOR_MODEL", "") != "off":
            from openai import AsyncOpenAI
            fn = modelo_openai(AsyncOpenAI(api_key=s.openai_key), os.environ.get("JAIME_ANTECIPADOR_MODEL") or "gpt-4o-mini")
        antecipador = Antecipador(fn, intervalo_s=0.0)
    if tts is None:
        from .tts import TTS
        tts = TTS(s)
    if not fluxo.conectado:
        await fluxo.iniciar()
    turnos = []
    imprimir(f"STT: {getattr(fluxo, 'nome', '?')} · antecipador: {'modelo' if antecipador.modelo_fn else 'heurística'} · TTS: {getattr(tts, 'motor', '?')} · {len(frases)} turnos")
    for i, frase in enumerate(frases, 1):
        pcm = gerar_audio(frase)
        if not pcm:
            imprimir(f"{i:2}. (sem áudio para «{frase}»)"); continue
        antecipador.limpar()
        r = await medir_turno(pcm, fluxo, antecipador, tts, ritmo_real)
        turnos.append(r)
        f = lambda v: f"{v * 1000:4.0f} ms" if v is not None else "   —   "
        imprimir(f"{i:2}. fala→texto {f(r['fala_texto'])} · texto→1ª frase {f(r['texto_frase'])} · fala→1ª frase {f(r['fala_frase'])}"
                 f"{' · antecipado' if r['antecipado'] else ''} · «{r['texto'][:40]}»")
        imprimir(f"    antecipação: {r['antecipacao']}")
    try:
        await fluxo.fechar()
    except Exception:
        pass
    resumo = {"turnos": len(turnos), "mediana_fala_texto": _med([t["fala_texto"] for t in turnos]),
              "mediana_texto_frase": _med([t["texto_frase"] for t in turnos]), "mediana_fala_frase": _med([t["fala_frase"] for t in turnos]),
              "mediana_primeiro_parcial": _med([t["primeiro_parcial_s"] for t in turnos]),
              "antecipados": sum(t["antecipado"] for t in turnos), "meta_ok": (_med([t["fala_frase"] for t in turnos]) or 9) < 0.7}
    f = lambda v: f"{v * 1000:.0f} ms" if v is not None else "—"
    imprimir(f"\nmediana: fala→texto {f(resumo['mediana_fala_texto'])} · texto→1ª frase {f(resumo['mediana_texto_frase'])} · "
             f"fala→1ª frase {f(resumo['mediana_fala_frase'])} · 1º parcial em {f(resumo['mediana_primeiro_parcial'])} · antecipados {resumo['antecipados']}/{resumo['turnos']}"
             f" · meta < 700 ms: {'OK' if resumo['meta_ok'] else 'ainda não'}")
    return resumo

def registrar_no_diario(vault, resumo: dict) -> None:
    f = lambda v: f"{v * 1000:.0f} ms" if v is not None else "—"
    try:
        vault.diario(f"Latência medida (voz latencia): fala→texto {f(resumo['mediana_fala_texto'])} · texto→1ª frase {f(resumo['mediana_texto_frase'])} · "
                     f"fala→1ª frase {f(resumo['mediana_fala_frase'])} · antecipados {resumo['antecipados']}/{resumo['turnos']}", "Log")
    except Exception:
        pass
