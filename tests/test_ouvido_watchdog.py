"""M-40 (Vigília 21/09): o laço de captura morreu num sono e o Jaime ficou 3 dias surdo com ativo=True e erro=''.
O watchdog reabre o microfone quando não chega frame com o Mac acordado, ou depois de um salto de relógio."""
import asyncio, time
from types import SimpleNamespace
from pathlib import Path
import pytest
from jaime.voice.duplex import OuvidoDuplex
from tests.test_duplex import _Fluxo, _Jaime, S

@pytest.fixture(autouse=True)
def isolar_reinicios(tmp_path, monkeypatch):
    p = tmp_path / ".reinicios"
    monkeypatch.setenv("JAIME_ARQUIVO_REINICIOS", str(p))

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


# ── M-47 (Vigília 21/09 18:30): CoreAudio travado após o sono — reabrir para sempre só empilha threads presas ──
def test_duas_reaberturas_sem_frames_reiniciam_o_processo():
    o = _ouvido(); saidas = []; o._sair = lambda c: saidas.append(c); o._iniciar_captura = lambda: None
    t = 1000.0; o._ultimo_frame = t
    # 1ª: sem áudio há 60 s com o Mac acordado → reabre
    m = o.verificar_microfone(t + 61); assert m.startswith("sem áudio") and o.decidir_reabertura(m, t + 61) == "reabrir"
    o.reabrir_microfone(m); o._ultimo_frame = t + 61; o._reaberturas[-1] = t + 61
    # 20 s depois nada voltou (frames_gen == 0): 2ª reabertura
    m = o.verificar_microfone(t + 82); assert m.startswith("sem áudio há 21 s") and o.decidir_reabertura(m, t + 82) == "reabrir"
    o.reabrir_microfone(m); o._ultimo_frame = t + 82; o._reaberturas[-1] = t + 82
    # mais 20 s sem frames: o CoreAudio não vai voltar — reinicia
    m = o.verificar_microfone(t + 103); assert o.decidir_reabertura(m, t + 103) == "reiniciar"
    o.reiniciar_processo(m)
    assert saidas == [3] and any(l.startswith("CoreAudio travado após o sono") for _, l in o.jaime.vault.linhas)

def test_frames_de_volta_zeram_as_falhas_e_o_limite_por_hora_tambem_reinicia():
    o = _ouvido(); o._iniciar_captura = lambda: None; t = 5000.0; o._ultimo_frame = t
    o.reabrir_microfone("x"); o._reaberturas[-1] = t; o._frames_gen = 40          # reabriu e o áudio voltou
    assert o.decidir_reabertura("sem áudio há 61 s com o Mac acordado", t + 200) == "reabrir" and o._falhas_seguidas == 0
    o._frames_gen = 0
    for i in range(6): o._reaberturas.append(t + 300 + i)
    assert o.decidir_reabertura("relógio saltou 3 min (o Mac dormiu)", t + 400) == "reiniciar"   # 7 na última hora


# ── M-48: Watchdog detecta surdez desde o boot (_ultimo_frame == 0.0) ─────────
def test_verificar_microfone_detecta_surdo_desde_o_boot():
    o = _ouvido(); t = 2000.0
    o._ultimo_frame = 0.0
    o._inicio_captura = t
    assert o.verificar_microfone(t + 15) == ""
    m = o.verificar_microfone(t + 61)
    assert m.startswith("sem áudio há 61 s com o Mac acordado")


# ── M-48b: Retentativas com terminate/initialize do PortAudio e device explícito ──
def test_retentativa_captura_reinicializa_portaudio(monkeypatch):
    import sys, threading, types
    from jaime.voice.duplex import FRAME
    eventos_sd = []
    class _StreamMock:
        tentativas = 0
        def __init__(self, **kw):
            _StreamMock.tentativas += 1
            self.kw = kw
            if _StreamMock.tentativas == 1:
                raise RuntimeError("AUHAL err='35'")
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n): return (b"\x00" * (FRAME * 2), False)
    sd = types.ModuleType("sounddevice")
    sd.RawInputStream = _StreamMock
    sd._terminate = lambda: eventos_sd.append("term")
    sd._initialize = lambda: eventos_sd.append("init")
    sd.query_devices = lambda kind="input": {"name": "Mic", "index": 2}
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    o = _ouvido(); o.ativo = False
    o._recuo_inicial = 0.01
    o._vad = types.SimpleNamespace(_janela=[]); o.det = types.SimpleNamespace(cancelar=lambda: None, falando=False)
    t = threading.Thread(target=o._capturar, args=(o._mic_gen,), daemon=True)
    t.start()
    time.sleep(0.08)
    o._parar.set()
    t.join(2)
    assert _StreamMock.tentativas >= 2
    assert "term" in eventos_sd and "init" in eventos_sd
    assert any("Ouvido falhou: RuntimeError: AUHAL err='35'" in l for _, l in o.jaime.vault.linhas)
    assert any("Ouvido ativo: microfone voltou a ler frames" in l for _, l in o.jaime.vault.linhas)


# ── M-48b: Medição de frames_ultimo_min e exposição no /hud/sistemas ─────────
def test_frames_ultimo_min_e_hud_sistemas():
    from jaime.hud.sistemas import montar
    o = _ouvido()
    t = int(time.time())
    o._frames_buckets.append([t - 70, 50])  # fora dos 60 s
    o._frames_buckets.append([t - 30, 20])
    o._frames_buckets.append([t - 10, 15])
    assert o.frames_ultimo_min == 35
    sist = montar(o.jaime, ouvido=o, settings=SimpleNamespace(voz_modo="duplex"))
    assert sist["ouvido"]["frames_ultimo_min"] == 35
    assert sist["ouvido"]["aberto"] is False
    assert sist["ouvido"]["ultimo_frame"] == 0.0


# ── M-49: Teto de reinícios por hora (a partir do 3º, mantém processo vivo) ──
def test_limite_de_reinicios_mantem_processo_vivo(tmp_path):
    o = _ouvido(); saidas = []
    o._sair = lambda c: saidas.append(c)
    o._arquivo_reinicios = tmp_path / ".reinicios"
    reabertos = []
    o.reabrir_microfone = lambda motivo: reabertos.append(motivo)
    
    t = 10000.0
    # 1º reinício: sai com 3
    o.reiniciar_processo("falha 1")
    assert saidas == [3] and len(reabertos) == 0
    
    # 2º reinício: sai com 3
    o.reiniciar_processo("falha 2")
    assert saidas == [3, 3] and len(reabertos) == 0
    
    # 3º reinício na mesma hora: NÃO sai, mantém vivo e chama reabrir_microfone
    o.reiniciar_processo("falha 3")
    assert saidas == [3, 3]  # não aumentou
    assert len(reabertos) == 1
    assert "limite de reinícios atingido" in o.erro
    assert any(l.startswith("Estou surdo: o microfone não abre") for _, l in o.jaime.vault.linhas)

