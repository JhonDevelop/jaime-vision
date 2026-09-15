"""Conteúdo para o @piloto.leal: cortar vídeo (ffmpeg), legendar (Deepgram → .srt), thumbnail (imagens.gerar).
O roteiro é texto — quem escreve é o modelo; aqui ficam as mãos. ffmpeg vem do pacote `static-ffmpeg`."""
from __future__ import annotations
import os, re, subprocess
from pathlib import Path

PASTA = Path(os.environ.get("JAIME_CONTEUDO", "~/Jaime/conteudo")).expanduser()

def ffmpeg() -> str:
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
    except Exception:
        pass
    import shutil
    return shutil.which("ffmpeg") or "ffmpeg"

def _segundos(t: str | float) -> float:
    if isinstance(t, (int, float)):
        return float(t)
    partes = [float(x) for x in str(t).strip().split(":")]
    return sum(p * 60 ** i for i, p in enumerate(reversed(partes)))

def cortar(video: Path, inicio: str | float, fim: str | float, saida: Path | None = None, recodificar: bool = False) -> Path:
    """Corte entre inicio e fim ('mm:ss' ou segundos). Sem recodificar = instantâneo (corta em keyframes)."""
    video = Path(video).expanduser()
    PASTA.mkdir(parents=True, exist_ok=True)
    saida = Path(saida).expanduser() if saida else PASTA / f"{video.stem}-corte-{int(_segundos(inicio))}-{int(_segundos(fim))}{video.suffix or '.mp4'}"
    cmd = [ffmpeg(), "-y", "-ss", str(_segundos(inicio)), "-to", str(_segundos(fim)), "-i", str(video)]
    cmd += (["-c:v", "libx264", "-c:a", "aac"] if recodificar else ["-c", "copy"]) + [str(saida)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0 or not saida.exists():
        raise RuntimeError(r.stderr[-300:])
    return saida

def extrair_audio(video: Path, saida: Path | None = None) -> Path:
    video = Path(video).expanduser()
    saida = Path(saida).expanduser() if saida else PASTA / f"{video.stem}.wav"
    PASTA.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([ffmpeg(), "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(saida)], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-300:])
    return saida

def _srt_tempo(s: float) -> str:
    h, rem = divmod(s, 3600); m, sec = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(sec):02d},{int(round((sec - int(sec)) * 1000)):03d}"

def montar_srt(trechos: list[dict]) -> str:
    """trechos: [{'inicio': s, 'fim': s, 'texto': str}] → conteúdo .srt"""
    linhas = []
    for i, t in enumerate(trechos, 1):
        linhas += [str(i), f"{_srt_tempo(t['inicio'])} --> {_srt_tempo(t['fim'])}", t["texto"].strip(), ""]
    return "\n".join(linhas)

async def legendar(video: Path, deepgram_key: str, saida: Path | None = None) -> Path:
    """Transcreve com a Deepgram (utterances) e escreve o .srt ao lado."""
    import httpx
    video = Path(video).expanduser()
    wav = extrair_audio(video)
    async with httpx.AsyncClient(timeout=300) as c:
        r = await c.post("https://api.deepgram.com/v1/listen?model=nova-3&language=pt-BR&smart_format=true&utterances=true",
                         headers={"Authorization": f"Token {deepgram_key}", "Content-Type": "audio/wav"}, content=wav.read_bytes())
        r.raise_for_status()
    utt = r.json().get("results", {}).get("utterances", [])
    trechos = [{"inicio": u["start"], "fim": u["end"], "texto": u["transcript"]} for u in utt]
    saida = Path(saida).expanduser() if saida else PASTA / f"{video.stem}.srt"
    saida.write_text(montar_srt(trechos), encoding="utf-8")
    return saida

def roteiro_para_cortes(roteiro: str) -> list[tuple[str, str, str]]:
    """Linhas '00:12-00:48 título' ou '[00:12 → 00:48] título' → [(inicio, fim, título)]."""
    out = []
    for l in roteiro.splitlines():
        m = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?)\s*(?:-|→|a|até)\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*[\]\-–:]?\s*(.*)$", l)
        if m:
            out.append((m.group(1), m.group(2), m.group(3).strip() or f"corte {len(out) + 1}"))
    return out
