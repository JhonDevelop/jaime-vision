# Jaime
Este assistente. Repositório privado no GitHub.

## Objetivo
Assistente com voz, cérebro próprio e mãos no computador.

## Status atual
- v0.2 — cérebro conectado (Estado autoatualizado, Origem, conversas), palavra-passe, HUD estilo Jarvis, espelho no Notion, maester-jaime, brief para o Cowork.

## Decisões
- 2026-09-14 — Agent SDK (Python) como núcleo; vault Obsidian como memória; n8n como camada de integração.
- 2026-09-14 — Notion como espelho (página raiz + Diário, Tarefas, Conversas); vault continua sendo a fonte primária.
- 2026-09-14 — Só local por padrão; palavra-passe com hash; reflexão a cada 6 turnos reescreve o Estado.

## Próximos passos
- [ ] rodar `python -m jaime chat` e validar as ferramentas do cérebro
- [ ] conectar MCPs (github, notion, n8n) via `claude mcp` / `/mcp`
- [ ] voz: Porcupine + Whisper local + ElevenLabs
- [ ] WhatsApp via Evolution API
- [ ] Twilio

## Links
