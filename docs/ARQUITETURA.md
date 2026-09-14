# Arquitetura

```
 entrada                 núcleo                          mãos
 ───────                 ──────                          ────
 CLI ─────────┐
 voz (wake→STT)┤   ┌──────────────────────────┐   ┌─ Bash / Read / Write (PC, arquivos, código)
 WhatsApp ─────┼──►│  JAIME  (ClaudeSDKClient)│──►├─ mcp__cerebro__*   (vault Obsidian)
 n8n /ask ─────┤   │  persistente, 1 processo │   ├─ mcp__github__*    (repos privados)
 Twilio ───────┘   │  system prompt = CLAUDE.md│   ├─ mcp__notion__* / mcp__n8n__*
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
