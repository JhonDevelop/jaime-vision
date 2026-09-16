"""Finanças pessoais: parse de valor, categorização, registro no CSV, resumo (saldo/categoria/mês) e a ferramenta."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from jaime.brain.vault import Vault
from jaime.financas.livro import Livro, _num

def _vault(tmp_path):
    for d in ("70-Financas", "40-Diario"):
        (tmp_path / d).mkdir(exist_ok=True)
    return Vault(tmp_path)

def test_num_parse():
    assert _num("R$ 50") == 50.0 and _num("1.234,56") == 1234.56 and _num("2 mil") == 2000.0 and _num("120,50") == 120.5

def test_registrar_categoriza_e_soma(tmp_path):
    l = Livro(_vault(tmp_path))
    l.registrar("R$ 50", "", "gasolina no posto")           # adivinha combustível, saída
    l.registrar("2 mil", "salário", "salário do mês", "entrada")
    l.registrar("120,50", "mercado", "compras")
    r = l.resumo()
    assert r["entradas"] == 2000.0 and r["saidas"] == 170.5 and r["saldo"] == 1829.5 and r["lancamentos"] == 3
    assert r["por_categoria"][0] == ["mercado", 120.5] and ["combustível", 50.0] in r["por_categoria"]
    assert r["por_mes"] and len(r["ultimos"]) == 3
    # persistiu no CSV do vault
    l2 = Livro(_vault(tmp_path))
    assert l2.resumo()["lancamentos"] == 3
    assert "combustível" in l.texto_resumo()

def test_adivinha_entrada_por_categoria(tmp_path):
    l = Livro(_vault(tmp_path))
    assert l.registrar("500", "vendas", "vendi 10 kits").tipo == "entrada"
    assert l.registrar("30", "", "ifood").categoria == "alimentação" and l.registrar("30", "", "ifood").tipo == "saída"

def test_ferramenta_registra_e_resume(tmp_path):
    from jaime.financas.tools import build_financas_server  # noqa
    l = Livro(_vault(tmp_path))
    # exercita a lógica direto (o server MCP é só o invólucro)
    l.registrar("spotify 21,90", "", "spotify")
    assert l.resumo()["por_categoria"][0][0] == "assinaturas"
