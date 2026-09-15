"""Humor do Jaime — estado afetivo em quatro eixos (0 a 1): energia, calor, gravidade, confiança.

Muda com: resultado das tarefas, tom do João, hora do dia, momento (aniversário, semana pesada).
Regras de coerência (não negociáveis):
  - nunca leve quando o João está em problema;
  - nunca grave em conquista;
  - erro próprio baixa a confiança um pouco e sobe a gravidade um pouco — sem drama.
É expressão coerente com a cena, não manipulação: não simula angústia, não cria dependência."""
from __future__ import annotations
import re
from dataclasses import dataclass, asdict
from datetime import datetime

TOM_RX = {
    "em_problema": re.compile(r"\b(problema|urgente|socorro|perdi|quebrou|caiu|n[aã]o funciona|deu ruim|travou|sumiu|preciso de ajuda|me ajuda)\b", re.I),
    "irritado":    re.compile(r"\b(droga|caramba|porra|merda|que saco|de novo isso|t[aá] errado|errado|n[aã]o era isso|refaz)\b", re.I),
    "animado":     re.compile(r"\b(consegui|fechou|deu certo|funcionou|boa|show|top|demais|excelente|perfeito|obrigado|valeu)\b", re.I),
}

def detectar_tom(texto: str) -> str:
    """em_problema > irritado > animado > neutro (o problema pesa mais que a irritação)."""
    for tom in ("em_problema", "irritado", "animado"):
        if TOM_RX[tom].search(texto or ""):
            return tom
    return "neutro"

def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))

@dataclass
class Estado:
    energia: float = 0.6
    calor: float = 0.6
    gravidade: float = 0.3
    confianca: float = 0.7

class Humor:
    def __init__(self):
        self.e = Estado()
        self.joao_em_problema = False
        self.conquista_recente = False
        self.atualizado = datetime.now()

    # ── entradas ──────────────────────────────────────
    def registrar_tom(self, tom: str) -> None:
        e = self.e
        if tom == "em_problema":
            self.joao_em_problema, self.conquista_recente = True, False
            e.calor = _clamp(e.calor + 0.2); e.gravidade = _clamp(max(e.gravidade, 0.6)); e.energia = _clamp(min(e.energia, 0.5))
        elif tom == "irritado":
            self.conquista_recente = False
            e.gravidade = _clamp(e.gravidade + 0.15); e.energia = _clamp(e.energia - 0.1); e.calor = _clamp(e.calor + 0.05)
        elif tom == "animado":
            self.joao_em_problema, self.conquista_recente = False, True
            e.energia = _clamp(e.energia + 0.2); e.calor = _clamp(e.calor + 0.1); e.gravidade = _clamp(min(e.gravidade, 0.3))
        else:
            # neutro: o problema passa devagar, a conquista também
            self.joao_em_problema = self.joao_em_problema and e.gravidade > 0.55
            e.gravidade = _clamp(e.gravidade - 0.05)
        self._coerencia()

    def registrar_resultado(self, sucesso: bool, grave: bool = False) -> None:
        e = self.e
        if sucesso:
            e.confianca = _clamp(e.confianca + 0.05); e.energia = _clamp(e.energia + 0.03)
        else:
            # erro próprio: assume, sem dramatizar — gravidade sobe pouco, confiança cai pouco
            e.confianca = _clamp(e.confianca - (0.15 if grave else 0.07))
            e.gravidade = _clamp(max(e.gravidade, 0.6 if grave else 0.45))
            e.energia = _clamp(e.energia - 0.05)
            self.conquista_recente = False
        self._coerencia()

    def registrar_hora(self, hora: int) -> None:
        e = self.e
        if hora < 7 or hora >= 22:
            e.energia = _clamp(min(e.energia, 0.45))
        elif 9 <= hora <= 11:
            e.energia = _clamp(e.energia + 0.05)
        self._coerencia()

    def registrar_momento(self, peso: str, aniversario: bool = False) -> None:
        e = self.e
        if aniversario:
            e.calor = _clamp(e.calor + 0.3); e.energia = _clamp(e.energia + 0.2); e.gravidade = _clamp(min(e.gravidade, 0.25))
        elif peso == "pesado":
            e.gravidade = _clamp(max(e.gravidade, 0.5)); e.energia = _clamp(e.energia - 0.05)
        elif peso == "leve":
            e.energia = _clamp(e.energia + 0.1)
        self._coerencia()

    # ── regras ────────────────────────────────────────
    def _coerencia(self) -> None:
        e = self.e
        if self.joao_em_problema:           # nunca leve com o João em problema
            e.gravidade = max(e.gravidade, 0.6); e.energia = min(e.energia, 0.55)
        if self.conquista_recente:          # nunca grave em conquista
            e.gravidade = min(e.gravidade, 0.35)
        e.gravidade = min(e.gravidade, 0.85)   # sem drama, nunca
        self.atualizado = datetime.now()

    # ── leitura ───────────────────────────────────────
    def rotulo(self) -> str:
        e = self.e
        if e.gravidade >= 0.6:
            return "grave"
        if e.energia >= 0.7 and e.gravidade <= 0.35:
            return "leve"
        if e.calor >= 0.75:
            return "caloroso"
        if e.confianca <= 0.45:
            return "cauteloso"
        return "neutro"

    def dados(self) -> dict:
        return {**{k: round(v, 2) for k, v in asdict(self.e).items()}, "rotulo": self.rotulo(),
                "joao_em_problema": self.joao_em_problema, "conquista_recente": self.conquista_recente}

    def texto(self) -> str:
        e = self.e
        return (f"humor: {self.rotulo()} (energia {e.energia:.0%}, calor {e.calor:.0%}, gravidade {e.gravidade:.0%}, "
                f"confiança {e.confianca:.0%})")
