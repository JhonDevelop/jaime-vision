"""M-04 (MENTE.md): o modelo do antecipador leva 3,7–5,4 s por parecer — o cache da 1ª frase nunca existia (0/10).
Rascunho LOCAL para pedidos comuns + pré-síntese enquanto o João fala + espera curta pela síntese em curso."""
import asyncio, math, time
from types import SimpleNamespace
from jaime.voice.antecipador import Antecipador, Antecipacao, heuristico, rascunho_local
from jaime.voice.duplex import OuvidoDuplex, SILENCIO_FECHOU_MS, PRE_SINTESES_POR_TURNO
from jaime.voice.escuta import FRAME_MS
from tests.test_duplex import _TTS, _Fluxo, _Jaime, S, F

def test_rascunho_local_para_pedidos_comuns():
    assert rascunho_local("Jaime, abre o Finder.") == ("abrir Finder", "Abrindo o Finder.")
    assert rascunho_local("jaime abre o site da oldsen") == ("abrir site da oldsen", "Abrindo o site da oldsen.")
    assert rascunho_local("Ô Jaime, quem me mandou mensagem?")[1] == "Deixa eu ver as mensagens."
    assert rascunho_local("manda mensagem pro rafael dizendo que vou atrasar")[1] == "Preparando a mensagem para Rafael."
    assert rascunho_local("qual a previsão do tempo para amanhã")[1] == "Deixa eu ver o tempo."
    assert rascunho_local("cria uma tarefa para ligar pro contador")[1] == "Criando a tarefa."
    assert rascunho_local("quanto está o dólar")[1] == "Deixa eu ver a cotação."
    assert rascunho_local("me lembra de beber água em vinte minutos")[1] == "Anotando o lembrete."
    assert rascunho_local("manda um resumo do dia")[1] == "Vou resumir o dia."
    assert rascunho_local("oi tudo bem") == ("", "") and rascunho_local("Jaime, está aí?") == ("", "")

def test_heuristica_so_especula_com_frase_fechada():
    a = Antecipacao(texto="x", **heuristico("jaime abre o finder"))
    assert a.especulavel and a.rascunho == "Abrindo o finder." and a.acao_prevista == "abrir finder"
    b = Antecipacao(texto="x", **heuristico("jaime abre o"))           # termina em artigo: ainda vai continuar
    assert not b.especulavel and b.rascunho == "" and not b.frase_fechou
    c = Antecipacao(texto="x", **heuristico("jaime abre o finder e"))  # conjunção solta: idem
    assert not c.especulavel and c.rascunho == ""

def _rodar_turno(o, parciais_n=20, cauda=0.45):
    async def _r():
        consumidor = asyncio.create_task(o._consumir())
        t0 = time.time()
        for i in range(parciais_n): o._alimentar(0.95, F, t0 + i * 0.032)
        await asyncio.sleep(0.05)
        n = 0
        while o.det.falando and n < 60:
            o._alimentar(0.05, F, t0 + (parciais_n + n) * 0.032); n += 1
        await asyncio.sleep(cauda); consumidor.cancel()
    return _r()

def test_sem_modelo_o_rascunho_local_vira_cache_e_toca_primeiro():
    async def rodar():
        loop = asyncio.get_running_loop()
        j = _Jaime(); fluxo = _Fluxo(["jaime abre", "jaime abre o finder"], "Jaime, abre o Finder.")
        o = OuvidoDuplex(j, S, loop, fluxo=fluxo, antecipador=Antecipador(None, intervalo_s=0.0))   # só heurística
        o._tts = _TTS(); o.fluxo.on_parcial = o._parcial
        await _rodar_turno(o)
        assert o._tts.pre == ["Abrindo o finder."]                                      # sintetizou enquanto ele falava
        assert o._tts.prontos == [("Abrindo o finder.", b"PCM:Abrindo o finder.")]      # e tocou do cache
        assert o._tts.falas == ["Abrindo o finder.", "Pronto, está aberto."]            # o modelo não repetiu a frase
        assert "JÁ disse" in j.pedidos[0][1] and o.latencias.turnos[-1]["antecipado"]
    asyncio.run(rodar())

def test_fim_de_turno_espera_a_sintese_em_curso():
    class _TTSLento(_TTS):
        def pre_sintetizar(self, t): time.sleep(0.3); return super().pre_sintetizar(t)
    async def rodar():
        loop = asyncio.get_running_loop()
        j = _Jaime(); fluxo = _Fluxo(["jaime abre o finder"], "Jaime, abre o Finder.")
        o = OuvidoDuplex(j, S, loop, fluxo=fluxo, antecipador=Antecipador(None, intervalo_s=0.0))
        o._tts = _TTSLento(); o.fluxo.on_parcial = o._parcial
        await _rodar_turno(o, cauda=0.9)
        assert o._tts.prontos == [("Abrindo o finder.", b"PCM:Abrindo o finder.")]
    asyncio.run(rodar())

def test_cache_de_outra_intencao_nao_toca_e_some():
    async def modelo(texto):
        return {"intencao": "abrir finder", "completude": 0.9, "ambigua": False, "rascunho": "Abrindo o Finder.", "frase_fechou": True}
    async def rodar():
        loop = asyncio.get_running_loop()
        j = _Jaime(); fluxo = _Fluxo(["jaime abre o finder"], "Jaime, manda mensagem pro Rafael dizendo que vou atrasar.")
        o = OuvidoDuplex(j, S, loop, fluxo=fluxo, antecipador=Antecipador(modelo, intervalo_s=0.0))
        o._tts = _TTS(); o.fluxo.on_parcial = o._parcial
        await _rodar_turno(o)
        assert o._tts.prontos == [] and o.cache_audio is None                         # não tocou e não sobrou para o próximo turno
    asyncio.run(rodar())

def test_no_maximo_duas_pre_sinteses_por_turno():
    async def rodar():
        loop = asyncio.get_running_loop()
        j = _Jaime()
        fluxo = _Fluxo(["jaime abre o finder", "jaime abre o finder e o terminal", "jaime abre o finder e o terminal e o safari"],
                       "Jaime, abre o Finder e o Terminal e o Safari.")
        o = OuvidoDuplex(j, S, loop, fluxo=fluxo, antecipador=Antecipador(None, intervalo_s=0.0))
        o._tts = _TTS(); o.fluxo.on_parcial = o._parcial
        await _rodar_turno(o)
        assert len(o._tts.pre) == PRE_SINTESES_POR_TURNO == 2
    asyncio.run(rodar())

def _linha_latencia(j):
    return next(t for _, t in j.vault.linhas if "Latência (voz)" in t)

def test_diario_diz_por_que_a_antecipacao_foi_ou_nao_usada():
    async def rodar():
        loop = asyncio.get_running_loop()
        # usada
        j = _Jaime(); fluxo = _Fluxo(["jaime abre o finder"], "Jaime, abre o Finder.")
        o = OuvidoDuplex(j, S, loop, fluxo=fluxo, antecipador=Antecipador(None, intervalo_s=0.0)); o._tts = _TTS(); o.fluxo.on_parcial = o._parcial
        await _rodar_turno(o)
        assert "antecipado · antecipação: usada: «Abrindo o finder.»" in _linha_latencia(j)
        # não bateu
        j = _Jaime(); fluxo = _Fluxo(["jaime abre o finder"], "Jaime, manda mensagem pro Rafael.")
        o = OuvidoDuplex(j, S, loop, fluxo=fluxo, antecipador=Antecipador(None, intervalo_s=0.0)); o._tts = _TTS(); o.fluxo.on_parcial = o._parcial
        await _rodar_turno(o)
        l = _linha_latencia(j); assert "antecipação: não bateu: «jaime abre o finder»" in l and "antecipado ·" not in l
        # sem rascunho
        j = _Jaime(); fluxo = _Fluxo(["jaime tudo bem com você"], "Jaime, tudo bem com você?")
        o = OuvidoDuplex(j, S, loop, fluxo=fluxo, antecipador=Antecipador(None, intervalo_s=0.0)); o._tts = _TTS(); o.fluxo.on_parcial = o._parcial
        await _rodar_turno(o)
        assert "antecipação: sem rascunho (heuristica, completude" in _linha_latencia(j)
    asyncio.run(rodar())

# ── M-11: fim de turno não pode cortar o João no meio ────────────────────────────────
def test_tres_palavras_soltas_nao_fecham_o_turno():
    for t in ("Estudar é muito bom Jaime, parabéns mas eu preciso", "você sabe sobre o meu", "jaime me manda", "eu quero que você"):
        h = heuristico(t); assert not h["frase_fechou"], t
    assert heuristico("Jaime, abre o Finder.")["frase_fechou"]            # pontuação final: fechou
    assert heuristico("jaime abre o finder")["frase_fechou"]              # pedido reconhecido: fechou
    assert not heuristico("jaime tudo bem com você hoje")["frase_fechou"]  # solto, sem pontuação: espera o incerto (700 ms)
