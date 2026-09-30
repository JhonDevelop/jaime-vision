"""Ferramentas MCP `apps`: apps de criação (Photoshop, Premiere, Blender, Canva…) e o estúdio de holograma.

O cérebro pode pôr um holograma na tela, editá-lo, exportar e mandar ao fatiador com as mesmas funções da voz
(`jaime.jarvis`). Script de Photoshop que salva por cima, apaga ou roda comando do sistema passa pelo Vigia."""
from __future__ import annotations
import asyncio, json
from claude_agent_sdk import tool, create_sdk_mcp_server
from . import apps


def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}


async def _consumir(gen) -> str:
    return " ".join([f.strip() async for f in gen]) if gen is not None else ""


def build_apps_server(vigia, jaime):
    @tool("apps_instalados", "Quais apps de criação estão instalados nesta máquina (Photoshop, Premiere, Blender, Figma, fatiador…).", {})
    async def instalados(args):
        return _txt(", ".join(await asyncio.to_thread(apps.instalados)) or "nenhum dos apps conhecidos")

    @tool("app_abrir", "Abre um app (photoshop, premiere, illustrator, after effects, blender, davinci resolve, capcut, figma, canva, "
                       "whatsapp, mail, bambu studio), opcionalmente com um arquivo. Canva/Figma sem app abrem na web. Livre.",
          {"app": str, "arquivo": str})
    async def abrir(args):
        r = await asyncio.to_thread(apps.abrir, args.get("app", ""), args.get("arquivo", "") or "")
        return _txt(f"aberto ({r['como']})" if r["ok"] else r["erro"])

    @tool("photoshop_script", "Roda ExtendScript (.jsx) no Photoshop aberto: criar/editar documento, camadas, texto, filtros, exportar "
                              "para ~/Jaime. Salvar por cima, apagar arquivo ou fechar sem salvar passa pelo Vigia.",
          {"jsx": str, "descricao": str})
    async def photoshop(args):
        jsx = args.get("jsx", "")
        if apps.PERIGOSO_JSX.search(jsx):
            from ..casa.seguranca import liberado
            ok, msg = liberado(vigia, "photoshop_script", {"jsx": jsx}, f"rodar no Photoshop: {args.get('descricao') or 'script que salva/apaga'}")
            if not ok:
                return _txt(msg)
        r = await asyncio.to_thread(apps.photoshop_jsx, jsx)
        return _txt(f"ok: {r.get('saida', '')}" if r["ok"] else f"falhou: {r['erro']} (script em {r.get('script')})")

    @tool("premiere_sequencia", "Monta uma sequência do Premiere com cortes de vídeo, na ordem: clipes = JSON "
                                "[{\"caminho\": \"/…/a.mp4\", \"inicio\": 12.5, \"fim\": 20}] (segundos). Gera o XML e abre no Premiere.",
          {"nome": str, "clipes": str, "fps": int})
    async def premiere(args):
        try:
            clipes = json.loads(args.get("clipes") or "[]")
            xml = await asyncio.to_thread(apps.premiere_xml, args.get("nome") or "Sequência do Jaime", clipes, args.get("fps") or 30)
        except (ValueError, json.JSONDecodeError) as e:
            return _txt(f"clipes inválidos: {e}")
        r = await asyncio.to_thread(apps.abrir, "premiere", xml)
        return _txt(f"sequência em {xml}" + ("; aberta no Premiere" if r["ok"] else f"; {r['erro']}"))

    def _jarvis():
        return getattr(jaime, "jarvis", None)

    @tool("holograma", "Põe na tela Jarvis o holograma 3D de QUALQUER objeto (o João manipula com as mãos). Use quando ele quiser VER algo em 3D.",
          {"objeto": str})
    async def holograma(args):
        j = _jarvis()
        if j is None:
            return _txt("tela Jarvis desligada")
        j.garantir_tela()
        return _txt(await _consumir(j._holograma(args.get("objeto", "")[:80])))

    @tool("holograma_editar", "Altera o holograma aberto como o João pediu ('abre as portas', 'aumenta a antena').", {"pedido": str})
    async def editar(args):
        j = _jarvis()
        if j is None or not j.estudio.aberto:
            return _txt("não há holograma aberto")
        return _txt(await j.estudio.editar(args.get("pedido", ""), j.modelo_holo))

    @tool("holograma_exportar", "Salva o holograma aberto como arquivo 3D (formatos: lista entre stl, obj, glb); blender=true abre no Blender.",
          {"formatos": list, "blender": bool})
    async def exportar(args):
        j = _jarvis()
        if j is None or not (j.estudio.aberto or j.estudio.spec):
            return _txt("não há holograma aberto")
        fmts = [f for f in (args.get("formatos") or ["stl", "obj", "glb"]) if f in ("stl", "obj", "glb")] or ["glb"]
        return _txt(await _consumir(j._exportar(fmts, blender=bool(args.get("blender")))))

    @tool("holograma_imprimir", "Prepara o holograma aberto para impressão 3D (STL em mm, Z para cima) com a maior medida em mm, e abre no fatiador. "
                                "Não inicia a impressão.", {"maior_mm": float})
    async def imprimir(args):
        j = _jarvis()
        if j is None or not (j.estudio.aberto or j.estudio.spec):
            return _txt("não há holograma aberto")
        return _txt(await _consumir(j._imprimir(float(args.get("maior_mm") or 100))))

    return create_sdk_mcp_server(name="apps", version="1.0.0",
                                 tools=[instalados, abrir, photoshop, premiere, holograma, editar, exportar, imprimir])
