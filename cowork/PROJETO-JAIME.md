# Projeto Jaime — brief para o Cowork

> Abra este arquivo como projeto no Claude Cowork (ou cole como contexto de projeto). É a fonte única de
> necessidades e funcionalidades do Jaime. O `maester-jaime` mantém; o João aprova.

## Objetivo
Um assistente pessoal e operacional — o "Jarvis" do João — que fala, ouve, lembra, age no computador e nos
serviços, sabe quem é e em que fase está, e melhora a cada semana.

## Pilares
1. **Cérebro** — vault Obsidian local (fonte primária) + espelho no Notion (compartilhado entre máquinas e celular).
2. **Autoconsciência** — `01-Estado/Estado.md` reescrito por ele mesmo; apresentação ao ligar em máquina nova.
3. **Mãos** — Agent SDK com shell, arquivos, git, MCPs (GitHub, Notion, n8n), computer use quando não houver API.
4. **Voz e presença** — wake word, STT, TTS, HUD estilo Jarvis com monitor da máquina e raciocínio visível.
5. **Segurança** — local por padrão, palavra-passe falada/digitada, Vigia para ações irreversíveis.

## Funcionalidades — status
| # | Funcionalidade | Nível | Status |
|---|---|---|---|
| F1 | Conversa por texto (CLI/HUD) com contexto do vault | funcional | feito (v0.2) |
| F2 | Ferramentas de memória: lembrar, buscar, diário, tarefas, estado | funcional | feito |
| F3 | Maesters: dev, agenda, comms, arquivista, ops, jaime | funcional | feito (prompts) |
| F4 | Vigia: bloqueio + "confirmo" | funcional | feito |
| F5 | Palavra-passe falada/digitada, timeout, "tranca" | funcional | feito |
| F6 | Apresentação em máquina nova + registro de máquinas | funcional | feito |
| F7 | Reflexão automática a cada 6 turnos → Estado | funcional | feito |
| F8 | HUD: anéis, monitor, raciocínio, produção, conversa | funcional | feito (v1 visual) |
| F9 | Espelho Notion: Estado, Diário, Tarefas, Conversas | funcional | feito (precisa NOTION_TOKEN) |
| F10 | MCPs GitHub/Notion/n8n autenticados no SDK | funcional | pendente (`/mcp`) |
| F11 | Voz local completa (wake → STT → TTS) | funcional | esqueleto; calibrar |
| F12 | Agenda via n8n (Google Calendar) | funcional | pendente |
| F13 | WhatsApp (Evolution API) só para o dono | funcional | esqueleto |
| F14 | Ligações (Twilio) | funcional | esqueleto |
| F15 | Fechamento do dia automático (cron n8n → /ask "fecha o dia") | ideal | pendente |
| F16 | Busca semântica no vault (FTS5/embeddings) quando passar de 1k notas | ideal | pendente |
| F17 | HUD: painel por maester (quem está trabalhando em quê) | ideal | pendente |
| F18 | Modo "sombra": Jaime observa a tela e sugere sem agir | ideal | pendente |
| F19 | Autoinstalação: `jaime bootstrap` em máquina limpa | ideal | pendente |
| F20 | Jaime propõe melhorias semanais em si mesmo (PR + "confirmo") | estratégica | pendente |
| F21 | Camada de negócio: métricas do BUB/estamparia no HUD | estratégica | pendente |
| F22 | Delegação longa: tarefas de horas com checkpoints e relatório | estratégica | pendente |

## Necessidades (o que o Jaime precisa do João)
- `.env` preenchido: ANTHROPIC_API_KEY, NOTION_TOKEN (integração interna com acesso à página raiz), chaves de voz.
- MCPs autenticados uma vez por máquina (`claude` → `/mcp`).
- Um usuário/pasta de trabalho definidos (`JAIME_WORKSPACE`).
- Feedback: quando ele errar, dizer "registra: …" para virar aprendizado.

## Como trabalhar neste projeto
- Repositório privado no GitHub; branch por feature; `maester-dev` aplica o checklist de produção.
- Sessões no Claude Code na pasta do repo (ver `docs/HANDOFF-CLAUDE-CODE.md`).
- Cada marco fechado → linha em `vault/20-Projetos/Jaime.md` → "Fase" no Estado.

## Fase atual
**0 → 1.** Esqueleto completo; falta o primeiro boot real na máquina do João, MCPs autenticados e NOTION_TOKEN.
