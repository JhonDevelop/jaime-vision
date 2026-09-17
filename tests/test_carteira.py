"""A carteira de iniciativas: o fio entre 'tive uma ideia' e 'entreguei'.
O que não pode cair: sem critério de aceite ele não produz (senão declara sucesso sozinho), orçamento
estourado larga a iniciativa, e o João pode riscar uma linha no Markdown que ele obedece."""
from types import SimpleNamespace
import pytest
from jaime.agente.carteira import Carteira, ETAPAS, REPETICOES


class _Vault:
    def __init__(self): self.notas = {}; self.diario_linhas = []
    def read(self, r): return self.notas.get(r, "")
    def write(self, r, t): self.notas[r] = t
    def diario(self, t, s="Log"): self.diario_linhas.append(t)


def test_imaginar_abre_iniciativa_e_registra_o_porque(tmp_path):
    v = _Vault(); c = Carteira(v)
    i = c.imaginar("refazer o painel de música", porque="ele reclamou disso 3 vezes", criterio="toca e mostra o artista")
    assert i.etapa == "imaginada" and i.porque.startswith("ele reclamou")
    assert any("Iniciativa nova" in l for l in v.diario_linhas)
    assert "refazer o painel de música" in v.notas["01-Estado/Iniciativas.md"]

def test_nao_abre_a_mesma_duas_vezes(tmp_path):
    c = Carteira(_Vault())
    a = c.imaginar("painel de música", "x", "y")
    b = c.imaginar("painel de música", "x", "y")
    assert a is b and len(c.itens) == 1

def test_sem_criterio_de_aceite_ele_nao_produz():
    """Sem critério escrito antes, ele vai achar que deu certo — e acha sempre."""
    c = Carteira(_Vault())
    c.imaginar("coisa vaga", porque="achei legal")           # sem critério
    r = c.avancar("coisa vaga", "produzindo")
    assert "critério de aceite" in r and c.achar("coisa vaga").etapa == "imaginada"

def test_com_criterio_o_ciclo_anda_ate_o_fim():
    c = Carteira(_Vault())
    c.imaginar("painel", porque="evidência", criterio="abre em menos de 1 s")
    for etapa in ("projetada", "validada", "produzindo", "testando", "lancada", "medida"):
        assert "→" in c.avancar("painel", etapa)
    i = c.achar("painel")
    assert i.etapa == "medida" and not i.viva

def test_orcamento_estourado_larga_a_iniciativa():
    v = _Vault(); c = Carteira(v)
    c.imaginar("caro", porque="x", criterio="y", orcamento_usd=1.0)
    c.avancar("caro", "produzindo", gasto_usd=0.6)
    r = c.avancar("caro", "testando", gasto_usd=0.7)          # passou de US$ 1,00
    assert "orçamento" in r and c.achar("caro").etapa == "abandonada"
    assert any("Larguei" in l for l in v.diario_linhas)

def test_etapa_inventada_e_recusada():
    c = Carteira(_Vault()); c.imaginar("x", "y", "z")
    assert "etapa desconhecida" in c.avancar("x", "voando")

def test_assunto_que_volta_tres_vezes_vira_trabalho():
    c = Carteira(_Vault())
    pensamentos = ["o escrow do BUB está parado", "falta decidir o escrow", "o escrow trava tudo", "outro assunto"]
    assert c.assunto_recorrente(pensamentos) == "escrow"

def test_assunto_que_apareceu_uma_vez_nao_vira_trabalho():
    c = Carteira(_Vault())
    assert c.assunto_recorrente(["pensei em estamparia", "pensei em vídeo", "pensei em contrato"]) == ""

def test_o_joao_risca_a_linha_e_ele_obedece():
    """A carteira mora em Markdown para o João poder discordar na mão."""
    v = _Vault(); c = Carteira(v)
    c.imaginar("uma", "pq", "crit"); c.imaginar("duas", "pq", "crit")
    texto = v.notas["01-Estado/Iniciativas.md"]
    v.notas["01-Estado/Iniciativas.md"] = "\n".join(
        l for l in texto.splitlines() if not l.startswith("| duas"))
    c2 = Carteira(v)
    assert [i.titulo for i in c2.itens] == ["uma"]

def test_resumo_conta_a_verdade():
    c = Carteira(_Vault())
    assert "carteira vazia" in c.resumo()
    c.imaginar("a", "pq", "crit"); c.avancar("a", "produzindo", gasto_usd=0.5)
    r = c.resumo()
    assert "1 em andamento de 1" in r and "US$ 0.50" in r and "[produzindo] a" in r
