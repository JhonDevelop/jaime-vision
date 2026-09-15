"""Ferramentas MCP `casa`: casa_estado, casa_ligar, casa_desligar, casa_servico, camera_ver."""
from __future__ import annotations
from claude_agent_sdk import tool, create_sdk_mcp_server
from .homeassistant import Casa, texto_estados
from . import camera as cam

def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}

def build_casa_server(casa: Casa, camera_padrao: str):
    def _ok():
        return "" if casa.ativa else "Home Assistant não configurado (HA_URL e HA_TOKEN no .env; docs/CONEXOES.md)."

    @tool("casa_estado", "Estado dos dispositivos da casa (Home Assistant). filtro opcional: 'escritório', 'luz', 'temperatura'.", {"filtro": str})
    async def casa_estado(args):
        if (e := _ok()): return _txt(e)
        try: return _txt(texto_estados(await casa.estados(args.get("filtro", ""))))
        except Exception as ex: return _txt(f"HA falhou: {type(ex).__name__}: {str(ex)[:120]}")

    @tool("casa_ligar", "Liga um dispositivo pelo nome ('luz do escritório', 'ventilador da sala').", {"nome": str})
    async def casa_ligar(args):
        if (e := _ok()): return _txt(e)
        try: return _txt(await casa.ligar(args["nome"]))
        except Exception as ex: return _txt(f"HA falhou: {type(ex).__name__}: {str(ex)[:120]}")

    @tool("casa_desligar", "Desliga um dispositivo pelo nome.", {"nome": str})
    async def casa_desligar(args):
        if (e := _ok()): return _txt(e)
        try: return _txt(await casa.desligar(args["nome"]))
        except Exception as ex: return _txt(f"HA falhou: {type(ex).__name__}: {str(ex)[:120]}")

    @tool("casa_servico", "Chama um serviço do HA (dominio, acao, entity_id, dados JSON opcional). Fechaduras/portões passam pelo Vigia.",
          {"dominio": str, "acao": str, "entity_id": str, "dados": str})
    async def casa_servico(args):
        if (e := _ok()): return _txt(e)
        import json
        try:
            dados = json.loads(args.get("dados") or "{}")
            return _txt(await casa.servico(args["dominio"], args["acao"], args["entity_id"], dados))
        except Exception as ex: return _txt(f"HA falhou: {type(ex).__name__}: {str(ex)[:120]}")

    @tool("camera_ver", "Tira um quadro da câmera (webcam do Mac por padrão, ou camera.xxx do HA) e devolve o caminho do PNG — leia com Read para descrever.", {"camera": str})
    async def camera_ver(args):
        try:
            p = await cam.quadro(casa, args.get("camera") or camera_padrao)
            return _txt(f"Quadro em {p}. Use Read nele e descreva o que vê.")
        except Exception as ex: return _txt(f"câmera falhou: {type(ex).__name__}: {str(ex)[:160]} — macOS pede permissão de Câmera para o Terminal")

    return create_sdk_mcp_server(name="casa", version="1.0.0", tools=[casa_estado, casa_ligar, casa_desligar, casa_servico, camera_ver])
