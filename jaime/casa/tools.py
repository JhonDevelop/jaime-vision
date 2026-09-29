"""Ferramentas MCP `casa`: casa_estado, casa_ligar, casa_desligar, casa_servico, camera_ver — e a Alexa como mãos e
boca do Jaime na casa (alexa_falar, alexa_comando, alexa_tocar, alexa_parar, alexa_volume, alexa_echos), presença
por Bluetooth e a saída de áudio. Destrancar, abrir portão, desarmar, comprar, ligar para alguém: lote do Vigia
(casa/seguranca.py)."""
from __future__ import annotations
from claude_agent_sdk import tool, create_sdk_mcp_server
from .homeassistant import Casa, texto_estados
from . import camera as cam
from .seguranca import liberado, motivo_alexa, motivo_servico

def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}

def build_casa_server(casa: Casa, camera_padrao: str, vigia=None, alexa=None, presenca=None):
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
            if (motivo := motivo_servico(args["dominio"], args["acao"], args["entity_id"])):
                ok, msg = liberado(vigia, "mcp__casa__casa_servico", {"alvo": args["entity_id"], "acao": args["acao"]},
                                   f"{motivo} ({args['entity_id']})")
                if not ok:
                    return _txt(msg)
            return _txt(await casa.servico(args["dominio"], args["acao"], args["entity_id"], dados))
        except Exception as ex: return _txt(f"HA falhou: {type(ex).__name__}: {str(ex)[:120]}")

    @tool("camera_ver", "Tira um quadro da câmera (webcam do Mac por padrão, ou camera.xxx do HA) e devolve o caminho do PNG — leia com Read para descrever.", {"camera": str})
    async def camera_ver(args):
        try:
            p = await cam.quadro(casa, args.get("camera") or camera_padrao)
            return _txt(f"Quadro em {p}. Use Read nele e descreva o que vê.")
        except Exception as ex: return _txt(f"câmera falhou: {type(ex).__name__}: {str(ex)[:160]} — macOS pede permissão de Câmera para o Terminal")

    ferramentas = [casa_estado, casa_ligar, casa_desligar, casa_servico, camera_ver]

    if alexa is not None:
        async def _alexa(coro):
            if (e := _ok()):
                return _txt(e)
            try:
                return _txt(await coro)
            except Exception as ex:
                return _txt(f"Alexa/HA falhou: {type(ex).__name__}: {str(ex)[:140]}")

        @tool("alexa_echos", "Quais Echos existem (e onde), e qual integração liga a Alexa ao Home Assistant.", {})
        async def alexa_echos(args):
            async def f():
                await alexa.detectar(forcar=True)
                return str(alexa.estado())
            return await _alexa(f())

        @tool("alexa_falar", "A ALEXA fala um texto num Echo (voz dela). lugar: 'sala', 'quarto', 'todos' (vazio = padrão). "
                             "modo 'announce' toca o sininho e fala em todos do grupo (avisos para a casa). Para a SUA voz, use a "
                             "voz normal ou `saida_audio`.", {"texto": str, "lugar": str, "modo": str})
        async def alexa_falar(args):
            return await _alexa(alexa.falar(args.get("texto", ""), args.get("lugar", ""), args.get("modo") or "speak"))

        @tool("alexa_comando", "Manda à Alexa, por texto, QUALQUER coisa que se diria a ela em voz alta (em português): ligar "
                               "algo que só existe no app Alexa, rotina, timer, 'toca X no Spotify', volume, 'que horas são'. "
                               "Você é o chefe: decida e mande. Compras, ligações, mensagens, destrancar/abrir/desarmar passam pelo "
                               "Vigia (o João confirma com 'sim').", {"texto": str, "lugar": str})
        async def alexa_comando(args):
            texto = args.get("texto", "")
            if (motivo := motivo_alexa(texto)):
                ok, msg = liberado(vigia, "mcp__casa__alexa_comando", {"alvo": texto.strip().lower()[:120]},
                                   f"pedir à Alexa «{texto.strip()[:60]}» ({motivo})")
                if not ok:
                    return _txt(msg)
            return await _alexa(alexa.comando(texto, args.get("lugar", "")))

        @tool("alexa_tocar", "Toca música/playlist/rádio/podcast num Echo. servico opcional: 'Spotify', 'Amazon Music', 'Deezer'.",
              {"o_que": str, "lugar": str, "servico": str})
        async def alexa_tocar(args):
            return await _alexa(alexa.tocar(args.get("o_que", ""), args.get("lugar", ""), args.get("servico", "")))

        @tool("alexa_parar", "Para o que o Echo está tocando.", {"lugar": str})
        async def alexa_parar(args):
            return await _alexa(alexa.parar(args.get("lugar", "")))

        @tool("alexa_volume", "Volume do Echo (0-100).", {"nivel": int, "lugar": str})
        async def alexa_volume(args):
            return await _alexa(alexa.volume(int(args.get("nivel", 40)), args.get("lugar", "")))

        ferramentas += [alexa_echos, alexa_falar, alexa_comando, alexa_tocar, alexa_parar, alexa_volume]

    @tool("casa_presenca", "Quem está em casa pelos aparelhos Bluetooth cadastrados (presença não autoriza nada).", {})
    async def casa_presenca(args):
        if presenca is None:
            return _txt("presença por Bluetooth desligada (JAIME_BT=on + JAIME_BT_CONHECIDOS; docs/CASA.md)")
        return _txt(f"presentes: {', '.join(presenca.presentes) or 'ninguém detectado'}")

    @tool("saida_audio", "Faz a SUA voz (Jaime) sair por um Echo pareado por Bluetooth como caixa de som.", {"dispositivo": str})
    async def saida_audio(args):
        from .bluetooth import saida_de_audio
        return _txt(saida_de_audio(args.get("dispositivo") or "Echo"))

    ferramentas += [casa_presenca, saida_audio]
    return create_sdk_mcp_server(name="casa", version="1.1.0", tools=ferramentas)
