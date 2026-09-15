"""Humor + canal → como falar.

Devolve `{"instructions": "...", "tags": [...], "eleven": {"stability": x, "style": y}}`:
- `instructions`: frase para TTS que aceita instrução de estilo (gpt-4o-mini-tts, etapa 9) e para o prompt;
- `tags`: tags de emoção para a ElevenLabs v3 (`[calm]`, `[serious]`…), quando o modelo for v3;
- `eleven`: ajustes numéricos para o flash v2.5 que usamos hoje (estabilidade alta = sério; estilo alto = expressivo)."""
from __future__ import annotations
from .humor import Humor

def prosodia(humor: Humor, canal: str = "voice") -> dict:
    e = humor.e
    rot = humor.rotulo()
    partes, tags = [], []
    if rot == "grave":
        partes += ["calmo e sério", "ritmo médio-lento", "meio tom mais baixo", "sem brincadeira"]
        tags += ["[calm]", "[serious]"]
        eleven = {"stability": 0.7, "style": 0.15}
    elif rot == "leve":
        partes += ["animado", "ritmo vivo", "leve sorriso na voz", "uma ironia seca no máximo"]
        tags += ["[cheerful]"]
        eleven = {"stability": 0.4, "style": 0.5}
    elif rot == "caloroso":
        partes += ["caloroso e próximo", "ritmo médio", "voz um pouco mais macia"]
        tags += ["[warm]"]
        eleven = {"stability": 0.5, "style": 0.4}
    elif rot == "cauteloso":
        partes += ["cauteloso", "ritmo médio", "afirma menos, pergunta mais"]
        tags += ["[hesitant]"]
        eleven = {"stability": 0.6, "style": 0.2}
    else:
        partes += ["direto e seco", "ritmo médio", "sem floreio"]
        eleven = {"stability": 0.5, "style": 0.3}
    if e.energia < 0.4:
        partes.append("energia baixa, sem pressa")
    if humor.joao_em_problema:
        partes.append("o João está com um problema: foco em resolver, nada de leveza")
    if canal != "voice":
        partes.append("por texto: frases curtas, sem markdown se for HUD")
    return {"instructions": "; ".join(partes) + ".", "tags": tags, "eleven": eleven, "rotulo": rot}
