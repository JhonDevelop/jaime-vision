"""M-40 (Vigília 21/09): o laço de captura morreu num sono e o Jaime ficou 3 dias surdo com ativo=True e erro=''.
O watchdog reabre o microfone quando não chega frame com o Mac acordado, ou depois de um salto de relógio."""
import asyncio, time
from types import SimpleNamespace
from jaime.voice.duplex import OuvidoDuplex
from tests.test_duplex import _Fluxo, _Jaime, S

def _ouvido():
    async def rodar():
        return OuvidoDuplex(_Jaime(), S, asyncio.get_running_loop(), fluxo=_Fluxo([], ""), antecipador=None)
    return asyncio.run(rodar())

def test_verificar_microfone_detecta_silencio_e_salto():
    o = _ouvido(); t = 1000.0
    o._ultimo_frame = t
    assert o.verificar_microfone(t + 15) == "" and o.verificar_microfone(t + 30) == ""
    assert o.verificar_microfone(t + 61).startswith("sem áudio há 61 s")            # frames pararam, Mac acordado
    o._ultimo_frame = t + 61
    assert o.verificar_microfone(t + 76) == ""
    assert o.verificar_microfone(t + 76 + 15 * 60).startswith("relógio saltou 15 min")   # o Mac dormiu

def test_reabrir_aborta_a_captura_presa_sobe_outra_e_registra():
    o = _ouvido(); chamadas = []
    o._iniciar_captura = lambda: chamadas.append(o._mic_gen)
    class _Mic:
        def __init__(self): self.abortado = False; self.fechado = False
        def abort(self): self.abortado = True
        def close(self): self.fechado = True
    mic = _Mic(); o._mic = mic; gen = o._mic_gen
    o.reabrir_microfone("sem áudio há 90 s com o Mac acordado")
    assert mic.abortado and mic.fechado and o._mic is None and o._mic_gen == gen + 1 and chamadas == [gen + 1]
    assert o.erro.startswith("microfone parado: sem áudio") and time.time() - o._ultimo_frame < 1
    assert any(t.startswith("Ouvido reaberto: sem áudio há 90 s") for _, t in o.jaime.vault.linhas)

def test_captura_antiga_sai_em_silencio_quando_abortada(monkeypatch):
    o = _ouvido(); o._mic_gen = 3
    o._capturar(2)                                        # geração velha: não deve tocar em erro nem abrir microfone
    assert o.erro == ""
