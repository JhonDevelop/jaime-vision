"""Grafo de relações: nós, arestas datadas, fato que muda vira histórico (nunca contradição), segredo filtrado,
quem_e resolve apelido, esquecer apaga de verdade só quando pedido, e a ferramenta MCP por cima disso tudo."""
import asyncio
import pytest
from jaime.relacoes.grafo import Relacoes, _seguro, _lista_apelidos


@pytest.fixture
def r(tmp_path):
    rel = Relacoes(tmp_path / "relacoes.db")
    yield rel
    rel.fechar()


# ── segredo filtrado ─────────────────────────────────────────────────────
def test_seguro_filtra_segredos_mas_deixa_numero_comum_passar():
    assert _seguro("a senha é 1234") == ""
    assert _seguro("cartão 1234 5678 9012 3456") == ""
    assert _seguro("CPF 123.456.789-00") == ""
    assert _seguro("token sk-abc123") == ""
    assert _seguro("salário R$ 2.500/mês") == "salário R$ 2.500/mês"
    assert _seguro("mora em Franca") == "mora em Franca"


def test_fato_com_segredo_nao_grava_nada(r):
    n = r.fato("Gabriel", "senha_wifi", "minha senha é 998877", tipo="pessoa")
    assert n == 0
    assert r.sobre("Gabriel") is None or r.sobre("Gabriel")["fatos"] == []


def test_ligar_com_segredo_no_detalhe_fica_vazio(r):
    r.ligar("João", "Banco X", "dono-de", detalhe="senha do cofre 445566")
    d = r.sobre("João")
    assert d["relacoes"][0]["detalhe"] == ""


# ── nós e apelidos ────────────────────────────────────────────────────────
def test_lembrar_pessoa_nao_duplica_e_funde_apelidos(r):
    id1 = r.lembrar_pessoa("Gabriel", "pessoa", apelidos=["Gabi"])
    id2 = r.lembrar_pessoa("Gabriel", "pessoa", apelidos=["Gabriel Santos"])
    assert id1 == id2
    d = r.sobre("Gabriel")
    assert "Gabi" in d["apelidos"] and "Gabriel Santos" in d["apelidos"]


def test_lista_apelidos_ignora_vazio_e_duplicata():
    assert _lista_apelidos("Gabi, gabi , , Gabriel Santos") == ["Gabi", "Gabriel Santos"]


# ── aresta datada e fato que muda vira histórico ───────────────────────────
def test_relacao_que_muda_vira_historico_nunca_contradicao(r):
    r.ligar("Gabriel", "BUB", "trabalha-em", detalhe="dev", desde="2024-01-01", evidencia="diário 2024",
           tipo_a="pessoa", tipo_b="organizacao")
    r.ligar("Gabriel", "BUB", "trabalha-em", detalhe="CTO", desde="2026-06-01", evidencia="diário 16/09")
    d = r.sobre("Gabriel")
    assert len(d["relacoes"]) == 1 and d["relacoes"][0]["detalhe"] == "CTO" and d["relacoes"][0]["ate"] is None
    assert len(d["relacoes_historico"]) == 1
    velho = d["relacoes_historico"][0]
    assert velho["detalhe"] == "dev" and velho["ate"] == "2026-06-01"   # fechado, não apagado


def test_relacao_repetida_soma_evidencia_sem_duplicar(r):
    r.ligar("Diego", "Oldsen", "sociedade", detalhe="sócio", evidencia="conversa 1")
    r.ligar("Diego", "Oldsen", "sociedade", detalhe="sócio", evidencia="conversa 2")
    d = r.sobre("Diego")
    assert len(d["relacoes"]) == 1
    assert d["relacoes"][0]["vezes"] == 2
    assert "conversa 1" in d["relacoes"][0]["evidencia"] and "conversa 2" in d["relacoes"][0]["evidencia"]


def test_fato_solto_que_muda_vira_historico(r):
    r.fato("Gabriel", "cargo", "desenvolvedor", desde="2024-01-01")
    r.fato("Gabriel", "cargo", "CTO", desde="2026-06-01")
    d = r.sobre("Gabriel")
    assert len(d["fatos"]) == 1 and d["fatos"][0]["valor"] == "CTO"
    assert len(d["fatos_historico"]) == 1 and d["fatos_historico"][0]["valor"] == "desenvolvedor"


# ── quem_e ─────────────────────────────────────────────────────────────
def test_quem_e_resolve_apelido_com_artigo(r):
    r.lembrar_pessoa("Rafael Souza", "pessoa", apelidos=["Rafa"])
    d = r.quem_e("o Rafael")
    assert d and d["nome"] == "Rafael Souza"
    d2 = r.quem_e("Rafa")
    assert d2 and d2["id"] == d["id"]


def test_quem_e_sem_match_devolve_none(r):
    assert r.quem_e("ninguém conhecido") is None


# ── esquecer ──────────────────────────────────────────────────────────
def test_esquecer_fato_especifico(r):
    r.fato("Gabriel", "carro", "aluga por R$ 3.600/mês")
    r.fato("Gabriel", "salario", "R$ 2.500/mês")
    n = r.esquecer("Gabriel", chave="carro")
    assert n == 1
    d = r.sobre("Gabriel")
    assert len(d["fatos"]) == 1 and d["fatos"][0]["chave"] == "salario"


def test_esquecer_relacao_especifica(r):
    r.ligar("Diego", "Oldsen", "sociedade")
    r.ligar("Diego", "Franca", "mora-em", tipo_b="lugar")
    n = r.esquecer("Diego", relacao="sociedade", com="Oldsen")
    assert n == 1
    d = r.sobre("Diego")
    assert len(d["relacoes"]) == 1 and d["relacoes"][0]["relacao"] == "mora-em"


def test_esquecer_no_inteiro_remove_tudo(r):
    r.ligar("Fulano", "Nada", "amizade")
    r.fato("Fulano", "apelido", "Fu")
    n = r.esquecer("Fulano")
    assert n >= 2
    assert r.sobre("Fulano") is None


def test_esquecer_quem_nao_existe(r):
    assert r.esquecer("Ninguém") == 0


# ── persistência (banco real em disco) ─────────────────────────────────
def test_persistencia_em_disco(tmp_path):
    caminho = tmp_path / "relacoes.db"
    r1 = Relacoes(caminho)
    r1.ligar("Maria Clara", "João", "amizade", detalhe="namorada")
    r1.fechar()
    r2 = Relacoes(caminho)
    d = r2.sobre("Maria Clara")
    assert d and d["relacoes"][0]["detalhe"] == "namorada"
    r2.fechar()


def test_caminho_padrao_usa_env(tmp_path, monkeypatch):
    monkeypatch.setenv("JAIME_RELACOES_DB", str(tmp_path / "sub" / "relacoes.db"))
    r = Relacoes()
    try:
        assert r.caminho == (tmp_path / "sub" / "relacoes.db")
        assert r.caminho.exists()
    finally:
        r.fechar()


# ── ferramenta MCP ──────────────────────────────────────────────────────
def test_ferramenta_lembrar_sobre_quem_e_esquecer(tmp_path):
    from jaime.relacoes.tools import build_relacoes_server  # noqa: garante que builda sem erro
    r = Relacoes(tmp_path / "relacoes.db")
    build_relacoes_server(r)   # exercita a construção do servidor MCP

    async def cenario():
        r.lembrar_pessoa("Gabriel", "pessoa", apelidos=["Gabi"], evidencia="Pessoas.md")
        r.ligar("Gabriel", "BUB", "sociedade", detalhe="sócio", tipo_b="organizacao")
        r.fato("Gabriel", "salario", "R$ 2.500/mês")
        return r.quem_e("o Gabi"), r.sobre("Gabriel")

    quem, sobre = asyncio.run(cenario())
    assert quem["nome"] == "Gabriel"
    assert sobre["relacoes"][0]["com"] == "BUB"
    assert sobre["fatos"][0]["valor"] == "R$ 2.500/mês"
    r.fechar()
