# Jaime
Este assistente. Repositório privado no GitHub.

## Objetivo
Assistente com voz, cérebro próprio e mãos no computador.

## Status atual
- v0.2 — cérebro conectado (Estado autoatualizado, Origem, conversas), palavra-passe, HUD estilo Jarvis, espelho no Notion, maester-jaime, brief para o Cowork.

## Decisões
- 2026-09-14 — Agent SDK (Python) como núcleo; vault Obsidian como memória.
- 2026-09-14 — Voz sem wake word por modelo: Silero VAD + Deepgram + ativação por nome na transcrição; Opus 5 sem pensamento estendido por voz.
- 2026-09-15 — n8n sai do projeto (pasta, docs, HUD). Automações passam a ser código nosso (scheduler, fase 2 etapa 5) e conectores diretos.
- 2026-09-15 — Nome mora só no frontmatter de 00-Jaime/Identidade.md; renomear é proposta + "confirmo" + branch chore/renomear-x. O boot confere o nome.
- 2026-09-15 — Córtex: modelo escolhido por tarefa (Fable 5.1 decisão, Opus 5 código, Sonnet padrão, Haiku rotina) com placar em 01-Estado/Placar.md; troca via ClaudeSDKClient.set_model, sem perder a conversa.
- 2026-09-15 — OpenAI entra como segundo provedor só para texto/pesquisa/redação (gpt-5.5; Responses API); as mãos ficam na Anthropic. Juiz (Fable 5.1) arbitra decisões e "pensa bem".
- 2026-09-15 — Cérebro emocional: toda pergunta ao João passa por perguntar_ao_joao (10-Eu/Perguntas-Feitas.md; >90 dias confirma em meia frase); Datas.md/Jeito.md; humor em 4 eixos com regras de coerência (nunca leve em problema, nunca grave em conquista, sem drama) dirigindo a prosódia da ElevenLabs.
- 2026-09-15 — Agenda própria: APScheduler no processo lendo 30-Tarefas/Rotinas.md; lembretes em Lembretes.md; hora/clima/feriado respondidos sem modelo. O n8n não volta.
- 2026-09-15 — Cérebro de estudo: 90-Estudo/Problemas.md + ciclo em /tmp/jaime-lab (turno avulso do SDK com hook de sandbox); resolvido vira 50-Conhecimento + skill; mente contínua mínima a cada 30 min quando ocioso.
- 2026-09-15 — Mãos: browser próprio com Playwright (perfil persistente em ~/Jaime/browser-profile), criar_projeto no workspace, organizar arquivos pelas regras do Jeito.md; skills oficiais pdf/docx/xlsx/pptx em .claude/skills.
- 2026-09-15 — Conexões: Google pelo OAuth do projeto do João (token local), Telegram só do dono; tudo que envia fica atrás do Vigia; registro vivo em 01-Estado/Conexoes.md. Instagram/WhatsApp pessoal por libs não oficiais: nunca.
- 2026-09-15 — Voz: gpt-4o-mini-tts (onyx) como motor principal enquanto a cota da ElevenLabs não volta; a persona corta frases de atendente; o humor vira instrução de estilo.
- 2026-09-15 — Mídia: gpt-image-2.5, Blender headless (quando instalado), ffmpeg estático e Deepgram para legendas; a tela é vista por captura e as interações passam pelo Vigia.
- 2026-09-15 — Meta só por APIs oficiais (WhatsApp Cloud + Instagram Messaging), webhook próprio assinado; terceiros viram rascunho e o envio espera "confirmo". Evolution API opcional.
- 2026-09-15 — Modo autônomo: objetivo decomposto em etapas com aceite, checkpoints, pausa no Vigia, limites de horas/custo, relatório no diário.
- 2026-09-15 — `jaime cerebro check` roda no boot; INDEX.md de Conhecimento e Projetos são gerados por código e entram no contexto inicial.
- 2026-09-14 — Notion como espelho (página raiz + Diário, Tarefas, Conversas); vault continua sendo a fonte primária.
- 2026-09-14 — Só local por padrão; palavra-passe com hash; reflexão a cada 6 turnos reescreve o Estado.

## Próximos passos
- [x] primeiro boot real (14/09); GitHub e Notion autenticados
- [x] voz direta (VAD + Deepgram + ElevenLabs) e HUD 3D
- [x] fase 2, etapa 1 — limpeza, saúde do cérebro, identidade (15/09)
- [x] fase 2, etapa 2 — Córtex + placar (15/09)
- [x] fase 2, etapa 3 — OpenAI + juiz (15/09; falta crédito na conta OpenAI para rodar ao vivo)
- [x] fase 2, etapa 4 — cérebro emocional (15/09)
- [x] fase 2, etapa 5 — agenda própria (15/09)
- [x] fase 2, etapa 6 — cérebro de estudo (15/09)
- [x] fase 2, etapa 7 — mãos (15/09)
- [x] fase 2, etapa 8 — conexões (15/09; credencial Google e bot do Telegram são do João)
- [x] fase 2, etapa 9 — voz com persona e emoção (15/09)
- [x] fase 2, etapa 10 — mídia e tela (15/09)
- [x] fase 2, etapa 11 — Meta (15/09; app é do João)
- [x] fase 2, etapa 12 — modo autônomo (15/09)
- [ ] fase 3 — a definir com o João (jogos de verdade, voz em tempo real, casa)
- [ ] NOTION_TOKEN para religar o espelho
- [ ] `.claude/agents/` — os maesters ainda não existem como arquivos

## Links
