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
        self._carregar()

    # ── modelo ────────────────────────────────────────
    def _encoder(self):
        if self._enc is None:
            import numpy as np
            if not hasattr(np, "long"):
                np.long = int          # resemblyzer 0.1.4 ainda usa np.long (sumiu no numpy 1.24)
            from resemblyzer import VoiceEncoder
            self._enc = VoiceEncoder("cpu", verbose=False)
        return self._enc

    def embedding(self, pcm16: bytes, sr: int = 16000):
        import numpy as np
        wav = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        if len(wav) < MIN_S * sr:
            return None
        enc = self._encoder()
        if hasattr(enc, "embed_utterance"):
            from resemblyzer import preprocess_wav
            return np.asarray(enc.embed_utterance(preprocess_wav(wav, source_sr=sr)), dtype=np.float32)
        return np.asarray(enc(wav), dtype=np.float32)     # dublê de teste: função wav → vetor

    # ── perfis ────────────────────────────────────────
    def _carregar(self):
        import numpy as np
        for p in self.pasta.glob("*.npy"):
            try:
                self.perfis[p.stem] = [np.load(p)]
            except Exception:
                pass

    def _salvar(self, nome: str, vetores: list):
        import numpy as np
        media = np.mean(np.stack(vetores), axis=0); media = media / (np.linalg.norm(media) + 1e-9)
        np.save(self.pasta / f"{nome}.npy", media.astype(np.float32))
        self.perfis[nome] = [media]
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
        """(nome, similaridade). 'desconhecido' quando ninguém passa do limiar; '' quando não dá para avaliar."""
        if not self.perfis:
            return "", 0.0
        e = self.embedding(pcm16, sr)
        if e is None:
            return "", 0.0
        import numpy as np
        pares = sorted(((float(np.dot(e, v[0]) / (np.linalg.norm(e) * np.linalg.norm(v[0]) + 1e-9)), n) for n, v in self.perfis.items()), reverse=True)
        melhor, nome = pares[0]
        segundo = pares[1][0] if len(pares) > 1 else -1.0
        if melhor >= LIMIAR and melhor - segundo >= MARGEM:
            self.ultimo = (nome, melhor); return nome, melhor
        self.ultimo = ("desconhecido", melhor); return "desconhecido", melhor

    def eh_dono(self, nome: str) -> bool:
        """Sem perfil do dono cadastrado, todo mundo é tratado como ele (comportamento antigo)."""
        return DONO not in self.perfis or nome in ("", DONO)
