"""Feriados do Brasil + São Paulo (biblioteca `holidays`), com a tabela fixa como reserva."""
from __future__ import annotations
from datetime import date, timedelta

FIXOS = {(1, 1): "Confraternização Universal", (4, 21): "Tiradentes", (5, 1): "Dia do Trabalho", (9, 7): "Independência",
         (10, 12): "Nossa Senhora Aparecida", (11, 2): "Finados", (11, 15): "Proclamação da República",
         (11, 20): "Consciência Negra", (12, 25): "Natal"}

def _calendario(ano: int):
    try:
        import holidays
        return holidays.country_holidays("BR", subdiv="SP", years=[ano, ano + 1], language="pt_BR")
    except Exception:
        return None

def feriado(d: date) -> str | None:
    cal = _calendario(d.year)
    if cal is not None:
        nome = cal.get(d)
        return str(nome) if nome else None
    return FIXOS.get((d.month, d.day))

def feriado_hoje(hoje: date | None = None) -> str | None:
    return feriado(hoje or date.today())

def proximo_feriado(hoje: date | None = None, limite_dias: int = 120) -> tuple[date, str] | None:
    hoje = hoje or date.today()
    for i in range(1, limite_dias + 1):
        d = hoje + timedelta(days=i)
        n = feriado(d)
        if n:
            return d, n
    return None

def texto(hoje: date | None = None) -> str:
    hoje = hoje or date.today()
    h = feriado(hoje)
    if h:
        return f"Hoje é feriado: {h}."
    p = proximo_feriado(hoje)
    if not p:
        return "Nenhum feriado nos próximos meses."
    d, n = p
    return f"Hoje não é feriado. O próximo é {n}, em {(d - hoje).days} dia(s) ({d:%d/%m})."
