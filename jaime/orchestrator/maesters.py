"""Carrega os maesters a partir de `.claude/agents/*.md` (fonte única de verdade).

O mesmo arquivo serve o Claude Code no terminal e o Agent SDK aqui."""
from __future__ import annotations
from pathlib import Path
import yaml
from claude_agent_sdk import AgentDefinition

def _parse(md: str) -> tuple[dict, str]:
    if not md.startswith("---"):
        return {}, md
    _, fm, body = md.split("---", 2)
    return yaml.safe_load(fm) or {}, body.strip()

def carregar_maesters(root: Path) -> dict[str, AgentDefinition]:
    """Todos os agentes de `.claude/agents/`.

    A `description` de cada um entra no contexto a CADA turno, então acervo grande custa latência e dinheiro.
    `JAIME_AGENTES_MAX` põe um teto: os 12 maesters da casa entram sempre e primeiro, depois a tripulação do
    Central, e o resto do acervo entra até o teto. Vazio ou 0 = carrega tudo (o padrão)."""
    import os
    teto = int(os.environ.get("JAIME_AGENTES_MAX", "40") or 0)   # 40 carregados; o resto vem por mcp__acervo__buscar
    maesters: dict[str, AgentDefinition] = {}
    carregados: dict[str, AgentDefinition] = {}
    for p in sorted((root / ".claude" / "agents").glob("*.md")):
        meta, prompt = _parse(p.read_text(encoding="utf-8"))
        if not meta.get("name") or not meta.get("description"):
            continue                      # README, LICENSE e afins não são agentes
        tools = meta.get("tools", "")
        tools = [t.strip() for t in tools.split(",")] if isinstance(tools, str) else list(tools or [])
        carregados[meta["name"]] = AgentDefinition(
            description=meta.get("description", ""),
            prompt=prompt,
            tools=tools or None,
            model=meta.get("model"),
        )
    if teto <= 0 or len(carregados) <= teto:
        return carregados
    # com teto: a casa primeiro, depois quem serve ao Central, depois o resto — em ordem estável
    try:
        from ..cerebros.tripulacao import NUCLEO
        prioridade = list(NUCLEO["central"])
    except Exception:
        prioridade = []
    ordem = ([n for n in carregados if n.startswith("maester-")]
             + [n for n in prioridade if n in carregados]
             + sorted(carregados))
    vistos: dict[str, AgentDefinition] = {}
    for n in ordem:
        if n not in vistos and n in carregados:
            vistos[n] = carregados[n]
        if len(vistos) >= teto:
            break
    return vistos
