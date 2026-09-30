"""Bibliotecas de visão da tela Jarvis guardadas NESTA máquina (sem depender de CDN na hora de usar).

`python -m jaime jarvis baixar` busca, uma vez, no registro do npm (versões fixas):
- face-api 1.7.15 (rosto: detector, 68 pontos, descritor) → ~7 MB;
- MediaPipe tasks-vision 0.10.14 (mãos: bundle + wasm) → ~12 MB;
- o modelo hand_landmarker.task (7,8 MB) do Google (e o face_landmarker.task, 3,7 MB, para o olhar); se o Google não responder, do pacote npm que o embute,
  conferindo que é o zip com os dois modelos certos.
Fica em `~/Jaime/jarvis-vendor/` (JAIME_JARVIS_VENDOR). A tela usa daqui; sem os arquivos, cai para o CDN.
"""
from __future__ import annotations
import io, json, os, tarfile, zipfile
from pathlib import Path
import httpx

PASTA = Path(os.environ.get("JAIME_JARVIS_VENDOR", "~/Jaime/jarvis-vendor")).expanduser()
NPM = "https://registry.npmjs.org"
FACE = ("@vladmandic/face-api", "1.7.15", {
    "package/dist/face-api.js": "face-api.js",
    **{f"package/model/{n}": f"modelos/{n}" for n in (
        "tiny_face_detector_model-weights_manifest.json", "tiny_face_detector_model.bin",
        "face_landmark_68_model-weights_manifest.json", "face_landmark_68_model.bin",
        "face_recognition_model-weights_manifest.json", "face_recognition_model.bin")}})
MAOS = ("@mediapipe/tasks-vision", "0.10.14", {
    "package/vision_bundle.mjs": "vision_bundle.mjs",
    "package/wasm/vision_wasm_internal.js": "wasm/vision_wasm_internal.js",
    "package/wasm/vision_wasm_internal.wasm": "wasm/vision_wasm_internal.wasm",
    "package/wasm/vision_wasm_nosimd_internal.js": "wasm/vision_wasm_nosimd_internal.js",
    "package/wasm/vision_wasm_nosimd_internal.wasm": "wasm/vision_wasm_nosimd_internal.wasm"})
MODELO_MAO = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MODELO_MAO_NPM = ("expo-vision-camera-v4-mediapipe", "package/hand_landmarker.task")
MODELO_ROSTO = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
MODELO_POSE = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
PERMITIDOS = {v for _, _, m in (FACE, MAOS) for v in m.values()} | {"hand_landmarker.task", "face_landmarker.task", "pose_landmarker_lite.task", "ok.json"}


def _tarball(c: httpx.Client, pacote: str, versao: str | None) -> bytes:
    meta = c.get(f"{NPM}/{pacote.replace('/', '%2f')}").raise_for_status().json()
    v = versao or meta["dist-tags"]["latest"]
    return c.get(meta["versions"][v]["dist"]["tarball"]).raise_for_status().content


def _extrair(dados: bytes, mapa: dict, destino: Path) -> list[str]:
    feitos = []
    with tarfile.open(fileobj=io.BytesIO(dados), mode="r:gz") as t:
        for membro, alvo in mapa.items():
            f = t.extractfile(membro)
            if f is None:
                raise FileNotFoundError(membro)
            p = destino / alvo
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(f.read()); feitos.append(alvo)
    return feitos


def modelo_mao_valido(dados: bytes) -> bool:
    try:
        nomes = set(zipfile.ZipFile(io.BytesIO(dados)).namelist())
        return {"hand_detector.tflite", "hand_landmarks_detector.tflite"} <= nomes
    except zipfile.BadZipFile:
        return False


def baixar(destino: Path | None = None, http: httpx.Client | None = None, log=print) -> dict:
    destino = destino or PASTA
    destino.mkdir(parents=True, exist_ok=True)
    c = http or httpx.Client(timeout=120, follow_redirects=True)
    feito: dict = {}
    for pacote, versao, mapa in (FACE, MAOS):
        log(f"→ {pacote}@{versao}")
        feito[pacote] = _extrair(_tarball(c, pacote, versao), mapa, destino)
    modelo = b""
    try:
        r = c.get(MODELO_MAO); r.raise_for_status(); modelo = r.content; origem = "google"
    except Exception:
        log("→ Google fora do ar daqui; tentando o pacote npm que embute o modelo")
        pacote, membro = MODELO_MAO_NPM
        with tarfile.open(fileobj=io.BytesIO(_tarball(c, pacote, None)), mode="r:gz") as t:
            modelo = t.extractfile(membro).read(); origem = f"npm:{pacote}"
    if not modelo_mao_valido(modelo):
        raise ValueError("hand_landmarker.task inválido (não tem os dois modelos esperados)")
    (destino / "hand_landmarker.task").write_bytes(modelo)
    feito["hand_landmarker.task"] = origem
    try:                                   # braços (pose): opcional — sem ele a tela usa o do Google na hora
        r = c.get(MODELO_POSE); r.raise_for_status()
        if zipfile.is_zipfile(io.BytesIO(r.content)):
            (destino / "pose_landmarker_lite.task").write_bytes(r.content); feito["pose_landmarker_lite.task"] = "google"
    except Exception as e:
        log(f"→ modelo dos braços não baixou ({type(e).__name__}); a tela usa o do Google quando ligar")
    try:                                   # olhar (íris): opcional — sem ele a tela usa o do Google na hora
        r = c.get(MODELO_ROSTO); r.raise_for_status()
        if {"face_detector.tflite", "face_landmarks_detector.tflite"} <= set(zipfile.ZipFile(io.BytesIO(r.content)).namelist()):
            (destino / "face_landmarker.task").write_bytes(r.content); feito["face_landmarker.task"] = "google"
    except Exception as e:
        log(f"→ modelo do olhar não baixou ({type(e).__name__}); a tela usa o do Google quando ligar")
    (destino / "ok.json").write_text(json.dumps({"face": FACE[1], "maos": MAOS[1], "modelo_mao": origem}), encoding="utf-8")
    log(f"✔ tudo em {destino}")
    return feito


def arquivo(nome: str, pasta: Path | None = None) -> Path | None:
    if nome not in PERMITIDOS:
        return None
    base = (pasta or PASTA).resolve()
    p = (base / nome).resolve()
    return p if base in p.parents and p.is_file() else None
