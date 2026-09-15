import numpy as np

from jaime.voice.eco import SupressorDeEco


def _pcm(sinal):
    return np.asarray(sinal, dtype=np.int16).tobytes()


def _seno(hz, sr, segundos, amplitude=12_000):
    t = np.arange(round(sr * segundos)) / sr
    return amplitude * np.sin(2 * np.pi * hz * t)


def test_eco_puro_com_atraso_e_reconhecido():
    eco = SupressorDeEco()
    referencia = np.random.default_rng(7).normal(0, 9_000, 24_000 * 3 // 10)
    eco.ao_tocar(_pcm(referencia))
    # O mic recebe 32 ms da referência, atrasados 120 ms e atenuados pela sala.
    inicio = round(0.12 * 16_000)
    mic = eco.referencia.recente_16k()[inicio:inicio + round(0.032 * 16_000)] * 0.25
    eh_eco, similaridade = eco.eh_eco(_pcm(mic))
    assert eh_eco and similaridade > 0.95


def test_voz_diferente_sobre_eco_nao_corta_jaime():
    eco = SupressorDeEco()
    eco.ao_tocar(_pcm(_seno(440, 24_000, 0.30)))
    voz_joao = _seno(1_100, 16_000, 0.032, 12_000)
    eco_baixo = _seno(440, 16_000, 0.032, 1_500)
    eh_eco, similaridade = eco.eh_eco(_pcm(voz_joao + eco_baixo))
    assert not eh_eco and similaridade < 0.80


def test_sem_referencia_nao_e_eco():
    eh_eco, similaridade = SupressorDeEco().eh_eco(_pcm(_seno(440, 16_000, 0.032)))
    assert not eh_eco and similaridade == 0.0
