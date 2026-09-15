"""Registro de conexões — `01-Estado/Conexoes.md`: serviço, escopo, como foi autorizado, como revogar, último uso.

O João lê isto para saber exatamente a que o Jaime tem acesso e como cortar cada acesso."""
from __future__ import annotations
import re
from datetime import datetime

ARQUIVO = "01-Estado/Conexoes.md"
CABECALHO = ("# Conexões\n\n> O que o Jaime consegue acessar, como foi autorizado e como revogar. Atualizado pelo código.\n\n"
             "| serviço | escopo | autorizado | revogar | último uso |\n|---|---|---|---|---|\n")

class Registro:
    def __init__(self, vault):
        self.vault = vault

    def _linhas(self) -> dict[str, list[str]]:
        out = {}
        for l in self.vault.read(ARQUIVO).splitlines():
            if l.startswith("|") and not l.startswith("| serviço") and not l.startswith("|---"):
                c = [x.strip() for x in l.strip().strip("|").split("|")]
                if len(c) >= 5:
                    out[c[0]] = c
        return out

    def registrar(self, servico: str, escopo: str, autorizado: str, revogar: str) -> None:
        linhas = self._linhas()
        antigo = linhas.get(servico)
        linhas[servico] = [servico, escopo, autorizado, revogar, antigo[4] if antigo else "—"]
        self._salvar(linhas)

    def usou(self, servico: str) -> None:
        linhas = self._linhas()
        if servico in linhas:
            linhas[servico][4] = datetime.now().strftime("%d/%m %H:%M")
            self._salvar(linhas)

    def remover(self, servico: str) -> None:
        linhas = self._linhas(); linhas.pop(servico, None); self._salvar(linhas)

    def _salvar(self, linhas: dict[str, list[str]]) -> None:
        corpo = CABECALHO + "".join("| " + " | ".join(c.replace("|", "/") for c in v) + " |\n" for v in linhas.values())
        self.vault.write(ARQUIVO, corpo)

    def texto(self) -> str:
        l = self._linhas()
        return "\n".join(f"- {v[0]}: {v[1]} (autorizado {v[2]}; último uso {v[4]})" for v in l.values()) or "Nenhuma conexão registrada."
