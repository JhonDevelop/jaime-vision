"""Ferramenta MCP `autonomo`: objetivo(texto, limite_horas) e situacao()."""
from __future__ import annotations
import asyncio
from claude_agent_sdk import tool, create_sdk_mcp_server

def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}

def build_autonomo_server(autonomo):
    @tool("objetivo", "Inicia um objetivo longo em modo autônomo (etapas com aceite, checkpoints no diário/HUD, pausa no Vigia). "
                      "Roda em segundo plano; acompanhe com situacao. limite_horas opcional.", {"texto": str, "limite_horas": float})
    async def objetivo(args):
        try:
            asyncio.get_event_loop().create_task(autonomo.objetivo(args["texto"], args.get("limite_horas") or None))
            return _txt(f"Objetivo iniciado em segundo plano: {args['texto'][:100]}")
        except RuntimeError as e:
            return _txt(str(e))

    @tool("situacao", "Situação do objetivo autônomo em andamento (ou do último).", {})
    async def situacao(args):
        m = autonomo.missao
        if not m:
            return _txt("Nenhum objetivo rodou ainda.")
        return _txt(m.resumo() + "\n" + "\n".join(f"{i}. [{e.estado}] {e.titulo}" for i, e in enumerate(m.etapas, 1)))

    return create_sdk_mcp_server(name="autonomo", version="1.0.0", tools=[objetivo, situacao])
