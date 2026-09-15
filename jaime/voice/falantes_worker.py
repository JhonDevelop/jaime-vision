"""Worker do reconhecimento de falante — processo separado, só com torch/resemblyzer.

Por quê: torch 2.2.2 e onnxruntime (Silero) no mesmo processo segfaultaram o servidor em 15/09. Aqui o torch fica
sozinho; o servidor conversa por stdin/stdout em JSON, uma linha por pedido:
  {"cmd": "embed", "pcm": "<base64 int16>", "sr": 16000}  →  {"ok": true, "vetor": [..256 floats..]}
  {"cmd": "ping"}                                          →  {"ok": true}
Uso: `.venv/bin/python -m jaime.voice.falantes_worker` (o Falantes sobe isto sozinho)."""
from __future__ import annotations
import base64, json, sys

def main() -> int:
    import numpy as np, warnings
    with warnings.catch_warnings():                 # o próprio hasattr(np, "long") emite FutureWarning no numpy 2
        warnings.simplefilter("ignore", FutureWarning)
        if not hasattr(np, "long"):
            np.long = int
    from resemblyzer import VoiceEncoder, preprocess_wav
    enc = VoiceEncoder("cpu", verbose=False)
    sys.stdout.write(json.dumps({"ok": True, "pronto": True}) + "\n"); sys.stdout.flush()
    for linha in sys.stdin:
        try:
            req = json.loads(linha)
            if req.get("cmd") == "ping":
                resp = {"ok": True}
            elif req.get("cmd") == "embed":
                pcm = np.frombuffer(base64.b64decode(req["pcm"]), dtype=np.int16).astype(np.float32) / 32768.0
                v = enc.embed_utterance(preprocess_wav(pcm, source_sr=int(req.get("sr", 16000))))
                resp = {"ok": True, "vetor": [float(x) for x in v]}
            else:
                resp = {"ok": False, "erro": "cmd desconhecido"}
        except Exception as e:
            resp = {"ok": False, "erro": f"{type(e).__name__}: {str(e)[:120]}"}
        sys.stdout.write(json.dumps(resp) + "\n"); sys.stdout.flush()
    return 0

if __name__ == "__main__":
    sys.exit(main())
