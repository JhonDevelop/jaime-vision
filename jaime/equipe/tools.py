"""Ferramentas MCP `equipe`: o J.A.I.M.E cria filhos (terminais no Maestri), delega, acompanha e dispensa."""
from __future__ import annotations
from claude_agent_sdk import tool, create_sdk_mcp_server

def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}

def build_equipe_server(equipe):
    @tool("equipe_listar", "Seus filhos (terminais no Maestri): nome, tipo, preset, estado, missão e último relatório. Também diz se o Maestri está disponível.", {})
    async def equipe_listar(args):
        try:
            canvas = equipe.maestri.listar() if equipe.maestri.disponivel else "(Maestri indisponível: app fechado ou sem terminal Maestro)"
        except Exception as e:
            canvas = f"(maestri list falhou: {e})"
        return _txt(equipe.resumo() + "\n\nCanvas:\n" + canvas)

    @tool("criar_filho", "Cria um filho: um terminal novo no Maestri com papel, missão e pasta próprios, para trabalhar em paralelo a você. "
                         "tipo: codigo (worktree isolado do Jaime, branch jaime/<slug>) | pesquisa (laboratório) | mvp (projeto novo em JAIME_WORKSPACE) | operacao (mão de obra numa pasta). "
                         "preset: claude (Claude Code) | codex (OpenAI Codex) | opencode | shell. projeto: pasta explícita (opcional). "
                         "Use quando a tarefa for grande, paralelizável, demorada (> 15 min), precisar de isolamento, ou for um sistema/experimento à parte. "
                         "Limite JAIME_FILHOS_MAX vivos. Registre no diário o porquê.",
          {"nome": str, "missao": str, "tipo": str, "preset": str, "projeto": str, "papel_extra": str})
    async def criar_filho(args):
        try:
            f = equipe.criar(args.get("nome", "").strip() or "Filho", args.get("missao", ""), args.get("tipo") or "codigo",
                             args.get("preset") or "claude", args.get("projeto") or "", args.get("papel_extra") or "")
        except Exception as e:
            return _txt(f"não consegui criar o filho: {e}")
        return _txt(f"Filho {f.nome} criado ({f.tipo}, {f.preset}) em {f.pasta}. Dê alguns segundos e use delegar para a primeira tarefa.")

    @tool("delegar", "Manda uma tarefa a um filho. esperar_s > 0 espera a resposta (até esse tempo); 0 dispara e volta — o relatório chega pela nota equipe-relatorios.",
          {"nome": str, "tarefa": str, "esperar_s": float})
    async def delegar(args):
        try:
            import asyncio
            r = await asyncio.to_thread(equipe.delegar, args.get("nome", ""), args.get("tarefa", ""), float(args.get("esperar_s") or 0))
        except Exception as e:
            return _txt(f"não consegui delegar: {e}")
        return _txt(r[:4000])

    @tool("checar_filho", "Olha o terminal de um filho agora (últimas linhas) e os relatórios novos da nota compartilhada.", {"nome": str})
    async def checar_filho(args):
        try:
            import asyncio
            novos = await asyncio.to_thread(equipe.ler_relatorios)
            tela = await asyncio.to_thread(equipe.checar, args.get("nome", ""))
        except Exception as e:
            return _txt(f"não consegui checar: {e}")
        rel = "\n".join(f"- {n}: {t[:200]}" for n, t in novos) or "(sem relatório novo)"
        return _txt(f"Relatórios novos:\n{rel}\n\nTerminal de {args.get('nome')}:\n{tela}")

    @tool("dispensar_filho", "Encerra o terminal de um filho (a pasta e a branch ficam). Ação do Vigia: pede 'sim' ao João.", {"nome": str, "motivo": str})
    async def dispensar_filho(args):
        try:
            return _txt(equipe.dispensar(args.get("nome", ""), args.get("motivo", "")))
        except Exception as e:
            return _txt(f"não consegui dispensar: {e}")

    return create_sdk_mcp_server(name="equipe", version="1.0.0", tools=[equipe_listar, criar_filho, delegar, checar_filho, dispensar_filho])
