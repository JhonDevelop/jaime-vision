"""Reconhecimento de falante com um encoder dublê (vetor = média/desvio do áudio), sem resemblyzer."""
import numpy as np
from pathlib import Path
from jaime.voice import falantes as fl

def _enc(wav):
    # "assinatura" simples: histograma normalizado de 8 faixas — vozes sintéticas diferentes dão vetores diferentes
    h, _ = np.histogram(wav, bins=8, range=(-1, 1)); h = h.astype(np.float32) + 1
    return h / np.linalg.norm(h)

def _voz(seed, seg=2.0, sr=16000):
    r = np.random.default_rng(seed); w = r.normal(0, 0.05 + 0.05 * seed, int(sr * seg)).clip(-1, 1)
    return (w * 32767).astype(np.int16).tobytes()

def test_interpretar():
    assert fl.interpretar("Jaime, aprende a minha voz") == ("aprender", "João")
    assert fl.interpretar("essa é a voz do Gabriel") == ("aprender", "Gabriel")
    assert fl.interpretar("quem está falando?") == ("quem", "")
    assert fl.interpretar("abre o Finder") is None

def test_cadastro_e_identificacao(tmp_path: Path):
    f = fl.Falantes(encoder=_enc, pasta=tmp_path)
    assert f.identificar(_voz(1)) == ("", 0.0) and f.eh_dono("")            # sem perfis: todo mundo é o dono
    assert "5 frases" in f.comecar_cadastro("João")
    for i in range(5):
        r = f.alimentar_cadastro(_voz(1))
    assert r == "Pronto: agora reconheço a voz de João." and f.conhecidos() == ["João"] and (tmp_path / "João.npy").exists()
    f.comecar_cadastro("Gabriel")
    for i in range(5): f.alimentar_cadastro(_voz(4))
    nome, s = f.identificar(_voz(1)); assert nome == "João" and s >= fl.LIMIAR
    nome, _ = f.identificar(_voz(4)); assert nome == "Gabriel"
    assert f.eh_dono("João") and not f.eh_dono("Gabriel") and not f.eh_dono("desconhecido")
    assert f.identificar(_voz(1, seg=0.5)) == ("", 0.0)                       # curto demais
    f2 = fl.Falantes(encoder=_enc, pasta=tmp_path); assert f2.conhecidos() == ["Gabriel", "João"]   # persistiu
