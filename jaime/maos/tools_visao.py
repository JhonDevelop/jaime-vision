"""Ferramentas MCP `visao`: jogar (inicia a sessão em segundo plano), parar, situacao."""
from __future__ import annotations
import asyncio
from claude_agent_sdk import tool, create_sdk_mcp_server

def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}

def build_visao_server(visao):
    @tool("jogar", "Inicia uma sessão de visão contínua: vê a tela em loop e age (jogo simples, app sem API). Só quando o João pediu explicitamente. "
                   "Encerra com 'para'. max_passos opcional.", {"objetivo": str, "max_passos": int})
    async def jogar(args):
        if visao.ativa:
            return _txt("Já há uma sessão ativa. Diga 'para' antes.")
        asyncio.get_event_loop().create_task(visao.rodar(args["objetivo"], args.get("max_passos") or None))
        return _txt(f"Sessão de visão iniciada: {args['objetivo'][:100]}. 'para' encerra.")

    @tool("parar_visao", "Encerra a sessão de visão contínua agora.", {})
    async def parar_visao(args):
        return _txt("Encerrada." if visao.parar() else "Nenhuma sessão ativa.")

    @tool("situacao_visao", "Passos e estado da sessão de visão atual/última.", {})
    async def situacao_visao(args):
        s = visao.sessao
        if not s:
            return _txt("Nenhuma sessão ainda.")
        return _txt(f"{'ativa' if s.ativa else 'encerrada'} · {len(s.passos)}/{s.max_passos} passos · {s.fim_motivo or '…'}\n" +
                    "\n".join(f"- {p['acao']} {p.get('x', '')}{',' + str(p.get('y')) if p.get('y') is not None else ''} {p.get('combo', '')} → {p.get('resultado', '')}" for p in s.passos[-10:]))

    return create_sdk_mcp_server(name="visao", version="1.0.0", tools=[jogar, parar_visao, situacao_visao])
