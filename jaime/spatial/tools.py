"""MCP `espacial` — o Central enxerga e usa a cena. Registrado só com JAIME_SPATIAL ligado.

As ferramentas que agem no SO passam pelo hook PreToolUse do Vigia como qualquer outra. A Lixeira usa o nome
`apagar` DE PROPÓSITO: o Vigia existente já segura `mcp__*__apagar` até o "sim" do João (confirmação em lote),
então a confirmação explícita que a política espacial exige é o próprio Vigia — sem segunda regra paralela."""
from __future__ import annotations
import json
from claude_agent_sdk import tool, create_sdk_mcp_server
from .acoes import ActionProposal
from .core import PALAVRAS_ISSO, objeto_de_dict


def _txt(d) -> dict:
    return {"content": [{"type": "text", "text": d if isinstance(d, str) else json.dumps(d, ensure_ascii=False)[:4000]}]}


def build_espacial_server(servico, acoes=None, voz=None):
    core = servico.core

    def _ator() -> str:
        return "joao" if servico.dono_ok() else "desconhecido"

    def _alvo(alvo: str) -> str | None:
        alvo = (alvo or "").strip()
        if alvo in core.objects:
            return alvo
        if voz is not None:
            if not alvo or alvo.lower() in PALAVRAS_ISSO:
                rec = voz.resolvedor._recentes()          # o modelo já resolveu a frase; aqui "isso" = a seleção mais nova
                return rec[0][0].id if rec else None
            r = voz.resolvedor.resolver(alvo)
            if r.status == "ok" and len(r.objetos) == 1:
                return r.objetos[0].id
        for o in core.objects.values():
            if (o.label or "").lower() == alvo.lower():
                return o.id
        return None

    @tool("estado", "Cena espacial agora: objetos virtuais (id, rótulo, tipo, posição no HUD), o que o João selecionou "
                    "com a mão e se o rastreamento está ligado. Use para saber o que 'isso' é.", {})
    async def estado(args):
        return _txt({**servico.estado(curto=True), "cena": core.cena()})

    @tool("selecionar", "Seleciona um objeto da cena pelo id ou rótulo (equivale ao João apontar para ele).", {"alvo": str})
    async def selecionar(args):
        oid = _alvo(args.get("alvo", ""))
        if not oid:
            return _txt("não achei esse objeto na cena")
        servico._publicar(core.select(_ator(), oid, 1.0, origem="ferramenta"))
        return _txt(f"selecionado: {oid}")

    @tool("criar_objeto", "Cria um objeto VIRTUAL na cena do HUD (um nó para desenhar/organizar). x,y em 0..1 da tela. "
                          "resource_ref (opcional) liga a um caminho real — só é usado depois de validado numa ação.",
          {"label": str, "kind": str, "x": float, "y": float, "resource_ref": str})
    async def criar_objeto(args):
        o = objeto_de_dict({"label": args.get("label"), "kind": args.get("kind") or "nota",
                            "pos": (float(args.get("x", 0.5)), float(args.get("y", 0.5))), "resource_ref": args.get("resource_ref") or None})
        if o.id in core.objects:
            return _txt("já existe")
        core.add(o)
        servico.emitir("espacial", evento="spatial.object", obj_novo=o.to_dict())
        return _txt(f"criado: {o.id}")

    tools = [estado, selecionar, criar_objeto]

    if acoes is not None:
        @tool("propor_acao", "Monta a PRÉVIA de uma ação espacial no SO. verbo: open | move_window. alvo: id, rótulo ou "
                             "'isso'. args_json: para move_window {\"app\":..., \"titulo\":..., \"x\":..., \"y\":...}. "
                             "Devolve status (allow/review/deny), efeitos e proposta_id. Nada acontece ainda.",
              {"verbo": str, "alvo": str, "args_json": str})
        async def propor_acao(args):
            oid = _alvo(args.get("alvo", ""))
            if not oid:
                return _txt("alvo não resolvido — pergunte ao João qual objeto")
            try:
                extra = json.loads(args.get("args_json") or "{}")
            except json.JSONDecodeError:
                extra = {}
            verbo = (args.get("verbo") or "").strip()
            if verbo == "move_to_trash":
                return _txt("para a Lixeira use `apagar` (o Vigia pede o 'sim' do João antes)")
            pv = await acoes.propor(ActionProposal(verbo, oid, _ator(), 1.0, "voz", extra))
            return _txt(pv.to_dict())

        @tool("executar", "Executa uma prévia allow (open/move_window) pelo proposta_id. Em dry-run devolve o recibo "
                          "sem tocar o SO. Repetir o mesmo id devolve o mesmo recibo.", {"proposta_id": str})
        async def executar(args):
            r = await acoes.executar(str(args.get("proposta_id", "")))
            return _txt(r.to_dict())

        @tool("apagar", "Move para a LIXEIRA (recuperável) o arquivo por trás de um objeto da cena. alvo: id/rótulo/'isso'. "
                        "O Vigia segura até o João dizer 'sim'. Nunca apaga definitivamente.",
              {"alvo": str, "caminho": str})
        async def apagar(args):
            oid = _alvo(args.get("alvo", ""))
            if not oid:
                return _txt("alvo não resolvido")
            p = ActionProposal("move_to_trash", oid, _ator(), 1.0, "voz")
            pv = await acoes.propor(p)
            if pv.status == "deny":
                return _txt(pv.to_dict())
            r = await acoes.executar(p.id, confirmado=True)      # chegou aqui = o Vigia já liberou com o "sim"
            return _txt(r.to_dict())

        @tool("desfazer", "Desfaz uma ação espacial pelo recibo_id (move a janela de volta, restaura da Lixeira).", {"recibo_id": str})
        async def desfazer(args):
            ok, msg = await acoes.desfazer(str(args.get("recibo_id", "")))
            return _txt({"ok": ok, "msg": msg})

        tools += [propor_acao, executar, apagar, desfazer]

    return create_sdk_mcp_server(name="espacial", version="0.1.0", tools=tools)
