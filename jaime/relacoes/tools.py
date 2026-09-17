"""Ferramentas MCP `relacoes` — o grafo de pessoas/animais/lugares/projetos/organizações (`mcp__relacoes__*`)."""
from __future__ import annotations
from claude_agent_sdk import tool, create_sdk_mcp_server
from .grafo import Relacoes


def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}


def build_curiosidade(curiosidade):
    """Ferramentas da curiosidade: quem fala com o João, quem ele ainda não conhece, e o que interrompe."""
    from claude_agent_sdk import tool as _tool, create_sdk_mcp_server as _srv

    def _t(s): return {"content": [{"type": "text", "text": s}]}

    @_tool("quem_me_fala", "Quem anda mandando mensagem para o João, quantas vezes, em que horário, e de "
                           "quem você JÁ sabe quem é. Olhe antes de decidir se um recado merece "
                           "interromper.", {})
    async def quem_me_fala(args):
        return _t(curiosidade.contexto() or "ainda não observei ninguém falando com ele.")

    @_tool("tenho_curiosidade", "A pergunta que você faria ao João sobre alguém que fala muito com ele e que "
                                "você não conhece. Faça UMA de cada vez, e só quando couber na conversa — "
                                "nunca no meio de outra coisa. Vazio quer dizer que não há o que perguntar.",
           {"nome": str})
    async def tenho_curiosidade(args):
        return _t(curiosidade.curiosidade(args.get("nome") or "") or "nada a perguntar sobre essa pessoa agora.")

    @_tool("aprendi_quem_e", "Guarda o que o João respondeu sobre alguém: quem a pessoa é e o que ela "
                             "significa para ele. Vira memória de verdade, com evidência e data, e a partir "
                             "daí você sabe se um recado dela merece interromper.",
           {"nome": str, "quem_e": str, "relacao": str})
    async def aprendi(args):
        return _t(curiosidade.aprendi(args.get("nome") or "", args.get("quem_e") or "",
                                      args.get("relacao") or "conhece"))

    @_tool("vale_interromper", "Este recado merece tirar o João do que ele está fazendo? Responde sim ou não "
                               "COM O PORQUÊ. Urgência de verdade passa mesmo de desconhecido; conversa fiada "
                               "não passa nem de gente próxima.", {"de": str, "texto": str})
    async def vale(args):
        ok, porque = curiosidade.vale_avisar(args.get("de") or "", args.get("texto") or "")
        return _t(("Avise: " if ok else "Não interrompa: ") + porque)

    return _srv(name="curiosidade", version="1.0.0",
                tools=[quem_me_fala, tenho_curiosidade, aprendi, vale])


def build_relacoes_server(relacoes: Relacoes):
    @tool("lembrar", "Guarda ou atualiza uma pessoa/animal/lugar/projeto/organização (tipo: pessoa|animal|lugar|"
                     "projeto|organizacao). Se vier `relacao` + `com`, também liga aos dois (relacao: parentesco|"
                     "amizade|sociedade|dono-de|trabalha-em|mora-em). Se vier `chave` + `valor`, guarda um fato solto "
                     "(ex.: chave='cargo' valor='CTO'). Fato ou relação que muda vira histórico sozinho — nunca chame "
                     "'esquecer' só porque algo mudou. Nunca guarda senha, documento, chave ou cartão (filtrado aqui).",
          {"nome": str, "tipo": str, "apelidos": str, "relacao": str, "com": str, "tipo_com": str, "detalhe": str,
           "chave": str, "valor": str, "desde": str, "evidencia": str})
    async def lembrar(args):
        nome = (args.get("nome") or "").strip()
        if not nome:
            return _txt("Faltou o nome de quem/o que lembrar.")
        tipo = args.get("tipo") or "pessoa"
        desde = args.get("desde") or None
        evidencia = args.get("evidencia") or ""
        relacoes.lembrar_pessoa(nome, tipo, args.get("apelidos") or "", evidencia, desde)
        partes = [f"Guardei {nome} ({tipo})."]
        if args.get("relacao") and args.get("com"):
            relacoes.ligar(nome, args["com"], args["relacao"], args.get("detalhe") or "", desde, evidencia,
                           tipo, args.get("tipo_com") or "pessoa")
            partes.append(f"{nome} — {args['relacao']} — {args['com']}"
                          + (f" ({args['detalhe']})" if args.get("detalhe") else "") + ".")
        if args.get("chave") and args.get("valor"):
            ok = relacoes.fato(nome, args["chave"], args["valor"], desde, evidencia, tipo)
            partes.append(f"{args['chave']}: {args['valor']}." if ok else "(esse valor parecia segredo — não guardei.)")
        return _txt(" ".join(partes))

    @tool("sobre", "Quem é essa pessoa/lugar/projeto/organização: o que já sei, as relações que valem hoje e o "
                   "histórico do que já valeu e mudou.", {"nome": str})
    async def sobre(args):
        d = relacoes.sobre(args.get("nome") or "")
        return _txt(relacoes.texto_sobre(d) if d else f"Ainda não conheço \"{args.get('nome', '')}\".")

    @tool("quem_e", "Resolve um apelido ou menção solta ('o Rafael', 'meu sócio', 'ela') para a pessoa certa no grafo.",
          {"apelido": str})
    async def quem_e(args):
        d = relacoes.quem_e(args.get("apelido") or "")
        return _txt(relacoes.texto_sobre(d) if d else f"Não sei quem é \"{args.get('apelido', '')}\" ainda.")

    @tool("esquecer", "Apaga de verdade um engano — não use quando um fato simplesmente MUDOU (isso já vira "
                     "histórico sozinho). Informe `chave` para apagar um fato, `relacao`/`com` para uma relação, "
                     "ou só `nome` para apagar o nó inteiro.",
          {"nome": str, "relacao": str, "com": str, "chave": str})
    async def esquecer(args):
        nome = (args.get("nome") or "").strip()
        if not nome:
            return _txt("Faltou dizer de quem/o que esquecer.")
        n = relacoes.esquecer(nome, args.get("relacao") or None, args.get("com") or None, args.get("chave") or None)
        return _txt(f"Apaguei {n} registro(s) sobre {nome}." if n else f"Não achei o que apagar em \"{nome}\".")

    return create_sdk_mcp_server(name="relacoes", version="1.0.0", tools=[lembrar, sobre, quem_e, esquecer])
