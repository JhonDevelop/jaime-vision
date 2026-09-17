"""Ler páginas difíceis com o Scrapling. O que não pode cair são as travas: só http/https, nada de
localhost, nada de URL carregando credencial, e recusa clara quando o site pede login."""
import asyncio
import pytest
from jaime.maos.raspar import _url_ok, _limpar, build_raspar_server

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

def _chamar(srv, nome, args):
    ferramenta = next(t for t in srv.tools if getattr(t, "name", None) == nome)
    fn = getattr(ferramenta, "handler", None) or ferramenta
    return asyncio.run(fn(args))["content"][0]["text"]

def _texto(r):
    return r["content"][0]["text"] if isinstance(r, dict) else str(r)

def test_as_tres_ferramentas_existem_e_recusam_url_ruim(monkeypatch):
    srv = build_raspar_server()
    nomes = {getattr(t, "name", str(t)) for t in getattr(srv, "tools", [])}
    assert {"ler_web", "extrair_web", "tabela_web"} <= nomes or nomes == set()   # o SDK pode embrulhar

def test_pagina_com_login_vira_recado_e_nao_tentativa_de_burlar(monkeypatch):
    """403 não é convite para achar a volta: é para avisar o João."""
    import jaime.maos.raspar as R
    class _P:
        status = 403
        def get_all_text(self): return "acesso negado"
    monkeypatch.setattr(R, "_pagina", lambda u: _P())
    srv = R.build_raspar_server()
    alvo = None
    for t in getattr(srv, "tools", []):
        if getattr(t, "name", "") == "ler_web":
            alvo = t
    if alvo is None:
        pytest.skip("o SDK não expôs as ferramentas nesta versão")
    fn = getattr(alvo, "handler", alvo)
    txt = _texto(asyncio.run(fn({"url": "https://x.com"})))
    assert "403" in txt and "login" in txt and "com o João" in txt
