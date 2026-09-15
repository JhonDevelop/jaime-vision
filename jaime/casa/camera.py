"""Câmera como olho: um quadro da webcam do Mac (ffmpeg/avfoundation) ou de uma câmera do Home Assistant.
O quadro vai para `~/Jaime/capturas/camera.png`; o modelo o lê com Read e descreve o que vê."""
from __future__ import annotations
import os, subprocess
from pathlib import Path

PASTA = Path(os.environ.get("JAIME_CAPTURAS", "~/Jaime/capturas")).expanduser()

def _ffmpeg() -> str:
    try:
        import static_ffmpeg; static_ffmpeg.add_paths()
    except Exception:
        pass
    import shutil
    return shutil.which("ffmpeg") or "ffmpeg"

def quadro_webcam(indice: str = "0", saida: Path | None = None) -> Path:
    """macOS: avfoundation. O sistema pede permissão de Câmera para o Terminal na primeira vez."""
    PASTA.mkdir(parents=True, exist_ok=True)
    saida = saida or PASTA / "camera.png"
    cmd = [_ffmpeg(), "-y", "-f", "avfoundation", "-framerate", "30", "-video_size", "1280x720", "-i", f"{indice}:none",
           "-frames:v", "1", "-update", "1", str(saida)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if r.returncode != 0 or not saida.exists():
        raise RuntimeError(r.stderr[-300:])
    return saida

async def quadro(casa, camera: str, saida: Path | None = None) -> Path:
    """`camera`: índice numérico (webcam) ou entity_id (camera.xxx do HA)."""
    if camera.startswith("camera."):
        dados = await casa.snapshot_camera(camera)
        PASTA.mkdir(parents=True, exist_ok=True)
        saida = saida or PASTA / "camera.png"; saida.write_bytes(dados); return saida
    return quadro_webcam(camera, saida)
