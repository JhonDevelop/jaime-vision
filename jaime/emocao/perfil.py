"""Quem é o João — lê e escreve `10-Eu/Perfil.md`, `10-Eu/Datas.md`, `10-Eu/Jeito.md`.

Datas.md aceita duas formas por linha:
  - `- 12/03 — Aniversário do João`              (repete todo ano)
  - `- 2026-10-01 — Entrega BUB v2 @BUB`          (data única / prazo)"""
from __future__ import annotations
import re
from dataclasses import dataclass
from datetime import date
from ..brain.vault import Vault

LINHA_RX = re.compile(r"^\s*-\s*(?:(\d{4})-(\d{2})-(\d{2})|(\d{1,2})/(\d{1,2}))\s*[—\-–:]\s*(.+?)\s*$")
ANIVERSARIO_RX = re.compile(r"anivers[aá]rio d[oa] jo[aã]o|meu anivers[aá]rio|anivers[aá]rio\s*$", re.I)

@dataclass
class Data:
    nome: str
    dia: int
    mes: int
    ano: int | None = None          # None = repete todo ano
    projeto: str = ""

    def proxima(self, hoje: date) -> date | None:
        if self.ano:
            try:
                return date(self.ano, self.mes, self.dia)
            except ValueError:
                return None
        for ano in (hoje.year, hoje.year + 1):
            try:
                d = date(ano, self.mes, self.dia)
            except ValueError:
                continue
            if d >= hoje:
                return d
        return None

    def dias_ate(self, hoje: date) -> int | None:
        p = self.proxima(hoje)
        return (p - hoje).days if p else None

    @property
    def eh_aniversario_do_joao(self) -> bool:
        return bool(ANIVERSARIO_RX.search(self.nome))

def parse_datas(texto: str) -> list[Data]:
    out = []
    for linha in texto.splitlines():
        m = LINHA_RX.match(linha)
        if not m:
            continue
        nome = m.group(6).strip()
        proj = ""
        if (pm := re.search(r"@(\S+)", nome)):
            proj = pm.group(1); nome = nome.replace(pm.group(0), "").strip()
        if m.group(1):
            out.append(Data(nome, int(m.group(3)), int(m.group(2)), int(m.group(1)), proj))
        else:
            out.append(Data(nome, int(m.group(4)), int(m.group(5)), None, proj))
    return out

class Perfil:
    def __init__(self, vault: Vault):
        self.vault = vault

    def perfil(self) -> str:
        return self.vault.read("10-Eu/Perfil.md")

    def jeito(self) -> str:
        return self.vault.read("10-Eu/Jeito.md")

    def datas(self) -> list[Data]:
        return parse_datas(self.vault.read("10-Eu/Datas.md"))

    def adicionar_data(self, descricao: str, dia: int, mes: int, ano: int | None = None, projeto: str = "") -> str:
        quando = f"{ano:04d}-{mes:02d}-{dia:02d}" if ano else f"{dia:02d}/{mes:02d}"
        linha = f"- {quando} — {descricao.strip()}" + (f" @{projeto}" if projeto else "")
        self.vault.append("10-Eu/Datas.md", linha)
        return linha

    def anotar_jeito(self, secao: str, texto: str) -> None:
        """Acrescenta uma observação numa seção de Jeito.md (cria a seção se faltar)."""
        atual = self.vault.read("10-Eu/Jeito.md")
        marker = f"## {secao}"
        linha = f"- {texto.strip()}"
        if marker in atual:
            head, tail = atual.split(marker, 1)
            resto = tail.split("\n## ", 1)
            depois = ("\n## " + resto[1]) if len(resto) > 1 else ""
            corpo = resto[0].rstrip("\n")
            self.vault.write("10-Eu/Jeito.md", f"{head}{marker}{corpo}\n{linha}\n{depois}")
        else:
            self.vault.append("10-Eu/Jeito.md", f"\n{marker}\n{linha}")
