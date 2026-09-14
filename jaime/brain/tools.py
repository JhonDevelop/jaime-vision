"""Ferramentas do cérebro expostas ao Claude como servidor MCP in-process (`mcp__cerebro__*`)."""
from __future__ import annotations
from claude_agent_sdk import tool, create_sdk_mcp_server
from .vault import Vault
from .estado import Estado
from ..hud.events import bus

def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}

def build_cerebro_server(vault: Vault, estado: Estado | None = None):
    @tool("lembrar", "Salva um fato durável sobre o João ou um projeto numa nota do vault (append).",
          {"nota": str, "texto": str})
    async def lembrar(args):
        rel = args["nota"] if args["nota"].endswith(".md") else f"{args['nota']}.md"
        vault.append(rel, f"- {args['texto'].strip()}")
        return _txt(f"Guardado em {rel}")

    @tool("buscar_memoria", "Busca um termo em todas as notas do vault. Use antes de perguntar ao João algo que ele já pode ter dito.",
          {"termo": str})
    async def buscar_memoria(args):
        hits = vault.buscar(args["termo"])
        if not hits:
            return _txt("Nada encontrado.")
        return _txt("\n".join(f"{p}:{n}: {l}" for p, n, l in hits))

    @tool("ler_nota", "Lê uma nota do vault pelo caminho relativo (ex: 20-Projetos/BUB.md).", {"caminho": str})
    async def ler_nota(args):
        return _txt(vault.read(args["caminho"]) or "(nota vazia ou inexistente)")

    @tool("registrar_diario", "Registra uma linha no diário de hoje. secao: Feito | Decisões | Pendente | Log.",
          {"texto": str, "secao": str})
    async def registrar_diario(args):
        rel = vault.diario(args["texto"], args.get("secao") or "Log")
        return _txt(f"Registrado em {rel}")

    @tool("criar_tarefa", "Adiciona uma tarefa ao Inbox. projeto e prazo (AAAA-MM-DD) são opcionais.",
          {"descricao": str, "projeto": str, "prazo": str})
    async def criar_tarefa(args):
        return _txt(vault.tarefa(args["descricao"], args.get("projeto", ""), args.get("prazo", "")))

    @tool("tarefas_abertas", "Lista as tarefas abertas do Inbox.", {})
    async def tarefas_abertas(args):
        t = vault.tarefas_abertas()
        return _txt("\n".join(t) if t else "Inbox vazio.")

    @tool("ler_estado", "Lê o seu próprio Estado (fase, situação, andamento, próximos passos).", {})
    async def ler_estado(args):
        return _txt(estado.ler() if estado else vault.read("01-Estado/Estado.md"))

    @tool("atualizar_estado", "Reescreve UMA seção do seu Estado. secao: Fase | Situação agora | Em andamento | Próximos passos | Aprendizados recentes.",
          {"secao": str, "corpo": str})
    async def atualizar_estado(args):
        if not estado:
            return _txt("Estado indisponível.")
        estado.atualizar_secao(args["secao"], args["corpo"])
        return _txt(f"Seção '{args['secao']}' atualizada.")

    @tool("pedir_teclado", "Abre o teclado no HUD quando você precisa que o João DIGITE algo (senha, chave, URL, "
                           "texto longo). Fora isso a conversa é por voz. motivo: o que ele deve escrever.", {"motivo": str})
    async def pedir_teclado(args):
        bus.emitir("teclado", aberto=True, motivo=(args.get("motivo") or "")[:120])
        return _txt("Teclado aberto no HUD. Diga em uma frase o que ele deve digitar e espere.")

    return create_sdk_mcp_server(
        name="cerebro", version="1.2.0",
        tools=[lembrar, buscar_memoria, ler_nota, registrar_diario, criar_tarefa, tarefas_abertas,
               ler_estado, atualizar_estado, pedir_teclado],
    )
