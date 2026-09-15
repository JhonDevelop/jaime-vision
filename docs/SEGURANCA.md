# Segurança

Jaime tem acesso real ao computador. Três camadas evitam que isso vire um problema:

## 0. Só local + palavra-passe
- O servidor sobe em `127.0.0.1` e recusa qualquer IP que não seja loopback (middleware), a menos que `JAIME_BIND` mude.
- O cérebro fica trancado até a palavra-passe (falada: "um dois três quatro…", ou digitada). Guardamos só o SHA-256; padrão 12341234 — troque com `python -m jaime senha`. Timeout de 30 min sem uso; "tranca" fecha na hora.
- Tentativas de senha não vão para o log de conversas.

## 1. Vigia (hooks em runtime) — `jaime/vigia/hooks.py`
Segura só o **irreversível** até receber "confirmo" (uma confirmação libera **uma** ação, por 5 min):
- Bash: `rm -rf`, `sudo`, `mkfs`, `git push --force`, push em `main`, `reset --hard`, `curl | sh`, `DROP TABLE`, `shutdown`…
- Ferramentas de envio: `mcp__*__send*`, `reply`, `forward`, `create_pull_request`, `merge_pull_request`, `delete`, `apagar`, `enviar`.
- Browser: clique em enviar/comprar/pagar/assinar/publicar/excluir.
- Escrita em `.env` e em `jaime/vigia/` (ele não se desarma sozinho).
- `vault/00-Jaime/` é sempre negada — só o João edita.

**Livre (desde 15/09/2026):** ver a tela, clicar, digitar, teclar, mover/renomear arquivos, `killall`, editar o
próprio código em `jaime/` (o git desfaz; a mudança só vale após reiniciar o serviço).

## 2. Permissões estáticas — `.claude/settings.json`
Lista do que roda sem prompt e o que é negado (`.env` nunca é lido).

## 3. Isolamento do SO (recomendado)
- Usuário separado no PC para o Jaime, com acesso só a `~/projetos` e ao vault.
- Chaves em `.env` desse usuário; nunca no repositório.
- Webhooks (`/ask`, `/webhook/whatsapp`) exigem `X-Jaime-Token`; exponha só via túnel autenticado.
- WhatsApp: só o número em `JAIME_OWNER_PHONE` dá ordens; outros são apenas registrados.

## O que fazer se algo escapar
`git log` + `git revert` nos repositórios; diário do dia mostra o que Jaime fez e quando.
