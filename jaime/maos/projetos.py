"""Criar projetos do jeito do João: pasta em JAIME_WORKSPACE, git init, README, .env.example, CLAUDE.md,
e a nota em `20-Projetos/` a partir de `vault/templates/Projeto.md`."""
from __future__ import annotations
import re, subprocess
from datetime import date
from pathlib import Path
from ..identidade import slug

TIPOS = {
    "python": {"arquivos": {".gitignore": ".venv/\n__pycache__/\n.env\n*.pyc\n", "pyproject.toml": '[project]\nname = "{slug}"\nversion = "0.1.0"\nrequires-python = ">=3.11"\ndependencies = []\n', "src/{slug}/__init__.py": "", "tests/test_basico.py": "def test_ok():\n    assert True\n"},
               "como_rodar": "python -m venv .venv && source .venv/bin/activate && pip install -e . && pytest -q"},
    "node":   {"arquivos": {".gitignore": "node_modules/\n.env\ndist/\n", "package.json": '{{\n  "name": "{slug}",\n  "version": "0.1.0",\n  "private": true,\n  "scripts": {{ "dev": "node src/index.js", "test": "node --test" }}\n}}\n', "src/index.js": "console.log('{nome} ok');\n"},
               "como_rodar": "npm install && npm run dev"},
    "generico": {"arquivos": {".gitignore": ".env\n.DS_Store\n"}, "como_rodar": "—"},
}

def criar_projeto(nome: str, tipo: str, workspace: Path, vault, descricao: str = "") -> dict:
    tipo = tipo if tipo in TIPOS else "generico"
    s = slug(nome)
    pasta = Path(workspace).expanduser() / s
    if pasta.exists() and any(pasta.iterdir()):
        return {"ok": False, "erro": f"{pasta} já existe e não está vazia", "pasta": str(pasta)}
    pasta.mkdir(parents=True, exist_ok=True)
    esp = TIPOS[tipo]
    arquivos = dict(esp["arquivos"])
    arquivos["README.md"] = f"# {nome}\n\n{descricao or 'Projeto do João Vitor Leal.'}\n\n## Como rodar\n```\n{esp['como_rodar']}\n```\n"
    arquivos[".env.example"] = "# copie para .env e preencha\n"
    arquivos["CLAUDE.md"] = (f"# {nome}\n\nProjeto do João (Franca/SP), criado pelo Jaime em {date.today():%d/%m/%Y}. Tipo: {tipo}.\n\n"
                             "## Regras\n- Branch por feature; testes antes de commit; nunca commitar .env.\n- Push em main e deploy só com \"confirmo\" do João.\n"
                             f"- Nota do projeto no vault do Jaime: `20-Projetos/{nome}.md`.\n")
    for rel, conteudo in arquivos.items():
        p = pasta / rel.format(slug=s.replace("-", "_"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(conteudo.format(slug=s.replace("-", "_"), nome=nome), encoding="utf-8")
    git_ok = False
    try:
        subprocess.run(["git", "init", "-q"], cwd=pasta, check=True, timeout=20)
        subprocess.run(["git", "add", "-A"], cwd=pasta, check=True, timeout=20)
        subprocess.run(["git", "commit", "-q", "-m", f"chore: projeto {nome} criado pelo Jaime"], cwd=pasta, check=True, timeout=20)
        git_ok = True
    except Exception:
        pass
    nota = _nota(vault, nome, tipo, pasta, descricao)
    vault.diario(f"Projeto criado: {nome} ({tipo}) em {pasta}", "Feito")
    return {"ok": True, "pasta": str(pasta), "git": git_ok, "nota": nota, "tipo": tipo}

def _nota(vault, nome: str, tipo: str, pasta: Path, descricao: str) -> str:
    rel = f"20-Projetos/{nome}.md"
    if vault.read(rel):
        return rel
    template = vault.read("templates/Projeto.md")
    if template:
        corpo = template.replace("{{nome}}", nome).replace("{{title}}", nome)
        corpo = re.sub(r"\{\{[^}]+\}\}", "", corpo)
        corpo += f"\n\n- Pasta: `{pasta}`\n- Tipo: {tipo}\n- Criado: {date.today():%d/%m/%Y}\n" + (f"- {descricao}\n" if descricao else "")
    else:
        corpo = f"# {nome}\n\n{descricao or ''}\n\n## Situação\n- criado em {date.today():%d/%m/%Y} ({tipo}) em `{pasta}`\n\n## Decisões\n\n## Próximos passos\n- [ ] primeiro commit útil\n"
    vault.write(rel, corpo)
    return rel
