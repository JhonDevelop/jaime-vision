"""Saúde do cérebro: `python -m jaime cerebro check`.

Verifica o vault antes de o Jaime confiar nele: pastas obrigatórias, frontmatter da Identidade,
links [[quebrados]], notas órfãs, notas grandes demais, diário parado, Estado coerente com o roadmap.
Roda no boot (Jaime.start): erro → ele avisa antes de qualquer coisa; aviso → vai para o diário.

Também gera os índices que entram no contexto inicial: `50-Conhecimento/INDEX.md` e `20-Projetos/INDEX.md`."""
from __future__ import annotations
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

PASTAS = ["00-Jaime", "01-Estado", "10-Eu", "20-Projetos", "30-Tarefas", "40-Diario", "50-Conhecimento", "60-Conversas"]
LINK_RX = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
TAMANHO_MAX = 200_000          # bytes; acima disso a nota está virando lixo ou log
DIARIO_PARADO_DIAS = 2

@dataclass
class Problema:
    nivel: str      # "erro" | "aviso"
    onde: str
    msg: str

    def __str__(self) -> str:
        return f"{'✘' if self.nivel == 'erro' else '!'} {self.onde}: {self.msg}"

def _notas(root: Path):
    for p in sorted(root.rglob("*.md")):
        if ".obsidian" not in p.parts:
            yield p

def verificar(vault: Path, repo: Path | None = None, hoje: date | None = None) -> list[Problema]:
    vault = Path(vault); hoje = hoje or date.today()
    probs: list[Problema] = []
    if not vault.is_dir():
        return [Problema("erro", str(vault), "vault não existe")]

    # 1) pastas obrigatórias
    for pasta in PASTAS:
        if not (vault / pasta).is_dir():
            probs.append(Problema("erro", pasta, "pasta obrigatória não existe"))

    # 2) identidade com frontmatter `nome:`
    ident = vault / "00-Jaime" / "Identidade.md"
    if not ident.exists():
        probs.append(Problema("erro", "00-Jaime/Identidade.md", "não existe"))
    else:
        txt = ident.read_text(encoding="utf-8")
        if not re.match(r"^---\n.*?^nome:\s*\S", txt, re.S | re.M):
            probs.append(Problema("erro", "00-Jaime/Identidade.md", "sem frontmatter `nome:` — o nome do Jaime vem daqui"))

    # 3) links quebrados e notas órfãs
    notas = list(_notas(vault))
    stems = {p.stem for p in notas} | {str(p.relative_to(vault).with_suffix("")) for p in notas}
    entradas: dict[str, int] = {}
    for p in notas:
        for alvo in LINK_RX.findall(p.read_text(encoding="utf-8", errors="ignore")):
            alvo = alvo.strip()
            if alvo in stems or alvo.removesuffix(".md") in stems:
                entradas[alvo.split("/")[-1].removesuffix(".md")] = entradas.get(alvo.split("/")[-1].removesuffix(".md"), 0) + 1
            else:
                probs.append(Problema("aviso", str(p.relative_to(vault)), f"link quebrado [[{alvo}]]"))
    for p in notas:
        rel = str(p.relative_to(vault))
        if rel.startswith(("20-Projetos/", "50-Conhecimento/")) and p.stem != "INDEX" and entradas.get(p.stem, 0) == 0:
            probs.append(Problema("aviso", rel, "nota órfã — nada aponta para ela (o INDEX resolve)"))
        if p.stat().st_size > TAMANHO_MAX:
            probs.append(Problema("aviso", rel, f"nota com {p.stat().st_size // 1000} KB — grande demais para ser memória"))

    # 4) diário parado
    diarios = sorted((vault / "40-Diario").glob("????-??-??.md")) if (vault / "40-Diario").is_dir() else []
    if diarios:
        ultimo = datetime.strptime(diarios[-1].stem, "%Y-%m-%d").date()
        if (hoje - ultimo).days > DIARIO_PARADO_DIAS:
            probs.append(Problema("aviso", "40-Diario", f"último diário é de {ultimo:%d/%m}; nada registrado há {(hoje - ultimo).days} dias"))
    else:
        probs.append(Problema("aviso", "40-Diario", "nenhum diário ainda"))

    # 5) Estado coerente com o roadmap
    estado = vault / "01-Estado" / "Estado.md"
    if not estado.exists():
        probs.append(Problema("erro", "01-Estado/Estado.md", "não existe (o boot cria)"))
    else:
        txt = estado.read_text(encoding="utf-8")
        m = re.search(r"^## Fase\s*\n\s*(\S.*)$", txt, re.M)
        if not m:
            probs.append(Problema("erro", "01-Estado/Estado.md", "sem seção '## Fase'"))
        else:
            fase = re.match(r"\s*(\d+)", m.group(1))
            roadmap = (repo / "docs" / "ROADMAP.md") if repo else None
            if not fase:
                probs.append(Problema("aviso", "01-Estado/Estado.md", f"fase não começa com número: '{m.group(1)[:40]}'"))
            elif roadmap and roadmap.exists():
                fases = set(re.findall(r"^\|\s*(\d+)\s*\|", roadmap.read_text(encoding="utf-8"), re.M))
                if fase.group(1) not in fases:
                    probs.append(Problema("aviso", "01-Estado/Estado.md", f"fase {fase.group(1)} não existe em docs/ROADMAP.md"))
    return probs

def gerar_indices(vault: Path) -> list[str]:
    """INDEX.md de 50-Conhecimento e 20-Projetos, por código. Devolve os caminhos gerados."""
    vault = Path(vault); gerados = []
    for pasta, titulo in (("50-Conhecimento", "Conhecimento"), ("20-Projetos", "Projetos")):
        d = vault / pasta
        if not d.is_dir():
            continue
        linhas = [f"# {titulo} — índice", "", f"> Gerado por `jaime cerebro check` em {date.today():%d/%m/%Y}. Não edite à mão.", ""]
        for p in sorted(d.glob("*.md")):
            if p.stem == "INDEX":
                continue
            corpo = [l.strip() for l in p.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
            corpo = [l for l in corpo if not l.startswith("---")]
            resumo = next((l for l in corpo if not l.startswith("#")), "")
            linhas.append(f"- [[{p.stem}]] — {resumo[:120]}" if resumo else f"- [[{p.stem}]]")
        alvo = d / "INDEX.md"
        alvo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        gerados.append(str(alvo.relative_to(vault)))
    return gerados

def relatorio(probs: list[Problema]) -> str:
    if not probs:
        return "✔ cérebro saudável"
    erros = [p for p in probs if p.nivel == "erro"]; avisos = [p for p in probs if p.nivel == "aviso"]
    linhas = [f"{len(erros)} erro(s), {len(avisos)} aviso(s)"] + [str(p) for p in erros + avisos]
    return "\n".join(linhas)

def resumo_falado(probs: list[Problema]) -> str:
    """Uma frase para o boot por voz."""
    erros = [p for p in probs if p.nivel == "erro"]
    if not erros:
        return ""
    return f"Atenção: meu cérebro tem {len(erros)} problema{'s' if len(erros) > 1 else ''} — {erros[0].onde}: {erros[0].msg}."
