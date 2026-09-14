# Workflows do Jaime — como importar

Nenhum deles carrega segredo: as chaves ficam no nó **Config** (ou no `.env` do Jaime),
e os arquivos versionados trazem só placeholders. Preencha depois de importar.

## Ordem
1. **`ferramentas-mcp.json`** — o que o Jaime *chama*. Importe, conecte as credenciais do
   Google Calendar e do Gmail, **ative** e copie a *Production URL* do nó `MCP Server Trigger`
   (fica `https://<sua-instância>/mcp/jaime-ferramentas`). Ela vai para o `claude mcp add` do n8n.
   O trigger usa `bearerAuth` — crie a credencial Bearer e guarde o token.
2. **`briefing-matinal.json`** — cron 07:00 dias úteis → pergunta ao Jaime → manda no WhatsApp.
   Preencha no nó Config: `jaime_url` (túnel para esta máquina), `jaime_token`
   (= `JAIME_SERVER_TOKEN` do `.env`), e os campos da Evolution API.
3. **`ponte-whatsapp.json`** — recebe mensagem do WhatsApp; só o dono conversa, terceiros viram
   registro no diário. Aponte o webhook da Evolution para `.../webhook/jaime-whatsapp`.

## O que falta para rodar
- **Instância do n8n**: `bubapp.app.n8n.cloud` devolve 404 em tudo (14/09/2026), inclusive
  `/signin` e `/healthz` — confirme o endereço atual antes de importar.
- **Túnel**: `jaime_url` precisa alcançar esta máquina. O Jaime escuta em 127.0.0.1 por padrão
  (`JAIME_BIND`); um `cloudflared tunnel --url http://127.0.0.1:8787` resolve sem abrir a porta.
- **Evolution API**: instância e apikey.
