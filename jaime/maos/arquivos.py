"""Organizar arquivos com as regras do João (`10-Eu/Jeito.md`, seção "## Arquivos").

Regra por linha: `- <padrão> → <pasta destino>`. Padrão = globs de extensão separados por vírgula, com opcional
`com "trecho"` (o nome precisa conter o trecho). O Jaime só PROPÕE (`planejar`); mover/renomear é ação do Vigia:
executa depois do "confirmo"."""
from __future__ import annotations
import fnmatch, re, shutil
from dataclasses import dataclass
from pathlib import Path

REGRA_RX = re.compile(r"^\s*>?\s*-\s*(.+?)\s*(?:→|->)\s*(.+?)\s*$")
TRECHO_RX = re.compile(r'\s+com\s+"([^"]+)"', re.I)

@dataclass
class Regra:
    padroes: list[str]
    trecho: str
    destino: Path

    def casa(self, arquivo: Path) -> bool:
        nome = arquivo.name.lower()
        if self.trecho and self.trecho.lower() not in nome:
            return False
        return any(fnmatch.fnmatch(nome, p.lower()) for p in self.padroes)

def regras(texto_jeito: str) -> list[Regra]:
    """Só linhas da seção '## Arquivos' e não comentadas com '>' (as de exemplo ficam comentadas)."""
    if "## Arquivos" not in texto_jeito:
        return []
    bloco = texto_jeito.split("## Arquivos", 1)[1].split("\n## ", 1)[0]
    out = []
    for l in bloco.splitlines():
        if l.strip().startswith(">"):
            continue
        m = REGRA_RX.match(l)
        if not m:
            continue
        padrao, destino = m.group(1), m.group(2)
        trecho = ""
        if (t := TRECHO_RX.search(padrao)):
            trecho = t.group(1); padrao = TRECHO_RX.sub("", padrao)
        out.append(Regra([p.strip() for p in padrao.split(",") if p.strip()], trecho, Path(destino).expanduser()))
    return out

def planejar(pasta: Path, lista: list[Regra]) -> list[tuple[Path, Path]]:
    """(origem, destino) para cada arquivo da pasta que casa com alguma regra. Não move nada."""
    pasta = Path(pasta).expanduser()
    plano = []
    for f in sorted(pasta.iterdir()) if pasta.is_dir() else []:
        if not f.is_file() or f.name.startswith("."):
            continue
        for r in lista:
            if r.casa(f):
                plano.append((f, r.destino / f.name)); break
    return plano

def mover(origem: Path, destino: Path) -> str:
    origem, destino = Path(origem).expanduser(), Path(destino).expanduser()
    if not origem.exists():
        return f"não existe: {origem}"
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        base, i = destino, 2
        while destino.exists():
            destino = base.with_name(f"{base.stem} ({i}){base.suffix}"); i += 1
    shutil.move(str(origem), str(destino))
    return f"{origem.name} → {destino}"

def texto_plano(plano: list[tuple[Path, Path]]) -> str:
    if not plano:
        return "Nada a mover: nenhum arquivo casa com as regras de 10-Eu/Jeito.md."
    return "Proposta (só executo com 'confirmo'):\n" + "\n".join(f"- {o.name} → {d.parent}" for o, d in plano)
