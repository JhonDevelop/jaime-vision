# Jaime ⇄ n8n

O n8n é a camada de integração: agenda (Google Calendar), Gmail, WhatsApp oficial, qualquer SaaS.

## Direção 1 — n8n chama o Jaime
Nó **HTTP Request** → `POST http://<host>:8787/ask`
Headers: `X-Jaime-Token: <JAIME_SERVER_TOKEN>`
Body: `{"texto": "resuma os e-mails de hoje", "canal": "n8n"}`

Casos: cron das 7h → briefing por WhatsApp; e-mail novo → "isso precisa de resposta?".

## Direção 2 — Jaime chama o n8n
Já configurado em `.mcp.json` (`mcp__n8n__*`). Crie workflows com **Webhook** trigger e exponha
via MCP Server Trigger; os maesters os chamam por nome (ex.: `criar_evento_calendar`).

## Workflows sugeridos
- `calendar.listar_dia` / `calendar.criar_evento`
- `gmail.buscar` / `gmail.rascunho` (envio só após "confirmo")
- `whatsapp.enviar` (Meta Cloud API) para o número comercial
