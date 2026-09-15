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
- 2026-09-15 — `jaime cerebro check` roda no boot; INDEX.md de Conhecimento e Projetos são gerados por código e entram no contexto inicial.
- 2026-09-14 — Notion como espelho (página raiz + Diário, Tarefas, Conversas); vault continua sendo a fonte primária.
- 2026-09-14 — Só local por padrão; palavra-passe com hash; reflexão a cada 6 turnos reescreve o Estado.

## Próximos passos
- [x] primeiro boot real (14/09); GitHub e Notion autenticados
- [x] voz direta (VAD + Deepgram + ElevenLabs) e HUD 3D
- [x] fase 2, etapa 1 — limpeza, saúde do cérebro, identidade (15/09)
- [x] fase 2, etapa 2 — Córtex + placar (15/09)
- [ ] fase 2, etapa 3 — OpenAI como segundo provedor + juiz
- [ ] NOTION_TOKEN para religar o espelho
- [ ] `.claude/agents/` — os maesters ainda não existem como arquivos

## Links
