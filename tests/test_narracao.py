"""O Central não fica mudo enquanto os outros dois trabalham.
Antes, o João pedia algo grande e o Jaime emudecia até o filho terminar — ele não sabia se alguém estava
trabalhando ou se tinha travado."""
from pathlib import Path
from types import SimpleNamespace
import pytest
from jaime.cerebros.hemisferios import Cerebros, _gerundio


class _Vault:
    root = Path(".")
    def read(self, r): return ""
    def write(self, r, t): pass


class _Ouvido:
    def __init__(self): self.falas = []
    def falar(self, t): self.falas.append(t)


class _Maestri:
    disponivel = True
    def listar(self): return 'Connected agents:\n  - name: "J.A.I.M.E · Gemini"\n'
    def pedir(self, nome, tarefa): return "feito"


class _Equipe:
    maestri = _Maestri(); vivos = []


@pytest.mark.parametrize("tarefa,esperado", [
    ("implementa o cache de frases", "escrevendo o código"),
    ("testa o barge-in", "rodando os testes"),
    ("pesquisa alternativas de TTS", "pesquisando"),
    ("revisa o meu plano", "revisando"),
    ("faz aquela coisa lá", "trabalhando nisso"),
])
def test_diz_o_que_o_hemisferio_esta_fazendo_em_portugues(tarefa, esperado):
    assert _gerundio(tarefa) == esperado

def test_narra_quando_delega_e_quando_o_filho_entrega():
    o = _Ouvido()
    c = Cerebros(_Vault(), _Equipe(), ouvido=o)
    c.delegar("direito", "pesquisa alternativas de TTS")
    assert any("pesquisando" in f for f in o.falas), o.falas
    assert any("entregou" in f for f in o.falas), o.falas

def test_nao_repete_a_mesma_narracao_duas_vezes_seguidas():
    o = _Ouvido()
    c = Cerebros(_Vault(), _Equipe(), ouvido=o)
    c.narrar("O Gemini está pesquisando.")
    c.narrar("O Gemini está pesquisando.")
    c.narrar("O Gemini entregou.")
    assert o.falas == ["O Gemini está pesquisando.", "O Gemini entregou."]

def test_sem_voz_ligada_a_narracao_nao_quebra():
    c = Cerebros(_Vault(), _Equipe())          # sem ouvido
    c.narrar("qualquer coisa")                 # não pode levantar exceção

def test_voz_que_falha_nao_derruba_a_delegacao():
    class _Ruim:
        def falar(self, t): raise RuntimeError("alto-falante fora do ar")
    c = Cerebros(_Vault(), _Equipe(), ouvido=_Ruim())
    assert c.delegar("direito", "pesquisa x") == "feito"


# ── a muleta cede o lugar ao narrador ─────────────────────────────────────
def test_o_narrador_fala_antes_da_muleta_pensar_em_disparar():
    """Dizer 'lendo os arquivos' é verdade sobre o trabalho; 'deixa eu ver' é enfeite.
    Quem está trabalhando conta o que faz — então o narrador tem que chegar primeiro."""
    from jaime.voice.narrador import PRIMEIRA_S
    from jaime.voice.escuta import MULETA_S
    assert PRIMEIRA_S < MULETA_S, "a muleta estaria roubando a vez do narrador"

def test_a_muleta_so_dispara_depois_que_a_resposta_realmente_demorou():
    """Com o acervo enxuto o 1º token chega rápido; a muleta vira exceção, não hábito."""
    from jaime.voice.escuta import MULETA_S
    assert MULETA_S >= 5.0

def test_o_narrador_diz_o_que_esta_fazendo_de_verdade():
    from jaime.voice.narrador import frase_para
    assert frase_para("Read") == "lendo os arquivos"
    assert frase_para("Bash") == "rodando um comando"
    assert "pesquisando" in frase_para("WebSearch")
