"""Curiosidade sobre quem fala com o João: contar, estranhar, perguntar UMA vez, guardar, decidir.
O que não pode cair: urgência de desconhecido passa, conversa fiada de conhecido não passa, e ele não
interroga o João sobre a mesma pessoa a vida inteira."""
import time
from types import SimpleNamespace
import pytest
from jaime.relacoes.curiosidade import Curiosidade, CURIOSO_A_PARTIR_DE, PERGUNTAS_POR_PESSOA


class _Grafo:
    def __init__(self, conhecidos=()):
        self.conhecidos = set(conhecidos); self.guardados = []
    def quem_e(self, n): return {"nome": n} if n in self.conhecidos else None
    def lembrar_pessoa(self, n, **k): self.conhecidos.add(n); self.guardados.append(("pessoa", n, k))
    def fato(self, n, c, v, **k): self.guardados.append(("fato", n, c, v, k))
    def ligar(self, a, b, r, **k): self.guardados.append(("ligar", a, b, r, k))


def _mandou(c, nome, vezes, texto="oi", hora=14):
    base = time.mktime((2026, 9, 17, hora, 0, 0, 0, 0, -1))
    for i in range(vezes):
        c.ouviu(nome, texto, quando=base + i * 3600 * 24)
    return c.remetentes[nome]


# ── contar ────────────────────────────────────────────────────────────────
def test_conta_quem_fala_quantas_vezes_e_em_que_horario():
    c = Curiosidade(_Grafo())
    r = _mandou(c, "Rafael", 3, "sobre o contrato", hora=9)
    assert r.mensagens == 3 and r.hora_tipica == "de manhã"
    assert "Rafael: 3 mensagens" in r.resumo() and "de manhã" in r.resumo()

def test_guarda_so_os_ultimos_assuntos_e_nao_cresce_sem_fim():
    c = Curiosidade(_Grafo())
    for i in range(30):
        c.ouviu("X", f"assunto {i}")
    assert len(c.remetentes["X"].assuntos) == 10


# ── estranhar e perguntar ────────────────────────────────────────────────
def test_pessoa_frequente_e_desconhecida_vira_curiosidade():
    c = Curiosidade(_Grafo())
    _mandou(c, "Mariana", CURIOSO_A_PARTIR_DE, hora=22)
    p = c.curiosidade("Mariana")
    assert "Mariana" in p and "não sei quem é" in p and "de noite" in p
    assert p.endswith("Quem é essa pessoa para você?")

def test_uma_mensagem_solta_nao_vira_pergunta():
    c = Curiosidade(_Grafo())
    _mandou(c, "Alguém", 1)
    assert c.curiosidade("Alguém") == ""

def test_quem_ele_ja_conhece_nao_vira_pergunta():
    c = Curiosidade(_Grafo({"Gabriel"}))
    _mandou(c, "Gabriel", 20)
    assert c.curiosidade("Gabriel") == ""

def test_ele_nao_interroga_o_joao_sobre_a_mesma_pessoa_para_sempre():
    """O João odeia responder duas vezes; insistir é pior que conviver com a dúvida."""
    c = Curiosidade(_Grafo())
    _mandou(c, "Fulano", 30)
    feitas = [c.curiosidade("Fulano") for _ in range(6)]
    assert sum(1 for p in feitas if p) == PERGUNTAS_POR_PESSOA


# ── guardar ───────────────────────────────────────────────────────────────
def test_a_resposta_do_joao_vira_memoria_com_evidencia():
    g = _Grafo(); c = Curiosidade(g)
    _mandou(c, "Mariana", 7)
    r = c.aprendi("Mariana", "advogada do contrato da estamparia", relacao="trabalha-com")
    assert "Anotei" in r and "advogada" in r
    tipos = [x[0] for x in g.guardados]
    assert "pessoa" in tipos and "fato" in tipos and "ligar" in tipos
    assert any("7 mensagens observadas" in str(x) for x in g.guardados)   # evidência junto
    assert c.curiosidade("Mariana") == ""                                  # deixou de ser lacuna

def test_nao_guarda_sem_saber_quem_e():
    c = Curiosidade(_Grafo())
    assert "faltou dizer" in c.aprendi("X", "")


# ── decidir se interrompe ────────────────────────────────────────────────
@pytest.mark.parametrize("texto", [
    "urgente, preciso falar com você", "o contrato vence amanhã", "teve um acidente",
    "o pagamento não entrou", "chegou uma intimação",
])
def test_assunto_que_nao_espera_passa_mesmo_de_desconhecido(texto):
    ok, porque = Curiosidade(_Grafo()).vale_avisar("Número novo", texto)
    assert ok and "não espera" in porque

@pytest.mark.parametrize("texto", [
    "bom dia!", "kkkkk", "olha esse meme", "você ganhou um cupom de desconto", "clique aqui",
])
def test_conversa_fiada_nao_interrompe_nem_vindo_de_quem_ele_conhece(texto):
    ok, porque = Curiosidade(_Grafo({"Gabriel"})).vale_avisar("Gabriel", texto)
    assert not ok and "conversa fiada" in porque

def test_quem_ele_conhece_passa():
    ok, porque = Curiosidade(_Grafo({"Gabriel"})).vale_avisar("Gabriel", "consegue olhar aquilo hoje?")
    assert ok and "sei quem é" in porque

def test_desconhecido_que_insiste_passa_justamente_por_isso():
    c = Curiosidade(_Grafo())
    _mandou(c, "Insistente", 9, "consegue falar?")
    ok, porque = c.vale_avisar("Insistente", "consegue falar?")
    assert ok and "ainda não sei quem é" in porque

def test_desconhecido_de_uma_vez_so_nao_interrompe():
    ok, porque = Curiosidade(_Grafo()).vale_avisar("Número aleatório", "oi, tudo bem?")
    assert not ok and "não conheço" in porque

def test_urgencia_ganha_da_conversa_fiada_na_mesma_frase():
    """«bom dia, o contrato vence hoje» é urgente, não é bom dia."""
    ok, _ = Curiosidade(_Grafo()).vale_avisar("X", "bom dia, o contrato vence hoje")
    assert ok

def test_o_contexto_diz_de_quem_ele_sabe_e_de_quem_nao_sabe():
    c = Curiosidade(_Grafo({"Gabriel"}))
    _mandou(c, "Gabriel", 8); _mandou(c, "Mariana", 6)
    t = c.contexto()
    assert "Gabriel" in t and "conheço" in t
    assert "Mariana" in t and "NÃO sei quem é" in t

def test_sem_ninguem_o_contexto_e_vazio():
    assert Curiosidade(_Grafo()).contexto() == ""
