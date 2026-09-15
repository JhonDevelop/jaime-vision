# Handoff — Claude Code na sua máquina

O Claude no chat não enxerga o seu computador; quem opera a pasta `Documents/jaime-assist/jaime-assisit` é o
Claude Code rodando aí. Este arquivo é o roteiro para ele.

## 1. Colocar o código na pasta
```bash
cd ~/Documents/jaime-assist/jaime-assisit
# se a pasta já é o clone do repositório:
git pull
# se está vazia: descompacte o jaime.zip aqui e faça o primeiro commit
git init && git add . && git commit -m "Jaime v0.2 — cérebro, HUD, palavra-passe" && git push -u origin main
```

## 2. Abrir o Claude Code e colar
```
claude
```
Cole:

> Você é o maester-jaime (veja .claude/agents/maester-jaime.md). Esta é a primeira vez que o Jaime roda nesta máquina.
> Faça, nesta ordem, e me pergunte só o que não conseguir resolver:
> 1. `bash scripts/install.sh` (aceite deps de voz se houver microfone).
> 2. Crie o `.env` a partir do `.env.example`; me peça ANTHROPIC_API_KEY e NOTION_TOKEN.
> 3. `python -m pytest -q` — tudo verde.
> 4. `claude mcp list` — se github/notion não estiverem autenticados, me oriente a rodar `/mcp`.
> 5. `python -m jaime hud` — abra o HUD, eu digito 12341234, e o Jaime deve se apresentar.
> 6. Registre no diário o que ficou pendente e atualize `vault/01-Estado/Estado.md` para a fase 1 se tudo passou.

## 3. Rotina diária
- Manhã: `python -m jaime hud` → "briefing".
- Trabalho: falar com o Jaime pelo HUD ou pelo Claude Code (mesmo cérebro, mesmo vault).
- Noite: "fecha o dia" → Estado, projetos e Notion atualizados.

## Notion — token
Em notion.so/my-integrations crie uma integração interna, copie o token para `NOTION_TOKEN` e, na página
"Jaime — Cérebro compartilhado", use ••• → Conexões → adicione a integração. Os IDs das bases já estão no `.env.example`.
