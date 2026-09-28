"""Configuração da expansão espacial — tudo opt-in e desligado por padrão (`JAIME_SPATIAL=off`).

Lida do ambiente na hora (não do `Settings` global) para os testes poderem montar configurações isoladas.
Nomes das variáveis vêm do pacote (`.env.spatial.example`); os valores extras são da casa."""
from __future__ import annotations
import os
from dataclasses import dataclass, field

MODOS = ("off", "sim", "replay", "camera")


def _on(v: str) -> bool:
    return (v or "").strip().lower() in ("1", "on", "sim", "true", "yes")


@dataclass
class ConfigEspacial:
    modo: str = "off"                      # off | sim (landmarks sintéticos) | replay (JSONL) | camera (webcam real)
    cameras: list[str] = field(default_factory=lambda: ["0"])
    dry_run: bool = True                   # ações no SO só em prévia até calibração + testes de segurança
    fila: int = 2                          # frames na fila; cheia → descarta o MAIS VELHO
    confianca_min: float = 0.85            # para propor ação no SO (o HUD aceita menos)
    rastreio_conf_min: float = 0.65
    calibracao: str = ""
    replay: str = ""
    cenario: str = "demo"
    repetir: bool = True                   # sim/replay em laço (demo contínua no HUD)
    espelhar: bool = True
    hz_efemero: float = 30.0               # teto de eventos efêmeros (cursor/drag) por segundo no bus
    perda_s: float = 0.25                  # mão ausente por mais que isso = tracking perdido
    ttl_referencia_s: float = 20.0         # "isso" vale até quanto tempo depois da seleção

    @property
    def ativo(self) -> bool:
        return self.modo != "off"

    @classmethod
    def do_ambiente(cls, env=None) -> "ConfigEspacial":
        e = os.environ if env is None else env
        g = lambda k, d="": (e.get(k, "") or "").strip() or d
        modo = g("JAIME_SPATIAL", "off").lower()
        if modo in ("on", "1", "true"):
            modo = "camera"
        if modo not in MODOS:
            modo = "off"
        return cls(
            modo=modo,
            cameras=[c.strip() for c in g("JAIME_SPATIAL_CAMERA_IDS", "0").split(",") if c.strip()],
            dry_run=_on(g("JAIME_SPATIAL_DRY_RUN", "on")),
            fila=max(1, min(8, int(g("JAIME_SPATIAL_FRAME_QUEUE", "2")))),
            confianca_min=float(g("JAIME_SPATIAL_MIN_CONFIDENCE", "0.85")),
            calibracao=g("JAIME_SPATIAL_CALIBRATION_FILE"),
            replay=g("JAIME_SPATIAL_REPLAY"),
            cenario=g("JAIME_SPATIAL_CENARIO", "demo"),
            repetir=_on(g("JAIME_SPATIAL_REPETIR", "on")),
            espelhar=_on(g("JAIME_SPATIAL_ESPELHAR", "on")),
            ttl_referencia_s=float(g("JAIME_SPATIAL_TTL_S", "20")),
        )
