"""Memória semântica — índice FTS5 do vault (`vault/.index.db`, derivado, gitignored).

`buscar(consulta)` substitui o grep quando o vault passa de LIMIAR_NOTAS; `recordar(texto)` é o recall proativo:
antes de cada turno, procura no vault o que o João pode já ter dito sobre o assunto e devolve até 3 lembretes curtos
("você falou disso em 12/03 em 20-Projetos/BUB.md"). Tokenizador unicode61 sem acentos: "orçamento" acha "orcamento".
Embeddings ficam para quando o FTS não bastar — por ora, BM25 resolve com centenas de notas."""
from __future__ import annotations
import re, sqlite3, unicodedata
from datetime import date
from pathlib import Path

LIMIAR_NOTAS = 500
STOP = {"para", "como", "isso", "esse", "essa", "esta", "este", "aqui", "ali", "onde", "quando", "porque", "mais", "menos",
        "muito", "pouco", "tudo", "nada", "você", "voce", "jaime", "joão", "joao", "sobre", "pode", "quero", "preciso", "vamos",
        "então", "entao", "hoje", "agora", "depois", "antes", "também", "tambem", "está", "esta", "estou", "fazer", "faz", "ficar"}
IGNORAR_PASTAS = ("60-Conversas", ".obsidian", "templates")

def _norm(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()

def palavras_chave(texto: str, max_n: int = 6) -> list[str]:
    toks = [w for w in re.findall(r"[a-z0-9]{4,}", _norm(texto)) if w not in STOP]
    vistos = []
    for w in toks:
        if w not in vistos:
            vistos.append(w)
    return vistos[:max_n]

class Indice:
    def __init__(self, vault_root: Path):
        self.root = Path(vault_root)
        self.db = self.root / ".index.db"
        self._con = sqlite3.connect(self.db)
        self._con.executescript("""
            CREATE TABLE IF NOT EXISTS notas(caminho TEXT PRIMARY KEY, mtime REAL);
            CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(caminho UNINDEXED, titulo, corpo, tokenize='unicode61 remove_diacritics 2');
        """)

    # ── manutenção ────────────────────────────────────
    def atualizar(self) -> int:
        """Reindexa só o que mudou (mtime). Devolve quantas notas foram (re)indexadas."""
        cur = self._con.cursor()
        conhecidas = dict(cur.execute("SELECT caminho, mtime FROM notas"))
        vistas, n = set(), 0
        for p in self.root.rglob("*.md"):
            if any(x in p.parts for x in IGNORAR_PASTAS):
                continue
            rel = str(p.relative_to(self.root)); vistas.add(rel)
            mt = p.stat().st_mtime
            if conhecidas.get(rel) == mt:
                continue
            txt = p.read_text(encoding="utf-8", errors="ignore")
            titulo = next((l.lstrip("# ").strip() for l in txt.splitlines() if l.startswith("#")), p.stem)
            cur.execute("DELETE FROM fts WHERE caminho = ?", (rel,))
            cur.execute("INSERT INTO fts(caminho, titulo, corpo) VALUES (?, ?, ?)", (rel, titulo, txt))
            cur.execute("INSERT OR REPLACE INTO notas(caminho, mtime) VALUES (?, ?)", (rel, mt))
            n += 1
        for rel in set(conhecidas) - vistas:
            cur.execute("DELETE FROM fts WHERE caminho = ?", (rel,)); cur.execute("DELETE FROM notas WHERE caminho = ?", (rel,))
        self._con.commit()
        return n

    def total(self) -> int:
        return self._con.execute("SELECT COUNT(*) FROM notas").fetchone()[0]

    # ── consultas ─────────────────────────────────────
    def buscar(self, consulta: str, limite: int = 12) -> list[tuple[str, str, float]]:
        """(caminho, trecho, score). Consulta livre: as palavras viram OR de prefixos."""
        termos = [f'"{t}"*' for t in palavras_chave(consulta, 8)] or [f'"{_norm(consulta)}"']
        q = " OR ".join(termos)
        try:
            rows = self._con.execute(
                "SELECT caminho, snippet(fts, 2, '«', '»', '…', 18), bm25(fts) FROM fts WHERE fts MATCH ? ORDER BY bm25(fts) LIMIT ?",
                (q, limite)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [(c, re.sub(r"\s+", " ", s).strip(), float(b)) for c, s, b in rows]

    def recordar(self, texto: str, limite: int = 3, hoje: date | None = None) -> list[str]:
        """Recall proativo: lembretes curtos do que o vault já sabe sobre o assunto (fora do diário de hoje)."""
        chaves = palavras_chave(texto)
        if len(chaves) < 2:
            return []
        hoje = hoje or date.today()
        out = []
        for caminho, trecho, score in self.buscar(" ".join(chaves), limite * 3):
            if caminho == f"40-Diario/{hoje.isoformat()}.md" or caminho.endswith("INDEX.md") or caminho.startswith("01-Estado/"):
                continue
            quando = ""
            if (m := re.match(r"40-Diario/(\d{4})-(\d{2})-(\d{2})\.md", caminho)):
                quando = f" (diário de {m.group(3)}/{m.group(2)})"
            out.append(f"{caminho}{quando}: {trecho[:160]}")
            if len(out) >= limite:
                break
        return out

    def fechar(self):
        self._con.close()
