# Prompts para o Claude Code (CLI)

Abra o terminal na pasta do repositório e rode `claude`. Depois cole um dos blocos.

---

## 1. Primeira sessão — instalação e primeiro boot

Você é o **maester-jaime** (`.claude/agents/maester-jaime.md`). Esta é a primeira sessão do Jaime nesta máquina.
Execute em ordem, mostrando o comando antes de rodar. Só me pergunte o que não conseguir resolver sozinho.

1. Leia `CLAUDE.md`, `docs/ROADMAP.md`, `cowork/PROJETO-JAIME.md` e `vault/01-Estado/Estado.md`. Resuma em 3 linhas quem você é e em que fase está.
2. `bash scripts/install.sh` — aceite as dependências de voz se houver microfone. Se o CLI `claude` não estiver no PATH para o SDK, resolva.
3. Crie `.env` a partir de `.env.example`. Peça-me `ANTHROPIC_API_KEY` e `NOTION_TOKEN`; deixe os IDs do Notion como estão. Nunca imprima os valores.
4. `python -m pytest -q` — tudo verde. Se algo quebrar por diferença de versão do `claude-agent-sdk`, corrija em `jaime/orchestrator/jaime.py` (nomes de classes/opções), rode de novo e me explique o que mudou em uma linha.
5. `claude mcp list` — se `github` ou `notion` não estiverem autenticados, diga-me exatamente o que digitar no `/mcp`.
6. `python -m jaime hud` em segundo plano. Eu abro o HUD, digito a palavra-passe e você confirma no log que: o acesso liberou, o Jaime se apresentou, a máquina foi registrada em `vault/01-Estado/Maquinas.md` e o Notion sincronizou (ou me diz por que não).
7. Feche a sessão: `registrar_diario` com o que ficou pendente; se tudo passou, atualize `vault/01-Estado/Estado.md` para "Fase: 1 — operando localmente"; commit em branch `chore/primeiro-boot` e me pergunte antes de dar push.

Regras: trabalhe em branch; nunca edite `vault/00-Jaime/`; ações do Vigia esperam meu "confirmo".

---

## 2. Sessão de trabalho — implementar um item do backlog

Você é o **maester-dev** com apoio do **maester-jaime**. Vamos implementar **[F-número e nome, ex.: F12 — Agenda]** do `cowork/PROJETO-JAIME.md`.

Antes de codar: leia a funcionalidade, o `docs/ARQUITETURA.md` e o `vault/50-Conhecimento/Checklist-Producao.md`. Proponha em até 8 linhas: arquivos que vão mudar, interface (funções/rotas/ferramentas MCP), como testar. Espere meu "ok".

Depois: branch `feat/[nome]`, implemente com testes em `tests/`, rode `pytest -q`, atualize `docs/` se a arquitetura mudou, marque o status em `cowork/PROJETO-JAIME.md` e adicione uma decisão datada em `vault/20-Projetos/Jaime.md`. Termine com a tabela do checklist de produção (frente | status | evidência) e o comando de push, que só roda com meu "confirmo".

---

## 3. Fechamento do dia

Você é o **maester-jaime**. Feche o dia: leia `vault/40-Diario/` de hoje, `vault/60-Conversas/` de hoje e `vault/01-Estado/Estado.md`.
Mova tarefas concluídas do `Inbox.md` para o diário, atualize as notas de projeto tocadas hoje, reescreva as seções
"Situação agora", "Em andamento", "Próximos passos" e "Aprendizados recentes" do Estado com `atualizar_estado`,
sincronize o Notion e me devolva 3 linhas: o que fechou, o que travou, o que vem amanhã.

---

## 4. Máquina nova (já com o repo clonado)

Você é o **maester-jaime**. Esta máquina é nova para o Jaime. Rode o bloco 1 a partir do passo 2, sem reinstalar o que já existir,
e ao final confirme que `vault/01-Estado/Maquinas.md` tem uma linha nova e que o Jaime se apresentou no HUD.
