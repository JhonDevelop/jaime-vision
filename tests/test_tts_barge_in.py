"""Barge-in não pode derrubar o processo: parar() numa thread enquanto o reprodutor escreve na placa em outra.
Em 15/09 14:06 o serviço morreu com SIGSEGV em PaUtil_WriteRingBuffer — o stream do PortAudio foi fechado no
meio de um write(). Aqui um `sounddevice` falso acusa qualquer escrita depois do fechamento."""
import sys, time, threading, types
import pytest


class _Stream:
    def __init__(self, registro, **kw):
        self.registro = registro
        self.fechado = False
        self.aberto = False

    def start(self): self.aberto = True

    def write(self, dados):
        if self.fechado:
            self.registro["erros"].append("write depois de fechar")
        self.registro["writes"].append(len(dados))
        time.sleep(0.02)                     # a placa "toca" o bloco; parar() pode chegar neste meio-tempo
        if self.fechado:
            self.registro["erros"].append("fechado durante o write")

    def stop(self): self.fechado = True
    def abort(self): self.fechado = True
    def close(self): self.fechado = True


@pytest.fixture
def placa(monkeypatch):
    registro = {"writes": [], "erros": [], "streams": []}
    sd = types.ModuleType("sounddevice")
    def RawOutputStream(**kw):
        st = _Stream(registro, **kw); registro["streams"].append(st); return st
    sd.RawOutputStream = RawOutputStream
    sd.query_devices = lambda kind=None: {"default_samplerate": 24000}
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    return registro


def _tts():
    import os
    os.environ["JAIME_SAIDA_AUDIO"] = "sounddevice"   # este teste exercita a placa (sounddevice), não o afplay
    from jaime.voice.tts import TTS
    return TTS(types.SimpleNamespace(openai_key="", elevenlabs_key=""))


def _esperar(cond, timeout=2.0):
    t0 = time.time()
    while not cond():
        assert time.time() - t0 < timeout, "tempo esgotado"
        time.sleep(0.005)


def test_parar_no_meio_da_fala_nao_fecha_o_stream_durante_o_write(placa):
    tts = _tts()
    pcm = b"\x00\x00" * 24000 * 3              # 3 s de silêncio, em blocos de 50 ms
    tts.tocar_pronto("Uma frase bem comprida para ser cortada no meio.", pcm)
    _esperar(lambda: len(placa["writes"]) >= 3)

    t0 = time.time()
    restantes = threading.Thread(target=lambda: setattr(tts, "_r", tts.parar()))
    restantes.start(); restantes.join(2.0)
    assert time.time() - t0 < 0.5             # cala em bem menos de meio segundo
    assert tts._r == 1 and tts.interrompida

    n = len(placa["writes"]); time.sleep(0.15)
    assert len(placa["writes"]) == n           # a frase antiga não continua depois de parar()
    assert placa["erros"] == []                # e nunca houve write() num stream fechado
    assert tts._stream is None and placa["streams"][0].fechado


def test_depois_de_parar_uma_frase_nova_abre_outro_stream(placa):
    tts = _tts()
    pcm = b"\x00\x00" * 24000 * 3
    tts.tocar_pronto("Primeira.", pcm)
    _esperar(lambda: len(placa["writes"]) >= 2)
    tts.parar()
    n = len(placa["writes"])
    tts.tocar_pronto("Segunda.", b"\x00\x00" * 2400)    # 100 ms → 2 blocos
    _esperar(lambda: tts._pendentes == 0 and len(placa["writes"]) >= n + 2)
    assert placa["erros"] == []
    assert len(placa["streams"]) == 2 and placa["streams"][1].fechado   # fechou ao terminar a resposta
