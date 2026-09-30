"""Fase 6 — Air Canvas (traços → formas sugeridas → grafo confirmado) e modo matemática sem eval."""
import math
import pytest
from jaime.spatial.canvas import Canvas, Traco, reconhecer
from jaime.spatial.core import SpatialCore
from jaime.spatial.matematica import ErroMatematica, analisar, resolver


def circulo(cx, cy, r, n=40, t0=0.0):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n), 0, t0 + i / 60, 0.95) for i in range(n + 1)]


def retangulo(x, y, w, h, t0=0.0):
    cantos = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
    pts = []
    for (a, b), (c, d) in zip(cantos, cantos[1:]):
        for k in range(10):
            pts.append((a + (c - a) * k / 10, b + (d - b) * k / 10, 0, t0 + len(pts) / 60, 0.95))
    pts.append((x, y, 0, t0 + len(pts) / 60, 0.95))
    return pts


def linha(a, b, n=20, t0=0.0):
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n, 0, t0 + i / 60, 0.95) for i in range(n + 1)]


def test_reconhece_circulo_retangulo_e_linha():
    assert reconhecer(Traco("c", circulo(0.5, 0.5, 0.08))).forma == "circulo"
    assert reconhecer(Traco("r", retangulo(0.2, 0.2, 0.2, 0.12))).forma == "retangulo"
    s = reconhecer(Traco("l", linha((0.1, 0.1), (0.6, 0.3))))
    assert s.forma == "linha" and s.de == pytest.approx((0.1, 0.1)) and s.para == pytest.approx((0.6, 0.3))


def test_fora_do_modo_desenho_nao_risca():
    c = Canvas(SpatialCore())
    for p in circulo(0.5, 0.5, 0.1):
        c.ponto(p[0], p[1], p[3])
    assert c.fechar_traco() is None and not c.tracos


def _desenhar(c, pts):
    for p in pts:
        c.ponto(p[0], p[1], p[3], p[4])
    return c.fechar_traco()


def test_quatro_nos_quatro_arestas_salvar_reabrir_e_mermaid(tmp_path):
    c = Canvas(SpatialCore()); c.ligar()
    nomes = {"App": (0.2, 0.3), "API": (0.5, 0.3), "Banco": (0.8, 0.3), "Fila": (0.5, 0.7)}
    for i, (nome, (x, y)) in enumerate(nomes.items()):
        s = _desenhar(c, retangulo(x - 0.06, y - 0.05, 0.12, 0.1) if i % 2 else circulo(x, y, 0.06))
        assert s.forma in ("circulo", "retangulo")
        c.confirmar_no(s.id, nome, "componente")
    ligacoes = [("App", "API", "chama"), ("API", "Banco", "lê/escreve"), ("API", "Fila", "publica"), ("Fila", "Banco", "grava")]
    for a, b, rel in ligacoes:
        pa, pb = nomes[a], nomes[b]
        s = _desenhar(c, linha(pa, pb))
        assert c.sugerir_aresta(s.id) == (f"no:{a.lower()}", f"no:{b.lower()}")
        c.confirmar_aresta(s.id, rel)
    ex = c.exportar()
    assert len(ex["nos"]) == 4 and len(ex["arestas"]) == 4
    assert all(e["evidence"].startswith("desenho:") and "confirmação:voz" in e["evidence"] for e in ex["arestas"])
    arq = c.salvar(tmp_path / "arq.json")
    c2 = Canvas.abrir(arq)
    assert c2.exportar()["arestas"] == ex["arestas"] and len(c2.tracos) == 8
    mm = c2.mermaid()
    assert mm.startswith("flowchart LR") and mm.count("-->") == 4 and '"Banco"' in mm
    assert "Premissas" in c2.para_raciocinio("isso aguenta 100 mil usuários?")


def test_linha_que_nao_liga_dois_nos_nao_vira_aresta_e_undo():
    c = Canvas(SpatialCore()); c.ligar()
    s = _desenhar(c, circulo(0.2, 0.2, 0.05)); c.confirmar_no(s.id, "A")
    s = _desenhar(c, linha((0.2, 0.2), (0.9, 0.9)))
    assert c.sugerir_aresta(s.id) is None
    with pytest.raises(ValueError):
        c.confirmar_aresta(s.id, "liga")
    assert "no:a" in c.core.objects
    c.desfazer(); c.desfazer()                           # tira o traço da linha e depois o nó
    assert "no:a" not in c.core.objects


# ── matemática ───────────────────────────────────────────────────────────────
def test_resolve_e_verifica_por_substituicao():
    r = resolver("2x + 3 = 11")
    assert r.resultado == ["x = 4"] and r.verificado and any("✓" in p for p in r.passos)
    r = resolver(r"x^{2} - 5x + 6 = 0")
    assert sorted(r.resultado) == ["x = 2", "x = 3"] and r.verificado


def test_latex_frac_sqrt_e_multiplicacao_implicita():
    r = resolver(r"\frac{x}{2} + \sqrt{16} = 10")
    assert r.resultado == ["x = 12"] and r.verificado
    r = resolver("3(2 + 4)")
    assert r.tipo == "expressao" and r.resultado == ["18"]


@pytest.mark.parametrize("malicioso", [
    "__import__('os').system('echo pwned')", "x.__class__", "open('/etc/passwd')", "lambda: 1", "x; import os",
    r"\input{/etc/passwd}", "[1,2]"])
def test_texto_reconhecido_nunca_vira_codigo(malicioso):
    with pytest.raises(ErroMatematica):
        analisar(malicioso)


def test_limites_de_tamanho_e_expoente():
    with pytest.raises(ErroMatematica):
        analisar("x+" * 100 + "1")
    with pytest.raises(ErroMatematica):
        analisar("2^1000")
