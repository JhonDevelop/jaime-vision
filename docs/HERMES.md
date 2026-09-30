# Hermes Agent no J.A.I.M.E

O [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research) é o "programa que transforma a IA em
agente de verdade" do passo 3: terminal, arquivos, navegador, memória própria, skills, cron, Telegram/WhatsApp, voz.
No Jaime ele é **mais um par de mãos por delegação** — o Jaime continua sendo quem fala com o João e quem decide.

## Como conversam
- O Hermes roda à parte (`hermes gateway`) com a API compatível com OpenAI em `127.0.0.1:8642`.
- O Jaime usa `/v1/runs` (jaime/hermes/cliente.py): cria o trabalho, acompanha, e quando o Hermes para num comando
  perigoso (`waiting_for_approval`) o pedido entra no **lote do Vigia**. "Sim" do João → `once` (só aquele comando).
  Qualquer outra coisa → `deny`. O Jaime nunca manda `session`/`always`.
- Tarefa que já é do tipo que o Vigia segura (mandar mensagem, comprar, apagar, publicar, push na main, instalar,
  produção, abrir a casa) só sai para o Hermes depois do "sim" — o Hermes não é porta dos fundos.
- Ferramentas: `mcp__hermes__hermes_delegar`, `hermes_aprovar`, `hermes_negar`, `hermes_estado`, `hermes_parar`.
- `.env`: `JAIME_HERMES=on`, `HERMES_URL`, `HERMES_API_KEY` (o instalador gera e grava sem mostrar).

## Instalar
- **Windows**: `.\scripts\hermes\instalar.ps1` (instalador oficial, `hermes setup` para escolher o modelo, API local,
  aprovação manual, negações duras, Tarefa Agendada no logon).
- **Mac Apple Silicon / Linux**: `bash scripts/hermes/instalar.sh` (LaunchAgent `com.jaime.hermes` via `jaime/ops/hermes.sh`).
- **Mac Intel (o Mac de hoje)**: não suportado pelo Hermes. Rodamos o instalador oficial em 30/09/2026 e ele parou
  em `cryptography 50`, que não tem versão para Intel (log em `~/Jaime/hermes-instalacao.log`).

## Validação (30/09/2026)
Hermes real (commit f42f579) rodando com um modelo de teste: `hermes_delegar` executou um comando no terminal do
Hermes; um `rm -rf` parou em aprovação, `hermes_aprovar` sem o sim foi recusado, com o sim apagou; `hermes_negar`
bloqueou. Mais 18 testes em `tests/test_hermes.py` com um Hermes simulado.
