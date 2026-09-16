"""Ferramentas MCP `financas`: o João fala e o Jaime registra o dinheiro."""
from __future__ import annotations
from claude_agent_sdk import tool, create_sdk_mcp_server

def _txt(s): return {"content": [{"type": "text", "text": s}]}

def build_financas_server(livro):
    @tool("registrar_financa", "Registra uma entrada ou saída de dinheiro no livro-caixa do João. Use quando ele disser "
                               "'gastei/paguei/comprei X' (saída) ou 'recebi/vendi/ganhei X' (entrada). valor aceita '50', "
                               "'R$ 1.234,56', '2 mil'. categoria: mercado, combustível, alimentação, assinaturas, salário, vendas… "
                               "(deixe vazio que eu adivinho pela descrição). tipo: entrada|saída (vazio = adivinho).",
          {"valor": str, "categoria": str, "descricao": str, "tipo": str})
    async def registrar_financa(args):
        l = livro.registrar(args.get("valor", "0"), args.get("categoria", "") or "outros",
                            args.get("descricao", ""), args.get("tipo", ""))
        return _txt(f"Anotado: {l.tipo} de R$ {l.valor:.2f} em {l.categoria}" + (f" ({l.descricao})" if l.descricao else "") + ".")

    @tool("resumo_financas", "Saldo, entradas, saídas e maiores gastos por categoria. mes vazio = mês atual; '2026-09' um mês.",
          {"mes": str})
    async def resumo_financas(args):
        return _txt(livro.texto_resumo(args.get("mes", "")))

    return create_sdk_mcp_server(name="financas", version="1.0.0", tools=[registrar_financa, resumo_financas])
