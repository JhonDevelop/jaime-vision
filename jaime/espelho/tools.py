"""Ferramentas MCP `espelho`: o que o J.A.I.M.E aprendeu sobre o jeito do João, contado do vault."""
from __future__ import annotations
from claude_agent_sdk import tool, create_sdk_mcp_server

def _txt(s): return {"content": [{"type": "text", "text": s}]}

def build_espelho_server(espelho):
    @tool("tracos_do_joao", "O que você aprendeu sobre o jeito do João ouvindo ele: ritmo do dia, tamanho da "
                            "frase, o que ele mais pede, as palavras dele, como decide, o que ele deixa parado. "
                            "Cada traço vem com a evidência. Use para antecipar e para decidir como ele decidiria — "
                            "nunca para bajular nem para dizer a ele como ele é, a menos que ele pergunte.", {})
    async def tracos(args):
        return _txt(espelho.contexto(limite=10))

    @tool("reler_o_joao", "Relê as conversas e o diário e atualiza 10-Eu/Tracos.md. Faça quando ele mudar de "
                          "rotina, começar um projeto novo, ou depois de um dia cheio de conversa.", {})
    async def reler(args):
        espelho.salvar()
        return _txt("Reli o que ele falou e atualizei os traços.\n\n" + espelho.contexto())

    return create_sdk_mcp_server(name="espelho", version="1.0.0", tools=[tracos, reler])
