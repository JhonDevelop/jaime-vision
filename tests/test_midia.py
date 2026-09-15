"""Imagens (cliente dublê), Blender (script + detecção), vídeo (ffmpeg estático num vídeo sintético), SRT, Vigia na tela."""
import asyncio, base64, shutil, subprocess
from pathlib import Path
import pytest
import jaime.maos.imagens as im
from jaime.maos import blender, conteudo, computador
from jaime.vigia.hooks import Vigia

def test_gerar_imagem_com_dublê(tmp_path, monkeypatch):
    monkeypatch.setattr(im, "PASTA", tmp_path / "img")
    class D:
        def __init__(self): self.images = self
        def generate(self, **k): self.k = k; return type("R", (), {"data": [type("I", (), {"b64_json": base64.b64encode(b"PNG").decode()})()]})()
    d = D(); i = im.Imagens("x", cliente=d)
    p = i.gerar("logo da estamparia, minimalista", "thumbnail")
    assert p.exists() and p.read_bytes() == b"PNG" and d.k["size"] == "1536x1024" and p.name.startswith("logo-da-estamparia")
    assert not im.Imagens("", cliente=None).disponivel

def test_blender_script_e_sem_binario(tmp_path, monkeypatch):
    monkeypatch.setattr(blender, "PASTA", tmp_path / "3d"); monkeypatch.setattr(blender, "CANDIDATOS", ["/nao/existe"])
    r = blender.gerar_blend("cubo", "bpy.ops.mesh.primitive_cube_add(size=2)")
    assert not r["ok"] and "blender.org" in r["erro"] and Path(r["script"]).exists()
    s = Path(r["script"]).read_text()
    assert "import bpy" in s and "primitive_cube_add" in s and "save_as_mainfile" in s

def test_srt_e_roteiro():
    srt = conteudo.montar_srt([{"inicio": 0.0, "fim": 2.5, "texto": "Oi"}, {"inicio": 61.2, "fim": 63.0, "texto": "Tchau"}])
    assert "1\n00:00:00,000 --> 00:00:02,500\nOi" in srt and "00:01:01,200 --> 00:01:03,000" in srt
    assert conteudo.roteiro_para_cortes("00:12-00:48 abertura\n[01:00 → 01:30] gancho\nsem tempo") == [("00:12", "00:48", "abertura"), ("01:00", "01:30", "gancho")]

@pytest.mark.skipif(not shutil.which("ffmpeg") and not __import__("importlib").util.find_spec("static_ffmpeg"), reason="sem ffmpeg")
def test_cortar_video_sintetico(tmp_path, monkeypatch):
    monkeypatch.setattr(conteudo, "PASTA", tmp_path / "c")
    ff = conteudo.ffmpeg()
    v = tmp_path / "in.mp4"
    subprocess.run([ff, "-y", "-f", "lavfi", "-i", "testsrc=duration=4:size=160x120:rate=10", "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(v)], check=True, capture_output=True, timeout=120)
    saida = conteudo.cortar(v, "00:01", "00:03", recodificar=True)
    assert saida.exists() and saida.stat().st_size > 0
    wav = conteudo.extrair_audio(v, tmp_path / "a.wav")
    assert wav.exists() and wav.stat().st_size > 1000

def test_vigia_segura_acoes_na_tela_mas_libera_captura():
    v = Vigia()
    h = lambda n, a: asyncio.run(v.pre_tool_use({"tool_name": n, "tool_input": a}, None, None))
    assert h("mcp__tela__tela_clicar", {"x": 1, "y": 1}).get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
    assert h("mcp__tela__tela_digitar", {"texto": "x"}).get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
    assert h("mcp__tela__tela_capturar", {}) == {}
    v.armar(); assert h("mcp__tela__tela_tecla", {"combo": "enter"}) == {}

def test_captura_de_tela_somente(tmp_path, monkeypatch):
    monkeypatch.setattr(computador, "PASTA", tmp_path); monkeypatch.setattr(computador, "ULTIMA", tmp_path / "tela.png")
    try:
        p = computador.capturar("teste")
    except Exception as e:
        pytest.skip(f"screencapture indisponível aqui: {e}")
    assert p.exists() and p.stat().st_size > 0
