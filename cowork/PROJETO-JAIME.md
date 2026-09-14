# Jaime — necessidades e funcionalidades

Backlog do projeto. Derivado de `docs/ROADMAP.md` (fases 0–7) e do estado real do
repositório em 14/09/2026. **Esta é a fonte de verdade do backlog**; o roadmap manda
na ordem das fases, este arquivo manda no status de cada funcionalidade.

Regra: nada aqui é marcado como pronto sem evidência no repo. O que não existe
está escrito como **não consta**, não como "pendente".

## Legenda

| Marca | Significa |
|---|---|
| ✅ | Pronto e verificado — há evidência executável (teste, execução) |
| 🟡 | Código escrito, **nunca executado nem testado** |
| 🔴 | Quebrado ou bloqueando outra coisa |
| ⬜ | Não consta no repo |
| 🔒 | Exige "confirmo" do João para operar |

> Só F6 está ✅ — é a única verificável sem executar o Jaime. O ambiente onde este
> arquivo foi escrito não tem `claude_agent_sdk` nem `pytest` instalados, então o
> critério da fase 0 segue não comprovado.

## Necessidades (o porquê)

1. **Uma cabeça só.** O João não quer cinco assistentes; quer um que saiba o contexto
   de todos os projetos e delegue internamente.
2. **Memória que ele consegue editar.** O cérebro é markdown no Obsidian, não um banco
   opaco. Se o Jaime entende errado, o João abre a nota e corrige.
3. **Mãos de verdade.** Shell, git, arquivos, MCPs. Um assistente que só conversa não
   resolve o dia.
4. **Voz como entrada padrão.** Digitar é o caminho lento; falar é o rápido.
5. **Freio antes do irreversível.** Enviar, apagar, dar push em `main`, pagar — tudo
   passa pelo Vigia e espera "confirmo".
6. **Segredo nunca vaza.** Nem em resposta, nem em commit, nem em nota, nem no Notion.

## Funcionalidades

### Fase 0 — Esqueleto
Critério de pronto (roadmap): `python -m jaime chat` responde e escreve no vault.

| # | Funcionalidade | Status | Evidência / o que falta |
|---|---|---|---|
| F1 | Orquestrador persistente, um processo, vários canais | 🟡 | `jaime/orchestrator/jaime.py` — `ClaudeSDKClient` + `asyncio.Lock`. Nunca conectou. |
| F2 | Cérebro: vault Obsidian + ferramentas `mcp__cerebro__*` | 🟡 | `jaime/brain/vault.py`, `brain/tools.py` (6 ferramentas). `tests/test_vault.py` existe mas **não foi executado**. |
| F3 | Vigia: hooks PreToolUse + fluxo "confirmo" | 🟡 🔒 | `jaime/vigia/hooks.py` — 14 padrões de bash, tools de envio, `.env` e `00-Jaime/` protegidos. Sem teste do hook em si. |
| F4 | Maesters carregados de `.claude/agents/*.md` | 🔴 | `orchestrator/maesters.py` lê o diretório, mas **`.claude/` não existe**. `carregar_maesters()` devolve `{}` — hoje não há nenhum maester e a delegação não acontece. Bloqueia F9, F14, F20. |
| F5 | CLI `python -m jaime chat` | 🟡 | `jaime/main.py` — três modos (chat/voice/serve). Critério da fase 0 **não comprovado**. |
| F6 | Higiene de repo e segredos | ✅ | `.gitignore` de Python (o anterior era template do Dynamics 365/AL e não ignorava `.env`). `.env.example` com as 14 variáveis de `config.py` + `ANTHROPIC_API_KEY`. Verificado: `git check-ignore` confirma `.env` ignorado e `.env.example` versionado; `git grep` não acha chave preenchida. Notas do vault seguem versionadas. |

### Fase 1 — MCPs conectados
Critério (roadmap): GitHub, Notion e n8n autenticados; maester-dev abre branch e commita.

| # | Funcionalidade | Status | Evidência / o que falta |
|---|---|---|---|
| F7 | `.mcp.json` declarando github, notion, n8n | ⬜ | **Não consta.** `docs/ARQUITETURA.md` e `n8n/README.md` afirmam "já configurado em `.mcp.json`" — é falso hoje. Corrigir os docs junto. |
| F8 | Autenticação dos MCPs via `claude` → `/mcp` | ⬜ 🔒 | Passo manual do João, no navegador dele. Não automatizável. Depende de F7. |
| F9 | maester-dev abre branch e commita | ⬜ | Depende de F4 + F7. Push e PR ficam atrás do Vigia. |
| F10 | Notion como espelho do vault (Diário, Tarefas, Conversas) | ⬜ | **Nenhum código de sincronização existe** — Notion só aparece citado em `docs/ARQUITETURA.md` e no perfil do João. Os bancos não constam. |
| F11 | Estado do Jaime + primeiro boot com apresentação | ⬜ | `vault/01-Estado/Estado.md` **não consta**; `Vault.contexto_inicial()` não o lê; `main.py` imprime só "Jaime online.". |
| F12 | Permissões estáticas `.claude/settings.json` | ⬜ | **Não consta.** Hoje o SDK roda em `permission_mode="acceptEdits"` com `allowed_tools` fixo no código. |

### Fase 2 — Agenda
Critério: n8n expõe Google Calendar; maester-agenda lista e cria eventos.

| # | Funcionalidade | Status | Evidência / o que falta |
|---|---|---|---|
| F13 | Workflows n8n de calendário (`listar_dia`, `criar_evento`) | ⬜ | `n8n/README.md` **sugere** os workflows; nenhum foi construído. O servidor n8n não constava conectado na última sessão. |
| F14 | maester-agenda: prazos, rotina, `30-Tarefas/Inbox.md` | ⬜ | Depende de F4 + F13. O formato da tarefa já está definido e testado em código: `- [ ] descrição @projeto ⏳ prazo`. |

### Fase 3 — Voz local
Critério: wake word → Whisper → ElevenLabs, latência < 3 s por turno.

| # | Funcionalidade | Status | Evidência / o que falta |
|---|---|---|---|
| F15 | Wake word (Porcupine) | 🟡 | `jaime/voice/wake.py`. Usa "jarvis" built-in; "jaime" exige `.ppn` treinado no console da Picovoice. Nunca rodou. |
| F16 | STT — Deepgram na nuvem, faster-whisper local como fallback | 🟡 | `jaime/voice/stt.py`, `nova-3` em pt-BR. Nunca rodou. |
| F17 | TTS — ElevenLabs em streaming | 🟡 | `jaime/voice/tts.py`. Sem chave, imprime no terminal — dá para testar o resto sem áudio. |
| F18 | Latência < 3 s por turno | ⬜ | **Nunca medido.** Precisa de instrumentação no `VoiceLoop`; não existe. |

### Fase 4 — WhatsApp
Critério: Evolution API → `/webhook/whatsapp`; respostas só ao dono.

| # | Funcionalidade | Status | Evidência / o que falta |
|---|---|---|---|
| F19 | Webhook WhatsApp com resposta restrita ao dono | 🟡 🔒 | `jaime/server.py` + `channels/whatsapp.py`. A regra do dono está escrita: número diferente de `JAIME_OWNER_PHONE` vira linha de diário, não vira ordem. Falta instância da Evolution API e host público. |

### Fase 5 — Arquivista diário
Critério: "fecha o dia" consolida o diário nas notas de projeto.

| # | Funcionalidade | Status | Evidência / o que falta |
|---|---|---|---|
| F20 | Comando "fecha o dia" → consolidação | ⬜ | **Não consta.** Depende de F4 (maester-arquivista). A regra 6 da constituição já exige o registro ao encerrar tarefa longa. |

### Fase 6 — Telefone
Critério: Twilio `<Gather>` → Jaime.

| # | Funcionalidade | Status | Evidência / o que falta |
|---|---|---|---|
| F21 | Ligação por Twilio `<Gather speech>` em pt-BR | 🟡 | `jaime/channels/telephony.py` — esqueleto de 25 linhas, TwiML pronto. Falta número Twilio e webhook público. |

### Fase 7 — Computer use
Critério: controle visual de apps sem API, só com confirmação.

| # | Funcionalidade | Status | Evidência / o que falta |
|---|---|---|---|
| F22 | Controle visual de apps sem API | ⬜ 🔒 | **Não consta.** Último item do roadmap. Cada ação exige confirmação. |

## Placar

| Fase | ✅ | 🟡 | 🔴 | ⬜ |
|---|---|---|---|---|
| 0 — Esqueleto | 1 | 4 | 1 | 0 |
| 1 — MCPs | 0 | 0 | 0 | 6 |
| 2 — Agenda | 0 | 0 | 0 | 2 |
| 3 — Voz | 0 | 3 | 0 | 1 |
| 4 — WhatsApp | 0 | 1 | 0 | 0 |
| 5 — Arquivista | 0 | 0 | 0 | 1 |
| 6 — Telefone | 0 | 1 | 0 | 0 |
| 7 — Computer use | 0 | 0 | 0 | 1 |
| **Total** | **1** | **9** | **1** | **11** |

## Caminho crítico

```
F6 (segredos) ✅ ─┐
F5 (chat roda)  ─┼─► F4 (maesters) ─► F7 (.mcp.json) ─► F8 (auth) ─► F9 (dev commita)
                │                          │
                └─► F11 (estado/boot)      └─► F10 (Notion) ─► F13/F14 (agenda)
```

F4 é o gargalo: sem `.claude/agents/`, metade do backlog não sai do lugar.

## O que exige "confirmo" do João

F3 (o mecanismo em si), F8 (autenticar MCP), F9 (push e PR), F19 (enviar WhatsApp),
F22 (qualquer ação visual). Mais: preencher `.env` com chave real, apagar arquivo,
push em `main`, pagamento, produção.

## Fora do escopo do Cowork

Quem escreve em `vault/01-Estado/Estado.md` é o próprio Jaime, por reflexão.
O gerente do projeto propõe a mudança de fase; não a executa.
