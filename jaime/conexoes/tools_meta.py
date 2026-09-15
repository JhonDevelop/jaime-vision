"""Ferramentas MCP `meta`: pendentes, enviar_whatsapp, enviar_instagram (as duas últimas são ações do Vigia)."""
from __future__ import annotations
from claude_agent_sdk import tool, create_sdk_mcp_server

def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}

def build_meta_server(meta):
    @tool("mensagens_pendentes", "Mensagens de terceiros (WhatsApp/Instagram) com resumo e rascunho aguardando o 'confirmo'.", {})
    async def mensagens_pendentes(args):
        if not meta.pendentes:
            return _txt("Nenhuma pendente.")
        return _txt("\n".join(f"- [{k}] {v['mensagem'].plataforma} · {v['mensagem'].nome or v['mensagem'].de}: {v['resumo']} → rascunho: {v['rascunho'][:120]}"
                              for k, v in meta.pendentes.items()))

    @tool("enviar_whatsapp", "ENVIA mensagem pelo WhatsApp Cloud API. Ação do Vigia: só com 'confirmo'.", {"para": str, "texto": str, "pendente_id": str})
    async def enviar_whatsapp(args):
        if not meta.ativo:
            return _txt("Meta não configurada (docs/CONEXOES.md).")
        try:
            r = await meta.enviar_whatsapp(args["para"], args["texto"]); meta.pendentes.pop(args.get("pendente_id") or "", None)
            return _txt(f"Enviado ({(r.get('messages') or [{}])[0].get('id', 'ok')}).")
        except Exception as e:
            return _txt(f"falhou: {type(e).__name__}: {str(e)[:120]}")

    @tool("enviar_instagram", "ENVIA DM pelo Instagram Messaging API. Ação do Vigia: só com 'confirmo'.", {"para": str, "texto": str, "pendente_id": str})
    async def enviar_instagram(args):
        if not meta.ativo:
            return _txt("Meta não configurada (docs/CONEXOES.md).")
        try:
            r = await meta.enviar_instagram(args["para"], args["texto"]); meta.pendentes.pop(args.get("pendente_id") or "", None)
            return _txt(f"Enviado ({r.get('message_id', 'ok')}).")
        except Exception as e:
            return _txt(f"falhou: {type(e).__name__}: {str(e)[:120]}")

    return create_sdk_mcp_server(name="meta", version="1.0.0", tools=[mensagens_pendentes, enviar_whatsapp, enviar_instagram])
