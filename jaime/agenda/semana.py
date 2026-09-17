"""A agenda física da semana — duas faixas por dia, e elas não se misturam.

    FAIXA DO JOÃO    compromissos, lembretes e prazos dele. É a vida dele.
    FAIXA DO JAIME   as rotinas dele, o que ele decidiu estudar, criar e melhorar por conta própria.

O João pediu a separação com todas as letras: o que o Jaime decide fazer sozinho **não faz parte da agenda dele**.
Então são duas faixas paralelas no mesmo calendário, com cores próprias — dá para ver a semana inteira de relance
e saber, em cada dia, o que é obrigação do João e o que é trabalho que o Jaime se deu.

A faixa do Jaime sai de coisas reais: as rotinas em `30-Tarefas/Rotinas.md` (cron de verdade, expandido dia a dia),
os problemas que ele abriu no estudo, e o que ele mesmo escreveu em `01-Estado/Agenda-Jaime.md` — a nota onde ele
anota o que decidiu fazer. Nada de agenda decorativa."""
from __future__ import annotations
import re
from datetime import datetime, date, timedelta

ROTINAS_REL = "30-Tarefas/Rotinas.md"
LEMBRETES_REL = "30-Tarefas/Lembretes.md"
INBOX_REL = "30-Tarefas/Inbox.md"
AGENDA_JAIME_REL = "01-Estado/Agenda-Jaime.md"

ROTINA_RX = re.compile(r"^-\s+([\d*/,\-]+)\s+([\d*/,\-]+)\s+([\w*/,\-]+)\s+([\w*/,\-]+)\s+([\w*/,\-]+)\s+·\s+(.+)$", re.M)
LEMBRETE_RX = re.compile(r"^-\s+\[([ x])\]\s+(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?\s+·\s+(.+)$", re.M)
TAREFA_RX = re.compile(r"^-\s+\[ \]\s+(.+?)(?:\s+⏳\s*(\d{4}-\d{2}-\d{2}))?\s*$", re.M)
JAIME_RX = re.compile(r"^-\s+(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?\s+·\s+(\w+)\s+·\s+(.+)$", re.M)

DIAS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
SEM = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

# Cada tipo tem cor própria: é o que faz a semana ser lida de relance.
CORES = {
    # faixa do João
    "compromisso": "#38e1ff", "lembrete": "#ffb347", "prazo": "#ff5c72", "tarefa": "#ff9f6b",
    # faixa do Jaime
    "rotina": "#7d5cff", "estudo": "#5fe0c0", "criacao": "#ff5cc8", "melhoria": "#49e6a0",
    "pensar": "#b98cff", "manutencao": "#8aa0bd",
}


def _campo_bate(campo: str, valor: int, nomes: dict | None = None) -> bool:
    """Um campo de cron (`*`, `5`, `1-5`, `mon-fri`, `1,3`, `*/2`) casa com este valor?"""
    campo = campo.strip().lower()
    if campo in ("*", "?"):
        return True
    for parte in campo.split(","):
        parte = parte.strip()
        passo = 1
        if "/" in parte:
            parte, p = parte.split("/", 1)
            passo = int(p) if p.isdigit() else 1
            if parte in ("*", ""):
                return valor % passo == 0
        def n(x):
            x = x.strip()
            return SEM[x] if nomes and x in SEM else (int(x) if x.lstrip("-").isdigit() else None)
        if "-" in parte.strip("-"):
            a, b = parte.split("-", 1)
            ia, ib = n(a), n(b)
            if ia is None or ib is None:
                continue
            faixa = range(ia, ib + 1) if ia <= ib else list(range(ia, 7)) + list(range(0, ib + 1))
            if valor in faixa and (valor - ia) % passo == 0:
                return True
        else:
            v = n(parte)
            if v is not None and v == valor:
                return True
    return False


def rotina_no_dia(cron: tuple[str, ...], d: date) -> bool:
    """A rotina cai neste dia? (dia do mês, mês e dia da semana; a hora não entra aqui)"""
    _, _, dia, mes, semana = cron
    return (_campo_bate(dia, d.day) and _campo_bate(mes, d.month)
            and _campo_bate(semana, d.weekday(), SEM))


def montar(vault, jaime=None, dias: int = 7, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    ler = lambda r: (vault.read(r) or "")

    # ── a faixa do JAIME: as rotinas dele, expandidas dia a dia ──────────
    rotinas = []
    for mi, ho, di, me, se, ordem in ROTINA_RX.findall(ler(ROTINAS_REL)):
        alvo = ordem.split(":")[0].strip()
        tipo = ("estudo" if "estud" in ordem.lower() else
                "criacao" if "cria" in ordem.lower() else
                "melhoria" if ("melhor" in ordem.lower() or "avaliação" in ordem.lower()) else
                "pensar" if "pensa" in ordem.lower() else "rotina")
        rotinas.append({"cron": (mi, ho, di, me, se), "hora": f"{int(ho):02d}:{int(mi):02d}" if ho.isdigit() and mi.isdigit() else "",
                        "titulo": alvo[:60], "descricao": ordem[:150], "tipo": tipo, "cor": CORES[tipo]})

    # o que o próprio Jaime anotou que vai fazer
    jaime_itens: dict[str, list[dict]] = {}
    for d, h, tipo, texto in JAIME_RX.findall(ler(AGENDA_JAIME_REL)):
        t = tipo.lower() if tipo.lower() in CORES else "melhoria"
        jaime_itens.setdefault(d, []).append({"hora": h or "", "titulo": texto[:60], "descricao": texto[:150],
                                              "tipo": t, "cor": CORES[t], "dele": True})

    # ── a faixa do JOÃO: lembretes, prazos e compromissos ────────────────
    joao_itens: dict[str, list[dict]] = {}
    for feito, d, h, texto in LEMBRETE_RX.findall(ler(LEMBRETES_REL)):
        joao_itens.setdefault(d, []).append({"hora": h or "", "titulo": texto[:60], "descricao": texto[:150],
                                             "tipo": "lembrete", "cor": CORES["lembrete"], "feito": feito == "x"})
    for texto, prazo in TAREFA_RX.findall(ler(INBOX_REL)):
        if prazo:
            joao_itens.setdefault(prazo, []).append({"hora": "", "titulo": texto[:60], "descricao": texto[:150],
                                                     "tipo": "prazo", "cor": CORES["prazo"]})
    try:
        for c in (jaime.agenda.compromissos_da_semana() if jaime else []):
            joao_itens.setdefault(str(c.get("data", "")), []).append(
                {"hora": c.get("hora", ""), "titulo": str(c.get("titulo", ""))[:60],
                 "descricao": str(c.get("descricao", ""))[:150], "tipo": "compromisso", "cor": CORES["compromisso"]})
    except Exception:
        pass

    # ── o calendário ─────────────────────────────────────────────────────
    grade = []
    for i in range(dias):
        d = hoje + timedelta(days=i)
        iso = d.isoformat()
        do_jaime = [r for r in rotinas if rotina_no_dia(r["cron"], d)] + jaime_itens.get(iso, [])
        do_jaime.sort(key=lambda x: x.get("hora") or "99")
        do_joao = sorted(joao_itens.get(iso, []), key=lambda x: x.get("hora") or "99")
        grade.append({"data": iso, "dia": d.day, "mes": d.month, "semana": DIAS[d.weekday()],
                      "hoje": d == hoje, "fim_de_semana": d.weekday() >= 5,
                      "joao": [{k: v for k, v in x.items() if k != "cron"} for x in do_joao],
                      "jaime": [{k: v for k, v in x.items() if k != "cron"} for x in do_jaime]})

    return {"dias": grade, "cores": CORES, "hoje": hoje.isoformat(),
            "total_joao": sum(len(g["joao"]) for g in grade),
            "total_jaime": sum(len(g["jaime"]) for g in grade)}
