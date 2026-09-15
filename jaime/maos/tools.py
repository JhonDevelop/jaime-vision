"""Ferramentas MCP `maos`: browser (abrir, ler_pagina, clicar, preencher, extrair, screenshot), projetos e arquivos."""
from __future__ import annotations
from pathlib import Path
from claude_agent_sdk import tool, create_sdk_mcp_server
from .browser import Navegador
from .projetos import criar_projeto as _criar_projeto
from . import arquivos as arq

def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}

def build_maos_server(vault, workspace: Path, navegador: Navegador | None = None):
    nav = navegador or Navegador()

    @tool("abrir", "Abre uma URL no browser do Jaime (janela própria, logins ficam salvos).", {"url": str})
    async def abrir(args):
        try: return _txt(await nav.abrir(args["url"]))
        except Exception as e: return _txt(f"falhou: {type(e).__name__}: {str(e)[:160]}")

    @tool("ler_pagina", "Texto visível da página atual (até 12 mil caracteres).", {})
    async def ler_pagina(args):
        try: return _txt(await nav.ler_pagina())
        except Exception as e: return _txt(f"falhou: {type(e).__name__}: {str(e)[:160]}")

    @tool("clicar", "Clica num elemento: seletor CSS ou texto visível. Enviar/comprar/pagar/confirmar passam pelo Vigia.", {"alvo": str})
    async def clicar(args):
        try: return _txt(await nav.clicar(args["alvo"]))
        except Exception as e: return _txt(f"falhou: {type(e).__name__}: {str(e)[:160]}")

    @tool("preencher", "Preenche um campo (seletor CSS, label ou placeholder). Nunca senhas nem cartão — peça ao João.", {"seletor": str, "texto": str})
    async def preencher(args):
        try: return _txt(await nav.preencher(args["seletor"], args["texto"]))
        except Exception as e: return _txt(f"falhou: {type(e).__name__}: {str(e)[:160]}")

    @tool("extrair", "Textos de todos os elementos que casam com o seletor CSS (tabelas, listas, preços).", {"seletor": str})
    async def extrair(args):
        try:
            itens = await nav.extrair(args["seletor"])
            return _txt("\n".join(f"- {i}" for i in itens) if itens else "nada encontrado")
        except Exception as e: return _txt(f"falhou: {type(e).__name__}: {str(e)[:160]}")

    @tool("screenshot", "Captura a página atual em ~/Jaime/capturas/<nome>.png (leia com Read para ver).", {"nome": str})
    async def screenshot(args):
        try: return _txt(await nav.screenshot(args.get("nome") or "pagina"))
        except Exception as e: return _txt(f"falhou: {type(e).__name__}: {str(e)[:160]}")

    @tool("criar_projeto", "Cria um projeto em JAIME_WORKSPACE: pasta, git init, README, .env.example, CLAUDE.md e nota em 20-Projetos/. tipo: python | node | generico",
          {"nome": str, "tipo": str, "descricao": str})
    async def criar_projeto(args):
        r = _criar_projeto(args["nome"], args.get("tipo") or "generico", workspace, vault, args.get("descricao", ""))
        return _txt(f"Projeto criado em {r['pasta']} (git {'ok' if r['git'] else 'falhou'}); nota {r['nota']}." if r["ok"] else f"Não criei: {r['erro']}")

    @tool("organizar_arquivos", "Propõe mover os arquivos de uma pasta segundo as regras de 10-Eu/Jeito.md (seção Arquivos). Só propõe.", {"pasta": str})
    async def organizar_arquivos(args):
        plano = arq.planejar(Path(args.get("pasta") or "~/Downloads"), arq.regras(vault.read("10-Eu/Jeito.md")))
        return _txt(arq.texto_plano(plano))

    @tool("mover", "Move/renomeia um arquivo (ação do Vigia: só executa após 'confirmo').", {"origem": str, "destino": str})
    async def mover(args):
        return _txt(arq.mover(Path(args["origem"]), Path(args["destino"])))

    return create_sdk_mcp_server(name="maos", version="1.0.0",
                                 tools=[abrir, ler_pagina, clicar, preencher, extrair, screenshot, criar_projeto, organizar_arquivos, mover])
