"""Inventário do host para a expansão espacial: SO, CPU, RAM, GPU/VRAM, câmeras, monitores, engines locais e frota.

Só LÊ. Não liga câmera (lista dispositivos), não instala nada, não abre porta. Não registra serial, chave nem
token: o que sai daqui pode ir para um relatório. `python -m jaime espacial inventario`."""
from __future__ import annotations
import importlib.util, json, os, platform, re, shutil, socket, subprocess
from pathlib import Path


def _rodar(cmd: list[str], timeout: float = 15) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, "", f"{type(e).__name__}"


def cpu() -> dict:
    d = {"arch": platform.machine(), "nucleos": os.cpu_count(), "modelo": platform.processor() or ""}
    if platform.system() == "Darwin":
        _, out, _ = _rodar(["sysctl", "-n", "machdep.cpu.brand_string"])
        d["modelo"] = out.strip() or d["modelo"]
    return d


def ram_gb() -> float | None:
    try:
        import psutil
        return round(psutil.virtual_memory().total / 2**30, 1)
    except Exception:
        return None


def gpus() -> list[dict]:
    out: list[dict] = []
    if shutil.which("nvidia-smi"):
        rc, txt, _ = _rodar(["nvidia-smi", "--query-gpu=name,memory.total,driver_version,compute_cap", "--format=csv,noheader,nounits"])
        for linha in txt.strip().splitlines() if rc == 0 else []:
            p = [x.strip() for x in linha.split(",")]
            if len(p) >= 3:
                out.append({"nome": p[0], "vram_gb": round(float(p[1]) / 1024, 1) if p[1].replace(".", "").isdigit() else None,
                            "driver": p[2], "cuda": True, "compute_cap": p[3] if len(p) > 3 else ""})
    if platform.system() == "Darwin":
        rc, txt, _ = _rodar(["system_profiler", "SPDisplaysDataType", "-json"], timeout=25)
        try:
            for g in json.loads(txt).get("SPDisplaysDataType", []) if rc == 0 else []:
                out.append({"nome": g.get("sppci_model") or g.get("_name"), "vram": g.get("spdisplays_vram") or g.get("spdisplays_vram_shared"),
                            "metal": g.get("spdisplays_mtlgpufamilysupport", ""), "cuda": False})
        except json.JSONDecodeError:
            pass
    return out


def cameras() -> dict:
    """Lista dispositivos de vídeo SEM abrir a câmera (ffmpeg -list_devices)."""
    try:
        from ..casa.camera import _ffmpeg
        ff = _ffmpeg()
    except Exception:
        ff = shutil.which("ffmpeg") or ""
    if not ff:
        return {"lista": [], "obs": "ffmpeg ausente"}
    so = platform.system()
    if so == "Darwin":
        _, _, err = _rodar([ff, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""])
        video = err.split("audio devices")[0] if "audio devices" in err else err
        return {"lista": [{"indice": int(i), "nome": n.strip()} for i, n in re.findall(r"\[(\d+)\]\s+(.+)", video)
                          if "Capture screen" not in n], "obs": "permissão de Câmera é dada ao app que roda o Jaime (Terminal/iTerm)"}
    if so == "Windows":
        _, _, err = _rodar([ff, "-hide_banner", "-f", "dshow", "-list_devices", "true", "-i", "dummy"])
        nomes = re.findall(r'"([^"]+)"\s+\(video\)', err)
        return {"lista": [{"indice": i, "nome": n} for i, n in enumerate(nomes)], "obs": "Configurações › Privacidade › Câmera"}
    devs = sorted(str(p) for p in Path("/dev").glob("video*"))
    return {"lista": [{"indice": i, "nome": d} for i, d in enumerate(devs)], "obs": ""}


def _porta_aberta(porta: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, porta), timeout=0.3):
            return True
    except OSError:
        return False


def engines_locais() -> dict:
    return {"ollama": {"binario": bool(shutil.which("ollama")), "porta_11434": _porta_aberta(11434)},
            "lm_studio": {"binario": bool(shutil.which("lms")), "porta_1234": _porta_aberta(1234)},
            "openshell": {"binario": bool(shutil.which("openshell"))},
            "pair": {"obs": "PAIR (beta) cita RTX 20+ e Apple M4+ — não roda em Mac Intel; verificar num nó RTX da frota"}}


def pacotes() -> dict:
    return {m: importlib.util.find_spec(m) is not None for m in ("cv2", "mediapipe", "sympy", "Quartz", "numpy", "httpx")}


def frota(vault: Path | None) -> dict:
    if not vault:
        return {"maquinas": [], "obs": "sem vault"}
    p = Path(vault) / "01-Estado" / "Frota.md"
    if not p.exists():
        return {"maquinas": [], "obs": "sem 01-Estado/Frota.md"}
    linhas = [l for l in p.read_text(encoding="utf-8", errors="ignore").splitlines() if l.startswith("|")][2:]
    maquinas = []
    for l in linhas:
        c = [x.strip() for x in l.strip("|").split("|")]
        if len(c) >= 4 and c[1]:
            maquinas.append({"apelido": c[0], "host": c[1], "dono": c[2], "nivel": c[3]})
    return {"maquinas": maquinas, "obs": "" if maquinas else "frota vazia: nenhum nó RTX cadastrado"}


def coletar(vault: Path | None = None) -> dict:
    from .telas import listar
    ds, origem = listar()
    g = gpus()
    return {"so": {"sistema": platform.system(), "versao": platform.release(), "python": platform.python_version()},
            "cpu": cpu(), "ram_gb": ram_gb(), "gpus": g, "cuda": any(x.get("cuda") for x in g),
            "cameras": cameras(), "monitores": {"backend": origem, "lista": [d.to_dict() for d in ds]},
            "engines_locais": engines_locais(), "pacotes": pacotes(), "frota": frota(vault)}
