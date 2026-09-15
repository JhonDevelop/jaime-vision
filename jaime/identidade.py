"""Identidade: o nome mora em UM lugar — o frontmatter de `vault/00-Jaime/Identidade.md`.

```
---
nome: Jaime
apelidos: []
wake_word: jaime
confirmado: false
---
```
Todo texto que o mundo vê (prompts, HUD, voz, diário) pergunta o nome aqui; nada é hardcoded.
`00-Jaime/` é do João — este módulo é o único código autorizado a escrever nele, e só nos campos
do frontmatter, via `renomear()`/`confirmar()`, que por sua vez só rodam depois de um "confirmo"."""
from __future__ import annotations
import re, subprocess
from pathlib import Path
import yaml

ARQUIVO_REL = "00-Jaime/Identidade.md"
FRONT_RX = re.compile(r"^---\n(.*?)\n---\n?", re.S)
PADRAO = {"nome": "Jaime", "apelidos": [], "wake_word": "jaime", "confirmado": False}
# como os transcritores costumam escrever cada nome (o STT erra por som, não por letra)
VARIANTES_CONHECIDAS = {
    "jaime": ["jayme", "jaimi", "jaimy", "jamie", "jaine", "jaim", "jaimes", "jaimin", "jardim", "gênio", "genio", "jay me"],
}
RENOMEAR_RX = re.compile(
    r"^(?:(?:me\s+)?(?:pode\s+)?(?:te\s+)?chama(?:r)?\s+(?:você\s+)?de|te\s+chamo\s+de|quero\s+te\s+chamar\s+de|"
    r"seu\s+nome\s+(?:agora\s+)?(?:é|e|vai\s+ser|será)|(?:vou\s+)?renomear(?:\s+você)?(?:\s+para)?)\s+([A-Za-zÀ-ÿ][\wÀ-ÿ-]{1,24})\b",
    re.I)

def slug(nome: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "nome"

def quer_renomear(texto: str) -> str | None:
    """'me chama de Fred' / 'seu nome agora é Vega' / 'renomear Atlas' → 'Fred' / 'Vega' / 'Atlas'."""
    m = RENOMEAR_RX.search(texto.strip().rstrip(".!?"))
    return m.group(1).strip().capitalize() if m else None

def eh_sim(texto: str) -> bool:
    return texto.strip().lower().rstrip(".!") in {"sim", "confirma", "confirmo", "isso", "é isso", "isso mesmo", "pode ser", "claro", "exato"}

class Identidade:
    def __init__(self, vault_root: Path, repo_root: Path | None = None):
        self.vault_root = Path(vault_root)
        self.repo_root = Path(repo_root) if repo_root else None
        self.arquivo = self.vault_root / ARQUIVO_REL

    # ── leitura ───────────────────────────────────────
    def _partes(self) -> tuple[dict, str]:
        txt = self.arquivo.read_text(encoding="utf-8") if self.arquivo.exists() else ""
        m = FRONT_RX.match(txt)
        if not m:
            return {}, txt
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        return (meta if isinstance(meta, dict) else {}), txt[m.end():]

    def ler(self) -> dict:
        meta, _ = self._partes()
        d = dict(PADRAO); d.update({k: v for k, v in meta.items() if k in PADRAO})
        d["apelidos"] = list(d.get("apelidos") or [])
        d["confirmado"] = bool(d.get("confirmado"))
        d["nome"] = str(d["nome"]).strip() or PADRAO["nome"]
        return d

    @property
    def nome(self) -> str:
        return self.ler()["nome"]

    @property
    def confirmado(self) -> bool:
        return self.ler()["confirmado"]

    def variantes(self) -> list[str]:
        """Nome, apelidos e grafias que o STT costuma produzir — para a ativação por voz."""
        d = self.ler(); base = d["nome"].lower()
        out = [base] + [a.lower() for a in d["apelidos"]] + VARIANTES_CONHECIDAS.get(base, [])
        return list(dict.fromkeys(out))

    # ── escrita (só frontmatter; o corpo é do João) ────
    def escrever(self, **campos) -> None:
        meta, corpo = self._partes()
        meta.update(campos)
        front = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self.arquivo.write_text(f"---\n{front}\n---\n{corpo.lstrip()}", encoding="utf-8")

    def confirmar(self) -> None:
        self.escrever(confirmado=True)

    def renomear(self, novo: str, git: bool = True) -> list[str]:
        """Aplica o §2.9: Identidade.md, CLAUDE.md, .env (JAIME_NOME). Devolve os arquivos alterados.
        Com git=True cria a branch chore/renomear-<slug> e commita."""
        novo = novo.strip()
        if not novo or novo.lower() == self.nome.lower():
            return []
        antigo = self.nome
        alterados = []
        # 1) frontmatter + primeira menção no corpo ("Sou o Jaime." → "Sou o Vega.")
        meta, corpo = self._partes()
        corpo_novo = re.sub(rf"\b{re.escape(antigo)}\b", novo, corpo, count=1)
        meta.update({"nome": novo, "wake_word": novo.lower(), "confirmado": False})
        front = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
        self.arquivo.write_text(f"---\n{front}\n---\n{corpo_novo.lstrip()}", encoding="utf-8")
        alterados.append(str(self.arquivo))
        if self.repo_root:
            # 2) CLAUDE.md: título e "Você é o **X**"
            claude = self.repo_root / "CLAUDE.md"
            if claude.exists():
                t = claude.read_text(encoding="utf-8")
                t2 = t.replace(f"# {antigo} — constituição", f"# {novo} — constituição").replace(f"Você é o **{antigo}**", f"Você é o **{novo}**")
                if t2 != t:
                    claude.write_text(t2, encoding="utf-8"); alterados.append(str(claude))
            # 3) .env / .env.example: JAIME_NOME
            for nome_arq in (".env", ".env.example"):
                env = self.repo_root / nome_arq
                if env.exists():
                    t = env.read_text(encoding="utf-8")
                    t2 = re.sub(r"^JAIME_NOME=.*$", f"JAIME_NOME={novo.lower()}", t, flags=re.M) if "JAIME_NOME=" in t else t + f"\nJAIME_NOME={novo.lower()}\n"
                    if t2 != t:
                        env.write_text(t2, encoding="utf-8")
                        if nome_arq != ".env":
                            alterados.append(str(env))
            if git:
                self._commit(f"chore/renomear-{slug(novo)}", f"chore: renomear {antigo} → {novo}", [a for a in alterados if not a.endswith("/.env")])
        return alterados

    def _commit(self, branch: str, msg: str, arquivos: list[str]) -> None:
        def g(*args):
            return subprocess.run(["git", *args], cwd=self.repo_root, capture_output=True, text=True, timeout=30)
        if g("rev-parse", "--is-inside-work-tree").returncode != 0:
            return
        atual = g("branch", "--show-current").stdout.strip()
        if atual != branch:
            if g("checkout", "-b", branch).returncode != 0:
                g("checkout", branch)
        g("add", *[str(Path(a).relative_to(self.repo_root)) for a in arquivos])
        g("commit", "-q", "-m", msg)
