# PR — Fase 2, etapa 4: cérebro emocional

**Branch:** `feat/fase2-emocional` → `main`

## O que muda
- `jaime/emocao/` (perfil, perguntas, momento, humor, prosodia, tools) — ver `docs/ARQUITETURA.md`, seção "Cérebro emocional".
- Notas novas em `vault/10-Eu/`: `Datas.md`, `Jeito.md`, `Perguntas-Feitas.md` (com cabeçalho; o Jaime preenche).
- Ferramentas MCP `emocao`: `perguntar_ao_joao` (obrigatória antes de perguntar), `registrar_resposta`,
  `datas_importantes`, `adicionar_data`, `momento_de_hoje`, `humor_atual`, `anotar_jeito`.
- `CLAUDE.md`: regra 7 — toda pergunta ao João passa por `perguntar_ao_joao`.
- System prompt: "Momento de hoje" (aniversário, feriado, prazos, semana pesada); aniversário vira a primeira frase do boot.
- Humor (energia, calor, gravidade, confiança) atualizado pelo tom do João, resultado do turno, hora e momento;
  regras de coerência (nunca leve em problema, nunca grave em conquista, sem drama). Prosódia aplicada na ElevenLabs
  (estabilidade/estilo por humor) e mostrada no header do HUD.

## Como testar
```
pytest -q                                   # 55 testes
# HUD: chip "humor" no header muda ao dizer "tenho um problema urgente…" (grave) ou "funcionou, valeu!" (leve)
# "quando é meu aniversário?" → ele chama perguntar_ao_joao, pergunta, e registra em 10-Eu/Perguntas-Feitas.md
```

## Critério §3 linha 4
Não repete pergunta já respondida (testes + ferramenta); aniversário em `Datas.md` abre o dia (momento no prompt de
apresentação); humor afeta o texto (prosódia no TTS e instruções no prompt via `humor_atual`).
