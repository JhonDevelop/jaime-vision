"""A tripulação de cada hemisfério — os agentes e as skills que são DELE, não do Jaime inteiro.

O João reclamou com razão: hemisfério que vive dormindo não aprende nem evolui. Duas coisas resolvem isso,
e as duas estão aqui.

**Cada lado tem gente própria.** Não é o acervo inteiro à disposição de todos: o Esquerdo (Codex) tem os
agentes de técnica — quem escreve código, testa, refatora, revisa, faz build e depura. O Direito (Gemini) tem
os de evolução — quem pesquisa, levanta alternativa, critica arquitetura, analisa e cria. O Central (Claude)
fica com os maesters da casa, que conhecem o vault, o Vigia e o João. Cada tripulante só entra na lista se o
arquivo dele existe de verdade em `.claude/agents/`; lista com nome de agente que não existe é decoração.

**Cada lado tem o que fazer sozinho.** `pauta()` devolve o trabalho que aquele hemisfério pode pegar agora sem
ninguém mandar, tirado de coisa real: teste vermelho e problema de código para o Esquerdo; problema aberto no
estudo e projeto sem nota para o Direito. É isso que o despertador usa para não deixar os dois parados."""
from __future__ import annotations
import re
from pathlib import Path

# Quem é de quem. São nomes do acervo em `.claude/agents/`; os que não existirem na máquina caem fora sozinhos.
TRIPULACAO: dict[str, tuple[str, ...]] = {
    "central": ("maester-jaime", "maester-arquivista", "maester-agenda", "maester-comms",
                "maester-ops", "maester-dados", "maester-seguranca", "maester-arquiteto"),
    "esquerdo": ("maester-dev", "maester-back", "maester-front", "maester-debug",
                 "backend-developer", "frontend-developer", "python-pro", "typescript-pro",
                 "javascript-pro", "test-automator", "debugger", "error-detective",
                 "refactoring-specialist", "code-reviewer", "build-engineer", "database-optimizer",
                 "performance-engineer", "devops-engineer", "sql-pro", "api-designer"),
    "direito": ("research-analyst", "search-specialist", "data-researcher", "trend-analyst",
                "architect-reviewer", "microservices-architect", "cloud-architect", "ui-designer",
                "ux-researcher", "prompt-engineer", "llm-architect", "ai-engineer",
                "product-manager", "competitive-analyst", "market-researcher", "legacy-modernizer",
                "knowledge-synthesizer", "content-planner"),
}

# As skills que são o ofício de cada lado.
SKILLS: dict[str, tuple[str, ...]] = {
    "central": ("conversa", "humanizacao", "sentimentos", "humor", "proatividade",
                "vontade-propria", "tres-cerebros", "pesquisa-web"),
    "esquerdo": ("systematic-debugging", "test-driven-development", "resolver-problemas",
                 "debugging-strategies", "code-review-excellence", "error-handling-patterns",
                 "python-testing-patterns", "verification-before-completion", "python-pro",
                 "refactoring-code-reviewer", "automelhoria"),
    "direito": ("brainstorming", "writing-plans", "first-principles-thinking", "autoaprendizado",
                "architecture-patterns", "competitive-landscape", "data-storytelling",
                "dispatching-parallel-agents", "subagent-driven-development", "prompt-engineering-patterns"),
}

TODO_RX = re.compile(r"^\s*#\s*(?:TODO|FIXME|XXX)[: ]\s*(.+)$", re.M)
PROBLEMA_RX = re.compile(r"^##\s+(P-\d+)\s+·\s+(.+?)\s+·\s+(\w+)", re.M)
# O que faz um problema ser do ESQUERDO: vocabulário de falha de sistema. O resto (fornecedor, preço,
# qual ferramenta escolher) é pesquisa, e vai para o Direito.
TECNICO_RX = re.compile(
    r"cód|code|erro|bug|test|falha|lento|trava|corta|quebra|parou|crash|timeout|exceç|stack|"
    r"não funciona|nao funciona|api|script|import|instal|depend|vers[ãa]o|log|performance|mem[óo]ria",
    re.I)


def _existe_agente(repo: Path, nome: str) -> bool:
    return (repo / ".claude" / "agents" / f"{nome}.md").is_file()


def _existe_skill(repo: Path, nome: str) -> bool:
    return (repo / ".claude" / "skills" / nome / "SKILL.md").is_file()


def tripulacao(repo: Path, hemisferio: str) -> list[str]:
    """Os agentes daquele lado que existem mesmo nesta máquina."""
    return [a for a in TRIPULACAO.get(hemisferio, ()) if _existe_agente(repo, a)]


def skills(repo: Path, hemisferio: str) -> list[str]:
    return [s for s in SKILLS.get(hemisferio, ()) if _existe_skill(repo, s)]


def pauta(vault, repo: Path, hemisferio: str, limite: int = 5) -> list[str]:
    """O que este hemisfério pode pegar AGORA, por conta própria. Só coisa real; lista vazia se não houver."""
    itens: list[str] = []
    ler = lambda rel: (vault.read(rel) or "")

    if hemisferio == "esquerdo":
        # problemas de estudo que cheiram a código
        for pid, titulo, estado in PROBLEMA_RX.findall(ler("90-Estudo/Problemas.md")):
            if estado != "resolvido" and TECNICO_RX.search(titulo):
                itens.append(f"{pid}: {titulo.strip()} — descubra a causa, conserte e deixe um teste que falharia antes.")
        # o que está marcado no próprio código
        for f in sorted((repo / "jaime").rglob("*.py"))[:400]:
            try:
                for t in TODO_RX.findall(f.read_text(encoding="utf-8", errors="ignore"))[:1]:
                    itens.append(f"TODO em {f.relative_to(repo)}: {t.strip()[:110]}")
            except OSError:
                continue
            if len(itens) >= limite * 2:
                break

    elif hemisferio == "direito":
        for pid, titulo, estado in PROBLEMA_RX.findall(ler("90-Estudo/Problemas.md")):
            if estado != "resolvido":
                itens.append(f"{pid}: {titulo.strip()} — pesquise e traga a resposta com as fontes, em 5 linhas.")
        # projeto sem nota é buraco de conhecimento
        try:
            for p in sorted((Path(vault.root) / "20-Projetos").glob("*.md")):
                if len(p.read_text(encoding="utf-8", errors="ignore")) < 400:
                    itens.append(f"A nota do projeto {p.stem} está quase vazia — levante o que existe e proponha o conteúdo dela.")
        except Exception:
            pass
        itens.append("Leia o último dia do diário e proponha UMA melhoria concreta no J.A.I.M.E, com o porquê.")

    vistos, saida = set(), []
    for i in itens:
        if i not in vistos:
            vistos.add(i); saida.append(i)
    return saida[:limite]
