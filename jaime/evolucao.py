"""Autoevolução — o Jaime propõe melhorias em si mesmo como PRs; o João aprova.

Semanalmente (rotina `propor melhoria`) ou a pedido: `propor()` lê os sinais (placar, problemas em aberto, pendências do
diário, aprendizados) e pede ao próprio Jaime UMA proposta em JSON. `implementar(id)` cria um **git worktree** em
`~/Jaime/worktrees/<slug>` na branch `jaime/<slug>` (o código em produção não é tocado — o Vigia só protege o repositório
principal), roda um turno avulso do Agent SDK ali (com testes), roda `pytest` nós mesmos, escreve `docs/PR-jaime-<slug>.md`
e commita. Merge só com o "confirmo" do João. Propostas ficam em `01-Estado/Propostas.md`."""
from __future__ import annotations
import asyncio, json, re, subprocess, time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from .hud.events import bus
from .identidade import slug as fazer_slug

ARQUIVO = "01-Estado/Propostas.md"
WORKTREES = Path("~/Jaime/worktrees").expanduser()

PROMPT_PROPOR = """Você está olhando para si mesmo. Sinais dos últimos dias:
{sinais}

Proponha UMA melhoria no seu próprio código (repositório jaime-vision) que resolva o sinal mais importante: pequena o bastante
para caber num PR com testes. Responda SOMENTE um JSON:
{{"titulo": "...", "motivo": "1-2 frases com o sinal que justifica", "arquivos": ["jaime/..."], "plano": "passos curtos", "testes": "o que o teste vai provar"}}"""

PROMPT_IMPLEMENTAR = """Você está num worktree do repositório do Jaime ({pasta}), na branch {branch}. Implemente esta melhoria:

Título: {titulo}
Motivo: {motivo}
Arquivos prováveis: {arquivos}
Plano: {plano}
Testes: {testes}

Regras: código no estilo do repositório (comentários em português explicando o porquê), testes em tests/, `pytest -q` verde.
Não toque em vault/, .env nem em nada fora de {pasta}. Ao terminar, responda em 3 linhas: o que mudou, como testou, o que ficou de fora."""

@dataclass
class Proposta:
    id: str
    titulo: str
    motivo: str
    arquivos: list[str] = field(default_factory=list)
    plano: str = ""
    testes: str = ""
    estado: str = "proposta"      # proposta | implementando | pronta | falhou | mergeada
    branch: str = ""
    pasta: str = ""
    criada: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))

    def linha(self) -> str:
        return (f"## {self.id} · {self.titulo} · {self.estado} · {self.criada}\n- motivo: {self.motivo}\n- arquivos: {', '.join(self.arquivos)}\n"
                f"- plano: {self.plano}\n- testes: {self.testes}\n" + (f"- branch: {self.branch} ({self.pasta})\n" if self.branch else ""))

SECAO_RX = re.compile(r"^## (M-\d{4}) · (.+?) · (\w+) · (\S+ \S+)\s*$", re.M)

def _extrair_json(txt: str) -> dict | None:
    m = re.search(r"\{.*\}", txt or "", re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None

def _git(pasta: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=pasta, capture_output=True, text=True, timeout=120)

class Evolucao:
    def __init__(self, jaime, repo_root: Path, implementador=None, testador=None):
        self.jaime, self.repo = jaime, Path(repo_root)
        self.implementador = implementador or self._implementar_com_sdk
        self.testador = testador or self._pytest

    # ── propostas ─────────────────────────────────────
    def propostas(self) -> list[Proposta]:
        txt = self.jaime.vault.read(ARQUIVO); out = []
        partes = SECAO_RX.split(txt)
        for i in range(1, len(partes), 5):
            pid, titulo, estado, criada, corpo = partes[i], partes[i + 1], partes[i + 2], partes[i + 3], partes[i + 4]
            g = lambda k: (re.search(rf"^- {k}:\s*(.*)$", corpo, re.M) or [None, ""])[1].strip()
            p = Proposta(pid, titulo.strip(), g("motivo"), [a.strip() for a in g("arquivos").split(",") if a.strip()], g("plano"), g("testes"), estado, criada=criada)
            if (b := re.search(r"^- branch:\s*(\S+) \((.+)\)$", corpo, re.M)):
                p.branch, p.pasta = b.group(1), b.group(2)
            out.append(p)
        return out

    def _salvar(self, lista: list[Proposta]) -> None:
        self.jaime.vault.write(ARQUIVO, "# Propostas de melhoria do Jaime\n\n> Ele propõe; o João aprova com \"confirmo\". Branches em ~/Jaime/worktrees.\n\n" + "\n".join(p.linha() for p in lista))

    def _atualizar(self, p: Proposta) -> None:
        lista = self.propostas()
        lista = [p if x.id == p.id else x for x in lista] if any(x.id == p.id for x in lista) else lista + [p]
        self._salvar(lista)

    def sinais(self) -> str:
        v = self.jaime.vault
        partes = []
        placar = v.read("01-Estado/Placar.md")
        if placar:
            partes.append("Placar:\n" + "\n".join(l for l in placar.splitlines() if l.startswith("| claude") or l.startswith("| openai") or l.startswith("| juiz"))[:1200])
        problemas = v.read("90-Estudo/Problemas.md")
        if problemas:
            partes.append("Problemas em aberto:\n" + "\n".join(l for l in problemas.splitlines() if l.startswith("## ") and "aberto" in l)[:800])
        pend = []
        for p in sorted((v.root / "40-Diario").glob("????-??-??.md"))[-7:]:
            t = p.read_text(encoding="utf-8", errors="ignore")
            if "## Pendente" in t:
                pend += [l for l in t.split("## Pendente", 1)[1].split("\n## ", 1)[0].splitlines() if l.startswith("- ")][:5]
        if pend:
            partes.append("Pendências do diário (7 dias):\n" + "\n".join(pend[-15:]))
        aprend = self.jaime.estado.secao("Aprendizados recentes") if getattr(self.jaime, "estado", None) else ""
        if aprend and "nenhum" not in aprend.lower():
            partes.append("Aprendizados recentes:\n" + aprend[:600])
        return "\n\n".join(partes) or "(sem sinais ainda: placar vazio, nenhum problema, diário sem pendências)"

    async def propor(self) -> Proposta | None:
        txt = await self.jaime.ask(PROMPT_PROPOR.format(sinais=self.sinais()), canal="evolucao")
        d = _extrair_json(txt)
        if not d or not d.get("titulo"):
            bus.emitir("evolucao", msg="não consegui formular uma proposta"); return None
        n = max((int(p.id[2:]) for p in self.propostas()), default=0) + 1
        p = Proposta(f"M-{n:04d}", str(d["titulo"])[:100], str(d.get("motivo", ""))[:300], [str(a) for a in d.get("arquivos", [])][:8],
                     str(d.get("plano", ""))[:400], str(d.get("testes", ""))[:300])
        self._atualizar(p)
        self.jaime.vault.diario(f"Proposta de melhoria {p.id}: {p.titulo} — diga 'implementa {p.id}' e depois 'confirmo' para o merge", "Pendente")
        bus.emitir("evolucao", id=p.id, titulo=p.titulo, estado=p.estado, msg=f"proposta {p.id}: {p.titulo}")
        return p

    # ── implementação em worktree ─────────────────────
    def worktree(self, p: Proposta) -> Path:
        s = fazer_slug(p.titulo)[:40]
        branch, pasta = f"jaime/{s}", WORKTREES / s
        WORKTREES.mkdir(parents=True, exist_ok=True)
        if not pasta.exists():
            r = _git(self.repo, "worktree", "add", "-b", branch, str(pasta), "main")
            if r.returncode != 0 and "already exists" in (r.stderr or ""):
                r = _git(self.repo, "worktree", "add", str(pasta), branch)
            if r.returncode != 0:
                raise RuntimeError(f"git worktree: {r.stderr[-200:]}")
        p.branch, p.pasta = branch, str(pasta)
        return pasta

    async def _implementar_com_sdk(self, p: Proposta, pasta: Path) -> str:
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock, HookMatcher
        raiz = str(pasta)
        async def so_no_worktree(input_data, tool_use_id, context):
            nome = input_data.get("tool_name", ""); a = input_data.get("tool_input", {}) or {}
            alvo = str(a.get("file_path", "")); cmd = str(a.get("command", ""))
            fora = (nome in ("Write", "Edit", "MultiEdit") and alvo and not alvo.startswith(raiz)) or \
                   (nome == "Bash" and (re.search(r"\bgit\s+push\b|\bsudo\b|\brm\s+-rf\s+/", cmd) or (self.repo.as_posix() in cmd and raiz not in cmd)))
            if fora or "/vault/" in alvo or alvo.endswith(".env"):
                return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": f"AUTOEVOLUÇÃO: só dentro de {raiz}, sem vault/.env/push."}}
            return {}
        opts = ClaudeAgentOptions(model=self.jaime.s.model_codigo, cwd=raiz, max_turns=60, permission_mode="bypassPermissions",
                                  allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
                                  hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[so_no_worktree])]},
                                  system_prompt="Você é o maester-dev do Jaime melhorando o próprio Jaime, num worktree isolado.")
        partes = []
        async for msg in query(prompt=PROMPT_IMPLEMENTAR.format(pasta=raiz, branch=p.branch, titulo=p.titulo, motivo=p.motivo,
                                                              arquivos=", ".join(p.arquivos), plano=p.plano, testes=p.testes), options=opts):
            if isinstance(msg, AssistantMessage):
                partes += [b.text for b in msg.content if isinstance(b, TextBlock)]
        return "".join(partes)[-600:]

    def _pytest(self, pasta: Path) -> tuple[bool, str]:
        venv = self.repo / ".venv" / "bin" / "python"
        r = subprocess.run([str(venv) if venv.exists() else "python3", "-m", "pytest", "-q", "-x"], cwd=pasta, capture_output=True, text=True, timeout=900)
        return r.returncode == 0, (r.stdout + r.stderr)[-400:]

    async def implementar(self, pid: str) -> Proposta:
        p = next((x for x in self.propostas() if x.id == pid), None)
        if not p:
            raise ValueError(f"{pid} não existe")
        pasta = self.worktree(p)
        p.estado = "implementando"; self._atualizar(p)
        bus.emitir("evolucao", id=p.id, titulo=p.titulo, estado=p.estado)
        relato = await self.implementador(p, pasta)
        ok, saida = await asyncio.to_thread(self.testador, pasta)
        p.estado = "pronta" if ok else "falhou"
        (pasta / "docs").mkdir(exist_ok=True)
        (pasta / "docs" / f"PR-jaime-{fazer_slug(p.titulo)[:40]}.md").write_text(
            f"# PR — {p.titulo}\n\n**Branch:** `{p.branch}` → `main` (proposta {p.id}, {p.criada})\n\n## Motivo\n{p.motivo}\n\n## Plano\n{p.plano}\n\n"
            f"## Testes\n{p.testes}\n\n## Relato do Jaime\n{relato}\n\n## pytest\n```\n{saida}\n```\n", encoding="utf-8")
        _git(pasta, "add", "-A"); _git(pasta, "commit", "-q", "-m", f"jaime: {p.titulo} ({p.id})")
        self._atualizar(p)
        self.jaime.vault.diario(f"Melhoria {p.id} {p.estado}: branch {p.branch} em {pasta} — merge só com 'confirmo'", "Feito" if ok else "Pendente")
        bus.emitir("evolucao", id=p.id, titulo=p.titulo, estado=p.estado, msg=f"{p.id} {p.estado}: {p.branch}")
        return p
