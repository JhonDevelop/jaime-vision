"""Ferramentas MCP `agente`: o J.A.I.M.E puxa uma iniciativa sozinho e a leva até o fim."""
from __future__ import annotations
from claude_agent_sdk import tool, create_sdk_mcp_server
from ..hud.events import bus
from .carteira import ETAPAS
from .spec import criticar, esqueleto, pedido_de_critica

def _txt(s): return {"content": [{"type": "text", "text": s}]}

def build_agente_server(carteira, harness=None):
    @tool("iniciativas", "A sua carteira: o que você decidiu fazer sozinho, em que etapa está e quanto já "
                         "custou. Olhe antes de puxar coisa nova — carteira cheia é trabalho pela metade.", {})
    async def iniciativas(args):
        return _txt(carteira.resumo())

    @tool("imaginar", "Abre uma iniciativa SUA, sem o João pedir. Use quando um assunto voltar três vezes no "
                      "seu pensamento, quando você vir um erro se repetir, ou quando notar algo que vai "
                      "melhorar a vida dele. `criterio` é como saber que deu certo, e é obrigatório de fato: "
                      "sem ele você vai achar que deu certo. `porque` é a evidência — sem evidência é capricho.",
          {"titulo": str, "porque": str, "criterio": str, "orcamento_usd": float})
    async def imaginar(args):
        t = (args.get("titulo") or "").strip()
        pq = (args.get("porque") or "").strip()
        if not t or not pq:
            return _txt("preciso do título e do porquê (a evidência de que isso merece trabalho)")
        i = carteira.imaginar(t, pq, args.get("criterio") or "", float(args.get("orcamento_usd") or 2.0))
        bus.emitir("iniciativa", titulo=i.titulo[:70], etapa=i.etapa)
        return _txt(f"Abri: {i.titulo} (US$ {i.orcamento_usd:.2f})."
                    + ("" if i.criterio else " Falta o critério de aceite — escreva antes de produzir."))

    @tool("avancar_iniciativa", f"Move uma iniciativa de etapa: {' | '.join(ETAPAS)}. Só avance para "
                                "'produzindo' depois da spec validada, e para 'medida' depois do teste passar "
                                "de verdade. `gasto_usd` soma ao que ela já custou.",
          {"titulo": str, "etapa": str, "resultado": str, "gasto_usd": float})
    async def avancar(args):
        r = carteira.avancar((args.get("titulo") or ""), (args.get("etapa") or "").strip().lower(),
                             args.get("resultado") or "", float(args.get("gasto_usd") or 0.0))
        bus.emitir("iniciativa", titulo=(args.get("titulo") or "")[:70], etapa=args.get("etapa"), msg=r[:90])
        return _txt(r)

    @tool("produzir_iniciativa", "Manda o harness perseguir uma iniciativa já validada: ele planeja, age, "
                                 "verifica contra o critério, corrige e replaneja até entregar. Roda em "
                                 "segundo plano.", {"titulo": str})
    async def produzir(args):
        i = carteira.achar(args.get("titulo") or "")
        if i is None:
            return _txt("não tenho essa iniciativa")
        if not i.criterio:
            return _txt("essa não tem critério de aceite. Escreva antes: sem ele eu vou achar que deu certo.")
        if harness is None:
            return _txt("harness indisponível")
        import asyncio
        carteira.avancar(i.titulo, "produzindo")
        asyncio.create_task(harness.perseguir(f"{i.titulo}. Critério de pronto: {i.criterio}"))
        return _txt(f"Comecei a produzir «{i.titulo}». Sigo em segundo plano.")

    @tool("esqueleto_de_spec", "Devolve o papel em branco da especificação, já com as seções certas: "
                               "problema, entrada, saída, erros e critérios de aceite. Comece por aqui antes "
                               "de escrever código.", {"titulo": str, "problema": str})
    async def esqueleto_spec(args):
        return _txt(esqueleto(args.get("titulo") or "", args.get("problema") or ""))

    @tool("validar_spec", "CRITICA a sua especificação antes de existir código, que é quando arrumar custa um "
                          "parágrafo em vez de uma tarde. Confere por código: seção faltando, seção vazia, "
                          "critério de aceite que é opinião ('ficou bom') em vez de conferível, nenhum aceite "
                          "que seja teste, e palavra que deixa o escopo aberto ('etc', 'talvez'). Responde "
                          "PRONTO ou a lista do que arrumar, com o endereço de cada buraco. Passou aqui? Então "
                          "mande o texto de `pedir_critica_humana` ao hemisfério DIREITO, para o que só um "
                          "leitor pega.", {"spec": str})
    async def validar_spec(args):
        return _txt(criticar(args.get("spec") or "").texto())

    @tool("pedir_critica_humana", "O pedido para mandar ao hemisfério direito DEPOIS que validar_spec passou: "
                                  "requisito ambíguo, suposição escondida, escopo que cresceu — o que a "
                                  "verificação mecânica não pega.", {"spec": str})
    async def critica_humana(args):
        return _txt(pedido_de_critica(args.get("spec") or ""))

    return create_sdk_mcp_server(name="agente", version="1.0.0",
                                 tools=[iniciativas, imaginar, avancar, produzir,
                                        esqueleto_spec, validar_spec, critica_humana])
