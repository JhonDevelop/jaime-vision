"""Que dia é hoje para o João — aniversário, feriado, prazo perto, semana pesada.

Alimenta o briefing, o contexto inicial e a prosódia. Feriados nacionais fixos vêm de uma tabela mínima
(a etapa 5 troca pela biblioteca `holidays` com SP)."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from .perfil import Perfil, Data

FERIADOS_FIXOS = {(1, 1): "Confraternização Universal", (4, 21): "Tiradentes", (5, 1): "Dia do Trabalho",
                  (9, 7): "Independência", (10, 12): "Nossa Senhora Aparecida", (11, 2): "Finados",
                  (11, 15): "Proclamação da República", (11, 20): "Consciência Negra", (12, 25): "Natal"}
PROXIMO_DIAS = 7            # "está perto" = até uma semana
SEMANA_PESADA_PRAZOS = 3    # ≥ 3 prazos em 7 dias
SEMANA_PESADA_TAREFAS = 12  # ou ≥ 12 tarefas abertas

@dataclass
class Momento:
    hoje: date
    aniversario: bool = False
    feriado: str | None = None
    hoje_e: list[str] = field(default_factory=list)           # datas que caem hoje
    proximas: list[tuple[int, Data]] = field(default_factory=list)   # (dias, data) até PROXIMO_DIAS
    prazos: list[tuple[int, Data]] = field(default_factory=list)
    tarefas_abertas: int = 0
    semana_pesada: bool = False

    @property
    def peso(self) -> str:
        """leve | normal | pesado — o que a prosódia e o humor usam."""
        if self.aniversario or self.feriado:
            return "leve"
        return "pesado" if self.semana_pesada else "normal"

    def texto(self) -> str:
        partes = []
        if self.aniversario:
            partes.append("HOJE É O ANIVERSÁRIO DO JOÃO — a primeira coisa do dia é isso.")
        for n in self.hoje_e:
            if "anivers" not in n.lower() or not self.aniversario:
                partes.append(f"Hoje: {n}.")
        if self.feriado:
            partes.append(f"Feriado: {self.feriado}.")
        for dias, d in self.proximas:
            partes.append(f"Em {dias} dia{'s' if dias != 1 else ''}: {d.nome}" + (f" (@{d.projeto})" if d.projeto else "") + ".")
        if self.semana_pesada:
            partes.append(f"Semana pesada: {len(self.prazos)} prazo(s) em 7 dias, {self.tarefas_abertas} tarefas abertas.")
        return " ".join(partes) or "Dia comum."

def momento(perfil: Perfil, hoje: date | None = None, tarefas_abertas: int | None = None) -> Momento:
    hoje = hoje or date.today()
    m = Momento(hoje)
    m.feriado = FERIADOS_FIXOS.get((hoje.month, hoje.day))
    if tarefas_abertas is None:
        try:
            tarefas_abertas = len(perfil.vault.tarefas_abertas())
        except Exception:
            tarefas_abertas = 0
    m.tarefas_abertas = tarefas_abertas
    for d in perfil.datas():
        dias = d.dias_ate(hoje)
        if dias is None:
            continue
        if dias == 0:
            m.hoje_e.append(d.nome)
            if d.eh_aniversario_do_joao:
                m.aniversario = True
        elif 0 < dias <= PROXIMO_DIAS:
            m.proximas.append((dias, d))
            if d.ano:               # data única = prazo
                m.prazos.append((dias, d))
    m.proximas.sort(key=lambda x: x[0])
    m.semana_pesada = len(m.prazos) >= SEMANA_PESADA_PRAZOS or m.tarefas_abertas >= SEMANA_PESADA_TAREFAS
    return m
