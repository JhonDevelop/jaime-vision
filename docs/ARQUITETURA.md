# Arquitetura

```
 entrada                 núcleo                          mãos
 ───────                 ──────                          ────
 CLI ─────────┐
 voz (wake→STT)┤   ┌──────────────────────────┐   ┌─ Bash / Read / Write (PC, arquivos, código)
 WhatsApp ─────┼──►│  JAIME  (ClaudeSDKClient)│──►├─ mcp__cerebro__*   (vault Obsidian)
 API /ask ─────┤   │  persistente, 1 processo │   ├─ mcp__github__*    (repos privados)
 Twilio ───────┘   │  system prompt = CLAUDE.md│   ├─ mcp__notion__*
                   │  + contexto do vault     │   └─ Task → maesters (subagentes)
                   └───────────┬──────────────┘
                               │ hooks PreToolUse
                           ┌───┴───┐
                           │ VIGIA │  nega ação perigosa até "confirmo"
                           └───────┘
```

## Fluxo de uma fala
1. Wake word dispara; grava até 0,9s de silêncio; STT devolve texto.
2. `Jaime.ask_stream(texto, canal="voice")` — o canal muda o estilo (curto, sem markdown).
3. Claude lê o contexto do vault (injetado no system prompt), decide sozinho ou delega via `Task` a um maester.
4. Cada chamada de ferramenta passa pelo Vigia. Bloqueou? Jaime pede "confirmo".
5. Texto sai frase a frase para o TTS. Decisões viram linha no diário.

## Por que um processo persistente
Reiniciar o agente a cada fala custa segundos e perde o contexto da conversa. O `ClaudeSDKClient`
fica conectado; `asyncio.Lock` serializa pedidos de canais diferentes.

## Onde cada coisa mora
| Preocupação | Arquivo |
|---|---|
| Quem o Jaime é | `CLAUDE.md`, `vault/00-Jaime/` |
| Especialistas | `.claude/agents/*.md` (lidos por `orchestrator/maesters.py`) |
| Ferramentas de memória | `brain/tools.py` → servidor MCP in-process `cerebro` |
| Regras de bloqueio | `vigia/hooks.py` |
| MCPs externos | `.mcp.json` (auth via `claude` → `/mcp`) |
| Permissões estáticas | `.claude/settings.json` |
| Voz | `voice/` |
| Canais HTTP | `server.py`, `channels/` |

## Memória: três camadas
1. **Sessão** — histórico do `ClaudeSDKClient` (some ao reiniciar).
2. **Diário** — `vault/40-Diario/AAAA-MM-DD.md`, escrito durante o dia.
3. **Notas** — projetos, perfil, conhecimento; o Arquivista consolida o diário nelas.

Quando o vault crescer (milhares de notas), trocar `Vault.buscar` por um índice (sqlite FTS5 ou embeddings) sem mudar a interface das ferramentas.


## Córtex (fase 2, etapa 2) — quem pensa em cada tarefa
`jaime/cortex/roteador.py` classifica cada fala (código · pesquisa · redação · decisão · imagem · voz · rotina) por
pistas de texto, sem chamar modelo, e escolhe o modelo pela política do placar: maior taxa de acerto (suavizada)
para aquele tipo, com `JAIME_CORTEX_EXPLORACAO` (10%) de chance de testar outro candidato. Candidatos vêm do `.env`
(`JAIME_MODEL_DECISAO` Fable 5.1, `JAIME_MODEL_CODIGO` Opus 5, `JAIME_MODEL_PADRAO` Sonnet, `JAIME_MODEL_ROTINA` Haiku).

`jaime/cortex/placar.py` guarda acertos/erros/latência/custo por (modelo, tipo) em `vault/.placar.json` (bruto,
gitignored) e `vault/01-Estado/Placar.md` (legível). Cada turno entra como acerto provisório; se o turno seguinte
for uma correção do João ("errado", "não era isso", "refaz", "de novo"), `corrigir_ultimo()` vira o acerto em erro.

**Troca de modelo sem perder a conversa:** o `ClaudeSDKClient` do SDK 0.2.152 tem `set_model(model)`; o
orquestrador chama antes de cada turno quando o roteador muda a escolha. Recriar o cliente perderia o contexto.
`python -m jaime cortex explicar "<tarefa>"` mostra tipo, modelo e porquê.


## Dois provedores (fase 2, etapa 3) — OpenAI ao lado da Anthropic
`jaime/cortex/provedores/` tem a interface única `responder(prompt, contexto, ferramentas=None) → Resposta`:
- `anthropic.py`: `claude_agent_sdk.query()` de um turno, sem ferramentas — é o árbitro e a segunda opinião.
- `openai.py`: Responses API (`JAIME_OPENAI_MODEL`, padrão `gpt-5.5`; `web_search` quando a tarefa é pesquisa).
  Lista real vista pela chave em 15/09/2026: gpt-5.5, gpt-5.5-pro, gpt-5.6-luna, gpt-5.6-sol; voz gpt-realtime-2,
  gpt-realtime-whisper, gpt-4o-mini-tts; imagem gpt-image-2.5-flare/sunburst. Não existem "GPT-6 Astra" nem "5.6 Terra".

**Regra:** ações no mundo (ferramentas do Agent SDK, MCPs, Vigia) continuam só pela Anthropic, no cliente
persistente. A OpenAI produz texto, decisões e — nas etapas 9/10 — voz e imagem. O roteador só lista
`openai:<modelo>` como candidato para *pesquisa* e *redação*, e só quando há `OPENAI_API_KEY`. Se a chamada
falhar (sem crédito, rede), o mesmo turno cai na Anthropic e o placar anota o erro.

**Juiz** (`jaime/cortex/juiz.py`): tarefa do tipo *decisão*, ou "pensa bem" / "compara" no texto → os dois
provedores respondem em paralelo e o Fable 5.1 (`JAIME_MODEL_DECISAO`) escolhe A, B ou mescla, com uma frase
de justificativa que vai para o diário (seção Decisões) e para o painel Raciocínio do HUD. Custa o dobro; se um
provedor falhar, devolve a resposta do outro sem arbitrar. O turno do juiz roda fora do cliente persistente
(sem as mãos), com o mesmo system prompt do Jaime como contexto.
