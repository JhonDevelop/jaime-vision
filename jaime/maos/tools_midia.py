"""Ferramentas MCP `midia` (imagens, 3D, vídeo) e `tela` (computer use)."""
from __future__ import annotations
from pathlib import Path
from claude_agent_sdk import tool, create_sdk_mcp_server
from .imagens import Imagens
from . import blender, conteudo, computador

def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}

def build_midia_server(imagens: Imagens, deepgram_key: str):
    @tool("gerar_imagem", "Gera uma imagem (gpt-image-2.5) e salva em ~/Jaime/imagens. formato: quadrada | paisagem | retrato | thumbnail. Leia o PNG com Read para ver.",
          {"prompt": str, "formato": str})
    async def gerar_imagem(args):
        if not imagens.disponivel:
            return _txt("OPENAI_API_KEY ausente.")
        try:
            import asyncio
            p = await asyncio.to_thread(imagens.gerar, args["prompt"], args.get("formato") or "quadrada")
            return _txt(f"Imagem em {p}")
        except Exception as e:
            return _txt(f"falhou: {e}")

    @tool("editar_imagem", "Edita uma imagem existente com um prompt (gpt-image-2.5).", {"caminho": str, "prompt": str})
    async def editar_imagem(args):
        if not imagens.disponivel:
            return _txt("OPENAI_API_KEY ausente.")
        try:
            import asyncio
            p = await asyncio.to_thread(imagens.editar, Path(args["caminho"]), args["prompt"])
            return _txt(f"Imagem editada em {p}")
        except Exception as e:
            return _txt(f"falhou: {e}")

    @tool("gerar_3d", "Gera um .blend via Blender headless a partir de código bpy que cria a cena (objetos, materiais, câmera, luz). Sem Blender instalado, salva o script e explica.",
          {"nome": str, "codigo_bpy": str})
    async def gerar_3d(args):
        import asyncio
        r = await asyncio.to_thread(blender.gerar_blend, args["nome"], args["codigo_bpy"])
        return _txt(f".blend em {r['blend']} (script {r['script']})" if r["ok"] else f"não gerei: {r['erro']} · script salvo em {r['script']}")

    @tool("cortar_video", "Corta um vídeo entre inicio e fim ('mm:ss' ou segundos) com ffmpeg; salva em ~/Jaime/conteudo.", {"video": str, "inicio": str, "fim": str})
    async def cortar_video(args):
        try:
            import asyncio
            p = await asyncio.to_thread(conteudo.cortar, Path(args["video"]), args["inicio"], args["fim"])
            return _txt(f"Corte em {p}")
        except Exception as e:
            return _txt(f"falhou: {e}")

    @tool("legendar_video", "Gera legenda .srt (Deepgram, pt-BR) para um vídeo.", {"video": str})
    async def legendar_video(args):
        if not deepgram_key:
            return _txt("DEEPGRAM_API_KEY ausente.")
        try:
            p = await conteudo.legendar(Path(args["video"]), deepgram_key)
            return _txt(f"Legenda em {p}")
        except Exception as e:
            return _txt(f"falhou: {e}")

    return create_sdk_mcp_server(name="midia", version="1.0.0", tools=[gerar_imagem, editar_imagem, gerar_3d, cortar_video, legendar_video])

def build_tela_server():
    @tool("tela_capturar", "Captura a tela inteira em ~/Jaime/capturas/tela.png (leia com Read para VER). Livre.", {})
    async def tela_capturar(args):
        try:
            return _txt(str(computador.capturar()) + f" · tamanho lógico {computador.tamanho()}")
        except Exception as e:
            return _txt(f"falhou: {type(e).__name__}: {e} — macOS pede Gravação de Tela/Acessibilidade para o Terminal")

    @tool("tela_clicar", "Clica em (x, y) da tela. Ação do Vigia: só com 'confirmo'. Capture antes para saber onde.", {"x": int, "y": int, "duplo": bool})
    async def tela_clicar(args):
        try:
            r = computador.clicar(int(args["x"]), int(args["y"]), duplo=bool(args.get("duplo"))); computador.capturar(); return _txt(r)
        except Exception as e:
            return _txt(f"falhou: {type(e).__name__}: {e}")

    @tool("tela_digitar", "Digita texto no app em foco. Ação do Vigia: só com 'confirmo'. Nunca senhas.", {"texto": str})
    async def tela_digitar(args):
        try:
            r = computador.digitar(args["texto"]); computador.capturar(); return _txt(r)
        except Exception as e:
            return _txt(f"falhou: {type(e).__name__}: {e}")

    @tool("tela_tecla", "Pressiona tecla/atalho ('enter', 'esc', 'cmd+s'). Ação do Vigia: só com 'confirmo'.", {"combo": str})
    async def tela_tecla(args):
        try:
            r = computador.tecla(args["combo"]); computador.capturar(); return _txt(r)
        except Exception as e:
            return _txt(f"falhou: {type(e).__name__}: {e}")

    return create_sdk_mcp_server(name="tela", version="1.0.0", tools=[tela_capturar, tela_clicar, tela_digitar, tela_tecla])
