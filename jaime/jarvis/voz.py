"""Frases que abrem as cenas do Jarvis sem passar pelo modelo (resposta em milissegundos, frase inteira ancorada):

- "bom dia" (manhã, 1ª vez) / "me dá o briefing"          → briefing (vídeo de 1:22)
- "ativar monitor" / "ativa o monitor"                    → rosto + relatório do treino (vídeo do monitor)
- "cria/abre/mostra um holograma do/da <objeto>"          → holograma 3D controlado pela mão (vídeo do carro)
- "fecha o holograma"                                     → fecha
- "aprende meu rosto" / "esquece meu rosto"               → cadastro do rosto (cortesia, nunca chave)
- "modo partículas" / "modo fios" / "orbe de partículas"  → estilo do orbe (vídeo da esfera de partículas)
"""
from __future__ import annotations
import re, unicodedata

MONITOR_RX = re.compile(r"^\s*(jarvis|jaime)?[,\s]*(ativar|ativa|ative|liga|ligar|abre|abrir)\s+(o\s+)?monitor\s*[.!]*\s*$", re.I)
HOLO_RX = re.compile(r"^\s*(jarvis|jaime)?[,\s]*(cria|crie|criar|faz|faca|faça|fazer|abre|abrir|mostra|mostrar|gera|gerar|monta|montar)"
                     r"\s+(pra mim\s+|para mim\s+)?(um|uma|o|a)?\s*holograma\s+(de|do|da|dos|das)\s+(?P<obj>[\w\s\-çãõáéíóúâêô]+?)"
                     r"(\s*,?\s*(pra|para)\s+(que\s+)?eu\s+.*)?\s*[.!?]*\s*$", re.I)
FECHA_HOLO_RX = re.compile(r"^\s*(fecha|fechar|some com|tira)\s+(o\s+)?holograma\s*[.!]*\s*$", re.I)
APRENDE_ROSTO_RX = re.compile(r"^\s*(jaime|jarvis)?[,\s]*(aprende|aprenda|cadastra|cadastre|grava|memoriza)\s+(o\s+)?meu\s+rosto\s*[.!]*\s*$", re.I)
ESQUECE_ROSTO_RX = re.compile(r"^\s*(jaime|jarvis)?[,\s]*(esquece|esqueça|apaga|apague)\s+(o\s+)?meu\s+rosto\s*[.!]*\s*$", re.I)
ORBE_RX = re.compile(r"^\s*(modo|orbe( de| em)?|esfera( de)?)\s+(?P<estilo>part[ií]culas|fios|energia)\s*[.!]*\s*$", re.I)


def _n(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn").strip()


def cena(texto: str) -> tuple[str, dict] | None:
    """('monitor'|'holograma'|'fecha_holograma'|'aprende_rosto'|'esquece_rosto'|'orbe', args) ou None."""
    t = (texto or "").strip()
    if MONITOR_RX.match(t):
        return "monitor", {}
    if (m := HOLO_RX.match(t)):
        return "holograma", {"objeto": m.group("obj").strip()}
    if FECHA_HOLO_RX.match(t):
        return "fecha_holograma", {}
    if APRENDE_ROSTO_RX.match(t):
        return "aprende_rosto", {}
    if ESQUECE_ROSTO_RX.match(t):
        return "esquece_rosto", {}
    if (m := ORBE_RX.match(t)):
        e = _n(m.group("estilo"))
        return "orbe", {"estilo": "particulas" if e.startswith("part") else "fios"}
    return None
