# PR — Fase 2, etapa 6: cérebro de estudo

**Branch:** `feat/fase2-estudo` → `main`

## O que muda
- `jaime/estudo/problemas.py` — `90-Estudo/Problemas.md` (ID, origem, contexto, tentativas; sem duplicar parecidos).
- `jaime/estudo/loop.py` — um problema por ciclo, 15 min, turno avulso do Agent SDK em `/tmp/jaime-lab` com hook que
  nega escrita/comando fora do laboratório. Resolvido → `50-Conhecimento/<slug>.md` + INDEX + aprendizado no Estado +
  placar + skill (`.claude/skills/<slug>/`) quando devolvida. Não resolvido → tentativa e "o que falta".
- Gatilhos automáticos: erro de ferramenta repetido, "pesquisa isso"/"não sei como" do João, resposta que admitiu não saber.
- Ferramentas MCP `estudo`: `abrir_problema`, `problemas_abertos`, `resolver_problema`. HUD: chip "estudando: N".
- Mente contínua mínima: `rodar_em_ciclos` a cada 30 min quando ocioso (cérebro liberado, ninguém falando, lock livre).

## Como testar
```
pytest -q                                   # 66 testes; ciclo resolvido com pesquisador offline, sandbox negando fora do lab
# HUD: "pesquisa isso: como rodar Whisper em GPU no Mac Intel" → chip estudando: 1; em ≤30 min ocioso ele estuda
```

## Critério §3 linha 6
Um problema real fechado com conhecimento gerado e placar atualizado — o teste `test_ciclo_resolve_com_pesquisador_offline`
cobre o fluxo inteiro; ao vivo depende de um ciclo ocioso (30 min) ou de `resolver_problema`.
