"""Maestri pelo Jaime — o serviço fala com o canvas usando a identidade do terminal Maestro "Cerebro Principal J.A.I.M.E".

O CLI `maestri` só responde com MAESTRI_SOCKET e MAESTRI_TERMINAL_ID; os dois são descobertos sozinhos (socket em
$TMPDIR/maestri-*/maestri.sock; terminal com `isManager` no workspace.json) ou fixados em JAIME_MAESTRI_SOCKET /
JAIME_MAESTRI_TERMINAL_ID. Sem Maestri aberto, `disponivel` é False e as ferramentas explicam isso — nunca travam.
`executor(args, timeout) -> (rc, saida)` é injetável para testes."""
from __future__ import annotations
import glob, json, os, shlex, subprocess, tempfile
from pathlib import Path

CLI_PADRAO = "/Applications/Maestri.app/Contents/Resources/maestri"
NOME_PREFERIDO = ("J.A.I.M.E", "JAIME", "Jaime")

def descobrir_socket() -> str:
    if (s := os.environ.get("JAIME_MAESTRI_SOCKET") or os.environ.get("MAESTRI_SOCKET")):
        return s
    candidatos = []
    for base in (os.environ.get("TMPDIR", ""), tempfile.gettempdir(), "/tmp"):
        if base:
            candidatos += glob.glob(os.path.join(base, "maestri-*", "maestri.sock"))
    candidatos = sorted(set(candidatos), key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0, reverse=True)
    return candidatos[0] if candidatos else ""

def _maestros() -> list[tuple[str, str]]:
    """(id, nome) dos terminais com Maestro ligado, em todos os workspaces do Maestri."""
    achados = []
    for f in glob.glob(os.path.expanduser("~/.maestri/workspaces/*/workspace.json")):
        try:
            d = json.load(open(f, encoding="utf-8")).get("payload", {})
        except Exception:
            continue
        for n in d.get("nodes", []):
            t = ((n.get("content") or {}).get("terminal") or {}).get("_0")
            if t and t.get("isManager") and t.get("status") == "running":
                achados.append((t.get("id", ""), t.get("name", "")))
    return achados

def descobrir_terminal(nome_preferido: tuple[str, ...] = NOME_PREFERIDO) -> tuple[str, str]:
    """(terminal_id, nome) do terminal Maestro que o Jaime usa para recrutar.
    Ordem: JAIME_MAESTRI_TERMINAL_ID explícito → o próprio terminal (MAESTRI_TERMINAL_ID) se ele for Maestro →
    um Maestro com 'J.A.I.M.E' no nome → o primeiro Maestro. Quando o serviço roda num terminal do Maestri que NÃO é
    Maestro (um nó "Shell" com `jaime serve`), ele age pelo Maestro do workspace — por isso o env do próprio terminal
    não vale sozinho."""
    if (t := os.environ.get("JAIME_MAESTRI_TERMINAL_ID")):
        return t, os.environ.get("JAIME_MAESTRI_TERMINAL_NOME", "")
    maestros = _maestros()
    proprio = os.environ.get("MAESTRI_TERMINAL_ID", "")
    for tid, nome in maestros:
        if proprio and tid == proprio:
            return tid, nome
    for tid, nome in maestros:
        if any(p.lower() in nome.lower() for p in nome_preferido):
            return tid, nome
    return maestros[0] if maestros else ("", "")

class Maestri:
    def __init__(self, executor=None, cli: str | None = None):
        self.cli = cli or os.environ.get("MAESTRI_CLI") or CLI_PADRAO
        self.socket = descobrir_socket()
        self.terminal_id, self.terminal_nome = descobrir_terminal()
        self.executor = executor or self._subprocess
        self.ultimo_erro = ""

    @property
    def disponivel(self) -> bool:
        return bool(self.socket and self.terminal_id and (self.executor is not self._subprocess or os.path.exists(self.cli)))

    def redescobrir(self) -> bool:
        self.socket = descobrir_socket(); self.terminal_id, self.terminal_nome = descobrir_terminal()
        return self.disponivel

    # ── execução ───────────────────────────────────────
    def _subprocess(self, args: list[str], timeout: float) -> tuple[int, str]:
        env = dict(os.environ, MAESTRI_SOCKET=self.socket, MAESTRI_TERMINAL_ID=self.terminal_id)
        try:
            r = subprocess.run([self.cli, *args], capture_output=True, text=True, timeout=timeout, env=env)
            return r.returncode, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            return 124, f"maestri {args[0]}: estourou {timeout:.0f}s"
        except FileNotFoundError:
            return 127, "maestri: CLI não encontrado"

    def _run(self, *args: str, timeout: float = 30) -> str:
        if not self.disponivel and not self.redescobrir():
            raise RuntimeError("Maestri não está disponível (app fechado, sem terminal Maestro ou sem socket)")
        rc, saida = self.executor(list(args), timeout)
        if rc != 0:
            self.ultimo_erro = saida.strip()[-300:]
            raise RuntimeError(f"maestri {args[0]}: {self.ultimo_erro}")
        return saida.strip()

    # ── equipe ─────────────────────────────────────────
    def listar(self) -> str: return self._run("list")
    def presets(self) -> list[str]:
        saida = self._run("preset", "list")
        return [l.strip().strip('"- ') .strip('"') for l in saida.splitlines() if l.strip().startswith("-")]
    def papeis(self) -> str: return self._run("role", "list")
    def criar_papel(self, nome: str, prompt: str) -> str: return self._run("role", "create", nome, prompt, timeout=60)
    def escrever_papel(self, nome: str, prompt: str) -> str: return self._run("role", "write", nome, prompt, timeout=60)
    def recrutar(self, nome: str, papel: str = "", preset: str = "Claude Code", pasta: str = "") -> str:
        args = ["recruit", nome, "--preset", preset]
        if papel: args += ["--role", papel]
        if pasta: args += ["--dir", pasta]
        return self._run(*args, timeout=90)
    def dispensar(self, nome: str) -> str: return self._run("dismiss", nome, timeout=60)
    def conectar(self, a: str, b: str) -> str: return self._run("connect", a, b)
    def pedir(self, nome: str, prompt: str, timeout: float = 600) -> str: return self._run("ask", nome, prompt, timeout=timeout)
    def enter(self, nome: str) -> str: return self._run("ask", nome, "--raw", "\\n", timeout=20)
    def checar(self, nome: str) -> str: return self._run("check", nome)
    # ── notas ──────────────────────────────────────────
    def nota_criar(self, nome: str, conteudo: str) -> str: return self._run("note", "create", "--name", nome, conteudo, timeout=60)
    def nota_ler(self, nome: str) -> str: return self._run("note", "read", nome)
    def nota_escrever(self, nome: str, conteudo: str) -> str: return self._run("note", "write", nome, conteudo, timeout=60)
    def nota_editar(self, nome: str, velho: str, novo: str) -> str: return self._run("note", "edit", nome, velho, novo, timeout=60)

    @staticmethod
    def texto_da_nota(saida: str) -> str:
        """`note read` devolve linhas numeradas ("12\\ttexto"); tira os números."""
        linhas = []
        for l in saida.splitlines():
            partes = l.split("\t", 1)
            linhas.append(partes[1] if len(partes) == 2 and partes[0].strip().isdigit() else l)
        return "\n".join(linhas)
