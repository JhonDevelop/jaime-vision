# Maestri — como montar a árvore de serviços do Jaime

> O Maestri é um canvas espacial com terminais, notas e portais. Cada terminal roda um agente (Claude Code, Codex, shell).
> O `maestri` (CLI) só funciona **dentro** de um terminal aberto pelo app: ele injeta `MAESTRI_SOCKET` e `MAESTRI_TERMINAL_ID`.

## 1. A ideia: um cérebro, vários braços

```
                 ┌──────────────────────────────┐
                 │  Cerebro Principal Jaime     │  ← Maestro (toggle ligado). Orquestra, decide, delega.
                 │  claude --continue  (dir: jaime-vision)
                 └──────┬──────────┬───────────┬───────────┐
        ┌───────────────┘          │           │           └───────────────┐
        ▼                          ▼           ▼                           ▼
 ┌─────────────┐          ┌─────────────┐ ┌─────────────┐          ┌──────────────┐
 │ Voz         │          │ Telemetria  │ │ Vontades    │          │ Revisor      │
 │ (duplex,    │          │ e rotina    │ │ e Vitrine   │          │ (só lê,      │
 │  TTS, fila) │          │ (Prompt D)  │ │ (Prompt E)  │          │  nunca edita)│
 └─────────────┘          └─────────────┘ └─────────────┘          └──────────────┘
        floor "voz"         floor "telemetria"  floor "vontades"       ground
        branch feat/…       branch feat/…       branch feat/…
```

- **Maestro** = o terminal que pode recrutar, criar papéis e pisos. Só um por equipe. Ligue o toggle "Maestro" no terminal
  "Cerebro Principal Jaime" (barra do terminal no canvas).
- **Recruta** = terminal criado pelo Maestro, já conectado a ele. Recebe um **papel** (role) — o prompt de sistema dele.
- **Piso (floor)** = uma cópia isolada do repositório (git worktree/clone) numa branch. Recrutas em pisos diferentes não pisam
  um no outro; ao terminar, `maestri floor land` traz a branch de volta ao chão.
- **Nota** = arquivo markdown no canvas que os agentes conectados leem e escrevem (contexto compartilhado, progresso).
- **Portal** = browser controlado por um agente (testar HUD, Google Cloud, Notion).

## 2. Passo a passo (uma vez)

1. Abra o Maestri no workspace da pasta `jaime-vision`.
2. Terminal principal: preset **Claude Code**, diretório `…/jaime-assist/jaime-vision`, comando `claude --continue`
   (reabre a última conversa) ou `claude` (nova). Nomeie "Cerebro Principal Jaime". **Ligue o Maestro** nele.
3. Dentro desse terminal, o Claude cria o resto sozinho com estes comandos (você não precisa digitar; está aqui para entender):

```bash
maestri list                                   # quem já está conectado (sempre antes de recrutar)
maestri preset list                            # Claude Code, Codex, Shell…
maestri role create "Voz do Jaime" "Você cuida de jaime/voice/ … Leia docs/FASE-3-TEMPO-REAL.md §2. Rode `maestri list` antes de perguntar. Ao fechar, `maestri ask \"Cerebro Principal Jaime\" \"<resumo>\"`."
maestri floor create "voz" --branch feat/fase3-voz          # piso isolado, branch própria
maestri recruit "Timbre" --role "Voz do Jaime" --floor "voz"
maestri note create --name "fase3-progresso" "# Progresso\n- [ ] A …"
maestri connect "fase3-progresso" "Timbre"
maestri ask --batch '{"Timbre": "Implemente o Prompt B…", "Bussola": "Implemente o Prompt D…"}'
maestri check "Timbre"                         # olhar o terminal dele sem interromper
maestri floor land "voz"                       # quando a branch estiver commitada e testada
```

4. Rotinas do canvas (`maestri routine …`, skill maestri-routines) servem para lembretes e comandos recorrentes de
   **desenvolvimento** (ex.: rodar `pytest` toda noite). A rotina **do Jaime** (briefing, fecha o dia) continua no
   scheduler dele, em `vault/30-Tarefas/Rotinas.md` — são coisas diferentes.

## 3. Como o Jaime faz mais de uma coisa ao mesmo tempo

Duas camadas, que não se confundem:

| Camada | Quem | Paralelismo | Onde se vê |
|---|---|---|---|
| **Desenvolvimento do Jaime** | Claude Code no Maestri (Maestro + recrutas) | um terminal por etapa/piso; `ask --batch` dispara todos | canvas do Maestri |
| **Operação do Jaime** (o assistente ligado) | serviço `com.jaime` (um processo) | tarefas assíncronas dentro do processo: ouvido duplex, notificações, scheduler, estudo, observador, Telegram | HUD (http://127.0.0.1:8787) |

Dentro do serviço, o Jaime já roda em paralelo: escuta enquanto pensa (duplex), lê notificações a cada 8 s, dispara rotinas,
estuda um problema a cada 30 min quando ocioso, vigia a tela. Pedidos ao modelo passam por **uma fila** (um turno por vez) —
é a fila de demandas (Prompt B) que deixa uma demanda interromper a outra sem perder nada. Os maesters (`.claude/agents/`)
são subagentes do mesmo processo: o Jaime delega e espera.

Se um dia quiser dois Jaimes (ex.: um só para vídeo), a regra é: **um cérebro (vault) e um serviço por máquina**; o segundo
vira um recruta no Maestri com um papel e a pasta do projeto dele — não um segundo `jaime serve`.

## 4. Diretórios que importam

```
jaime-vision/                 ← chão: o Cerebro Principal trabalha aqui
├── vault/                    ← cérebro (Obsidian). Nunca copiar para outro piso: é um só.
├── jaime/                    ← código do assistente
├── .claude/agents/*.md       ← maesters (subagentes do Jaime em operação)
├── .claude/skills/           ← skills (o cérebro de estudo cria novas aqui)
├── .maestri/roles/<id>/      ← papéis criados pelo Maestro (prompts dos recrutas)
└── docs/FASE-3-TEMPO-REAL.md ← a tese; todo recruta lê antes de começar
~/Jaime/                      ← estado da máquina: jaime.log, tokens, capturas, criações
~/.maestri/workspaces/<id>/   ← estado do canvas (não editar à mão)
```

## 5. Regras para os recrutas (cole no papel de cada um)

- Leia `CLAUDE.md`, `docs/FASE-3-TEMPO-REAL.md` e a nota `fase3-progresso` antes de começar.
- Só toque nos arquivos do seu escopo; módulo novo em pasta nova. Wiring em `server.py`/`config.py` em uma linha, avisando.
- Testes verdes (`pytest -q`) antes de dizer "pronto". Commit na sua branch; nunca push em `main`.
- Ao terminar: `maestri ask "Cerebro Principal Jaime" "PRONTO: <o que mudou, como testou, o que ficou>"`.
- Sem segredos em notas, commits ou mensagens (`.env` é só de leitura).
