"""Nunca perguntar duas vezes — `10-Eu/Perguntas-Feitas.md`.

Toda pergunta que o Jaime faz ao João entra aqui com a resposta. Antes de perguntar qualquer coisa,
`decidir(pergunta)`:
  - "usar":      já tem resposta recente → use-a, não pergunte
  - "confirmar": resposta com mais de VALIDADE_DIAS → confirme em meia frase ("continua X?")
  - "perguntar": nunca foi feita → pergunte e registre"""
from __future__ import annotations
import re, unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from ..brain.vault import Vault

ARQUIVO = "10-Eu/Perguntas-Feitas.md"
VALIDADE_DIAS = 90
SIMILARIDADE_MIN = 0.6
STOP = {"o", "a", "os", "as", "de", "do", "da", "dos", "das", "em", "no", "na", "que", "qual", "é", "e", "um", "uma",
        "você", "voce", "seu", "sua", "para", "pra", "com", "por", "ou", "se", "eu", "me", "meu", "minha", "tem", "ter"}

def _tokens(t: str) -> set[str]:
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    return {w for w in re.findall(r"[a-z0-9]+", t) if w not in STOP and len(w) > 1}

def similaridade(a: str, b: str) -> float:
    """Contenção (interseção / menor conjunto): 'qual é o seu aniversário' e 'quando é seu aniversário'
    partilham o que importa. Jaccard puro punia demais a redação diferente."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))

@dataclass
class Registro:
    data: date
    pergunta: str
    resposta: str

    def dias(self, hoje: date) -> int:
        return (hoje - self.data).days

class Perguntas:
    def __init__(self, vault: Vault):
        self.vault = vault

    def todas(self) -> list[Registro]:
        out = []
        for linha in self.vault.read(ARQUIVO).splitlines():
            if not linha.startswith("|") or linha.startswith("| data") or linha.startswith("|---"):
                continue
            partes = [c.strip() for c in linha.strip().strip("|").split("|")]
            if len(partes) < 3:
                continue
            try:
                d = datetime.strptime(partes[0], "%Y-%m-%d").date()
            except ValueError:
                continue
            out.append(Registro(d, partes[1], partes[2]))
        return out

    def buscar(self, pergunta: str) -> Registro | None:
        melhor, nota = None, 0.0
        for r in self.todas():
            s = similaridade(pergunta, r.pergunta)
            if s > nota:
                melhor, nota = r, s
        return melhor if nota >= SIMILARIDADE_MIN else None

    def decidir(self, pergunta: str, hoje: date | None = None) -> dict:
        hoje = hoje or date.today()
        r = self.buscar(pergunta)
        if not r or not r.resposta or r.resposta in ("—", "?"):
            return {"acao": "perguntar", "resposta": "", "dias": None, "pergunta_original": r.pergunta if r else ""}
        if r.dias(hoje) > VALIDADE_DIAS:
            return {"acao": "confirmar", "resposta": r.resposta, "dias": r.dias(hoje), "pergunta_original": r.pergunta}
        return {"acao": "usar", "resposta": r.resposta, "dias": r.dias(hoje), "pergunta_original": r.pergunta}

    def registrar(self, pergunta: str, resposta: str = "—", hoje: date | None = None) -> None:
        """Registra a pergunta (sem resposta ainda) ou atualiza a resposta de uma pergunta parecida."""
        hoje = hoje or date.today()
        limpo = lambda s: s.replace("|", "/").replace("\n", " ").strip()
        linhas = self.vault.read(ARQUIVO).splitlines()
        if not linhas:
            linhas = ["# Perguntas já feitas ao João", "", "| data | pergunta | resposta |", "|---|---|---|"]
        alvo = self.buscar(pergunta)
        if alvo and resposta != "—":
            for i, l in enumerate(linhas):
                if l.startswith("|") and f"| {alvo.pergunta} |" in l:
                    linhas[i] = f"| {hoje.isoformat()} | {limpo(alvo.pergunta)} | {limpo(resposta)} |"
                    break
        else:
            linhas.append(f"| {hoje.isoformat()} | {limpo(pergunta)} | {limpo(resposta)} |")
        self.vault.write(ARQUIVO, "\n".join(linhas).rstrip("\n") + "\n")
