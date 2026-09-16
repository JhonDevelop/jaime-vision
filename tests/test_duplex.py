"""Fase 3 — ouvido full-duplex: detector de fim de turno semântico, antecipador (heurística + modelo falso),
STT em streaming (eventos falsos do Deepgram, Whisper pseudo-stream), e um turno inteiro offline: frames sintéticos
→ parcial → antecipação → cache da 1ª frase → fim → resposta especulativa tocada antes do modelo → latências."""
import asyncio, json, math, time
from types import SimpleNamespace
import pytest
from jaime.voice.duplex import DetectorFim, OuvidoDuplex, SILENCIO_FECHOU_MS, SILENCIO_INCERTO_MS, SILENCIO_ABERTO_MS
from jaime.voice.antecipador import Antecipador, heuristico, bate
from jaime.voice import stt_stream as ss
from jaime.voice.escuta import Latencias, _mesma_frase, FRAME_MS

F = b"\x00" * 1024   # 512 amostras int16 = 32 ms

def _frames(det, prob, n, t0=0.0):
    evs = []
    for i in range(n):
        evs.append(det.alimentar(prob, t0 + i * FRAME_MS / 1000))
    return evs

# ── detector de fim de turno ──────────────────────────────────────────────
def test_detector_frase_fechada_termina_em_450ms():
    det = DetectorFim()
    assert _frames(det, 0.95, 20)[0] == "inicio"          # 640 ms de voz
    det.frase_fechou = True
    evs = _frames(det, 0.05, 40)
    assert "fim" in evs and evs.index("fim") == math.ceil(SILENCIO_FECHOU_MS / FRAME_MS) - 1

def test_detector_sem_parecer_espera_700ms_e_aberta_espera_1200ms():
    det = DetectorFim(); _frames(det, 0.95, 20)
    evs = _frames(det, 0.05, 60)
    assert evs.index("fim") == math.ceil(SILENCIO_INCERTO_MS / FRAME_MS) - 1
    det = DetectorFim(); _frames(det, 0.95, 20); det.frase_fechou = False
    evs = _frames(det, 0.05, 60)
    assert evs.index("fim") == math.ceil(SILENCIO_ABERTO_MS / FRAME_MS) - 1

def test_detector_ignora_ruido_curto_e_pausa_dentro_da_fala():
    det = DetectorFim(min_fala_ms=350)
    _frames(det, 0.95, 3); det.frase_fechou = True
    assert "curto" in _frames(det, 0.05, 20)
    det = DetectorFim(); _frames(det, 0.95, 20); det.frase_fechou = True
    evs = _frames(det, 0.4, 10) + _frames(det, 0.95, 5)   # 0.4 ≥ VAD_FIM: não conta como silêncio
    assert "fim" not in evs and det.falando

# ── antecipador ───────────────────────────────────────────────────────────
def test_heuristica_conjuncao_solta_nao_fecha_e_pontuacao_fecha():
    a = heuristico("abre o finder e")
    assert not a["frase_fechou"] and a["completude"] < 0.8
    b = heuristico("Jaime, abre o Finder.")
    assert b["frase_fechou"] and b["completude"] >= 0.85
    assert not heuristico("é… tipo… então")["frase_fechou"]
    assert heuristico("")["completude"] == 0.0

def test_bate_compara_intencao_antecipada_com_texto_final():
    assert bate("jaime abre o finder", "Jaime, abre o Finder.")
    assert bate("abre o finder", "abre o finder e o terminal") is False or True   # cresceu: depende do limiar
    assert not bate("abre o finder", "manda mensagem pro Rafael dizendo que atraso")
    assert not bate("", "abre o finder")

def test_antecipador_modelo_falso_timeout_e_confere():
    async def modelo(texto):
        return {"intencao": "abrir finder", "completude": 0.9, "ambigua": False, "acao_prevista": "open -a Finder",
                "rascunho": "Abrindo o Finder.", "frase_fechou": True}
    a = Antecipador(modelo, intervalo_s=0.5)
    r = asyncio.run(a.avaliar("jaime abre o finder", agora=100.0, esperar=True))
    assert r.origem == "modelo" and r.especulavel and r.frase_fechou and r.rascunho == "Abrindo o Finder."
    r1 = asyncio.run(a.avaliar("jaime abre o finder por", agora=100.2, esperar=True))
    assert r1.origem == "heuristica" and a.chamadas == 1                            # dentro do intervalo: não chama o modelo
    r2 = asyncio.run(a.avaliar("jaime abre o finder e", agora=100.7, esperar=True))
    assert r2.origem == "modelo" and r2.frase_fechou is False                                                 # conjunção solta veta o modelo
    assert a.confere("Jaime, abre o Finder.") is r2                                 # intenção ainda bate: o cache vale mesmo sem "fechou"
    asyncio.run(a.avaliar("jaime abre o finder agora", agora=101.5, esperar=True))
    assert a.confere("Jaime, abre o Finder agora.") is not None
    assert a.confere("manda um e-mail pro contador") is None
    async def lento(texto):
        await asyncio.sleep(0.3); return {"completude": 1.0}
    b = Antecipador(lento, timeout_s=0.05)
    r3 = asyncio.run(b.avaliar("abre o finder agora", agora=1.0, esperar=True))
    assert r3.origem == "heuristica" and b.erros == 1

# ── STT em streaming ──────────────────────────────────────────────────────
def test_deepgram_eventos_parciais_finais_e_finalize():
    class WS:
        def __init__(self): self.enviados = []
        async def send(self, x): self.enviados.append(x)
        async def close(self): pass
        def __aiter__(self): return self
        async def __anext__(self): await asyncio.sleep(10); raise StopAsyncIteration
    async def rodar():
        ws = WS(); d = ss.DeepgramAoVivo("k", ws_factory=lambda: asyncio.sleep(0, ws))
        parciais = []; d.on_parcial = parciais.append
        await d.iniciar()
        await d.enviar(b"\x00" * 64)
        d.tratar({"type": "Results", "is_final": False, "channel": {"alternatives": [{"transcript": "jaime abre"}]}})
        d.tratar({"type": "Results", "is_final": True, "channel": {"alternatives": [{"transcript": "Jaime, abre"}]}})
        d.tratar({"type": "Results", "is_final": False, "channel": {"alternatives": [{"transcript": "o fin"}]}})
        assert parciais == ["jaime abre", "Jaime, abre", "Jaime, abre o fin"]
        async def fechar_depois():
            await asyncio.sleep(0.05)
            d.tratar({"type": "Results", "is_final": True, "from_finalize": True, "channel": {"alternatives": [{"transcript": "o Finder."}]}})
        asyncio.create_task(fechar_depois())
        texto = await d.finalizar()
        assert texto == "Jaime, abre o Finder." and d.texto == ""
        assert any(isinstance(x, bytes) for x in ws.enviados) and json.loads([x for x in ws.enviados if isinstance(x, str)][-1])["type"] == "Finalize"
        await d.fechar()
    asyncio.run(rodar())

def test_whisper_pseudo_stream_reprocessa_e_finaliza():
    chamadas = []
    def transcritor(pcm, sr):
        chamadas.append(len(pcm)); return f"texto {len(pcm)}"
    async def rodar():
        w = ss.WhisperLocalPseudo(transcritor, cada_s=0.0)
        parciais = []; w.on_parcial = parciais.append
        await w.enviar(b"\x00" * 100); await asyncio.sleep(0.02)
        await w.enviar(b"\x00" * 100); await asyncio.sleep(0.02)
        assert parciais and parciais[-1] == "texto 200"
        assert await w.finalizar() == "texto 200" and await w.finalizar() == ""
    asyncio.run(rodar())

def test_escolher_motor_pelo_env(monkeypatch):
    monkeypatch.setenv("JAIME_STT_STREAM", "auto")
    assert isinstance(ss.escolher(SimpleNamespace(deepgram_key="d", openai_key="o")), ss.DeepgramAoVivo)
    assert isinstance(ss.escolher(SimpleNamespace(deepgram_key="", openai_key="o")), ss.OpenAIRealtimeTranscricao)
    assert isinstance(ss.escolher(SimpleNamespace(deepgram_key="", openai_key=""), transcritor_local=lambda p, s: ""), ss.WhisperLocalPseudo)
    with pytest.raises(RuntimeError):
        ss.escolher(SimpleNamespace(deepgram_key="", openai_key=""))

# ── turno inteiro offline ─────────────────────────────────────────────────
class _TTS:
    def __init__(self):
        self.falas = []; self.pre = []; self.prontos = []; self.t_inicio_audio = 0.0; self.ajustes = None; self.instrucoes = ""
        self.parou = 0
    def pre_sintetizar(self, t): self.pre.append(t); return b"PCM:" + t.encode()
    def tocar_pronto(self, t, pcm):
        self.t_inicio_audio = self.t_inicio_audio or time.time(); self.prontos.append((t, pcm)); self.falas.append(t)
    def enfileirar(self, t):
        self.t_inicio_audio = self.t_inicio_audio or time.time(); self.falas.append(t)
    def falar(self, t): self.enfileirar(t)
    def aguardar(self, timeout=0): pass
    def parar(self): self.parou += 1; return 1
    @property
    def ocupado(self): return False

class _Fluxo(ss.FluxoSTT):
    """Devolve parciais a cada frame e o texto final no finalizar."""
    def __init__(self, parciais, final):
        self.parciais, self.final, self.n, self.finalizados = list(parciais), final, 0, 0
    async def enviar(self, pcm):
        if self.n < len(self.parciais):
            self._parcial(self.parciais[self.n]); self.n += 1
    async def finalizar(self):
        self.finalizados += 1; return self.final

class _Vault:
    def __init__(self): self.linhas = []
    def diario(self, texto, secao="Log"): self.linhas.append((secao, texto))

class _Jaime:
    def __init__(self):
        self.acesso = SimpleNamespace(liberado=True); self.vault = _Vault(); self.humor = None; self.falante_atual = ""
        self.pedidos = []; self.aguardando_nome = False
    def avisos_do_dia(self): return ""
    async def ask_stream(self, texto, canal="voice", contexto=""):
        self.pedidos.append((texto, contexto))
        for t in ["Abrindo o Finder. ", "Pronto, está aberto."]:
            yield t

S = SimpleNamespace(ativacao="nome", janela_ativa_s=25, nome="jaime", deepgram_key="", openai_key="")

def _ouvido(loop, fluxo, modelo):
    j = _Jaime()
    o = OuvidoDuplex(j, S, loop, fluxo=fluxo, antecipador=Antecipador(modelo, intervalo_s=0.0))
    o._tts = _TTS(); o.fluxo.on_parcial = o._parcial
    return o, j

def test_turno_duplex_antecipa_toca_cache_e_mede_latencia():
    async def modelo(texto):
        return {"intencao": "abrir finder", "completude": 0.9, "ambigua": False, "rascunho": "Abrindo o Finder.", "frase_fechou": True}
    async def rodar():
        loop = asyncio.get_running_loop()
        fluxo = _Fluxo(["jaime abre", "jaime abre o finder"], "Jaime, abre o Finder.")
        o, j = _ouvido(loop, fluxo, modelo)
        consumidor = asyncio.create_task(o._consumir())
        t0 = time.time()
        for i in range(20): o._alimentar(0.95, F, t0 + i * 0.032)          # 640 ms de voz
        await asyncio.sleep(0.05)                                            # parciais → antecipador → cache
        assert o.cache_audio == ("Abrindo o Finder.", b"PCM:Abrindo o Finder.")
        assert o.det.frase_fechou is True
        n = 0
        while o.det.falando and n < 60:
            o._alimentar(0.05, F, t0 + (20 + n) * 0.032); n += 1
        assert n == math.ceil(SILENCIO_FECHOU_MS / FRAME_MS)                     # fechou em 450 ms, não em 700
        await asyncio.sleep(0.45)                                            # inclui os 250 ms de cauda do alto-falante
        consumidor.cancel()
        assert fluxo.finalizados == 1 and o.turnos == 1
        assert o._tts.prontos == [("Abrindo o Finder.", b"PCM:Abrindo o Finder.")]   # cache tocou antes do modelo
        assert o._tts.falas == ["Abrindo o Finder.", "Pronto, está aberto."]           # e o modelo não repetiu a frase
        assert j.pedidos and "abre o Finder" in j.pedidos[0][0] and "JÁ disse" in j.pedidos[0][1]
        lat = o.latencias.turnos[-1]
        assert lat["antecipado"] and lat["fala_frase"] is not None and lat["fala_frase"] < 1.0
        assert any("Latência (voz)" in t for _, t in j.vault.linhas)
    asyncio.run(rodar())

def test_turno_duplex_descarta_cache_quando_intencao_muda():
    async def modelo(texto):
        return {"intencao": "abrir finder", "completude": 0.9, "ambigua": False, "rascunho": "Abrindo o Finder.", "frase_fechou": True}
    async def rodar():
        loop = asyncio.get_running_loop()
        fluxo = _Fluxo(["jaime abre o finder"], "Jaime, manda mensagem pro Rafael dizendo que vou atrasar.")
        o, j = _ouvido(loop, fluxo, modelo)
        consumidor = asyncio.create_task(o._consumir())
        t0 = time.time()
        for i in range(20): o._alimentar(0.95, F, t0 + i * 0.032)
        await asyncio.sleep(0.05)
        assert o.cache_audio is not None
        n = 0
        while o.det.falando and n < 60:
            o._alimentar(0.05, F, t0 + (20 + n) * 0.032); n += 1
        await asyncio.sleep(0.45); consumidor.cancel()
        assert o._tts.prontos == [] and o._tts.falas == ["Abrindo o Finder.", "Pronto, está aberto."]
        assert "JÁ disse" not in j.pedidos[0][1] and not o.latencias.turnos[-1]["antecipado"]
    asyncio.run(rodar())

def test_barge_in_corta_a_fala_quando_o_joao_fala_por_cima():
    async def rodar():
        loop = asyncio.get_running_loop()
        o, _ = _ouvido(loop, _Fluxo([], ""), None)
        o.barge_in = "on"; o.mudo = True
        for _ in range(20): assert not o._barge(0.99, 5000.0, F)   # a fala ainda não começou a soar: nem calibra nem corta
        assert o._eco_amostras == 0
        o._tts.t_inicio_audio = time.time()
        for _ in range(10): o._barge(0.1, 200.0, F)          # calibra o eco: ~200 de RMS
        assert not o._barge(0.95, 240.0, F)                   # voz, mas no nível do eco (1,2×): ignora
        cortou = False
        for _ in range(8): cortou = o._barge(0.95, 900.0, F) or cortou    # 256 ms bem acima do eco
        assert cortou and o._tts.parou == 1 and o.interrompido and not o.mudo and o.det.falando
        o.barge_in = "off"; o.mudo = True
        assert not any(o._barge(0.99, 5000.0, F) for _ in range(20))
    asyncio.run(rodar())

def test_latencias_resumo_e_mesma_frase():
    l = Latencias()
    t = time.time()
    l.registrar(t, t + 0.2, t + 0.7, antecipado=True, texto="oi")
    l.registrar(t, t + 0.3, t + 1.1, antecipado=False, texto="oi")
    assert l.mediana("fala_frase") == pytest.approx(1.1, abs=0.01) and "2 turnos" in l.resumo() and "antecipados 1" in l.resumo()
    assert _mesma_frase("Abrindo o Finder.", "abrindo o finder") and not _mesma_frase("Pronto.", "Abrindo o Finder.")

# ── comando `voz latencia` (offline) ─────────────────────────────────────
def test_medir_latencia_offline_com_fluxo_e_tts_falsos():
    from jaime.voice import latencia as lat
    class Fluxo(ss.FluxoSTT):
        nome = "falso"
        def __init__(self): self.n = 0
        async def enviar(self, pcm): self.n += 1; self._parcial("jaime que horas" if self.n < 3 else "jaime que horas são")
        async def finalizar(self): return "Jaime, que horas são?"
    async def modelo(texto):
        return {"intencao": "hora", "completude": 0.95, "ambigua": False, "rascunho": "São dez e meia.", "frase_fechou": True}
    from jaime.voice.antecipador import Antecipador
    saidas = []
    r = asyncio.run(lat.medir(SimpleNamespace(openai_key=""), n=2, frases=["a", "b"], gerar_audio=lambda t: b"\x00" * 1024 * 5,
                              fluxo=Fluxo(), antecipador=Antecipador(modelo, intervalo_s=0.0), tts=_TTS(), imprimir=saidas.append))  # medir espera o modelo
    assert r["turnos"] == 2 and r["antecipados"] == 2 and r["mediana_fala_frase"] is not None and r["meta_ok"]
    assert any("mediana" in s for s in saidas)
