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

def test_o_painel_acompanha_a_delegacao_do_comeco_ao_fim():
    """O cockpit vê começo e fim; a boca não. Foi o João quem pediu assim."""
    from jaime.hud.events import bus
    vistos = []
    orig = bus.emitir
    bus.emitir = lambda tipo, **kw: vistos.append(kw.get("narracao", ""))
    try:
        Cerebros(_Vault(), _Equipe(), ouvido=_Ouvido()).delegar("direito", "pesquisa alternativas de TTS")
    finally:
        bus.emitir = orig
    assert any("pesquisando" in v for v in vistos), vistos
    assert any("entregou" in v for v in vistos), vistos

def test_nao_repete_o_mesmo_aviso_duas_vezes_seguidas():
    o = _Ouvido()
    c = Cerebros(_Vault(), _Equipe(), ouvido=o)
    c.narrar("Um dos meus agentes terminou X.", importante=True)
    c.narrar("Um dos meus agentes terminou X.", importante=True)
    c.narrar("Um dos meus agentes terminou Y.", importante=True)
    assert o.falas == ["Um dos meus agentes terminou X.", "Um dos meus agentes terminou Y."]

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


# ── ele para de narrar o que o João não pediu ─────────────────────────────
def test_trabalho_que_ele_mesmo_puxou_nao_vira_fala():
    """O João, 17/09: «não quero que ele fique me falando Gemini ou Codex entregou»."""
    o = _Ouvido()
    c = Cerebros(_Vault(), _Equipe(), ouvido=o)
    c.delegar("direito", "pesquisa alternativas de TTS")
    assert o.falas == [], f"falou sem precisar: {o.falas}"

def test_so_fala_quando_e_coisa_que_o_joao_pediu_e_sem_nome_de_motor():
    o = _Ouvido()
    c = Cerebros(_Vault(), _Equipe(), ouvido=o)
    c.avisar_do_joao("o relatório da estamparia")
    assert len(o.falas) == 1
    frase = o.falas[0]
    assert "um dos meus agentes" in frase.lower() and "relatório da estamparia" in frase
    for motor in ("codex", "gemini", "claude", "antigravity"):
        assert motor not in frase.lower(), f"disse o nome do motor: {frase}"

def test_nao_fala_por_cima_do_joao():
    """Cortar o João é o pior defeito possível; nem o aviso importante passa na frente."""
    class _Falando(_Ouvido):
        mudo = False
        det = SimpleNamespace(falando=True)          # o João está falando AGORA
    o = _Falando()
    Cerebros(_Vault(), _Equipe(), ouvido=o).avisar_do_joao("qualquer coisa")
    assert o.falas == []

def test_nao_fala_enquanto_ele_proprio_ja_esta_falando():
    class _Mudo(_Ouvido):
        mudo = True                                   # o Jaime está com a palavra
        det = SimpleNamespace(falando=False)
    o = _Mudo()
    Cerebros(_Vault(), _Equipe(), ouvido=o).avisar_do_joao("x")
    assert o.falas == []

def test_o_painel_ve_tudo_mesmo_o_que_a_voz_cala():
    """Silêncio na boca não é cegueira: o cockpit continua mostrando o trabalho."""
    from jaime.hud.events import bus
    vistos = []
    orig = bus.emitir
    bus.emitir = lambda tipo, **kw: vistos.append((tipo, kw))
    try:
        Cerebros(_Vault(), _Equipe(), ouvido=_Ouvido()).delegar("direito", "pesquisa x")
    finally:
        bus.emitir = orig
    assert any(t == "cerebro" and "narracao" in kw for t, kw in vistos)


# ── voz como a do ChatGPT: fala, responde, acabou ─────────────────────────
def test_a_retomada_vem_desligada():
    """João, 17/09: «não quero que ele fique voltando em "continuo dizendo o que eu dizia"».
    Cortar o Jaime JÁ É a resposta dele; perguntar "continuo?" transforma o corte em assunto novo."""
    from jaime.voice.escuta import RETOMAR
    assert RETOMAR is False

def test_sem_ferramenta_nao_existe_muleta():
    """«Peraí» sem estar fazendo nada promete e não entrega — é pior que silêncio."""
    import inspect
    from jaime.voice import escuta
    fonte = inspect.getsource(escuta)
    i = fonte.index("async def muleta()")
    corpo = fonte[i:i + 700]
    assert "return" in corpo.split("except asyncio.TimeoutError:")[1][:80], \
        "o ramo sem ferramenta ainda dispara muleta"
