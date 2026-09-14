# Segurança

Jaime tem acesso real ao computador. Três camadas evitam que isso vire um problema:

## 1. Vigia (hooks em runtime) — `jaime/vigia/hooks.py`
Bloqueia até receber "confirmo" (uma confirmação libera **uma** ação, por 120 s):
- Bash: `rm -rf`, `sudo`, `mkfs`, `git push --force`, push em `main`, `reset --hard`, `curl | sh`, `DROP TABLE`, `shutdown`…
- Ferramentas de envio: `mcp__*__send*`, `reply`, `forward`, `create_pull_request`, `merge_pull_request`, `delete`.
- Escrita em `.env` e `vault/00-Jaime/` é sempre negada.

## 2. Permissões estáticas — `.claude/settings.json`
Lista do que roda sem prompt e o que é negado (`.env` nunca é lido).

## 3. Isolamento do SO (recomendado)
- Usuário separado no PC para o Jaime, com acesso só a `~/projetos` e ao vault.
- Chaves em `.env` desse usuário; nunca no repositório.
- Webhooks (`/ask`, `/webhook/whatsapp`) exigem `X-Jaime-Token`; exponha só via túnel autenticado.
- WhatsApp: só o número em `JAIME_OWNER_PHONE` dá ordens; outros são apenas registrados.

## O que fazer se algo escapar
`git log` + `git revert` nos repositórios; diário do dia mostra o que Jaime fez e quando.
