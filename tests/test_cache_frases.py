import os
import time
from types import SimpleNamespace

from jaime.voice.cache_frases import CacheFrases
from jaime.voice.tts import TTS


def test_cache_acerta_e_erra_e_chave_muda_com_voz(tmp_path):
    cache = CacheFrases(tmp_path, motor="openai", voz="onyx", velocidade=1.15, instrucoes="calmo")
    assert cache.get("Estou aqui, senhor.") is None
    cache.put("Estou aqui, senhor.", b"pcm")
    assert cache.get("Estou aqui, senhor.") == b"pcm"
    outro = CacheFrases(tmp_path, motor="openai", voz="nova", velocidade=1.15, instrucoes="calmo")
    assert outro.get("Estou aqui, senhor.") is None


def test_cache_poda_lru_e_ignora_texto_longo(tmp_path):
    cache = CacheFrases(tmp_path, max_arquivos=2)
    cache.put("um", b"1"); time.sleep(0.01)
    cache.put("dois", b"2"); assert cache.get("um") == b"1"  # torna "um" o mais recente
    time.sleep(0.01); cache.put("tres", b"3")
    assert cache.get("um") == b"1" and cache.get("dois") is None and cache.get("tres") == b"3"
    cache.put("x" * 81, b"longo")
    assert len(list(tmp_path.glob("*.pcm"))) == 2


def test_pre_sintetizar_usa_cache_e_texto_longo_nao_entra(tmp_path, monkeypatch):
    monkeypatch.setenv("JAIME_CACHE_FRASES", str(tmp_path))
    tts = TTS(SimpleNamespace(openai_key="", elevenlabs_key="", elevenlabs_voice=""))
    chamadas = []
    def sintetizar(texto, **_):
        chamadas.append(texto); return b"pcm:" + texto.encode()
    tts._sintetizar = sintetizar
    assert tts.pre_sintetizar("Pode escrever.") == b"pcm:Pode escrever."
    assert tts.pre_sintetizar("Pode escrever.") == b"pcm:Pode escrever."
    longo = "x" * 81
    tts.pre_sintetizar(longo); tts.pre_sintetizar(longo)
    assert chamadas[0] == "Pode escrever." and len(chamadas) == 3 and chamadas[1] == chamadas[2]


def test_cache_desligado_por_env(tmp_path, monkeypatch):
    monkeypatch.setenv("JAIME_CACHE_FRASES", "off")
    cache = CacheFrases(tmp_path)
    cache.put("Pode escrever.", b"pcm")
    assert cache.get("Pode escrever.") is None and not list(tmp_path.glob("*.pcm"))


def test_fluxo_grava_cache_sem_atrasar_blocos(tmp_path, monkeypatch):
    monkeypatch.setenv("JAIME_CACHE_FRASES", str(tmp_path))
    tts = TTS(SimpleNamespace(openai_key="", elevenlabs_key="", elevenlabs_voice=""))
    chamadas = []
    def sintetizar(texto, **_):
        chamadas.append(texto)
        return iter((b"um", b"dois"))
    tts._sintetizar = sintetizar
    assert b"".join(tts._sintetizar_com_cache("Estou aqui, senhor.", streaming=True)) == b"umdois"
    for _ in range(50):
        if tts._cache_frases.get("Estou aqui, senhor."):
            break
        time.sleep(0.01)
    assert tts._sintetizar_com_cache("Estou aqui, senhor.", streaming=True) == b"umdois"
    assert chamadas == ["Estou aqui, senhor."]
