"""A trava que impede o J.A.I.M.E de se cortar quando fala no alto-falante.

João, 17/09: «sai no alto-falante e ele mesmo se corta. Quero continuar podendo interromper QUALQUER fala
dele, mas se o que ele estiver escutando for transcrito para a mesma coisa que ele vai falar, ele ignora».

A assimetria é de propósito: deixar de cortar quando o João falou custa a ele repetir a frase; cortar a si
mesmo no meio faz o Jaime parecer quebrado. Então na dúvida, é eco."""
import pytest
from jaime.voice.duplex import (eh_eco_do_jaime, fala_de_verdade, _sem_acento,
                                BARGE_IN_ECO_TEXTO, BARGE_IN_ECO_SEQ)

DIZENDO = ("O relatório da estamparia está pronto, com trinta e sete páginas. "
           "As três reuniões de amanhã continuam marcadas.")


@pytest.mark.parametrize("ouvido", [
    "o relatorio da estamparia esta pronto",                       # sem acento, como o STT às vezes devolve
    "O relatório da estamparia está pronto",                       # com acento
    "com trinta e sete paginas",                                   # só um trecho do meio
    "as tres reunioes de amanha continuam marcadas",               # o fim
    "relatorio da estamparia pronto com trinta sete paginas ah",    # o STT comeu e inventou palavra
    "as três reuniões de amanhã continuam",                        # cortado no meio
    "O RELATÓRIO DA ESTAMPARIA ESTÁ PRONTO",                       # maiúscula
])
def test_o_proprio_jaime_voltando_pelo_alto_falante_e_ignorado(ouvido):
    assert eh_eco_do_jaime(ouvido, DIZENDO), f"não reconheceu como eco: {ouvido}"
    assert not fala_de_verdade(ouvido, DIZENDO), "isso cortaria o Jaime no meio da própria fala"


@pytest.mark.parametrize("ouvido", [
    "jaime para de falar",
    "chega disso, muda de assunto",
    "espera aí, quero outra coisa",
    "abre o finder por favor",
    "não era isso que eu queria",
    "quanto ficou o saldo hoje",
    "cancela isso",
])
def test_o_joao_continua_conseguindo_interromper_qualquer_fala(ouvido):
    assert not eh_eco_do_jaime(ouvido, DIZENDO), f"confundiu o João com eco: {ouvido}"
    assert fala_de_verdade(ouvido, DIZENDO), f"não cortaria quando o João mandou parar: {ouvido}"


def test_a_prova_da_proporcao():
    """Metade das palavras vindas do que ele diz já é eco."""
    assert eh_eco_do_jaime("relatorio estamparia pronto", "O relatório da estamparia está pronto")
    assert BARGE_IN_ECO_TEXTO == 0.5

def test_a_prova_da_sequencia_pega_o_eco_com_palavra_a_mais():
    """Era o caso em que a proporção falhava: o STT inventa uma palavra e a conta cai do limiar."""
    assert eh_eco_do_jaime("está na tela joão", "Está na tela.")
    assert 0.5 < BARGE_IN_ECO_SEQ < 0.8

def test_a_prova_da_palavra_rara():
    """Duas palavras longas e específicas dele na escuta não são coincidência."""
    assert eh_eco_do_jaime("estamparia continuam", DIZENDO)

def test_uma_palavra_so_e_tratada_como_eco_e_isso_nao_atrapalha():
    """Escrevi este teste esperando o contrário e o código estava certo: uma palavra solta que saiu
    inteira da fala dele É eco pela proporção. E não atrapalha o João, porque uma palavra nunca
    interrompe de todo jeito — fala_de_verdade exige duas."""
    assert eh_eco_do_jaime("e a estamparia", "O relatório da estamparia chegou")
    assert not fala_de_verdade("estamparia", "")        # sem eco nenhum, uma palavra ainda não corta

def test_o_joao_repetindo_uma_palavra_dele_com_mais_contexto_corta():
    """Duas palavras, sendo uma dele e outra não, continua sendo o João falando."""
    assert fala_de_verdade("estamparia não", "O relatório da estamparia chegou") or \
           fala_de_verdade("para com a estamparia", "O relatório da estamparia chegou")

def test_sem_nada_sendo_dito_nada_e_eco():
    assert not eh_eco_do_jaime("qualquer coisa", "")
    assert not eh_eco_do_jaime("", DIZENDO)

def test_tira_acento_para_comparar():
    assert _sem_acento("Ação, três, coração") == "acao, tres, coracao"

def test_lixo_do_stt_nao_corta_nem_sem_eco():
    assert not fala_de_verdade("...", "")
    assert not fala_de_verdade("ah", "")

def test_frase_curta_do_joao_ainda_corta():
    """«para» e «chega» são o jeito mais natural de interromper; não podem exigir frase longa."""
    assert fala_de_verdade("para jaime", DIZENDO)
    assert fala_de_verdade("chega disso", DIZENDO)


# ── a frase que está tocando AGORA ────────────────────────────────────────
def test_o_tts_marca_qual_frase_esta_soando_e_limpa_depois():
    """A comparação com a resposta inteira pega eco de qualquer parte; a comparação com a frase que está
    soando agora pega o eco exato do que acabou de sair no alto-falante. As duas juntas fecham o buraco."""
    from types import SimpleNamespace
    from jaime.voice.tts import TTS
    t = TTS(SimpleNamespace(openai_key="", elevenlabs_key=""))
    assert hasattr(t, "frase_atual") and t.frase_atual == ""
    t.frase_atual = "Está na tela."
    assert eh_eco_do_jaime("esta na tela", t.frase_atual)
    t.frase_atual = ""
    assert not eh_eco_do_jaime("esta na tela", t.frase_atual)   # parou de soar, não veta mais
