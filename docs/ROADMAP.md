# Roadmap

| Fase | Entrega | Critério de pronto |
|---|---|---|
| 0 | Esqueleto + cérebro conectado, HUD, palavra-passe, espelho Notion | `python -m jaime hud` abre, aceita 12341234, o Jaime se apresenta e escreve no vault |
| 1 | MCPs conectados | GitHub, Notion e n8n autenticados; maester-dev abre branch e commita |
| 2 | Agenda | n8n expõe Google Calendar; maester-agenda lista e cria eventos |
| 3 | Voz local | wake word → Whisper → ElevenLabs, latência < 3 s por turno |
| 4 | WhatsApp | Evolution API → `/webhook/whatsapp`; respostas só ao dono |
| 5 | Arquivista diário | "fecha o dia" consolida diário nas notas de projeto |
| 6 | Telefone | Twilio `<Gather>` → Jaime |
| 7 | Computer use | controle visual de apps sem API, só com confirmação |

Cada fase fecha com uma linha em `vault/20-Projetos/Jaime.md` → Decisões.
