"""Pré-aquece a voz: as frases que o J.A.I.M.E mais repete ficam prontas no disco, e saem em ~0 ms.

Medido em 17/09, com a voz Jarvis: sintetizar «Ok, sem problemas.» levava **3,5 segundos** para 2,3 s de
fala. O contexto já tinha sido enxugado de 65 mil para 4,7 mil tokens, então o gargalo deixou de ser o
modelo pensar e passou a ser o TTS falar. Numa conversa curta — que é a maioria — esses 3,5 s são a
diferença entre um assistente que responde e um que faz esperar.

A saída é boba e eficaz: as frases fixas dele não mudam. "Ok.", "Certo.", "Pronto.", "Palavra-passe, por
favor.", as muletas, as confirmações. Sintetiza uma vez, guarda o PCM, e nas próximas o `tocar_pronto()`
toca do disco em ~0 ms.

    .venv/bin/python -m jaime.ops.aquecer_voz          # aquece o que falta
    .venv/bin/python -m jaime.ops.aquecer_voz --tudo   # refaz, mesmo o que já está lá

Rode de novo depois de trocar a voz ou o estilo no `.env`: o cache é nomeado pela configuração sonora que
o produziu, então voz nova gera arquivo novo e o antigo não é usado por engano."""
from __future__ import annotations
import argparse, time

# O que ele diz o tempo todo. Vem da conduta que o João pediu: quando a fala dele não pede ação, a resposta
# é uma frase e ponto.
FRASES = [
    # o essencial, e só
    "Ok.", "Ok, sem problemas.", "Certo.", "Pronto.", "Feito.", "Tranquilo.", "Fechado.",
    "Sim, senhor.", "Entendi.", "Anotado.", "Já vai.", "Um instante.",
    # acesso
    "Palavra-passe, por favor.", "Bem-vindo de volta, João. Estou às ordens.",
    "Não foi essa. Tenta de novo.",
    # trabalho em curso
    "Está na tela.", "Fechei.", "Abrindo.", "Rodando os testes.", "Lendo os arquivos.",
    "Pesquisando na web.", "Escrevendo o código.",
    # «Anotando no vault.», «O Codex entregou.» e companhia saíram em 17/09: o João não quer ouvir a
    # contabilidade interna dele (ver SILENCIOSAS em jaime/voice/narrador.py). Frase que ele não diz
    # mais não precisa estar pronta no cache.
    # quando não sabe ou não pode
    "Não sei.", "Não entendi.", "Isso é com o João.", "Preciso do seu confirmo.",
    "Não peguei. Pode repetir?", "Quer o detalhe?",
    # as muletas, para quando ainda assim precisarem sair
    "Deixa eu ver…", "Só um segundo.", "Peraí, já te digo.",
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Deixa as frases curtas do J.A.I.M.E prontas no cache.")
    ap.add_argument("--tudo", action="store_true", help="refaz também o que já está no cache")
    a = ap.parse_args(argv)

    from ..config import settings
    from ..voice.tts import TTS
    tts = TTS(settings)
    cache = tts._cache_frases
    if not cache.habilitado:
        print("✗ cache desligado (JAIME_CACHE_FRASES=off)"); return 2
    tts._cache_atualizar()

    print(f"voz: {tts.motor} · {tts._voz_cache()} · velocidade {tts.velocidade}")
    print(f"cache em {cache.pasta}\n")
    novas = prontas = falhas = 0
    t0 = time.time()
    for frase in FRASES:
        if not a.tudo and cache.get(frase):
            prontas += 1
            continue
        t = time.time()
        pcm = tts._sintetizar(frase, guardar_anterior=False)
        if not pcm:
            print(f"  ✗ {frase[:44]}"); falhas += 1; continue
        cache.put(frase, pcm)
        novas += 1
        print(f"  ✓ {frase[:44]:<46} {(time.time()-t)*1000:4.0f} ms → agora sai em ~0 ms")
    print(f"\n{novas} sintetizadas, {prontas} já estavam prontas, {falhas} falharam "
          f"({time.time()-t0:.0f}s no total).")
    if novas:
        print("Essas frases deixam de custar de 1,5 a 3,5 segundos cada vez que ele as diz.")
    return 0 if not falhas else 1


if __name__ == "__main__":
    raise SystemExit(main())
