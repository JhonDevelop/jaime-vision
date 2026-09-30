"""Clientes não-web dos blocos: terminal e janela nativa (a parte que não precisa de tela)."""
from jaime.blocos.clientes.janela import LARGURA, barras, geometria
from jaime.blocos.clientes.terminal import caixa, tela


def test_caixa_do_terminal_tem_bordas_alinhadas():
    ls = caixa({"titulo": "Hoje", "linhas": ["a", "b" * 300], "id": "h", "fonte": "x"}, 50, cores=False)
    larguras = {len(l.split("  h")[0]) for l in ls}
    assert len(larguras) == 1 and "ao vivo" in ls[0]


def test_tela_vazia_convida_a_abrir_por_voz():
    assert "abre o bloco" in tela({}, 80, cores=False)


def test_janela_respeita_ancoragem_ou_empilha_a_direita():
    assert geometria(0, {"ancoragem": {"x": 0.5, "y": 0.25}}, 1000, 800) == (500, 200)
    x0, y0 = geometria(0, {}, 1440, 900)
    x1, y1 = geometria(1, {}, 1440, 900)
    assert x0 == x1 == 1440 - (LARGURA + 24) and y1 > y0
    assert geometria(4, {}, 1440, 900)[0] < x0                            # quinta janela abre outra coluna


def test_barras_com_negativos_e_series():
    r = barras([{"pontos": [{"y": 10}, {"y": -5}]}, {"pontos": [{"y": 5}, {"y": 0}]}], 200, 100)
    assert len(r) == 4 and all(y0 <= y1 for _, y0, _, y1, _ in r)
    assert barras([], 200, 100) == []
