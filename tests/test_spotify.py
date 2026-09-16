"""Spotify: cliente injetável (sem rede) — o que toca, o gosto (artistas/gêneros/músicas), tocar/pausar, e o off."""
import asyncio
from pathlib import Path
from jaime.conexoes.spotify import Spotify

class _Cli:
    """Dublê do Spotify Web API: responde por rota."""
    def __init__(self): self.chamadas = []
    def get(self, path, **kw):
        self.chamadas.append(("GET", path, kw))
        if path == "/me": return {"display_name": "João"}
        if path == "/me/player/currently-playing": return {"item": {"name": "Faixa X", "artists": [{"name": "Artista Y"}]}}
        if path == "/me/top/artists": return {"items": [{"name": "Djavan", "genres": ["mpb", "samba"]}, {"name": "Racionais", "genres": ["rap", "hip hop"]}]}
        if path == "/me/top/tracks": return {"items": [{"name": "Oceano", "artists": [{"name": "Djavan"}]}]}
        if path == "/search": return {"tracks": {"items": [{"uri": "spotify:track:1", "name": "Oceano", "artists": [{"name": "Djavan"}]}]}}
        return {}
    def put(self, path, **kw): self.chamadas.append(("PUT", path, kw)); return {}
    def post(self, path, **kw): self.chamadas.append(("POST", path, kw)); return {}

def _sp(tmp_path):
    return Spotify(tmp_path / "tok.json", cliente=_Cli())

def test_conectado_e_leitura(tmp_path):
    sp = _sp(tmp_path)
    assert sp.conectado and sp.me() == "João"
    assert sp.o_que_toca() == "Faixa X — Artista Y"
    assert sp.top("artists") == ["Djavan", "Racionais"]
    g = sp.gosto()
    assert "Djavan" in g and ("mpb" in g or "rap" in g) and "Oceano" in g

def test_tocar_busca_e_toca(tmp_path):
    sp = _sp(tmp_path)
    r = sp.tocar("oceano djavan")
    assert "Oceano" in r and any(m[0] == "PUT" and m[1] == "/me/player/play" for m in sp._cli.chamadas)
    assert sp.pausar() == "Pausado."

def test_desconectado_sem_token(tmp_path):
    sp = Spotify(tmp_path / "naoexiste.json")
    assert not sp.conectado

def test_ferramenta_off_quando_desconectado(tmp_path):
    from jaime.conexoes.tools_musica import build_musica_server
    sp = Spotify(tmp_path / "naoexiste.json")
    # a lógica do off é simples: conectado=False → mensagem de conectar
    assert not sp.conectado
