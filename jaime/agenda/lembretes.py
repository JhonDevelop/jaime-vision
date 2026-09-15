"""Lembretes: "me lembra em 20 min de ligar pro Zé", "me lembra às 15h da reunião", "me lembra amanhã às 9 de X".

`interpretar(texto, agora)` → (quando: datetime, o_que: str) ou None. Persistidos em `30-Tarefas/Lembretes.md`
para sobreviver a um reinício; o scheduler agenda os que ainda não passaram."""
from __future__ import annotations
import re
from datetime import datetime, timedelta, date
from .relogio import FUSO

ARQUIVO = "30-Tarefas/Lembretes.md"
GATILHO_RX = re.compile(r"\b(me\s+)?lembr[ae](?:r)?(?:\s+me)?\b", re.I)
EM_RX = re.compile(r"\bem\s+(\d+|uma?|meia)\s*(min(?:uto)?s?|h(?:ora)?s?|dias?|segundos?)\b", re.I)
AS_RX = re.compile(r"\b(?:[àa]s?|as)\s+(\d{1,2})(?:[:h](\d{2}))?\s*(?:h(?:oras)?)?\b(?!\s*(?:min|dia))", re.I)
DIA_RX = re.compile(r"\b(hoje|amanh[aã]|depois de amanh[aã]|dia\s+(\d{1,2})(?:/(\d{1,2}))?)\b", re.I)
DE_RX = re.compile(r"\b(?:de|da|do|que|para|pra)\s+(.+)$", re.I)
UNIDADES = {"min": 60, "h": 3600, "dia": 86400, "seg": 1}

def _quantidade(s: str) -> float:
    s = s.lower()
    return 1.0 if s in ("um", "uma") else 0.5 if s == "meia" else float(s)

def interpretar(texto: str, agora: datetime | None = None) -> tuple[datetime, str] | None:
    agora = agora or datetime.now(FUSO)
    t = (texto or "").strip()
    if not GATILHO_RX.search(t):
        return None
    quando: datetime | None = None
    resto = t
    if (m := EM_RX.search(t)):
        n = _quantidade(m.group(1)); u = m.group(2).lower()
        seg = n * (UNIDADES["min"] if u.startswith("min") else UNIDADES["h"] if u.startswith("h") else UNIDADES["dia"] if u.startswith("dia") else 1)
        quando = agora + timedelta(seconds=seg); resto = t[:m.start()] + t[m.end():]
    else:
        base = agora.date()
        if (md := DIA_RX.search(t)):
            g = md.group(1).lower()
            if g.startswith("amanh"): base = agora.date() + timedelta(days=1)
            elif g.startswith("depois"): base = agora.date() + timedelta(days=2)
            elif md.group(2):
                dia = int(md.group(2)); mes = int(md.group(3)) if md.group(3) else agora.month
                try:
                    base = date(agora.year, mes, dia)
                    if base < agora.date():
                        base = date(agora.year + 1, mes, dia)
                except ValueError:
                    return None
            resto = t[:md.start()] + t[md.end():]
        if (mh := AS_RX.search(resto)):
            h, mi = int(mh.group(1)), int(mh.group(2) or 0)
            if h > 23 or mi > 59:
                return None
            quando = datetime(base.year, base.month, base.day, h, mi, tzinfo=agora.tzinfo)
            if quando <= agora and base == agora.date() and not DIA_RX.search(t):
                quando += timedelta(days=1)          # "às 9" já passou → amanhã às 9
            resto = resto[:mh.start()] + resto[mh.end():]
        elif base != agora.date():
            quando = datetime(base.year, base.month, base.day, 9, 0, tzinfo=agora.tzinfo)   # dia sem hora: 9h
    if not quando:
        return None
    resto = GATILHO_RX.sub("", resto, count=1)
    o_que = (DE_RX.search(resto.strip()) or [None, resto])[1] if DE_RX.search(resto.strip()) else resto
    o_que = re.sub(r"\s+", " ", o_que).strip(" ,.:;-")
    return quando, (o_que or "lembrete")

def linha(quando: datetime, o_que: str) -> str:
    return f"- [ ] {quando:%Y-%m-%d %H:%M} · {o_que}"

def pendentes(texto_arquivo: str, agora: datetime | None = None) -> list[tuple[datetime, str]]:
    agora = agora or datetime.now(FUSO)
    out = []
    for l in (texto_arquivo or "").splitlines():
        m = re.match(r"- \[ \] (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) · (.+)$", l.strip())
        if not m:
            continue
        q = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=agora.tzinfo)
        if q > agora:
            out.append((q, m.group(2)))
    return out

def marcar_feito(texto_arquivo: str, quando: datetime, o_que: str) -> str:
    alvo = linha(quando, o_que)
    return (texto_arquivo or "").replace(alvo, alvo.replace("- [ ]", "- [x]", 1), 1)
