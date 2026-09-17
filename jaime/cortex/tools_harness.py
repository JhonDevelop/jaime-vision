"""Ferramentas MCP `harness`: o J.A.I.M.E persegue um objetivo até conseguir, sozinho."""
from __future__ import annotations
import asyncio
from claude_agent_sdk import tool, create_sdk_mcp_server

def _txt(s): return {"content": [{"type": "text", "text": s}]}

def build_harness_server(harness):
    @tool("perseguir", "PERSEGUE um objetivo até conseguir, sem pedir licença a cada passo: você planeja, age, "
                       "VERIFICA contra o critério, corrige quando falha e troca o caminho quando empaca. Use para "
                       "o que tem fim mensurável e leva mais de um turno ('deixa o painel de música funcionando', "
                       "'descobre por que o barge-in corta sozinho e conserta'). Roda em segundo plano: você "
                       "responde ao João na hora e o laço segue. NÃO use para o que resolve num turno, nem para "
                       "coisa sem critério de pronto.", {"objetivo": str})
    async def perseguir(args):
        alvo = (args.get("objetivo") or "").strip()
        if not alvo:
            return _txt("faltou dizer o objetivo")
        if harness.atual and harness.atual.estado in ("planejando", "rodando"):
            return _txt(f"já estou perseguindo: {harness.atual.objetivo[:70]}. Pare essa antes.")
        asyncio.create_task(harness.perseguir(alvo))
        return _txt(f"Comecei a perseguir: {alvo}. Sigo em segundo plano; pergunte 'como vai' quando quiser.")

    @tool("como_vai", "Em que pé está o objetivo que você está perseguindo: plano, o que já fechou, o que "
                      "travou e por quê.", {})
    async def como_vai(args):
        return _txt(harness.como_vai())

    @tool("parar_perseguicao", "Para o objetivo em andamento. Use quando o João mandar parar ou quando ficar "
                               "claro que não vale mais a pena.", {})
    async def parar(args):
        return _txt("Parei." if harness.interromper() else "Não havia nada em andamento.")

    return create_sdk_mcp_server(name="harness", version="1.0.0", tools=[perseguir, como_vai, parar])
