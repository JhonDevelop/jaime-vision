"""Ferramentas MCP `interface`: o J.A.I.M.E MOSTRA as coisas — e, quando não existe tela para algo, ele CRIA uma.

`mostrar` recebe um HTML curto que ele mesmo compõe (tabela, gráfico, cartão, lista) e abre como pop-up no cockpit.
O HTML roda num iframe isolado (sandbox, sem acesso ao cockpit nem aos dados locais): é só desenho.
`abrir_tela` abre as telas que já existem (finanças, afazeres, agenda, música, cérebro)."""
from __future__ import annotations
from claude_agent_sdk import tool, create_sdk_mcp_server
from .events import bus

def _txt(s): return {"content": [{"type": "text", "text": s}]}

TELAS = ("financas", "afazeres", "agenda", "musica", "agentes", "teclado", "inicio")

def build_interface_server():
    @tool("mostrar", "MOSTRA algo visualmente ao João num pop-up do cockpit, criando a interface na hora. Use SEMPRE que "
                     "ele pedir para VER algo que não tem tela pronta (uma comparação, uma tabela, um gráfico, um resumo, "
                     "um passo a passo, um plano). Componha `html` você mesmo: HTML+CSS simples e escuro (fundo transparente, "
                     "texto #dfe9f5, destaque #38e1ff e #ffb347, fonte monospace), sem <script>, sem imagens externas. "
                     "Para gráfico use barras com <div> e largura em %. Seja direto e bonito. titulo: 2-4 palavras.",
          {"titulo": str, "html": str})
    async def mostrar(args):
        titulo = (args.get("titulo") or "J.A.I.M.E").strip()[:60]
        html = (args.get("html") or "").strip()
        if not html:
            return _txt("faltou o html para mostrar")
        bus.emitir("mostrar", titulo=titulo, html=html[:20000])
        return _txt(f"Mostrei no cockpit: {titulo}.")

    @tool("abrir_tela", f"Abre uma tela que já existe no cockpit. tela: {' | '.join(TELAS)}.", {"tela": str})
    async def abrir_tela(args):
        t = (args.get("tela") or "").strip().lower()
        if t not in TELAS:
            return _txt(f"tela desconhecida; use: {', '.join(TELAS)}")
        bus.emitir("painel", tela=t)
        return _txt(f"Abrindo {t}.")

    return create_sdk_mcp_server(name="interface", version="1.0.0", tools=[mostrar, abrir_tela])
