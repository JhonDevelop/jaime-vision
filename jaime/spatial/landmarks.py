"""Contratos de percepção: CameraFrame e HandPose, e a conversão pose → amostra do gesto.

Convenção dos 21 landmarks: a do MediaPipe Hands (0 punho, 4 ponta do polegar, 5 base do indicador,
8 ponta do indicador, 17 base do mínimo). Coordenadas normalizadas da imagem (x, y em 0..1; z relativo ao punho,
SEM unidade métrica — "nunca fingir profundidade métrica a partir de z normalizado de uma webcam").

Frames brutos vivem só em memória, pelo tempo de um ciclo; não vão para SSE, vault nem log."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from .core import SpatialCore, SpatialObject, Vec3

POLEGAR, INDICADOR, BASE_INDICADOR, BASE_MINIMO, PUNHO = 4, 8, 5, 17, 0
Ponto = tuple[float, float, float]


@dataclass
class CameraFrame:
    camera_id: str
    frame_id: int
    capture_ts: float                    # relógio monotônico do servidor no momento da captura
    pixels: Any = None                   # numpy (fonte real) — nunca serializado
    poses: list["HandPose"] | None = None  # fonte simulada/replay já entrega landmarks
    calib_version: int = 0
    wall_ms: float = 0.0                 # time.time()*1000 — para medir até o render no navegador (mesma máquina)
    media_ts: float | None = None        # relógio DA MÍDIA (replay/sim): gestos e filtros usam este tempo, não o de parede

    @property
    def ts(self) -> float:
        return self.capture_ts if self.media_ts is None else self.media_ts


@dataclass
class HandPose:
    landmarks: list[Ponto]
    hand_id: str = "right"               # "left" | "right" (lateralidade do rastreador, já corrigida do espelho)
    confidence: float = 1.0
    actor: str = "desconhecido"          # só vira "joao" depois da autenticação existente (servico decide)
    camera_id: str = "0"
    occluded: bool = False
    source_cameras: tuple[str, ...] = field(default_factory=tuple)

    def valida(self) -> bool:
        return len(self.landmarks) == 21 and all(len(p) == 3 for p in self.landmarks)

    def to_dict(self) -> dict:
        return {"hand": self.hand_id, "conf": round(self.confidence, 3),
                "lm": [[round(c, 4) for c in p] for p in self.landmarks]}


def _dist2(a: Ponto, b: Ponto) -> float:
    # largura da palma e pinça medidas no PLANO da imagem: z normalizado da webcam é ruidoso e sem escala
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def largura_palma(lm: list[Ponto]) -> float:
    return _dist2(lm[BASE_INDICADOR], lm[BASE_MINIMO])


def razao_pinca(lm: list[Ponto]) -> float:
    """Distância polegar–indicador relativa à largura da palma: invariante à distância da mão até a câmera."""
    w = largura_palma(lm)
    return _dist2(lm[POLEGAR], lm[INDICADOR]) / w if w > 1e-6 else float("inf")


def ponto_de_mira(lm: list[Ponto], espelhar: bool = True) -> tuple[float, float]:
    """Onde a mão "aponta" no HUD: o meio entre polegar e indicador (estável durante a pinça, ao contrário
    da ponta do indicador sozinha, que salta quando os dedos se fecham). Espelhado como um espelho: mover a mão
    para a direita move o cursor para a direita."""
    x = (lm[POLEGAR][0] + lm[INDICADOR][0]) / 2
    y = (lm[POLEGAR][1] + lm[INDICADOR][1]) / 2
    return ((1.0 - x) if espelhar else x, y)


def alvo_em(core: SpatialCore, x: float, y: float, folga: float = 1.0) -> SpatialObject | None:
    """Objeto sob o cursor (mais próximo dentro do raio). Sem alvo quando dois empatam de perto: melhor não
    selecionar do que selecionar o errado."""
    candidatos = []
    for o in core.objects.values():
        d = ((o.position.x - x) ** 2 + (o.position.y - y) ** 2) ** 0.5
        if d <= o.radius * o.scale * folga:
            candidatos.append((d, o))
    if not candidatos:
        return None
    candidatos.sort(key=lambda c: c[0])
    if len(candidatos) > 1 and candidatos[1][0] - candidatos[0][0] < 0.005:
        return None
    return candidatos[0][1]


def cursor(lm: list[Ponto], espelhar: bool = True) -> Vec3:
    x, y = ponto_de_mira(lm, espelhar)
    return Vec3(x, y, 0.0)
