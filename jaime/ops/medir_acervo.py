"""Quanto o J.A.I.M.E carrega por turno — e quanto ele tem guardado sem custar nada."""
from __future__ import annotations
import os, re, pathlib

DESC_RX = re.compile(r"^description:\s*(.*)$", re.M)


def _desc(p: pathlib.Path) -> str:
    try:
        m = DESC_RX.search(p.read_text(encoding="utf-8", errors="ignore")[:1200])
    except OSError:
        return ""
    return (m.group(1) if m else "").strip()


def _conta(pasta: pathlib.Path, glob: str) -> list[pathlib.Path]:
    return sorted(pasta.glob(glob)) if pasta.is_dir() else []


def main() -> None:
    raiz = pathlib.Path(".")
    agentes = [p for p in _conta(raiz / ".claude/agents", "*.md") if p.stem != "README"]
    skills = [d for d in (raiz / ".claude/skills").iterdir()
              if d.is_dir() and (d / "SKILL.md").is_file()] if (raiz / ".claude/skills").is_dir() else []
    teto = int(os.environ.get("JAIME_AGENTES_MAX", "40") or 0)
    # a mesma ordem que carregar_maesters usa: a casa primeiro
    ordem = sorted(agentes, key=lambda p: (not p.stem.startswith("maester-"), p.stem))
    carregados = ordem[:teto] if teto > 0 else ordem
    custo = (sum(len(p.stem) + len(_desc(p)) for p in carregados)
             + sum(len(d.name) + len(_desc(d / "SKILL.md")) for d in skills))
    guard_ag = len(_conta(raiz / ".claude/acervo/agents", "*.md"))
    guard_sk = len([d for d in (raiz / ".claude/acervo/skills").iterdir() if d.is_dir()]) \
        if (raiz / ".claude/acervo/skills").is_dir() else 0
    print(f"CARREGA por turno : {len(carregados)} agentes + {len(skills)} skills ≈ {custo // 4} tokens")
    print(f"guardado no acervo: {guard_ag} agentes + {guard_sk} skills "
          f"(fora do contexto, achável por mcp__acervo__buscar)")
    print(f"total que ele sabe: {len(agentes) + guard_ag} agentes + {len(skills) + guard_sk} skills")


if __name__ == "__main__":
    main()
