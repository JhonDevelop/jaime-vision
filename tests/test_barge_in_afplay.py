"""Barge-in com afplay (16/09): referência de eco no ritmo da reprodução, calibração só com áudio tocando, e o
resumo 'Barge-in não cortou' no diário quando o João fala por cima e nada acontece."""
import asyncio, os, stat, sys, time, types
from types import SimpleNamespace
import pytest
from jaime.voice.duplex import OuvidoDuplex, BARGE_IN_ECO_X
from tests.test_duplex import _TTS, _Fluxo, _Jaime, S, F

def test_afplay_entrega_a_referencia_aos_poucos(tmp_path, monkeypatch):
    from jaime.voice.tts import TTS, PCM_SR
    fatias = []
    tts = TTS(SimpleNamespace(openai_key="", elevenlabs_key=""), ao_tocar=fatias.append)
    falso = tmp_path / "afplay"; falso.write_text("#!/bin/sh\nsleep 0.35\n"); falso.chmod(falso.stat().st_mode | stat.S_IEXEC)
    tts._afplay = str(falso); tts._usar_afplay = True
    pcm = b"\x01\x00" * int(PCM_SR * 0.3)                     # 300 ms de áudio
    tts._tocar(pcm)
    assert len(fatias) >= 4                                  # não veio tudo de uma vez
    assert b"".join(fatias) == pcm                           # e chegou inteiro, na ordem
    assert all(len(f) % 2 == 0 for f in fatias)

def test_resumo_no_diario_quando_a_voz_nao_corta():
    async def rodar():
        loop = asyncio.get_running_loop()
        j = _Jaime(); o = OuvidoDuplex(j, S, loop, fluxo=_Fluxo([], ""), antecipador=None)
        o._tts = _TTS(); o.barge_in = "on"; o.mudo = True; o._tts.t_inicio_audio = time.time()
        for _ in range(10): o._barge(0.1, 1500.0, F)          # eco alto (alto-falante)
        for _ in range(20): assert not o._barge(0.95, 1400.0, F)   # voz, mas ABAIXO do eco: nem energia nem sustentada
        o.mudo = False; o._fim_da_fala()
        await asyncio.sleep(0.01)
        linhas = [t for _, t in j.vault.linhas if t.startswith("Barge-in não cortou")]
        assert len(linhas) == 1 and "voz por 640 ms" in linhas[0] and f"×{BARGE_IN_ECO_X}" in linhas[0]
        assert o._barge_stats == {} and o._eco_amostras == 0
    asyncio.run(rodar())


def test_voz_sustentada_no_nivel_do_eco_corta_mesmo_sem_passar_o_limiar():
    """Vigília 16/09: voz do João por 2,6–3,3 s a 1,2× o eco e nada cortava. Eco não fica tanto tempo acima da própria média."""
    async def rodar():
        loop = asyncio.get_running_loop()
        j = _Jaime(); o = OuvidoDuplex(j, S, loop, fluxo=_Fluxo([], ""), antecipador=None)
        o._tts = _TTS(); o.barge_in = "on"; o.mudo = True; o._tts.t_inicio_audio = time.time()
        for _ in range(10): o._barge(0.1, 1500.0, F)
        cortou = [o._barge(0.95, 1750.0, F) for _ in range(24)]      # 1,17× o eco (abaixo de 1,4×), 768 ms
        assert cortou.index(True) * 32 >= 640 and o._tts.parou == 1 and o._barge_stats["motivo"] == "sustentado"
    asyncio.run(rodar())


def test_estouro_curto_acima_do_eco_nao_corta():
    """16/09 08:46–08:47: dois cortes por eco com 160 e 224 ms de 'voz' a 1,75× e 2,9× o eco. Menos de 320 ms não corta."""
    async def rodar():
        loop = asyncio.get_running_loop()
        j = _Jaime(); o = OuvidoDuplex(j, S, loop, fluxo=_Fluxo([], ""), antecipador=None)
        o._tts = _TTS(); o.barge_in = "on"; o.mudo = True; o._tts.t_inicio_audio = time.time()
        for _ in range(10): o._barge(0.1, 400.0, F)
        assert not any(o._barge(0.95, 1200.0, F) for _ in range(7))      # 224 ms a 3× o eco: estouro, não fala
        for _ in range(10): o._barge(0.1, 300.0, F)                       # silêncio: o contador esvazia
        assert o._tts.parou == 0 and o._barge_ms < 320
    asyncio.run(rodar())


def test_linha_exata_da_vigilia_0919_corta_mesmo_com_prob_e_rms_oscilando():
    """09:19: 'voz por 1696 ms, acima do eco 1376 ms, vetada 0 ms, rms 1230 vs eco 358×1.4, sim 0.85' e nenhum corte.
    Frames qualificados intercalados com frames ruins (prob/rms oscilam a cada 32 ms) precisam cortar mesmo assim."""
    async def rodar():
        loop = asyncio.get_running_loop()
        j = _Jaime(); o = OuvidoDuplex(j, S, loop, fluxo=_Fluxo([], ""), antecipador=None)
        o._tts = _TTS(); o.barge_in = "on"; o.mudo = True; o._tts.t_inicio_audio = time.time()
        for _ in range(10): o._barge(0.1, 358.0, F)                       # eco 358
        cortou_em = None
        for i in range(53):                                               # 1696 ms; 81% dos frames acima do eco (1376 ms)
            bom = (i % 5) != 4
            r = o._barge(0.95 if bom else 0.5, 1230.0 if bom else 300.0, F)
            if r: cortou_em = i * 32; break
        assert cortou_em is not None and cortou_em <= 640, cortou_em      # cortou dentro de 640 ms, não "no fim do segmento"
        assert o._tts.parou == 1 and o._barge_stats["motivo"] == "energia"
    asyncio.run(rodar())

def test_nao_cortou_diz_qual_gate_faltou():
    async def rodar():
        loop = asyncio.get_running_loop()
        j = _Jaime(); o = OuvidoDuplex(j, S, loop, fluxo=_Fluxo([], ""), antecipador=None)
        o._tts = _TTS(); o.barge_in = "on"; o.mudo = True; o._tts.t_inicio_audio = time.time()
        for _ in range(10): o._barge(0.1, 1000.0, F)
        for _ in range(15): o._barge(0.95, 1100.0, F)                     # 480 ms a 1,1×: nem energia (1,4×) nem sustentada (700)
        o.mudo = False; o._fim_da_fala(); await asyncio.sleep(0.01)
        l = next(t for _, t in j.vault.linhas if t.startswith("Barge-in não cortou"))
        assert "janela máx 0/320 ms, sustentada máx 0/700 ms, vad máx 480/640 ms, piso de voz máx 100%/50%" in l    # 1,1×: nem 1,4× nem 1,15×
    asyncio.run(rodar())


def test_linha_exata_da_vigilia_0946_vad_esparso_corta_pela_energia():
    """09:46: 'voz por 864 ms, acima do eco 832 ms, vetada 0, rms 1321 vs eco 335×1.4, sim 0.81, janela máx 224/320'.
    O João fala junto com o áudio do Jaime: o VAD dispara em 1 de cada 4 frames, mas o rms fica 3,9× acima do eco o tempo todo."""
    async def rodar():
        loop = asyncio.get_running_loop()
        j = _Jaime(); o = OuvidoDuplex(j, S, loop, fluxo=_Fluxo([], ""), antecipador=None)
        o._tts = _TTS(); o.barge_in = "on"; o.mudo = True; o._tts.t_inicio_audio = time.time()
        for _ in range(10): o._barge(0.1, 335.0, F)
        cortou_em = None
        for i in range(60):
            r = o._barge(0.95 if i % 4 == 0 else 0.4, 1321.0, F)
            if r: cortou_em = i * 32; break
        assert cortou_em is not None and cortou_em <= 352 and o._barge_stats["motivo"] == "energia"
    asyncio.run(rodar())

def test_eco_alto_do_proprio_jaime_nao_corta_pela_sustentada():
    """A janela sustentada não usa VAD: o eco do próprio Jaime oscila em torno de 1,0× da média — abaixo de 1,15× não conta."""
    async def rodar():
        loop = asyncio.get_running_loop()
        j = _Jaime(); o = OuvidoDuplex(j, S, loop, fluxo=_Fluxo([], ""), antecipador=None)
        o._tts = _TTS(); o.barge_in = "on"; o.mudo = True; o._tts.t_inicio_audio = time.time()
        for _ in range(10): o._barge(0.9, 1000.0, F)
        assert not any(o._barge(0.9, 1000.0 * (1.1 if i % 2 else 0.9), F) for i in range(60))   # 2 s de eco oscilando
        assert o._tts.parou == 0
    asyncio.run(rodar())


def test_linha_exata_da_vigilia_1009_toque_de_telefone_nao_corta():
    """10:09: 'cortou (energia): voz 64 ms, rms máx 3202 vs eco 349, sim 0.39' — era o telefone tocando. Energia 9× o eco,
    mas quase nenhum frame com probabilidade de voz: o piso de VAD (≥ 0,3 em ≥ 50 % da janela) segura."""
    async def rodar():
        loop = asyncio.get_running_loop()
        j = _Jaime(); o = OuvidoDuplex(j, S, loop, fluxo=_Fluxo([], ""), antecipador=None)
        o._tts = _TTS(); o.barge_in = "on"; o.mudo = True; o._tts.t_inicio_audio = time.time()
        for _ in range(10): o._barge(0.1, 349.0, F)
        assert not any(o._barge(0.9 if i in (7, 8) else 0.05, 3202.0, F) for i in range(40))   # 1,3 s de toque, 2 frames "voz"
        assert o._tts.parou == 0 and o._barge_stats["piso_max"] < 0.5
        # o João falando junto (VAD esparso, mas ≥ 0,3 na maior parte) continua cortando
        for _ in range(25): o._barge(0.05, 200.0, F)
        cortou = any(o._barge(0.95 if i % 4 == 0 else 0.45, 1321.0, F) for i in range(30))
        assert cortou and o._tts.parou == 1
    asyncio.run(rodar())
