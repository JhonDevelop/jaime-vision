"""MCP `blocos` — o cérebro abre, atualiza, fecha e cria blocos de interface em QUALQUER superfície conectada.

Preferir isto ao `mcp__interface__mostrar` (HTML só-web): um bloco estruturado aparece no cockpit, na janela
nativa, no terminal, nos óculos e é lido em voz no falante. HTML fica como último recurso (tipo `html`, com
`alternativo` em texto para quem não é web)."""
from __future__ import annotations
import json
from claude_agent_sdk import tool, create_sdk_mcp_server
from .modelo import TIPOS, BlocoInvalido


def _txt(d) -> dict:
    return {"content": [{"type": "text", "text": d if isinstance(d, str) else json.dumps(d, ensure_ascii=False)[:4000]}]}


FORMATOS = ("texto {texto} · lista {itens:[{texto,detalhe,feito}]} · tabela {colunas,linhas} · "
            "metricas {itens:[{rotulo,valor,unidade,variacao,estado}]} · grafico {forma:barras|linha, series:[{nome,pontos:[{x,y}]}], unidade} · "
            "grafo {nos:[{id,rotulo}],arestas:[{de,para,rotulo}]} · status {estado:ok|atencao|ruim,texto} · progresso {valor 0..1,texto} · "
            "acoes {texto,botoes:[{rotulo,intencao}]} · html {html sem script, alternativo}")


def build_blocos_server(g, modelos, fontes):
    @tool("abrir", "ABRE (ou atualiza, se o id já existe) um bloco de interface para o João VER — em todas as superfícies: "
                   "cockpit, janela nativa, terminal, óculos, visor; no falante vira resumo em voz. "
                   f"tipo: {' | '.join(TIPOS)}. conteudo_json por tipo: {FORMATOS}. "
                   "Ou use `modelo` (um nome de `modelos`) OU `fonte` (dado vivo, ver `fontes`) em vez de conteúdo. "
                   "prioridade 0-3 (óculos mostram só os 3 maiores). ttl_s fecha sozinho. falar=true lê ao abrir. "
                   "x,y (0..1) posição preferida na tela.",
          {"tipo": str, "titulo": str, "conteudo_json": str, "modelo": str, "fonte": str, "id": str, "prioridade": int,
           "ttl_s": float, "falar": bool, "x": float, "y": float, "superficie": str})
    async def abrir(args):
        try:
            if args.get("modelo"):
                d = modelos.instanciar(args["modelo"])
                if args.get("titulo"):
                    d["titulo"] = args["titulo"]
            else:
                d = {"tipo": args.get("tipo"), "titulo": args.get("titulo"), "fonte": args.get("fonte") or None,
                     "conteudo": json.loads(args.get("conteudo_json") or "{}")}
            for k in ("id", "prioridade", "ttl_s", "falar"):
                if args.get(k) not in (None, ""):
                    d[k] = args[k]
            anc = {k: args[k] for k in ("x", "y") if args.get(k) is not None}
            if args.get("superficie"):
                anc["superficie"] = args["superficie"]
            if anc:
                d["ancoragem"] = {**(d.get("ancoragem") or {}), **anc}
            b = g.abrir(d, origem="jaime")
            return _txt(f"bloco '{b.titulo}' aberto (id {b.id}, {b.tipo}{', privado' if b.privado else ''}).")
        except KeyError as e:
            return _txt(f"modelo desconhecido: {e}. Tenho: {', '.join(modelos.nomes())}")
        except (BlocoInvalido, json.JSONDecodeError) as e:
            return _txt(f"bloco recusado: {e}")

    @tool("atualizar", "Muda um bloco aberto: conteudo_json (mescla), titulo, prioridade, x/y.",
          {"id": str, "conteudo_json": str, "titulo": str, "prioridade": int, "x": float, "y": float})
    async def atualizar(args):
        patch = {}
        try:
            if args.get("conteudo_json"):
                patch["conteudo"] = json.loads(args["conteudo_json"])
            for k in ("titulo", "prioridade"):
                if args.get(k) not in (None, ""):
                    patch[k] = args[k]
            anc = {k: args[k] for k in ("x", "y") if args.get(k) is not None}
            if anc:
                patch["ancoragem"] = anc
            b = g.atualizar(str(args.get("id", "")), patch)
            return _txt(f"bloco {b.id} atualizado (v{b.versao}).")
        except KeyError:
            return _txt("bloco não está aberto")
        except (BlocoInvalido, json.JSONDecodeError) as e:
            return _txt(f"recusado: {e}")

    @tool("fechar", "Fecha um bloco pelo id, ou 'todos'. Quem abriu fecha: nunca peça ao João para fechar na mão.", {"id": str})
    async def fechar(args):
        ids = g.fechar(str(args.get("id") or ""), motivo="modelo")
        return _txt(f"fechei: {', '.join(ids)}" if ids else "nada fechado (id não está aberto)")

    @tool("listar", "Blocos abertos agora, superfícies conectadas, modelos e fontes disponíveis.", {})
    async def listar(args):
        return _txt({"abertos": [{"id": b.id, "titulo": b.titulo, "tipo": b.tipo, "fonte": b.fonte} for b in g.listar()],
                     "superficies": [{"perfil": s.perfil, "nome": s.nome} for s in g.sessoes.values()],
                     "modelos": modelos.nomes(), "fontes": fontes.listar(), "layouts": list(g.layouts())})

    @tool("layout", "Salva o que está aberto como layout com nome (acao=salvar) ou reabre um layout (acao=abrir).",
          {"acao": str, "nome": str})
    async def layout(args):
        nome = str(args.get("nome") or "").strip()
        if not nome:
            return _txt("faltou o nome")
        try:
            if args.get("acao") == "abrir":
                return _txt(f"layout {nome}: {len(g.abrir_layout(nome))} blocos abertos")
            return _txt(f"layout {nome} salvo com {g.salvar_layout(nome)} blocos")
        except (KeyError, RuntimeError) as e:
            return _txt(str(e))

    @tool("criar_modelo", "Transforma um bloco útil em MODELO reutilizável (\"sempre que eu pedir X, mostre assim\"). "
                          "bloco_json no mesmo formato de `abrir`. Só grava se passar no contrato (renderiza em todas as "
                          "superfícies, tem resumo falado, sem conteúdo privado estático). Versões anteriores ficam guardadas.",
          {"nome": str, "bloco_json": str, "motivo": str})
    async def criar_modelo(args):
        try:
            ok, msg = modelos.salvar(str(args.get("nome") or ""), json.loads(args.get("bloco_json") or "{}"),
                                     autor="jaime", motivo=str(args.get("motivo") or ""))
        except json.JSONDecodeError as e:
            ok, msg = False, f"json inválido: {e}"
        return _txt(msg)

    @tool("ler", "Lê em voz o resumo de um bloco aberto (superfície de voz/falante).", {"id": str})
    async def ler(args):
        return _txt(g.ler(str(args.get("id") or "")) or "bloco não está aberto")

    return create_sdk_mcp_server(name="blocos", version="1.0.0",
                                 tools=[abrir, atualizar, fechar, listar, layout, criar_modelo, ler])
