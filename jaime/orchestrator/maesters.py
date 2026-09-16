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
    maesters: dict[str, AgentDefinition] = {}
    for p in sorted((root / ".claude" / "agents").glob("*.md")):
        meta, prompt = _parse(p.read_text(encoding="utf-8"))
        if not meta.get("name") or not meta.get("description"):
            continue                      # README, LICENSE e afins não são agentes
        tools = meta.get("tools", "")
        tools = [t.strip() for t in tools.split(",")] if isinstance(tools, str) else list(tools or [])
        maesters[meta["name"]] = AgentDefinition(
            description=meta.get("description", ""),
            prompt=prompt,
            tools=tools or None,
            model=meta.get("model"),
        )
    return maesters
