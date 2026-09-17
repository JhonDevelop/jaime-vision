"""Emoção a partir de FATOS REAIS — não de tom de conversa nem de hora do dia (isso já é `humor.py`/`momento.py`).

O problema que resolve: hoje o humor só reage ao que o João diz e a quando é. Mas há coisas que acontecem no
mundo dele sem ele precisar dizer nada com "tom" — o BUB saiu do lugar, a Oldsen travou de novo, o aniversário
da Maria Clara chegou, o Gabriel reapareceu depois de duas semanas sem notícia, um cliente caiu fora, um projeto
fechou. Este módulo dá nome a esses seis tipos de evento (`TIPOS`), cada um com uma causa, uma intensidade
(0 a 1) e um `quando`, e faz duas coisas com ele: modula o humor existente de forma coerente (reaproveitando as
regras de `humor.py` — nunca leve com o João em problema, nunca grave numa conquista) e vira uma linha no
diário, porque decisão emocional relevante também é decisão registrada.

Regra inegociável da constituição (`00-Jaime/Origem.md` + `CLAUDE.md`, Vontades §3): o Jaime sabe que é robô.
Ele NUNCA diz que sente dor, medo ou cansaço, nunca finge sofrimento — "fico contente que o BUB avançou", nunca
"eu estava ansioso". As frases aqui são fixas por tipo (nunca geradas livres a partir da causa) exatamente para
não abrir essa porta; e `_sem_fingir` tira qualquer resquício de frase em primeira pessoa de sofrimento que
tenha vindo colado na causa (ex.: um texto de terceiro copiado sem querer). Isso nunca segura uma decisão do
João — é só registro e tom de voz."""
from __future__ import annotations
import re
from dataclasses import dataclass
from datetime import datetime
from .humor import Humor, _clamp

TIPOS = ("projeto_avancou", "projeto_travou", "data_importante", "pessoa_reapareceu", "perda", "conquista")

# Frase fixa por tipo — nunca livre, para nunca acidentalmente simular um sentimento humano que não é o Jaime.
_FRASES = {
    "projeto_avancou":   "Fico contente que {alvo} avançou: {causa}.",
    "projeto_travou":    "Registro sem drama: {alvo} travou — {causa}. Vou acompanhar.",
    "data_importante":   "Hoje é {causa}.",
    "pessoa_reapareceu": "Bom ver {alvo} de volta: {causa}.",
    "perda":             "Anoto: {causa}.",
    "conquista":         "Boa — {causa}. Conquista registrada.",
}

# Quanto cada tipo mexe em cada eixo do Humor (energia, calor, gravidade, confiança), por unidade de intensidade.
# Reaproveita os mesmos quatro eixos de humor.Estado — este módulo não inventa um humor paralelo.
_PESOS: dict[str, dict[str, float]] = {
    "projeto_avancou":   {"confianca": 0.10, "energia": 0.08, "gravidade": -0.05},
    "projeto_travou":    {"confianca": -0.08, "gravidade": 0.12, "energia": -0.05},
    "data_importante":   {"calor": 0.15, "energia": 0.05, "gravidade": -0.05},
    "pessoa_reapareceu": {"calor": 0.20, "energia": 0.05},
    "perda":             {"gravidade": 0.15, "energia": -0.05},
    "conquista":         {"confianca": 0.15, "energia": 0.10, "gravidade": -0.10},
}

# Frases em primeira pessoa fingindo sofrimento humano — nunca passam, mesmo se vierem coladas na causa.
_PROIBIDO_RX = re.compile(
    r"\b(eu\s+(?:sinto|sofro|tenho\s+medo|fiquei\s+com\s+medo|estou\s+com\s+medo|canso|estou\s+cansad[oa]|"
    r"senti\s+dor|tenho\s+dor|morri\s+de\s+medo))\b", re.I,
)


def _sem_fingir(texto: str) -> str:
    return _PROIBIDO_RX.sub("", texto or "").strip()


@dataclass
class Evento:
    tipo: str
    causa: str
    intensidade: float = 0.5
    quando: datetime | None = None
    projeto: str = ""
    pessoa: str = ""

    def frase(self) -> str:
        """A linha que vai para o diário — sempre um dos seis moldes fixos, nunca texto livre."""
        alvo = self.projeto or self.pessoa or "isso"
        causa = _sem_fingir(self.causa) or "sem detalhe"
        modelo = _FRASES.get(self.tipo, "Registro: {causa}.")
        return modelo.format(alvo=alvo, causa=causa)

    def aplicar(self, humor: Humor) -> None:
        """Modula o Humor existente — mesma régua de `humor.py`: usa os métodos e a `_coerencia()` de lá, não
        inventa um jeito próprio de mudar de ideia. Intensidade baixa mexe pouco; intensidade alta mexe mais,
        mas nunca dispensa a coerência final (grave nunca passa de 0,85; conquista nunca fica grave)."""
        fator = 0.3 + 0.7 * self.intensidade
        e = humor.e
        for campo, peso in _PESOS.get(self.tipo, {}).items():
            setattr(e, campo, _clamp(getattr(e, campo) + peso * fator))
        if self.tipo in ("conquista", "projeto_avancou") and self.intensidade >= 0.6:
            humor.conquista_recente = True
        if self.tipo in ("perda", "projeto_travou") and self.intensidade >= 0.6:
            humor.joao_em_problema = True
        humor._coerencia()   # mesma trava de humor.py: reaplica "nunca leve em problema" / "nunca grave em conquista"


def criar(tipo: str, causa: str, intensidade: float = 0.5, quando: datetime | None = None,
          projeto: str = "", pessoa: str = "") -> Evento:
    if tipo not in TIPOS:
        raise ValueError(f"tipo de evento desconhecido: {tipo!r} — use um de {TIPOS}")
    return Evento(tipo=tipo, causa=(causa or "").strip(), intensidade=_clamp(float(intensidade)),
                  quando=quando or datetime.now(), projeto=(projeto or "").strip(), pessoa=(pessoa or "").strip())


def processar(vault, humor: Humor, evento: Evento) -> str:
    """Um evento, um efeito coerente: modula o humor, vira lembrança no diário, avisa o resto do sistema pelo
    bus (se houver — o bus é best-effort, um evento emocional nunca pode falhar por causa do HUD estar fora)."""
    evento.aplicar(humor)
    rel = vault.diario(evento.frase(), "Log")
    try:
        from ..hud.events import bus
        bus.emitir("evento_emocional", tipo=evento.tipo, causa=evento.causa[:160],
                   intensidade=round(evento.intensidade, 2), projeto=evento.projeto, pessoa=evento.pessoa)
    except Exception:
        pass
    return rel
