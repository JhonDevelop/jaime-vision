"""Ferramentas MCP `emocao` — o cérebro emocional exposto ao modelo (`mcp__emocao__*`).

Regra da constituição: toda pergunta ao João passa por `perguntar_ao_joao`. Ela devolve a resposta
registrada quando existe, pede confirmação em meia frase quando está velha, e só então autoriza perguntar."""
from __future__ import annotations
from datetime import date
from claude_agent_sdk import tool, create_sdk_mcp_server
from .perfil import Perfil
from .perguntas import Perguntas
from .momento import momento as calcular_momento
from .humor import Humor
from .prosodia import prosodia

def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}

def build_emocao_server(perfil: Perfil, perguntas: Perguntas, humor: Humor):
    @tool("perguntar_ao_joao", "OBRIGATÓRIO antes de perguntar qualquer coisa ao João. Devolve a resposta já registrada "
                               "(não pergunte de novo), ou pede confirmação em meia frase se for antiga, ou autoriza perguntar.",
          {"pergunta": str})
    async def perguntar_ao_joao(args):
        p = (args.get("pergunta") or "").strip()
        if not p:
            return _txt("Pergunta vazia.")
        d = perguntas.decidir(p)
        if d["acao"] == "usar":
            return _txt(f"JÁ RESPONDIDA há {d['dias']} dia(s) (\"{d['pergunta_original']}\"): {d['resposta']}. Use isso; não pergunte de novo.")
        if d["acao"] == "confirmar":
            return _txt(f"Respondida há {d['dias']} dias: \"{d['resposta']}\". Confirme em meia frase (\"continua {d['resposta'][:40]}?\") "
                        f"e registre com registrar_resposta.")
        perguntas.registrar(p)
        return _txt(f"Nunca perguntei isso. Pode perguntar agora — registrei como feita; quando ele responder, chame registrar_resposta.")

    @tool("registrar_resposta", "Guarda a resposta do João a uma pergunta (para nunca perguntar de novo).",
          {"pergunta": str, "resposta": str})
    async def registrar_resposta(args):
        perguntas.registrar(args.get("pergunta", ""), args.get("resposta", "").strip() or "—")
        return _txt("Registrado em 10-Eu/Perguntas-Feitas.md.")

    @tool("datas_importantes", "Lista as datas do João (aniversário, prazos, datas que repetem) com quantos dias faltam.", {})
    async def datas_importantes(args):
        hoje = date.today()
        linhas = []
        for d in sorted(perfil.datas(), key=lambda x: (x.dias_ate(hoje) is None, x.dias_ate(hoje) or 0)):
            dias = d.dias_ate(hoje)
            linhas.append(f"- {d.nome}" + (f" (@{d.projeto})" if d.projeto else "") + (f" — em {dias} dia(s)" if dias is not None else " — passou"))
        return _txt("\n".join(linhas) if linhas else "Nenhuma data em 10-Eu/Datas.md ainda. Pergunte o aniversário dele (via perguntar_ao_joao) e registre com adicionar_data.")

    @tool("adicionar_data", "Registra uma data em 10-Eu/Datas.md. ano vazio = repete todo ano (aniversário).",
          {"descricao": str, "dia": int, "mes": int, "ano": int, "projeto": str})
    async def adicionar_data(args):
        ano = args.get("ano") or None
        return _txt("Anotado: " + perfil.adicionar_data(args["descricao"], int(args["dia"]), int(args["mes"]), int(ano) if ano else None, args.get("projeto", "")))

    @tool("momento_de_hoje", "Que dia é hoje para o João: aniversário, feriado, prazos perto, semana pesada.", {})
    async def momento_de_hoje(args):
        m = calcular_momento(perfil)
        return _txt(m.texto())

    @tool("humor_atual", "Seu humor agora (energia, calor, gravidade, confiança) e como falar por causa dele.", {})
    async def humor_atual(args):
        return _txt(humor.texto() + "\n" + prosodia(humor)["instructions"])

    @tool("anotar_jeito", "Anota algo sobre o jeito do João em 10-Eu/Jeito.md. secao: Como fala | O que odeia | Horários | Quando quer resposta curta.",
          {"secao": str, "texto": str})
    async def anotar_jeito(args):
        perfil.anotar_jeito(args.get("secao") or "Como fala", args.get("texto", ""))
        return _txt("Anotado em 10-Eu/Jeito.md.")

    return create_sdk_mcp_server(name="emocao", version="1.0.0",
                                 tools=[perguntar_ao_joao, registrar_resposta, datas_importantes, adicionar_data,
                                        momento_de_hoje, humor_atual, anotar_jeito])
