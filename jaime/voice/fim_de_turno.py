"""Fim de turno pelo ÁUDIO — para o J.A.I.M.E parar de cortar o João quando ele respira.

O problema, com a causa medida no código: o Deepgram roda com `punctuate=true` e `smart_format=true`, então
põe ponto final em quase toda pausa. A heurística do antecipador vê pontuação, marca `frase_fechou=True`, e
o DetectorFim corta em 450 ms — no meio da respiração do João. O texto não tem como distinguir uma pausa
para respirar de um ponto final de verdade, porque essa diferença não está no texto: está na prosódia, no
áudio.

A saída é ouvir o áudio. O Smart Turn v3 (pipecat-ai, BSD-2) é um modelo pequeno que olha os últimos 8 s e
diz a probabilidade de a pessoa ter terminado. Roda local, em CPU: medido nesta máquina, 64 ms por decisão.

Como ele entra no fluxo:
    1. o Silero acusa a pausa (já era assim);
    2. em vez de decidir por pontuação, este módulo olha o áudio e diz completo ou incompleto;
    3. incompleto → espera de verdade, mesmo com o Deepgram tendo posto um ponto;
    4. rede de segurança: passou de `TETO_SILENCIO_MS` em silêncio, fecha assim mesmo — o João travou de fato.

Nada aqui pode emudecer o Jaime: sem modelo, sem onnxruntime ou com erro, `disponivel` é False e o turno
volta a decidir pela heurística de antes. Um detector de fim de turno que quebra a escuta é pior que
nenhum. `JAIME_FIM_TURNO=off` desliga."""
from __future__ import annotations
import os, threading, time
from pathlib import Path

MODELO = Path(os.environ.get(
    "JAIME_FIM_TURNO_MODELO", str(Path.home() / "Jaime/modelos/smart-turn-v3.2-cpu.onnx")))
LIGADO = os.environ.get("JAIME_FIM_TURNO", "on").lower() not in ("off", "0", "false")
SR = 16000
JANELA_S = 8                       # o que o modelo enxerga: os últimos 8 s
LIMIAR = float(os.environ.get("JAIME_FIM_TURNO_LIMIAR", "0.5"))
TETO_SILENCIO_MS = int(os.environ.get("JAIME_FIM_TURNO_TETO_MS", "2500"))


class FimDeTurno:
    """Diz se o João terminou de falar, ouvindo o áudio em vez de ler a pontuação."""

    def __init__(self, caminho: Path | None = None, limiar: float = LIMIAR):
        self.caminho = Path(caminho or MODELO)
        self.limiar = limiar
        self._sessao = None
        self._extrator = None
        self._lock = threading.Lock()
        self._erro = ""
        self.ultima_prob = 0.0
        self.ultimo_ms = 0.0
        self.decisoes = 0

    # ── carregamento preguiçoso: não atrasa o boot ───────────────────────
    def _carregar(self) -> bool:
        if self._sessao is not None:
            return True
        if self._erro:
            return False
        try:
            import numpy as np  # noqa: F401
            import onnxruntime as ort
            from transformers import WhisperFeatureExtractor
        except Exception as e:
            self._erro = f"falta dependência: {type(e).__name__}"
            return False
        if not self.caminho.is_file():
            self._erro = f"modelo não está em {self.caminho}"
            return False
        try:
            so = ort.SessionOptions()
            so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            so.inter_op_num_threads = 1
            so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self._sessao = ort.InferenceSession(str(self.caminho), sess_options=so,
                                                providers=["CPUExecutionProvider"])
            self._extrator = WhisperFeatureExtractor(chunk_length=JANELA_S)
        except Exception as e:
            self._erro = f"não carregou: {type(e).__name__}: {e}"
            self._sessao = None
            return False
        return True

    @property
    def disponivel(self) -> bool:
        """Carrega o modelo se ainda não carregou. NÃO chame no caminho quente: a 1ª vez leva ~1 s."""
        return LIGADO and self._carregar()

    @property
    def pronto(self) -> bool:
        """Já está carregado? Sem efeito colateral, seguro de chamar a cada frame."""
        return LIGADO and self._sessao is not None

    def aquecer(self) -> None:
        """Carrega em segundo plano, no boot, para a primeira decisão não custar 1 s no meio da fala."""
        threading.Thread(target=self._carregar, daemon=True).start()

    @property
    def porque_nao(self) -> str:
        return "" if self.disponivel else (self._erro or ("desligado em JAIME_FIM_TURNO" if not LIGADO else "?"))

    # ── a decisão ────────────────────────────────────────────────────────
    def probabilidade(self, pcm16: bytes) -> float | None:
        """Chance de o falante ter terminado (0..1). `None` quando não dá para decidir pelo áudio."""
        if not self.disponivel or not pcm16:
            return None
        import numpy as np
        try:
            x = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        except ValueError:
            return None
        if x.size < SR // 4:                       # menos de 250 ms não dá para julgar prosódia
            return None
        x = x[-SR * JANELA_S:]                     # o fim é o que importa: é lá que está a entoação
        t0 = time.time()
        try:
            with self._lock:                       # uma sessão ONNX só; duas threads ao mesmo tempo a corrompem
                f = self._extrator(x, sampling_rate=SR, return_tensors="np", padding="max_length",
                                   max_length=SR * JANELA_S, truncation=True, do_normalize=True)
                feat = np.expand_dims(f.input_features.squeeze(0).astype(np.float32), 0)
                saida = self._sessao.run(None, {"input_features": feat})
            p = float(saida[0][0].item())
        except Exception as e:
            self._erro = f"falhou ao decidir: {type(e).__name__}"
            self._sessao = None                    # da próxima vez tenta carregar de novo
            return None
        self.ultimo_ms = (time.time() - t0) * 1000
        self.ultima_prob = p
        self.decisoes += 1
        return p

    def fechou(self, pcm16: bytes, silencio_ms: int = 0) -> bool | None:
        """`True` terminou, `False` ainda está falando, `None` decida pelo jeito antigo.

        A rede de segurança existe porque o modelo erra: se ele insiste em "incompleto" mas o silêncio já
        passou do teto, o João parou de fato — hesitou, se distraiu, largou a frase. Esperar mais que isso
        é o Jaime ficando mudo na cara dele, que é pior do que cortar."""
        p = self.probabilidade(pcm16)
        if p is None:
            return None
        if p >= self.limiar:
            return True
        if silencio_ms >= TETO_SILENCIO_MS:
            return True
        return False

    def estado(self) -> str:
        if not self.disponivel:
            return f"fim de turno pelo áudio: desligado ({self.porque_nao})"
        return (f"fim de turno pelo áudio: ligado · {self.decisoes} decisões · "
                f"última {self.ultima_prob:.2f} em {self.ultimo_ms:.0f} ms · limiar {self.limiar}")
