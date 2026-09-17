"""Multilíngue — o J.A.I.M.E ouve e fala português com o resto do mundo dentro.

O pedido (17/09): «ele precisa ser multilinguagem de transcrição, para caso precise falar ou receber outras
línguas, ou falar nomes em inglês, projetos em inglês».

O problema era em dois lados opostos, e os dois estavam travados:

**Ouvindo.** O idioma estava fixo em `pt-BR` em cinco lugares diferentes — Deepgram em fluxo, Deepgram em
lote, Whisper local, OpenAI Realtime e o modo conversa. Com idioma fixo, o reconhecedor força tudo para o
português: «GearHead» virava «guiar head», «escrow» virava «escrói», «worktree» virava «work tri». O nome
do projeto do João chegava errado no modelo, e daí em diante tudo o que ele fazia era com o nome errado.

**Falando.** Pior: a instrução da voz dizia, com essas palavras, «nenhuma sílaba em inglês». Eu escrevi isso
para consertar o sotaque, e de quebra proibi o Jaime de pronunciar o nome dos projetos dele.

O que muda: o Deepgram nova-3 aceita `language=multi`, que reconhece a troca de língua dentro da mesma
frase — é exatamente o caso de quem fala português e cita nome em inglês. O Whisper fica em português por
padrão, porque a detecção automática dele às vezes vira a frase inteira para o inglês por causa de uma
palavra; mas dá para trocar.

E os NOMES PRÓPRIOS entram como `keyterm`: o reconhecedor recebe a lista do que existe na vida do João
(projetos, pessoas, termos) e passa a acertá-los em vez de inventar som parecido. Isso vale mais que
qualquer ajuste de modelo, porque erro de nome próprio é o que mais atrapalha."""
from __future__ import annotations
import os
from pathlib import Path
from urllib.parse import quote

# `multi` = o nova-3 identifica a língua frase a frase e aceita troca no meio. Quem quiser travar num
# idioma põe `pt-BR`, `en`, `es`… em JAIME_STT_IDIOMA.
IDIOMA_STT = os.environ.get("JAIME_STT_IDIOMA", "multi")
# O Whisper local continua em português: a autodetecção dele vira a frase inteira para o inglês por causa
# de uma palavra estrangeira, e errar a frase toda é pior que errar uma palavra.
IDIOMA_WHISPER = os.environ.get("JAIME_WHISPER_IDIOMA", "pt")
# O Realtime aceita um idioma só; `pt` mantém a conversa em português e ainda solta nome em inglês.
IDIOMA_REALTIME = os.environ.get("JAIME_REALTIME_IDIOMA", "pt")

MAX_KEYTERMS = 40
# O que sempre entra, mesmo antes de ler o vault.
BASE = ("Jaime", "J.A.I.M.E", "João Vitor Leal", "Gabriel Mello", "Franca", "Obsidian", "Maestri",
        "Codex", "Gemini", "Claude", "cockpit", "worktree", "escrow", "vault", "prompt", "commit")


def termos_do_vault(vault=None, limite: int = MAX_KEYTERMS) -> list[str]:
    """Nomes que existem na vida do João: projetos e pessoas. É o que o reconhecedor mais erra.

    Vem do vault porque é lá que a verdade mora — nome de projeto novo passa a ser reconhecido no boot
    seguinte, sem ninguém editar lista nenhuma."""
    termos = list(BASE)
    if vault is None:
        return termos[:limite]
    try:
        raiz = Path(getattr(vault, "root", "."))
        for p in sorted((raiz / "20-Projetos").glob("*.md")):
            if p.stem not in ("INDEX",):
                termos.append(p.stem)
    except Exception:
        pass
    try:
        import re
        txt = vault.read("10-Eu/Pessoas.md") or ""
        # linhas de lista e cabeçalhos são onde os nomes ficam; pega a primeira palavra maiúscula
        for m in re.finditer(r"^(?:##+\s*|-\s*)([A-ZÀ-Ý][\wÀ-ÿ]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ]+)?)", txt, re.M):
            termos.append(m.group(1).strip())
    except Exception:
        pass
    vistos, saida = set(), []
    for t in termos:
        k = t.lower()
        if k not in vistos and 2 < len(t) <= 40:
            vistos.add(k); saida.append(t)
    return saida[:limite]


def query_deepgram(vault=None, idioma: str | None = None) -> str:
    """O trecho de query com idioma e keyterms, pronto para colar na URL do Deepgram."""
    partes = [f"language={idioma or IDIOMA_STT}"]
    partes += [f"keyterm={quote(t)}" for t in termos_do_vault(vault)]
    return "&".join(partes)
