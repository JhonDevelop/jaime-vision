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
        cortou = [o._barge(0.95, 1600.0, F) for _ in range(24)]      # 1,07× o eco, 768 ms
        assert cortou.index(True) * 32 >= 640 and o._tts.parou == 1 and o._barge_stats["motivo"] == "sustentado"
    asyncio.run(rodar())
