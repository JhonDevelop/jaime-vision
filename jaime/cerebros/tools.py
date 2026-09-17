"""Ferramentas MCP `cerebros`: o J.A.I.M.E escolhe com QUAL cérebro pensar, acorda o hemisfério e aprende
com o resultado. O Central é ele mesmo; o Esquerdo (Codex) e o Direito (Gemini) são terminais no Maestri."""
from __future__ import annotations
from claude_agent_sdk import tool, create_sdk_mcp_server
from ..hud.events import bus
from .hemisferios import POR_ID, tipo_do_pedido

def _txt(s): return {"content": [{"type": "text", "text": s}]}

def build_cerebros_server(cerebros):
    @tool("cerebros", "Como estão os seus três hemisférios: quem está acordado, forte em quê, e o placar de "
                      "acertos e erros de cada um. Use antes de delegar algo grande.", {})
    async def estado(args):
        linhas = [f"{d['nome']} ({d['preset']}) · {'acordado' if d['acordado'] else 'dormindo'} · "
                  f"forte em {d['forte_em']} · {d['acertos']} acertos, {d['erros']} erros — {d['funcao']}"
                  for d in cerebros.estado()]
        return _txt("\n".join(linhas))

    @tool("pensar_com", "Manda um trabalho para o hemisfério certo e espera a entrega. ESQUERDO (Codex) para "
                        "código, execução, teste, refatoração e mão de obra. DIREITO (Gemini) para pesquisa "
                        "longa, alternativas, crítica e criação. Deixe `hemisferio` vazio para eu escolher pelo "
                        "tipo do pedido. O Central é você: não delegue para ele.",
          {"tarefa": str, "hemisferio": str})
    async def pensar_com(args):
        tarefa = (args.get("tarefa") or "").strip()
        if not tarefa:
            return _txt("faltou dizer a tarefa")
        h = (args.get("hemisferio") or "").strip().lower() or cerebros.escolher(tarefa).id
        if h == "central":
            return _txt("O Central sou eu — isso eu resolvo sem delegar.")
        bus.emitir("cerebro", hemisferio=h, estado="pensando", tarefa=tarefa[:90])
        r = cerebros.delegar(h, tarefa)
        bus.emitir("cerebro", hemisferio=h, estado="entregou", tarefa=tarefa[:90])
        return _txt(f"[{POR_ID[h].nome}] {r}")

    @tool("acordar_cerebro", "Acorda um hemisfério que está dormindo: esquerdo (Codex) ou direito (Gemini). "
                             "Faça isso quando souber que vai precisar dele em seguida.", {"hemisferio": str})
    async def acordar(args):
        h = (args.get("hemisferio") or "").strip().lower()
        r = cerebros.acordar(h)
        bus.emitir("cerebro", hemisferio=h, estado="acordou")
        return _txt(r)

    @tool("avaliar_cerebro", "Diz se o hemisfério entregou BEM aquele trabalho. É assim que o roteamento aprende: "
                             "acertar sobe o peso dele naquele tipo, errar derruba o dobro. Chame sempre depois de "
                             "conferir uma entrega.", {"hemisferio": str, "tarefa": str, "bom": bool})
    async def avaliar(args):
        h = (args.get("hemisferio") or "").strip().lower()
        tipo = tipo_do_pedido(args.get("tarefa") or "")
        novo = cerebros.registrar(h, tipo, bool(args.get("bom")))
        bus.emitir("cerebro", hemisferio=h, estado="aprendeu", peso=novo, tipo=tipo)
        return _txt(f"anotado: {h} em {tipo} agora vale {novo:.2f}")

    return create_sdk_mcp_server(name="cerebros", version="1.0.0",
                                 tools=[estado, pensar_com, acordar, avaliar])
