"""Reconhecimento de quem fala — João, Gabriel, ou desconhecido.

Embedding de voz (resemblyzer, d-vector GE2E, local, sem nuvem) por fala; comparação por cosseno com os perfis
guardados em `~/Jaime/vozes/<nome>.npy` (média dos exemplos). Cadastro por voz: "Jaime, aprende a minha voz" →
as próximas 5 falas do João viram perfil; "essa é a voz do Gabriel" → as próximas 5 de quem falar viram Gabriel.

O que muda com o falante:
- o modelo recebe `[falante: Gabriel]` e responde a ele pelo nome, como sócio — sem executar o irreversível e sem
  revelar o que é privado do João;
- palavra-passe e "confirmo" só valem na voz do João (quando o perfil dele existe);
- o HUD mostra quem falou. `encoder` é injetável para teste."""
from __future__ import annotations
import json, os, re, time
from pathlib import Path

PASTA = Path(os.environ.get("JAIME_VOZES", "~/Jaime/vozes")).expanduser()
LIMIAR = 0.75            # similaridade mínima para dizer "é fulano"
REJEITAR = 0.55          # abaixo disto é outra pessoa; entre REJEITAR e LIMIAR é "incerto" (áudio ruim, não estranho)
EMA = 0.6                # peso da fala atual na média móvel entre tentativas seguidas (P-0003)
EMA_JANELA_S = 20.0      # duas falas mais distantes que isto não se somam
MARGEM = 0.05            # e precisa vencer o segundo colocado por isto
EXEMPLOS = 5             # falas para fechar um cadastro
MIN_S = 1.2              # falas mais curtas que isto não identificam nem cadastram
DONO = "João"

APRENDER_RX = re.compile(r"\b(aprende|aprenda|grava|guarda|memoriza|reconhece)\s+(a\s+)?(minha|a minha)\s+voz\b", re.I)
VOZ_DE_RX = re.compile(r"\b(ess[ae]|est[ae])\s+(é|e)\s+a\s+voz\s+d[oa]\s+([A-Za-zÀ-ÿ][\wÀ-ÿ-]{1,24})\b|\baprende\s+a\s+voz\s+d[oa]\s+([A-Za-zÀ-ÿ][\wÀ-ÿ-]{1,24})\b", re.I)
QUEM_FALA_RX = re.compile(r"\b(quem\s+(est[aá]|t[aá])\s+falando|reconhece(u)?\s+(a\s+)?minha\s+voz|sabe\s+quem\s+(sou|eu\s+sou))\b", re.I)

def interpretar(texto: str) -> tuple[str, str] | None:
    t = (texto or "").strip()
    if APRENDER_RX.search(t):
        return "aprender", DONO
    if (m := VOZ_DE_RX.search(t)):
        return "aprender", (m.group(3) or m.group(4)).strip().capitalize()
    if QUEM_FALA_RX.search(t):
        return "quem", ""
    return None

class Falantes:
    def __init__(self, encoder=None, pasta: Path = PASTA):
        self.pasta = Path(pasta); self.pasta.mkdir(parents=True, exist_ok=True)
        self._enc = encoder
        self.perfis: dict[str, list] = {}
        self.cadastrando: tuple[str, list] | None = None      # (nome, embeddings já coletados)
        self.ultimo: tuple[str, float] = ("", 0.0)
        self._ema: tuple[str, float, float] = ("", 0.0, 0.0)     # (nome, score suavizado, quando) da última fala incerta
        self._carregar()

    # ── modelo ────────────────────────────────────────
    def _encoder(self):
        """Encoder num PROCESSO separado (falantes_worker): torch junto do onnxruntime segfaultava o servidor."""
        if self._enc is None:
            import subprocess, sys, json, threading
            proc = subprocess.Popen([sys.executable, "-m", "jaime.voice.falantes_worker"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, text=True, bufsize=1)
            pronto = proc.stdout.readline()               # {"ok": true, "pronto": true} depois de carregar o modelo
            if not pronto or not json.loads(pronto).get("ok"):
                raise RuntimeError("worker de voz não subiu")
            lock = threading.Lock()
            def pedir(req: dict) -> dict:
                with lock:
                    proc.stdin.write(json.dumps(req) + "\n"); proc.stdin.flush()
                    return json.loads(proc.stdout.readline() or '{"ok": false, "erro": "worker caiu"}')
            self._enc = pedir; self._proc = proc
        return self._enc

    def embedding(self, pcm16: bytes, sr: int = 16000):
        import base64, numpy as np
        wav = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        if len(wav) < MIN_S * sr:
            return None
        enc = self._encoder()
        if getattr(enc, "__name__", "") == "pedir":
            r = enc({"cmd": "embed", "pcm": base64.b64encode(pcm16).decode(), "sr": sr})
            return np.asarray(r["vetor"], dtype=np.float32) if r.get("ok") else None
        return np.asarray(enc(wav), dtype=np.float32)     # dublê de teste: função wav → vetor

    # ── perfis ────────────────────────────────────────
    def _carregar(self):
        import numpy as np
        for p in self.pasta.glob("*.npy"):
            if p.stem.endswith(".amostras"):
                continue
            try:
                vetores = [np.load(p)]
                amostras = p.with_name(f"{p.stem}.amostras.npy")
                if amostras.exists():                      # as 5 frases do cadastro: o score usa a melhor delas também
                    vetores += list(np.load(amostras))
                self.perfis[p.stem] = vetores
            except Exception:
                pass

    def _salvar(self, nome: str, vetores: list):
        import numpy as np
        media = np.mean(np.stack(vetores), axis=0); media = media / (np.linalg.norm(media) + 1e-9)
        np.save(self.pasta / f"{nome}.npy", media.astype(np.float32))
        np.save(self.pasta / f"{nome}.amostras.npy", np.stack(vetores).astype(np.float32))
        self.perfis[nome] = [media] + list(vetores)
        meta = self.pasta / "vozes.json"
        d = json.loads(meta.read_text()) if meta.exists() else {}
        d[nome] = {"exemplos": len(vetores), "quando": time.strftime("%Y-%m-%d %H:%M")}
        meta.write_text(json.dumps(d, ensure_ascii=False, indent=1))

    def conhecidos(self) -> list[str]:
        return sorted(self.perfis)

    # ── cadastro ──────────────────────────────────────
    def comecar_cadastro(self, nome: str) -> str:
        self.cadastrando = (nome, [])
        return (f"Certo. Vou aprender a voz de {nome} nas próximas {EXEMPLOS} falas — fale normalmente, frases inteiras."
                if nome != DONO else f"Certo, senhor. Fale normalmente por {EXEMPLOS} frases que eu aprendo a sua voz.")

    def alimentar_cadastro(self, pcm16: bytes, sr: int = 16000) -> str | None:
        """Devolve uma mensagem quando o cadastro fecha (ou None enquanto coleta)."""
        if not self.cadastrando:
            return None
        e = self.embedding(pcm16, sr)
        if e is None:
            return None
        nome, vetores = self.cadastrando
        vetores.append(e)
        if len(vetores) >= EXEMPLOS:
            self._salvar(nome, vetores); self.cadastrando = None
            return f"Pronto: agora reconheço a voz de {nome}."
        return None

    # ── identificação ─────────────────────────────────
    def identificar(self, pcm16: bytes, sr: int = 16000) -> tuple[str, float]:
        """(nome, similaridade). Três zonas (P-0003): ≥ LIMIAR é a pessoa; < REJEITAR é 'desconhecido'; no meio é
        'incerto' — áudio ruim de alguém conhecido, não um estranho. Falas incertas seguidas (≤ EMA_JANELA_S) somam numa
        média móvel: repetir a frase pode fechar a decisão. '' quando não dá para avaliar."""
        if not self.perfis:
            return "", 0.0
        e = self.embedding(pcm16, sr)
        if e is None:
            return "", 0.0
        import numpy as np
        ne = np.linalg.norm(e) + 1e-9
        def sim(v): return float(np.dot(e, v) / (ne * np.linalg.norm(v) + 1e-9))
        # score = max(centróide, melhor amostra do cadastro): um só embedding médio pune quem varia o jeito de falar
        pares = sorted(((max(sim(v) for v in vs), n) for n, vs in self.perfis.items()), reverse=True)
        melhor, nome = pares[0]
        segundo = pares[1][0] if len(pares) > 1 else -1.0
        if melhor >= LIMIAR and melhor - segundo >= MARGEM:
            self._ema = ("", 0.0, 0.0); self.ultimo = (nome, melhor); return nome, melhor
        if melhor < REJEITAR:
            self._ema = ("", 0.0, 0.0); self.ultimo = ("desconhecido", melhor); return "desconhecido", melhor
        agora = time.time()
        n_ant, s_ant, t_ant = self._ema
        score = EMA * melhor + (1 - EMA) * s_ant if n_ant == nome and agora - t_ant <= EMA_JANELA_S else melhor
        self._ema = (nome, score, agora)
        if score >= LIMIAR and melhor - segundo >= MARGEM:
            self.ultimo = (nome, score); return nome, score
        self.ultimo = ("incerto", score); return "incerto", score

    def eh_dono(self, nome: str) -> bool:
        """Sem perfil do dono cadastrado, todo mundo é tratado como ele (comportamento antigo)."""
        return DONO not in self.perfis or nome in ("", DONO)
