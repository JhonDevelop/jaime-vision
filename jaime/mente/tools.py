"""Ferramentas MCP `mente`: o J.A.I.M.E pensa por conta própria e consulta o que já pensou (raciocínio próprio)."""
from __future__ import annotations
from claude_agent_sdk import tool, create_sdk_mcp_server

def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}

def build_mente_server(pensar):
    @tool("pensar_agora", "Forma um pensamento próprio sobre um assunto (um projeto, uma decisão, um padrão do João) e o registra. "
                          "Use quando quiser raciocinar sozinho antes de agir, ou quando o João pedir sua opinião e você quiser pensar de novo.",
          {"assunto": str})
    async def pensar_agora(args):
        p = await pensar.pensar(args.get("assunto") or None)
        return _txt(f"Pensei ({p.tema}): {p.texto}" if p else "Não tive um pensamento útil sobre isso agora.")

    @tool("pensamentos", "O que você já pensou sobre um assunto (raciocínio próprio guardado). Consulte ANTES de responder ao João: "
                         "a Mente contínua pode já ter chegado lá. Sem assunto, mostra os pensamentos recentes.",
          {"assunto": str})
    async def pensamentos(args):
        a = (args.get("assunto") or "").strip()
        hits = pensar.sobre(a) if a else pensar.pensamentos[-5:]
        return _txt("\n".join(f"- {p.quando} · {p.tema}: {p.texto}" for p in hits) if hits else "Ainda não pensei sobre isso.")

    return create_sdk_mcp_server(name="mente", version="1.0.0", tools=[pensar_agora, pensamentos])
