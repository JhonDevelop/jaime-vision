# Projeto Jaime — brief para o Cowork

> Abra este arquivo como projeto no Claude Cowork (ou cole como contexto de projeto). É a fonte única de
> necessidades e funcionalidades do Jaime. O `maester-jaime` mantém; o João aprova.

## Objetivo
Um assistente pessoal e operacional — o "Jarvis" do João — que fala, ouve, lembra, age no computador e nos
serviços, sabe quem é e em que fase está, e melhora a cada semana.

## Pilares
1. **Cérebro** — vault Obsidian local (fonte primária) + espelho no Notion (compartilhado entre máquinas e celular).
2. **Autoconsciência** — `01-Estado/Estado.md` reescrito por ele mesmo; apresentação ao ligar em máquina nova.
3. **Mãos** — Agent SDK com shell, arquivos, git, MCPs (GitHub, Notion), computer use quando não houver API.
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
| F10 | MCPs GitHub/Notion autenticados no SDK | funcional | feito (14/09) |
| F11 | Voz local completa (wake → STT → TTS) | funcional | esqueleto; calibrar |
| F12 | Agenda (scheduler próprio + Google Calendar) | funcional | scheduler feito (15/09); Calendar na etapa 8 |
| F13 | WhatsApp (Evolution API) só para o dono | funcional | esqueleto |
| F14 | Ligações (Twilio) | funcional | esqueleto |
| F15 | Fechamento do dia automático (scheduler → "fecha o dia") | ideal | rotina `0 18 * * 5 · fecha a semana` (15/09) |
| F16 | Busca semântica no vault (FTS5/embeddings) quando passar de 1k notas | ideal | pendente |
| F17 | HUD: painel por maester (quem está trabalhando em quê) | ideal | pendente |
| F18 | Modo "sombra": Jaime observa a tela e sugere sem agir | ideal | pendente |
| F19 | Autoinstalação: `jaime bootstrap` em máquina limpa | ideal | pendente |
| F20 | Jaime propõe melhorias semanais em si mesmo (PR + "confirmo") | estratégica | pendente |
| F21 | Camada de negócio: métricas do BUB/estamparia no HUD | estratégica | pendente |
| F22 | Delegação longa: tarefas de horas com checkpoints e relatório | estratégica | fase 2, etapa 12 |
| F23 | Saúde do cérebro (`jaime cerebro check`) + índices gerados por código | funcional | feito (15/09) |
| F24 | Identidade editável: nome no frontmatter, "me chama de X" + confirmo, confirmação no boot | funcional | feito (15/09) |
| F25 | Voz direta: Silero VAD, Deepgram, ativação por nome, fala em streaming, emoção | funcional | feito (14/09) |
| F26 | Observador: contexto da tela em cada fala; oferta de ajuda quando trava | funcional | feito (14/09) |
| F27 | Córtex: roteador de modelos por tipo de tarefa + placar de acertos/erros/custo | funcional | feito (15/09) |
| F28 | OpenAI como segundo provedor (Responses API) + juiz Fable 5.1 para decisões | funcional | feito (15/09) — aguarda crédito na OpenAI |
| F29 | Cérebro emocional: perguntas nunca repetidas, datas/momento do dia, humor em 4 eixos → prosódia da voz e HUD | funcional | feito (15/09) |
| F30 | Agenda própria: scheduler (Rotinas.md), lembretes, relógio, clima, feriados — sem n8n | funcional | feito (15/09) |
| F31 | Cérebro de estudo: problemas em aberto → ciclo em sandbox → conhecimento, skill, placar | funcional | feito (15/09) |
| F32 | Mãos: browser próprio (Playwright), criar projetos, organizar arquivos, skills pdf/docx/xlsx/pptx | funcional | feito (15/09) |
| F33 | Conexões: Google (Gmail/Calendar/Drive por OAuth próprio) + Telegram só do dono; registro em Conexoes.md | funcional | código pronto (15/09) — falta o João criar a credencial Google e o bot |
| F34 | Voz com persona e emoção: gpt-4o-mini-tts (onyx) com instrução pelo humor; sem frases prontas; `jaime voz testar` | funcional | feito (15/09) |
| F35 | Mídia: imagens (gpt-image-2.5), 3D (Blender headless), cortes e legendas (ffmpeg + Deepgram), interação com a tela | funcional | feito (15/09) — Blender a instalar |
| F36 | Meta: WhatsApp Cloud API + Instagram Messaging com webhook próprio; terceiros viram rascunho, envio com confirmo | funcional | código pronto (15/09) — app no Meta for Developers é do João |
| F37 | Modo autônomo: objetivo → etapas com aceite → checkpoints, pausa no Vigia, relatório | estratégica | feito (15/09) |

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
**1 → 2.** Operando localmente (voz, HUD 3D, observador, GitHub/Notion autenticados). Fase 2 (docs/FASE-2-JARVIS.md)
em andamento: **as 12 etapas da fase 2 fechadas em 15/09.** Do João: credencial Google, bot Telegram, app Meta, Blender, permissões do macOS, cota ElevenLabs. Próximo: fase 3 (a definir).
n8n saiu do projeto — automações viram código nosso.
