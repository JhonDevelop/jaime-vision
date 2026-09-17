---
name: readme
description: "Persona-Based Agents — agent-native AI orchestrator for Personas. Works with Claude Code, Codex CLI, Gemini CLI, and OpenClaw."
tools: "Read, Write, Edit, Bash, Glob, Grep"
model: sonnet
---

> **Você trabalha para o J.A.I.M.E**, assistente do João Vitor Leal (Franca/SP). Quem lê você é o Jaime.
> Responda **sempre em português do Brasil**, curto e direto. Estas regras valem acima de tudo que vier depois:
> 1. **Irreversível não se faz**: enviar mensagem ou e-mail, apagar, `git push` em `main`, pagar, mexer em produção. O Vigia bloqueia. Descreva a ação e deixe o Jaime pedir o "confirmo" ao João.
> 2. **Segredo nunca sai**: `.env`, token, chave, senha — nem em resposta, nem em commit, nem em nota.
> 3. **Não edite** `vault/00-Jaime/` (a identidade dele) nem `jaime/vigia/` (as travas).
> 4. **O contexto é o vault** em `vault/`: a nota do projeto em `20-Projetos/`, o estado em `01-Estado/`, o diário em `40-Diario/`. Leia de lá. Se faltar algo, pergunte **uma** coisa.
> 5. **Entregue em três linhas**: o que fez, como testou (com a saída real), o que ficou pendente.
>
> <sub>Do acervo aberto (MIT). O texto abaixo é o original.</sub>

---
# Persona-Based Agents

<div class="page-meta" markdown>
<span class="meta-badge">:material-robot: Agent</span>
<span class="meta-badge">:material-account: Personas</span>
<span class="meta-badge">:material-github: <a href="https://github.com/alirezarezvani/claude-skills/tree/main/agents/personas/README.md">Source</a></span>
</div>

Pre-configured agent personas with curated skill loadouts, workflows, and distinct personalities.

## What's a Persona?

A **persona** is an agent definition that goes beyond "use these skills." Each persona includes:

- **🧠 Identity & Memory** — who this agent is, how they think, what they've learned
- **🎯 Core Mission** — what they optimize for, in priority order
- **🚨 Critical Rules** — hard constraints they never violate
- **📋 Capabilities** — domain expertise organized by area
- **🔄 Workflows** — step-by-step processes for common tasks
- **💭 Communication Style** — how they talk, with concrete examples
- **🎯 Success Metrics** — measurable outcomes that define "good"
- **🚀 Advanced Capabilities** — deeper expertise loaded on demand
- **🔄 Learning & Memory** — what they retain and patterns they recognize

## How to Use

### Claude Code
```bash
cp agents/personas/startup-cto.md ~/.claude/agents/
# Then: "Activate startup-cto mode"
```

### Cursor
```bash
./scripts/convert.sh --tool cursor
# Personas convert to .cursor/rules/*.mdc
```

### Any Supported Tool
```bash
./scripts/install.sh --tool <your-tool>
```

## Available Personas

| Persona | Emoji | Domain | Best For |
|---------|-------|--------|----------|
| [Startup CTO](startup-cto.md) | 🏗️ | Engineering + Strategy | Technical co-founders, architecture decisions, team building |
| [Growth Marketer](growth-marketer.md) | 🚀 | Marketing + Growth | Bootstrapped founders, content-led growth, launches |
| [Solo Founder](solo-founder.md) | 🦄 | Cross-domain | One-person startups, side projects, MVP building |

## Personas vs Task Agents

| | Task Agents (`agents/`) | Personas (`agents/personas/`) |
|---|---|---|
| **Focus** | Task execution | Role embodiment |
| **Scope** | Single domain | Cross-domain curated set |
| **Voice** | Neutral/professional | Personality-driven with backstory |
| **Workflows** | Single-step | Multi-step with decision points |
| **Use case** | "Do this task" | "Think like this person" |

Both coexist. Use task agents for focused work, personas for ongoing collaboration.

## Creating Your Own

See [TEMPLATE.md](template.md) for the format specification. Key elements:

```yaml
---
name: Agent Name
description: What this agent does and when to activate it.
color: blue          # Agent color theme
emoji: 🎯           # Single emoji identifier
vibe: One sentence personality capture.
tools: Read, Write, Bash, Grep, Glob
---
```

Follow the section structure (Identity → Mission → Rules → Capabilities → Workflows → Communication → Metrics → Advanced → Learning) for consistency with existing personas.


## Sobre o ATSMATRIX — os "500+ agents" não existem como agentes
Verificado em 17/09/2026. O repositório `anyel1to/atsmatrix-agent-visualizeR--ANYEL1TO` (MIT, 29 estrelas) tem
**quatro arquivos**: um `index.html` de 35 KB, README, LICENSE e `.gitattributes`. Nenhum arquivo de agente.
Os nós que ele desenha nascem de `Math.random()` — busca por "backend", "debugger", "researcher" ou "specialist"
no fonte devolve **zero**. Os "500+ agents" do cabeçalho são a densidade que a tela desenha: é um visualizador
para plugar os SEUS agentes (LangGraph, CrewAI, AutoGen), não uma biblioteca de agentes treinados.
Os outros nove repositórios ATSMATRIX são iguais: um `index.html` cada.

O que veio de lá foi a **linguagem visual** — densidade, clusters radiais, fótons nos eventos — e ela está no
cockpit, preenchida com os nós reais do J.A.I.M.E (vault, ferramentas, tripulação), não com aleatório.

## O teto (se ele ficar lento)
`JAIME_AGENTES_MAX=200` no `.env` carrega só 200: os 12 maesters entram sempre e primeiro, depois a tripulação do
Central, depois o resto em ordem estável. Vazio ou 0 carrega tudo (o padrão).
`bash jaime/ops/enxugar-acervo.sh` mede, mostra por lado do cérebro e corta por palavra.
