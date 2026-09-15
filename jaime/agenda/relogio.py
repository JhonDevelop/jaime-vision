"""Relógio: hora, data, dia da semana, fuso. Perguntas de hora não vão ao modelo — respondem aqui."""
from __future__ import annotations
import re
from datetime import datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
HORA_RX = re.compile(r"\b(que horas?( s[aã]o)?|hora [eé] (agora|essa)|horas [eé]|me diz a hora|qual a hora)\b", re.I)
DATA_RX = re.compile(r"\b(que dia [eé] hoje|qual (?:[eé] )?a data( de hoje)?|data de hoje|que dia da semana|hoje [eé] que dia)\b", re.I)

def agora(tz=FUSO) -> datetime:
    return datetime.now(tz)

def texto_hora(dt: datetime) -> str:
    h, m = dt.hour, dt.minute
    if m == 0:
        return f"{h} em ponto" if h not in (0, 12) else ("meio-dia em ponto" if h == 12 else "meia-noite em ponto")
    if m == 30:
        return f"{h} e meia"
    return f"{h} e {m:02d}"

def texto_data(dt: datetime) -> str:
    return f"{DIAS[dt.weekday()]}, {dt.day} de {MESES[dt.month - 1]} de {dt.year}"

def responder(texto: str, dt: datetime | None = None) -> str | None:
    """Resposta curta para hora/data, ou None se a frase não é sobre isso."""
    dt = dt or agora()
    t = texto or ""
    if HORA_RX.search(t):
        return f"São {texto_hora(dt)}."
    if DATA_RX.search(t):
        return f"Hoje é {texto_data(dt)}."
    return None
