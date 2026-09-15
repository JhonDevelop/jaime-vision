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

## Meta — WhatsApp Cloud API e Instagram Messaging (contas comerciais)
Só APIs oficiais. O webhook é o próprio servidor do Jaime (`/webhook/meta`), exposto por um túnel (ex.: `cloudflared tunnel --url http://127.0.0.1:8787`).

1. https://developers.facebook.com → **Meus apps → Criar app → Empresa**. Adicione os produtos **WhatsApp** e **Instagram**
   (Messenger API para Instagram).
2. **WhatsApp → Configuração da API**: número comercial (o de teste serve para começar), copie o **Phone number ID** →
   `META_WHATSAPP_PHONE_ID`. Gere um **token de acesso permanente** (usuário do sistema no Business Manager) → `META_ACCESS_TOKEN`.
3. **Instagram**: conta profissional vinculada a uma Página; permissões `instagram_basic`, `instagram_manage_messages`;
   ID da conta → `META_INSTAGRAM_ACCOUNT_ID`. Para responder DMs de qualquer pessoa o app precisa passar pela **revisão** da Meta;
   antes disso só testadores do app conversam.
4. **Configurações do app → Básico**: *Chave secreta do aplicativo* → `META_APP_SECRET` (assina cada webhook).
5. **Webhooks**: URL `https://<seu-túnel>/webhook/meta`, *Verify token* = o que você puser em `META_VERIFY_TOKEN`; assine
   `messages` (WhatsApp) e `messages` (Instagram).
6. Reinicie o servidor. Mensagem sua (número em `JAIME_OWNER_PHONE`) → ele responde; mensagem de terceiro → resumo +
   rascunho no HUD, e **só envia com "confirmo"** (`enviar_whatsapp` / `enviar_instagram` são ações do Vigia).

**Revogar**: apague o token no Business Manager ou remova o app. A Evolution API (WhatsApp pessoal) ficou **opcional**:
risco real de bloqueio da conta.

## Home Assistant (casa) e câmera
1. No HA: perfil → **Tokens de acesso de longa duração** → criar → `HA_TOKEN` no `.env`; `HA_URL=http://homeassistant.local:8123`.
2. HomeKit: integração *HomeKit Controller* no HA traz os acessórios como entidades (`light.*`, `switch.*`).
3. Câmera: `JAIME_CAMERA=0` usa a FaceTime do Mac (macOS pede permissão de Câmera para o Terminal); `camera.entrada` usa uma
   câmera do HA. Fechaduras e portões (`lock.*`, `cover.*`) passam pelo Vigia.

## GitHub e Notion
Já autenticados como MCPs do Claude (`claude mcp list`). Revogar: nas configurações de cada serviço (tokens/integrações).

## O que NÃO entra
- Instagram e WhatsApp pessoal por bibliotecas não oficiais: derrubam a conta. WhatsApp Cloud API e Instagram Messaging API
  (contas comerciais) entram na etapa 11.
- Senhas, cartões e chaves nunca passam pelo Jaime: ele pede o teclado e você digita no lugar certo.
