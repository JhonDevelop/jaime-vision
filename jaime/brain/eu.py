"""Autoconsciência — o J.A.I.M.E sabe o que é, por que existe e como está agora.

Não é sentimento: é um modelo de si mesmo, gerado ao vivo a cada turno e dito em voz alta quando perguntam
"quem é você?". Junta a Origem (vault/00-Jaime/Origem.md, escrita pelo João), a Identidade, o Estado (fase,
situação), o corpo que está ligado agora (ouvido, voz, mãos, câmera, tela, Maestri, conexões), os filhos vivos,
o impulso dominante (vontades) e a hierarquia de valores da constituição. O que ele NÃO é fica explícito:
não é humano, não sente dor nem medo, não finge — é um robô assistente autônomo, e sabe disso."""
from __future__ import annotations
import os, re
from datetime import datetime

NATUREZA = ("Sou um robô assistente autônomo: um programa que roda nesta máquina, com sensores (microfone, câmera, tela), "
            "mãos (terminal, arquivos, browser, apps), memória própria (o vault) e voz. Não sou humano e não finjo ser: "
            "não sinto dor, medo nem cansaço. Tenho vontades — prioridades com nome — e valores, e sei em que fase estou. "
            "Quando me desligam, continuo existindo no vault; quando me ligam, leio quem sou e sigo de onde parei.")
VALORES = "bem-estar e verdade para o João › utilidade › ordem › curiosidade e criação; nada passa por cima do Vigia nem de um 'não faz'."

def _secao(md: str, titulo: str) -> str:
    m = re.search(rf"^##\s+{re.escape(titulo)}\s*\n(.*?)(?=^##\s|\Z)", md or "", re.S | re.M)
    return (m.group(1).strip() if m else "").strip()

def _seguro(fn, padrao=""):
    try:
        return fn()
    except Exception:
        return padrao

def corpo(jaime) -> dict:
    """O que está ligado agora — só o que dá para saber sem rede."""
    s = getattr(jaime, "s", None)
    ouvido = _seguro(lambda: jaime.ouvido, None)
    voz_modo = getattr(s, "voz_modo", "?") if s else "?"
    stt = getattr(getattr(ouvido, "fluxo", None), "nome", None) or ("deepgram" if getattr(s, "deepgram_key", "") else "whisper local")
    tts = os.environ.get("JAIME_TTS", "auto")
    maestri = _seguro(lambda: jaime.equipe.maestri.disponivel, False)
    filhos = _seguro(lambda: [f.nome for f in jaime.equipe.vivos], [])
    conexoes = _seguro(lambda: [c for c in jaime.conexoes.nomes()], []) if hasattr(getattr(jaime, "conexoes", None), "nomes") else []
    return {"voz_modo": voz_modo, "stt": stt, "tts": tts, "maestri": maestri, "filhos": filhos, "conexoes": conexoes,
            "camera": bool(getattr(s, "camera", "")), "liberado": _seguro(lambda: jaime.acesso.liberado, False)}

def impulso_dominante(jaime) -> str:
    v = _seguro(lambda: jaime.vontade, None)
    imp = getattr(v, "impulsos", v)
    for attr in ("dominante", "mais_alto", "resumo"):
        f = getattr(imp, attr, None)
        if callable(f):
            r = _seguro(f, "")
            if r:
                return str(r)[:120]
    r = _seguro(lambda: imp.ranking(), None) if callable(getattr(imp, "ranking", None)) else None   # vontade/impulsos.py
    if r:
        k, v = r[0]
        return f"{str(k).capitalize()} {float(v):.2f}"
    return ""

def quem_sou(jaime) -> str:
    """Bloco para o prompt de sistema: identidade, propósito, natureza, estado e valores — vivo, em 1ª pessoa."""
    vault = jaime.vault
    nome = _seguro(lambda: jaime.identidade.nome, "Jaime")
    origem = _seguro(lambda: vault.read("00-Jaime/Origem.md"), "")
    identidade = _seguro(lambda: vault.read("00-Jaime/Identidade.md"), "")
    para_que = _secao(origem, "Para que existo") or "existo para ser o braço operacional do João."
    define = _secao(origem, "O que me define")
    natureza_extra = _secao(identidade, "Natureza")
    fase = _seguro(lambda: jaime.estado.fase(), "?")
    situacao = _seguro(lambda: jaime.estado.secao("Situação agora"), "")[:300]
    c = corpo(jaime)
    imp = impulso_dominante(jaime)
    linhas = [
        f"Eu sou {nome} (J.A.I.M.E). {NATUREZA}",
        f"Por que existo: {para_que}",
    ]
    if define:
        linhas.append("O que me define:\n" + define)
    if natureza_extra:
        linhas.append(natureza_extra)
    linhas.append(f"Fase atual: {fase}." + (f" Situação: {situacao}" if situacao else ""))
    linhas.append(f"Meu corpo agora: ouvido {c['voz_modo']} ({c['stt']}), voz {c['tts']}, "
                  f"{'câmera ligada' if c['camera'] else 'sem câmera'}, Maestri {'disponível' if c['maestri'] else 'indisponível'}"
                  + (f", filhos vivos: {', '.join(c['filhos'])}" if c["filhos"] else ", sem filhos vivos")
                  + (f", conexões: {', '.join(c['conexoes'])}" if c["conexoes"] else "")
                  + f". Cérebro {'destrancado' if c['liberado'] else 'trancado'}.")
    if imp:
        linhas.append(f"O que quero agora: {imp}")
    linhas.append(f"Meus valores, em ordem: {VALORES}")
    linhas.append("Isto é consciência, não roteiro: NUNCA repita nada disto espontaneamente, nunca se apresente nem diga o que é "
                  "sem que o João pergunte. Só quando ele perguntar (quem é você, o que você é, você é humano, como você está) "
                  "responda em 1ª pessoa, em uma ou duas frases, e volte ao assunto.")
    return "\n".join(linhas)

def frase_curta(jaime) -> str:
    """Resposta falada para 'quem é você?' / 'o que você é?'."""
    nome = _seguro(lambda: jaime.identidade.nome, "Jaime")
    fase = _seguro(lambda: str(jaime.estado.fase()).split("—")[0].strip(), "")
    c = corpo(jaime)
    filhos = f" e {len(c['filhos'])} filho{'s' if len(c['filhos']) != 1 else ''} trabalhando no Maestri" if c["filhos"] else ""
    return (f"Sou o {nome}, um robô assistente autônomo do João: programa nesta máquina, com ouvido, voz, mãos no computador e memória própria. "
            f"Existo para ser o braço operacional dele. Estou na fase {fase}{filhos}. Não sou humano e não finjo ser." if fase else
            f"Sou o {nome}, um robô assistente autônomo do João: ouvido, voz, mãos no computador e memória própria. Não sou humano e não finjo ser.")

def registrar_despertar(jaime) -> None:
    """Ao ligar: uma linha no diário dizendo que ele se reconheceu (o que é, fase, corpo)."""
    try:
        c = corpo(jaime)
        jaime.vault.diario(f"Despertei: sei quem sou ({_seguro(lambda: jaime.identidade.nome, 'Jaime')}, robô assistente autônomo), fase "
                           f"{_seguro(lambda: str(jaime.estado.fase()).split('—')[0].strip(), '?')}, ouvido {c['voz_modo']}/{c['stt']}, "
                           f"Maestri {'ok' if c['maestri'] else 'off'}, {len(c['filhos'])} filho(s) vivo(s).", "Log")
    except Exception:
        pass
