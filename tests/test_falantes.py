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


# ── três zonas (P-0003): áudio ruim do João é "incerto", não "desconhecido" ─────────────────
def _enc_angulo(wav):
    # dublê controlável: o 1º sample codifica um ângulo (graus) → vetor unitário; similaridade = cos(Δ)
    ang = np.deg2rad(float(wav[0]) * 32768.0 / 100.0)
    return np.array([np.cos(ang), np.sin(ang)], dtype=np.float32)

def _pcm_angulo(graus, seg=2.0, sr=16000):
    w = np.zeros(int(sr * seg), dtype=np.int16); w[0] = int(graus * 100); return w.tobytes()

def test_tres_zonas_ema_e_amostras(tmp_path: Path, monkeypatch):
    f = fl.Falantes(encoder=_enc_angulo, pasta=tmp_path)
    f.comecar_cadastro("João")
    for g in (0, 4, -4, 2, -2): f.alimentar_cadastro(_pcm_angulo(g))
    assert (tmp_path / "João.amostras.npy").exists()
    assert len(f.perfis["João"]) == 6                                          # centróide + 5 amostras
    assert f.identificar(_pcm_angulo(0))[0] == "João"                          # limpo: aceita
    assert f.identificar(_pcm_angulo(80))[0] == "desconhecido"                 # cos 80° ≈ 0,17: outra pessoa
    nome, s = f.identificar(_pcm_angulo(50))                                   # cos 46° (melhor amostra) ≈ 0,69: zona do meio
    assert nome == "incerto" and fl.REJEITAR <= s < fl.LIMIAR and not f.eh_dono("incerto")
    nome, s2 = f.identificar(_pcm_angulo(30))                                  # repetiu melhor: EMA 0,6×0,90 + 0,4×0,69 ≈ 0,82 → João
    assert nome == "João" and s2 >= fl.LIMIAR
    # a média móvel não atravessa um "desconhecido" nem uma fala aceita
    assert f.identificar(_pcm_angulo(50))[0] == "incerto"
    assert f.identificar(_pcm_angulo(80))[0] == "desconhecido"
    assert f.identificar(_pcm_angulo(50))[0] == "incerto"
    # e expira: duas incertas separadas por mais que a janela não somam
    t = [1000.0]; monkeypatch.setattr(fl.time, "time", lambda: t[0])
    assert f.identificar(_pcm_angulo(50))[0] == "incerto"
    t[0] += fl.EMA_JANELA_S + 1
    assert f.identificar(_pcm_angulo(50))[0] == "incerto"
    # perfil antigo (só o centróide, sem .amostras.npy) continua carregando
    (tmp_path / "João.amostras.npy").unlink()
    f2 = fl.Falantes(encoder=_enc_angulo, pasta=tmp_path); assert len(f2.perfis["João"]) == 1 and f2.identificar(_pcm_angulo(0))[0] == "João"
