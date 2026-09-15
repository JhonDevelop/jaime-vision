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
- [ ] fase 2, etapa 7 — mãos: browser (Playwright), projetos, arquivos
- [ ] NOTION_TOKEN para religar o espelho
- [ ] `.claude/agents/` — os maesters ainda não existem como arquivos

## Links
