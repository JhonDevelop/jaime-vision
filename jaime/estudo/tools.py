"""Ferramentas MCP `estudo`: abrir_problema, problemas_abertos, resolver_problema."""
from __future__ import annotations
from claude_agent_sdk import tool, create_sdk_mcp_server

def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}

def build_estudo_server(estudo):
    @tool("abrir_problema", "Registra um problema em aberto para o cérebro de estudo pesquisar depois (erro repetido, "
                            "pergunta sem resposta, 'não sei'). origem: ferramenta_falhou | teste_quebrou | joao_pediu | sem_resposta | correcao | manual",
          {"titulo": str, "contexto": str, "origem": str})
    async def abrir_problema(args):
        p = estudo.abrir(args.get("titulo", ""), args.get("contexto", ""), args.get("origem") or "manual")
        return _txt(f"{p.id} aberto: {p.titulo}. Entra no próximo ciclo de estudo.")

    @tool("problemas_abertos", "Lista os problemas em aberto e quantas tentativas cada um já teve.", {})
    async def problemas_abertos(args):
        ab = estudo.problemas.abertos()
        return _txt("\n".join(f"- {p.id} · {p.titulo} · {len(p.tentativas)} tentativa(s)" for p in ab) if ab else "Nenhum problema em aberto.")

    @tool("resolver_problema", "Marca um problema como resolvido com o que se aprendeu (vira nota em 50-Conhecimento/).",
          {"id": str, "titulo": str, "como_reproduzir": str, "o_que_resolveu": str, "onde_se_aplica": str})
    async def resolver_problema(args):
        p = estudo.problemas.por_id(args.get("id", ""))
        if not p:
            return _txt("ID não encontrado.")
        rel = estudo._escrever_conhecimento(p, {k: args.get(k, "") for k in ("titulo", "como_reproduzir", "o_que_resolveu", "onde_se_aplica")})
        estudo.problemas.resolver(p.id, rel); estudo.emitir(f"resolvido {p.id} → {rel}")
        return _txt(f"{p.id} resolvido → {rel}")

    return create_sdk_mcp_server(name="estudo", version="1.0.0", tools=[abrir_problema, problemas_abertos, resolver_problema])
