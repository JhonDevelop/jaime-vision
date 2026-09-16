"""Acesso ao vault Obsidian — a memória de longo prazo do Jaime.

Tudo é markdown em disco: o João pode abrir no Obsidian e editar; o Jaime lê e escreve
pelas mesmas funções. Sem banco, sem embeddings por padrão — grep resolve até o vault
passar de alguns milhares de notas."""
from __future__ import annotations
import hashlib, os, re
from datetime import date, datetime
from pathlib import Path

# ── redator de segredos ─────────────────────────────────────
# 16/09 07:24: uma reflexão do próprio Jaime escreveu a palavra-passe em texto puro no diário. Toda escrita no vault
# passa por aqui: qualquer sequência de dígitos (ou números por extenso) cujo SHA-256 bata com JAIME_PASSPHRASE_HASH
# vira "••••". Compara-se o hash, nunca a senha.
_HASH_PADRAO = "1718c24b10aeb8099e3fc44960ab6949ab76a267352459f203ea1036bec382c2"
_NUM = r"(?:zero|uma?|hum|du[ao]s|dois|tr[êe]s|quatro|cinco|seis|meia|sete|oito|nove|\d)"
_SEQ_RX = re.compile(rf"\b{_NUM}(?:[ ,.\-]*{_NUM}){{3,15}}\b", re.I)

def redigir_segredos(texto: str) -> str:
    h = (os.environ.get("JAIME_PASSPHRASE_HASH") or _HASH_PADRAO).strip().lower()
    if not texto or not h:
        return texto
    from ..vigia.acesso import normalizar
    def _mascarar(m: re.Match) -> str:
        digitos = normalizar(m.group(0))
        if len(digitos) >= 4 and hashlib.sha256(digitos.encode()).hexdigest() == h:
            return "••••"
        return m.group(0)
    return _SEQ_RX.sub(_mascarar, texto)

DAILY_TEMPLATE = """# {dia}

## Feito
## Decisões
## Pendente
## Log
"""

class Vault:
    def __init__(self, root: Path):
        self.root = Path(root)
        if not self.root.exists():
            raise FileNotFoundError(f"Vault não encontrado: {self.root}")

    # ── básico ─────────────────────────────────────────
    def path(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if self.root not in p.parents and p != self.root:
            raise ValueError("Caminho fora do vault")
        return p

    def read(self, rel: str) -> str:
        p = self.path(rel)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def write(self, rel: str, content: str) -> Path:
        if rel.startswith("00-Jaime/"):
            raise PermissionError("00-Jaime/ só o João edita")
        p = self.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(redigir_segredos(content), encoding="utf-8")
        return p

    def append(self, rel: str, text: str) -> Path:
        cur = self.read(rel)
        sep = "" if cur.endswith("\n") or not cur else "\n"
        return self.write(rel, f"{cur}{sep}{text.rstrip()}\n")

    # ── diário ─────────────────────────────────────────
    def daily_rel(self, d: date | None = None) -> str:
        d = d or date.today()
        return f"40-Diario/{d.isoformat()}.md"

    def diario(self, texto: str, secao: str = "Log") -> str:
        rel = self.daily_rel()
        if not self.read(rel):
            self.write(rel, DAILY_TEMPLATE.format(dia=date.today().strftime("%d/%m/%Y")))
        content = self.read(rel)
        linha = f"- {datetime.now():%H:%M} {texto.strip()}"
        marker = f"## {secao}"
        if marker in content:
            head, tail = content.split(marker, 1)
            # insere logo após o cabeçalho da seção
            tail_lines = tail.split("\n", 1)
            rest = tail_lines[1] if len(tail_lines) > 1 else ""
            content = f"{head}{marker}\n{linha}\n{rest}"
            self.write(rel, content)
        else:
            self.append(rel, f"\n{marker}\n{linha}")
        return rel

    # ── tarefas ────────────────────────────────────────
    def tarefa(self, descricao: str, projeto: str = "", prazo: str = "") -> str:
        item = f"- [ ] {descricao.strip()}"
        if projeto:
            item += f" @{projeto.strip().lstrip('@')}"
        if prazo:
            item += f" ⏳ {prazo.strip()}"
        self.append("30-Tarefas/Inbox.md", item)
        return item

    def tarefas_abertas(self) -> list[str]:
        return [l for l in self.read("30-Tarefas/Inbox.md").splitlines() if l.startswith("- [ ]")]

    # ── busca ──────────────────────────────────────────
    indice = None   # jaime/brain/indice.py, ligado pelo orquestrador; usado quando o vault passa de 500 notas

    def buscar(self, termo: str, limite: int = 12) -> list[tuple[str, int, str]]:
        if self.indice is not None:
            try:
                from .indice import LIMIAR_NOTAS
                if self.indice.total() > LIMIAR_NOTAS:
                    self.indice.atualizar()
                    return [(c, 0, t) for c, t, _ in self.indice.buscar(termo, limite)]
            except Exception:
                pass
        rx = re.compile(re.escape(termo), re.IGNORECASE)
        hits: list[tuple[str, int, str]] = []
        for p in sorted(self.root.rglob("*.md")):
            if ".obsidian" in p.parts:
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if rx.search(line):
                    hits.append((str(p.relative_to(self.root)), i, line.strip()[:200]))
                    if len(hits) >= limite:
                        return hits
        return hits

    def projetos(self) -> list[tuple[str, str]]:
        """(nome, primeira linha de descrição) de cada nota em 20-Projetos/."""
        out = []
        for p in sorted((self.root / "20-Projetos").glob("*.md")):
            body = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
            out.append((p.stem, body[0] if body else ""))
        return out

    # ── contexto de sessão ─────────────────────────────
    def contexto_inicial(self) -> str:
        blocos = [
            ("Identidade", self.read("00-Jaime/Identidade.md")),
            ("Regras", self.read("00-Jaime/Regras.md")),
            ("Perfil do João", self.read("10-Eu/Perfil.md")),
            ("Pessoas próximas", self.read("10-Eu/Pessoas.md")),
            ("Datas importantes", self.read("10-Eu/Datas.md")),
            ("Projetos", "\n".join(f"- [[{n}]] — {d}" for n, d in self.projetos())
             + "\n(use ler_nota para o dossiê completo de cada um; se estiver raso, aprofundar enche a nota)"),
            ("Conhecimento (índice)", "\n".join(l for l in self.read("50-Conhecimento/INDEX.md").splitlines() if l.startswith("- "))),
            ("Tarefas abertas", "\n".join(self.tarefas_abertas()[:15])),
            ("Diário de hoje", self.read(self.daily_rel())),
        ]
        return "\n\n".join(f"### {t}\n{c.strip()}" for t, c in blocos if c.strip())
