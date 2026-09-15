# Conexões — como o Jaime recebe cada acesso

O registro vivo do que ele consegue acessar fica em `vault/01-Estado/Conexoes.md` (serviço, escopo, como foi
autorizado, como revogar, último uso). Tudo que **envia** (e-mail, mensagem) passa pelo Vigia: só com "confirmo".

## Google (Gmail + Calendar + Drive) — OAuth do seu próprio projeto
Sem intermediário: o token fica na sua máquina (`~/Jaime/google-token.json`).

1. Abra https://console.cloud.google.com → **Novo projeto** → nome `Jaime`.
2. **APIs e serviços → Biblioteca**: ative *Gmail API*, *Google Calendar API* e *Google Drive API*.
3. **Tela de consentimento OAuth**: tipo *Externo*, nome do app `Jaime`, seu e-mail de suporte; em *Usuários de teste*
   adicione o seu Gmail (enquanto o app estiver em "teste", só ele entra — é o que queremos).
4. **Credenciais → Criar credenciais → ID do cliente OAuth → Tipo: App para computador (Desktop)** → *Baixar JSON*.
5. Salve o arquivo em `~/Jaime/google-client-secret.json` (ou aponte `GOOGLE_CLIENT_SECRET_FILE` no `.env`).
6. No repositório: `python -m jaime conectar google` — abre o navegador, você aceita, o token é salvo e o Jaime registra
   a conexão em `Conexoes.md`. Renovação é automática.

Escopos pedidos: `gmail.modify` (ler, rascunhar, enviar, marcar), `calendar` (ler e criar eventos), `drive.readonly`.
**Revogar**: https://myaccount.google.com → Segurança → *Acesso de terceiros* → Jaime → remover. Apagar
`~/Jaime/google-token.json` também corta na hora.

Ferramentas: `email_hoje`, `email_buscar`, `email_rascunho`, `email_enviar` (Vigia), `agenda_dia`, `agenda_criar`, `conexoes`.

## Telegram — canal rápido do celular
1. No Telegram, fale com **@BotFather** → `/newbot` → nome `Jaime` → copie o **token**.
2. Fale com **@userinfobot** → ele mostra o seu **id numérico**.
3. No `.env`: `TELEGRAM_BOT_TOKEN=…` e `JAIME_OWNER_TELEGRAM_ID=…`. Reinicie o servidor.
4. Mande "Jaime, está aí?" para o bot. Só o seu id recebe resposta; qualquer outro remetente vira uma linha no diário.

**Revogar**: @BotFather → `/revoke` (gera token novo) ou `/deletebot`. Ou apague o token do `.env`.

## GitHub e Notion
Já autenticados como MCPs do Claude (`claude mcp list`). Revogar: nas configurações de cada serviço (tokens/integrações).

## O que NÃO entra
- Instagram e WhatsApp pessoal por bibliotecas não oficiais: derrubam a conta. WhatsApp Cloud API e Instagram Messaging API
  (contas comerciais) entram na etapa 11.
- Senhas, cartões e chaves nunca passam pelo Jaime: ele pede o teclado e você digita no lugar certo.
