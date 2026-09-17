"""Ler páginas difíceis com o Scrapling. O que não pode cair são as travas: só http/https, nada de
localhost, nada de URL carregando credencial, e recusa clara quando o site pede login."""
import asyncio
import pytest
from jaime.maos.raspar import _url_ok, _limpar, ler, extrair, tabela, build_raspar_server

@pytest.mark.parametrize("url,ok", [
    ("https://example.com", True), ("http://example.com/a?b=1", True), ("example.com", True),
    ("", False), ("file:///etc/passwd", False), ("ftp://x.com", False),
    ("http://localhost:8787/hud/estado", False), ("https://127.0.0.1/x", False),
    ("https://meu-mac.local/x", False), ("https://x.com/a?token=abc123", False),
    ("https://x.com/a?senha=123", False), ("https://x.com/a?api_key=k", False),
])
def test_so_passa_url_publica_e_sem_segredo(url, ok):
    assert (_url_ok(url) == "") is ok

def test_o_motivo_da_recusa_e_dito_em_portugues():
    assert "própria máquina" in _url_ok("http://localhost:1/x")
    assert "credencial" in _url_ok("https://x.com?token=1")
    assert "http e https" in _url_ok("ftp://x.com")

def test_limpa_espaco_e_linha_repetida():
    assert _limpar("a\n\n\n\nb   c\t\td ") == "a\n\nb c d"

def test_as_tres_ferramentas_existem_no_servidor():
    srv = build_raspar_server()
    assert srv["name"] == "web" and srv["type"] and srv["instance"]

def test_pagina_com_login_vira_recado_e_nao_tentativa_de_burlar(monkeypatch):
    """403 não é convite para achar a volta: é para avisar o João."""
    import jaime.maos.raspar as R
    class _P:
        status = 403
        def get_all_text(self): return "acesso negado"
    monkeypatch.setattr(R, "_pagina", lambda u: _P())
    t = R.ler("https://x.com")
    assert "403" in t and "login" in t and "com o João" in t

def test_pagina_boa_volta_com_texto_limpo(monkeypatch):
    import jaime.maos.raspar as R
    class _P:
        status = 200
        def get_all_text(self): return "Título\n\n\n\nCorpo   com    espaço"
    monkeypatch.setattr(R, "_pagina", lambda u: _P())
    t = R.ler("https://x.com")
    assert t.startswith("[200] https://x.com") and "Corpo com espaço" in t

def test_extrair_e_tabela_recusam_url_ruim_antes_de_qualquer_rede():
    assert "própria máquina" in extrair("http://localhost/x", "h1")
    assert "credencial" in tabela("https://x.com?token=1", 0)
    assert "seletor" in extrair("https://x.com", "")

def test_tabela_pede_indice_que_existe(monkeypatch):
    import jaime.maos.raspar as R
    class _P:
        status = 200
        def css(self, s): return []
    monkeypatch.setattr(R, "_pagina", lambda u: _P())
    assert "não há tabela" in R.tabela("https://x.com", 0)
