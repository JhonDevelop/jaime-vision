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
        for _ in range(20): assert not o._barge(0.95, 2000.0, F)   # voz do João, mas abaixo de 1,8× o eco
        o.mudo = False; o._fim_da_fala()
        await asyncio.sleep(0.01)
        linhas = [t for _, t in j.vault.linhas if t.startswith("Barge-in não cortou")]
        assert len(linhas) == 1 and "voz por 640 ms" in linhas[0] and f"×{BARGE_IN_ECO_X}" in linhas[0]
        assert o._barge_stats == {} and o._eco_amostras == 0
    asyncio.run(rodar())
