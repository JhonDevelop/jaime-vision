# Jaime

Assistente pessoal e operacional com voz, memória própria (vault Obsidian) e acesso real ao computador — construído sobre o **Claude Agent SDK**.

```
você fala ──► ouvido (Silero VAD + STT, ativação por "Jaime") ──► JAIME (orquestrador) ──► maesters ──► ferramentas
                                              │  cérebro: vault/ (Obsidian)      (shell, git, MCPs,
                                              │  vigia: confirmações            WhatsApp, agenda)
                                              └──► voz (TTS) ──► você
```

## Peças

| Peça | Onde | O que faz |
|---|---|---|
| **Jaime** (orquestrador) | `jaime/orchestrator/` | Processo persistente com o Agent SDK. Recebe texto ou voz, decide, delega, responde. |
| **Maesters** | `.claude/agents/*.md` | Especialistas: dev, agenda, comms, arquivista, ops. Cada um com ferramentas e regras próprias. |
| **Cérebro** | `vault/` + `jaime/brain/` | Vault Obsidian. Identidade, regras, projetos, tarefas, diário. Jaime lê no início e escreve durante o dia. |
| **Vigia** | `jaime/vigia/` | Hooks que interceptam ações perigosas e exigem "confirmo". |
| **HUD** | `jaime/hud/` | Interface estilo Jarvis: anéis que pulsam quando ele fala, monitor da máquina, raciocínio e produção ao vivo, porta com palavra-passe. |
| **Estado** | `jaime/brain/estado.py` + `vault/01-Estado/` | Autoconsciência: fase, situação, última conversa, máquinas; reescrito pelo próprio Jaime. |
| **Espelho** | `jaime/brain/notion_sync.py` | Cérebro compartilhado no Notion (Estado, Diário, Tarefas, Conversas). |
| **Voz** | `jaime/voice/` | Silero VAD → Whisper/Deepgram (STT) → ativação por "Jaime" → ElevenLabs em PCM streaming (TTS). Ver `docs/VOZ.md`. |
| **Canais** | `jaime/channels/` + `jaime/server.py` | CLI, HUD, WhatsApp (Evolution API / Meta), telefone (Twilio), `/ask` para integrações. |

## Começar em 5 minutos

```bash
git clone <este repo> && cd jaime
bash scripts/install.sh          # venv + deps + .env
cp .env.example .env             # preencha ANTHROPIC_API_KEY
python -m jaime chat             # conversa por texto
python -m jaime voice            # modo voz (precisa das deps de voz)
python -m jaime hud              # interface Jarvis (local) + apresentação + palavra-passe
python -m jaime serve            # API + webhooks (WhatsApp)
```

Abra a pasta `vault/` no Obsidian. É o cérebro do Jaime — edite as notas e ele passa a agir diferente.

## Documentação
- `docs/ARQUITETURA.md` — como as peças conversam
- `docs/SEGURANCA.md` — o que o Vigia bloqueia e por quê
- `docs/ROADMAP.md` — ordem de construção
- `CLAUDE.md` — a constituição do Jaime (lida em toda sessão)
