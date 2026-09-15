"""Ferramentas MCP `evolucao`: propor_melhoria, implementar_melhoria, propostas — e `memoria`: recordar."""
from __future__ import annotations
import asyncio
from claude_agent_sdk import tool, create_sdk_mcp_server

def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}

def build_evolucao_server(evolucao, indice=None):
    @tool("propor_melhoria", "Olha para os sinais (placar, problemas, pendências) e propõe UMA melhoria em si mesmo (vira M-xxxx em 01-Estado/Propostas.md).", {})
    async def propor_melhoria(args):
        p = await evolucao.propor()
        return _txt(f"{p.id}: {p.titulo} — {p.motivo}\nPara implementar: implementar_melhoria('{p.id}')." if p else "Sem proposta desta vez.")

    @tool("implementar_melhoria", "Implementa uma proposta num worktree isolado (branch jaime/<slug>), roda os testes e escreve o PR. O merge é do João ('confirmo').", {"id": str})
    async def implementar_melhoria(args):
        try:
            asyncio.get_event_loop().create_task(evolucao.implementar(args["id"]))
            return _txt(f"Implementando {args['id']} em segundo plano; acompanhe em propostas.")
        except Exception as e:
            return _txt(f"falhou: {type(e).__name__}: {e}")

    @tool("propostas", "Lista as propostas de melhoria e o estado de cada uma.", {})
    async def propostas(args):
        ps = evolucao.propostas()
        return _txt("\n".join(f"- {p.id} · {p.titulo} · {p.estado}" + (f" · {p.branch}" if p.branch else "") for p in ps) if ps else "Nenhuma proposta ainda.")

    ferramentas = [propor_melhoria, implementar_melhoria, propostas]
    if indice is not None:
        @tool("recordar", "Busca semântica no vault (FTS5): o que o João já disse sobre um assunto, com trecho e nota.", {"assunto": str})
        async def recordar(args):
            indice.atualizar()
            hits = indice.buscar(args["assunto"], 8)
            return _txt("\n".join(f"- {c}: {t}" for c, t, _ in hits) if hits else "Nada no vault sobre isso.")
        ferramentas.append(recordar)
    return create_sdk_mcp_server(name="evolucao", version="1.0.0", tools=ferramentas)
