# PR — Fase 3, etapas 6 e 7: memória semântica e autoevolução

**Branch:** `feat/fase3-memoria-evolucao` → `main`

## O que muda
- `jaime/brain/indice.py`: índice FTS5 do vault (derivado, gitignored), busca sem acentos, BM25, reindex incremental;
  `Vault.buscar` usa o índice acima de 500 notas; **recall proativo** injeta até 3 lembretes do vault em cada turno;
  ferramenta `recordar`.
- `jaime/evolucao.py` + MCP `evolucao`: proposta semanal (`0 9 * * 1 · propor melhoria`) ou a pedido; "implementa M-0001"
  cria worktree `~/Jaime/worktrees/<slug>` na branch `jaime/<slug>`, implementa com o Agent SDK confinado, roda `pytest`,
  escreve `docs/PR-jaime-<slug>.md`, commita. Merge só com "confirmo". Propostas em `01-Estado/Propostas.md`.
- HUD: eventos `evolucao` (aviso quando uma melhoria fica pronta) e `memória` no painel Raciocínio.

## Como testar
```
pytest -q                                   # 102 testes; índice em vault temporário, evolução em repositório git temporário
# HUD: "Jaime, quanto ficou o orçamento do BUB?" → painel Raciocínio mostra "memória: 20-Projetos/BUB.md"
# "Jaime, propõe uma melhoria" → M-0001; "implementa M-0001" → branch jaime/<slug> pronta com PR
```
