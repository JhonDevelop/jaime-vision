"""Fontes vivas: um bloco com `fonte` se atualiza sozinho a cada `intervalo_s`.

Cada fonte é uma função pequena que devolve `(tipo, conteudo)` a partir do que o Jaime JÁ sabe — as mesmas
chamadas que as rotas /hud/* usam. Fonte privada (finanças, tarefas, agenda, pessoas) marca o bloco como privado:
ele só aparece em superfície do dono com o cérebro destrancado.

Fonte nova = registrar(nome, função, privada). O modelo não inventa fonte: pede pelo nome, e nome desconhecido é recusado.
"""
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class Fonte:
    nome: str
    descricao: str
    tipo: str
    privada: bool
    fn: Callable[[dict], dict]
    intervalo_padrao: float = 0.0


class Fontes:
    def __init__(self):
        self._f: dict[str, Fonte] = {}

    def registrar(self, nome: str, descricao: str, tipo: str, fn: Callable[[dict], dict], privada: bool = False,
                  intervalo_padrao: float = 0.0) -> None:
        self._f[nome] = Fonte(nome, descricao, tipo, privada, fn, intervalo_padrao)

    def __contains__(self, nome: str) -> bool:
        return nome in self._f

    def get(self, nome: str) -> Fonte | None:
        return self._f.get(nome)

    def listar(self) -> list[dict]:
        return [{"nome": f.nome, "descricao": f.descricao, "tipo": f.tipo, "privada": f.privada} for f in self._f.values()]

    def ler(self, nome: str, parametros: dict | None = None) -> tuple[str, dict]:
        f = self._f[nome]
        return f.tipo, f.fn(parametros or {})


# ── fontes padrão ────────────────────────────────────────────────────────────
def _maquina(_p: dict) -> dict:
    import psutil
    disco = psutil.disk_usage("/")
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=None)
    est = lambda v, a, r: "ruim" if v >= r else "atencao" if v >= a else "ok"
    return {"itens": [
        {"rotulo": "CPU", "valor": f"{cpu:.0f}", "unidade": "%", "estado": est(cpu, 70, 90)},
        {"rotulo": "Memória", "valor": f"{mem.percent:.0f}", "unidade": "%", "estado": est(mem.percent, 75, 90)},
        {"rotulo": "Disco", "valor": f"{disco.percent:.0f}", "unidade": "%", "estado": est(disco.percent, 80, 92)},
    ]}


def _relogio(_p: dict) -> dict:
    from datetime import datetime
    agora = datetime.now()
    dias = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    return {"texto": f"{agora:%H:%M} · {dias[agora.weekday()]}, {agora:%d/%m/%Y}"}


def padrao(jaime=None) -> Fontes:
    """As fontes que existem sempre (máquina, relógio) + as que dependem do Jaime vivo."""
    f = Fontes()
    f.registrar("sistema.maquina", "CPU, memória e disco desta máquina", "metricas", _maquina, intervalo_padrao=5)
    f.registrar("relogio", "hora e data", "texto", _relogio, intervalo_padrao=30)
    if jaime is None:
        return f

    def financas(p: dict) -> dict:
        r = jaime.financas.resumo(p.get("mes", "")) or {}
        itens = []
        for rot, chave in (("Saldo", "saldo"), ("Entradas", "entradas"), ("Saídas", "saidas")):
            if chave in r:
                itens.append({"rotulo": rot, "valor": f"{float(r[chave]):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                              "unidade": "R$", "estado": "ruim" if chave == "saldo" and float(r[chave]) < 0 else ""})
        return {"itens": itens}
    f.registrar("financas.resumo", "saldo, entradas e saídas do mês", "metricas", financas, privada=True, intervalo_padrao=60)

    def financas_mensal(_p: dict) -> dict:
        por_mes = (jaime.financas.resumo() or {}).get("por_mes", [])[-12:]
        return {"forma": "barras", "unidade": "R$", "series": [
            {"nome": "entradas", "pontos": [{"x": m, "y": e} for m, e, _ in por_mes]},
            {"nome": "saídas", "pontos": [{"x": m, "y": s_} for m, _, s_ in por_mes]}]}
    f.registrar("financas.mensal", "entradas e saídas mês a mês", "grafico", financas_mensal, privada=True, intervalo_padrao=300)

    def tarefas(_p: dict) -> dict:
        limpa = lambda t: str(t)[6:].strip() if str(t).startswith("- [ ]") else str(t)
        return {"itens": [{"texto": limpa(t)[:300]} for t in (jaime.vault.tarefas_abertas() or [])[:30]]}
    f.registrar("tarefas.abertas", "tarefas abertas do Inbox", "lista", tarefas, privada=True, intervalo_padrao=30)

    def agenda(_p: dict) -> dict:
        try:
            itens = [{"texto": o, "detalhe": q.strftime("%d/%m %H:%M")} for q, o in sorted(jaime.agenda.lembretes())[:12]]
        except Exception:
            itens = []
        return {"itens": itens}
    f.registrar("agenda.lembretes", "próximos lembretes", "lista", agenda, privada=True, intervalo_padrao=60)

    def estado(_p: dict) -> dict:
        return {"texto": f"Fase: {jaime.estado.fase()}\n{jaime.estado.secao('Situação agora') or ''}".strip()}
    f.registrar("jaime.estado", "em que fase o Jaime está e o que está fazendo", "texto", estado, intervalo_padrao=60)

    def placar(_p: dict) -> dict:
        dados = getattr(jaime.placar, "dados", {}).get("placar", {})
        linhas = []
        for chave, c in sorted(dados.items()):
            n = c["acertos"] + c["erros"]
            if n:
                modelo, tipo = chave.split("|", 1)
                linhas.append([modelo.replace("claude-", ""), tipo, f"{c['acertos']}/{n}", f"{c['latencia'] / max(c['n'], 1):.1f} s"])
        return {"colunas": ["modelo", "tipo", "acertos", "latência"], "linhas": linhas[:40]}
    f.registrar("cortex.placar", "acertos e erros de cada modelo", "tabela", placar, intervalo_padrao=120)

    def espacial(_p: dict) -> dict:
        s = getattr(jaime, "espacial", None)
        if not s:
            return {"estado": "atencao", "texto": "expansão espacial desligada (JAIME_SPATIAL=off)"}
        e = s.estado(curto=True)
        return {"estado": "ok" if e["rodando"] else "atencao",
                "texto": f"{e['modo']} · {'rodando' if e['rodando'] else 'parado'}{' · dry-run' if e['dry_run'] else ''}"
                         + (f" · {e['erro']}" if e.get("erro") else "")}
    f.registrar("espacial.estado", "rastreamento de mãos: ligado, modo, erros", "status", espacial, intervalo_padrao=5)
    return f


def agora() -> float:
    return time.time()
