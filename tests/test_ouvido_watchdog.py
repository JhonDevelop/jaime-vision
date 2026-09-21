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

def test_reabrir_nao_toca_no_stream_antigo_sobe_outra_e_registra():
    o = _ouvido(); chamadas = []
    o._iniciar_captura = lambda: chamadas.append(o._mic_gen)
    class _Mic:
        def __init__(self): self.abortado = False; self.fechado = False
        def abort(self): self.abortado = True
        def close(self): self.fechado = True
    mic = _Mic(); o._mic = mic; gen = o._mic_gen
    o.reabrir_microfone("sem áudio há 90 s com o Mac acordado")
    assert not mic.abortado and not mic.fechado                     # o stream é da thread de captura (M-45: close() de fora = SIGSEGV)
    assert o._mic is None and o._mic_gen == gen + 1 and chamadas == [gen + 1]
    assert o.erro.startswith("microfone parado: sem áudio") and time.time() - o._ultimo_frame < 1
    assert any(t.startswith("Ouvido reaberto: sem áudio há 90 s") for _, t in o.jaime.vault.linhas)

def test_captura_antiga_sai_em_silencio_quando_abortada(monkeypatch):
    o = _ouvido(); o._mic_gen = 3
    o._capturar(2)                                        # geração velha: não deve tocar em erro nem abrir microfone
    assert o.erro == ""


def test_reabrir_nunca_fecha_o_stream_de_fora_mesmo_com_read_preso(monkeypatch):
    """21/09 12:51: SIGSEGV em PaUtil_ReadRingBuffer — o watchdog fechou o stream enquanto a captura estava em read().
    Agora a reabertura só sobe outra captura; o stream antigo é fechado pela própria thread, ao sair do read()."""
    import sys, threading, types, numpy as np
    from jaime.voice.duplex import FRAME
    solta = threading.Event(); registro = {"fechados": [], "abertos": 0, "fechado_por": []}
    class _Stream:
        def __init__(self, **kw): registro["abertos"] += 1; self.id = registro["abertos"]
        def __enter__(self): return self
        def __exit__(self, *a): registro["fechados"].append(self.id); registro["fechado_por"].append(threading.current_thread().name); return False
        def read(self, n):
            if self.id == 1:
                solta.wait(5)                                   # a 1ª captura fica presa no read() (como após o sono)
            return (b"\x00" * (FRAME * 2), False)
        def abort(self): raise AssertionError("abort() de fora do stream")
        def close(self): raise AssertionError("close() de fora do stream")
    sd = types.ModuleType("sounddevice"); sd.RawInputStream = _Stream
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    o = _ouvido(); o.ativo = False                                # ativo=False: o loop só lê e descarta (sem VAD)
    o._vad = types.SimpleNamespace(_janela=[]); o.det = types.SimpleNamespace(cancelar=lambda: None, falando=False)
    t1 = threading.Thread(target=o._capturar, args=(o._mic_gen,), name="captura-1", daemon=True); t1.start()
    time.sleep(0.05); assert registro["abertos"] == 1 and registro["fechados"] == []
    novas = []; o._iniciar_captura = lambda: novas.append(o._mic_gen)
    o.reabrir_microfone("relógio saltou 2 min (o Mac dormiu)")     # não pode encostar no stream 1
    assert novas == [1] and registro["fechados"] == [] and o.erro.startswith("microfone parado")
    solta.set(); t1.join(2)                                        # o read() destrava: a thread vê a geração vencida e fecha o SEU stream
    assert not t1.is_alive() and registro["fechados"] == [1] and registro["fechado_por"] == ["captura-1"]
