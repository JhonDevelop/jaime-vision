"""Ferramentas MCP `musica`: o J.A.I.M.E toca no Spotify e conhece o gosto do João."""
from __future__ import annotations
from claude_agent_sdk import tool, create_sdk_mcp_server

def _txt(s): return {"content": [{"type": "text", "text": s}]}

def build_musica_server(spotify):
    def _off():
        return _txt("O Spotify ainda não está conectado. O João conecta com: python -m jaime conectar spotify (precisa de "
                    "SPOTIFY_CLIENT_ID/SECRET no .env, de um app em developer.spotify.com).")

    @tool("tocar", "Toca uma música/artista no Spotify do João (precisa Premium e um aparelho ativo). Vazio = retoma.", {"o_que": str})
    async def tocar(args):
        if not spotify.conectado: return _off()
        try: return _txt(spotify.tocar(args.get("o_que", "").strip()))
        except Exception as e: return _txt(f"não consegui tocar: {type(e).__name__} (tem um aparelho aberto e Premium?)")

    @tool("pausar_musica", "Pausa o que está tocando no Spotify.", {})
    async def pausar_musica(args):
        if not spotify.conectado: return _off()
        try: return _txt(spotify.pausar())
        except Exception as e: return _txt(f"não consegui: {type(e).__name__}")

    @tool("o_que_toca", "O que está tocando agora no Spotify do João.", {})
    async def o_que_toca(args):
        if not spotify.conectado: return _off()
        try: return _txt(spotify.o_que_toca())
        except Exception as e: return _txt(f"não consegui ler: {type(e).__name__}")

    @tool("meu_gosto", "O gosto musical do João: artistas, gêneros e músicas do momento (para recomendar e conversar).", {})
    async def meu_gosto(args):
        if not spotify.conectado: return _off()
        try: return _txt(spotify.gosto())
        except Exception as e: return _txt(f"não consegui ler o gosto: {type(e).__name__}")

    return create_sdk_mcp_server(name="musica", version="1.0.0", tools=[tocar, pausar_musica, o_que_toca, meu_gosto])
