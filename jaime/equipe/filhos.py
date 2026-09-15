"""Filhos do J.A.I.M.E — ele cria orquestradores e sistemas secundários para ampliar as próprias capacidades.

Um filho é um terminal no Maestri (Claude Code, Codex, shell…) com um papel, uma missão e uma pasta própria:
- `codigo`   → git worktree em ~/Jaime/worktrees/<slug> (branch jaime/<slug>) — nunca toca o Jaime em produção
- `pesquisa` → ~/Jaime/filhos/<slug> (laboratório: sandbox, sem acesso ao vault)
- `mvp`      → ~/projetos/<slug> (um produto/sistema novo, com git próprio)
- `operacao` → a pasta que a missão pedir (mão de obra: rodar, instalar, migrar)
O filho relata pela nota compartilhada `equipe-relatorios` ("## <nome> · <hora>\n…"); o Jaime lê a cada minuto,
leva ao diário/HUD e, se for importante, fala. Registro persistente em `01-Estado/Equipe.md`.
Limites: JAIME_FILHOS_MAX (padrão 4) vivos ao mesmo tempo; dispensar passa pelo Vigia."""
from __future__ import annotations
import asyncio, os, re, subprocess, time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from ..hud.events import bus
from ..identidade import slug as fazer_slug
from .maestri import Maestri

ARQUIVO = "01-Estado/Equipe.md"
NOTA_RELATORIOS = "equipe-relatorios"
WORKTREES = Path(os.environ.get("JAIME_WORKTREES", "~/Jaime/worktrees")).expanduser()
LABORATORIOS = Path(os.environ.get("JAIME_FILHOS_DIR", "~/Jaime/filhos")).expanduser()
MAX_FILHOS = int(os.environ.get("JAIME_FILHOS_MAX", "4"))
PRESETS = {"claude": "Claude Code", "codex": "Codex", "opencode": "OpenCode", "shell": "Shell", "antigravity": "Antigravity"}
TIPOS = ("codigo", "pesquisa", "mvp", "operacao")

REGRAS_COMUNS = """
Regras: você é um filho do J.A.I.M.E (assistente pessoal do João, Franca/SP). Trabalhe SÓ na pasta {pasta}.
Não toque no repositório principal do Jaime nem no vault dele. Nunca git push; nunca apague nada fora da sua pasta;
nunca exponha segredos. Não pare para pedir confirmação: decida, registre e siga; o que só o João decide, anote.
A cada avanço relevante e ao terminar, escreva um relatório curto (5 linhas) na nota compartilhada `{nota}` com
`maestri note edit "{nota}" "## fim" "## {nome} · <hora>\\n<relatório>\\n\\n## fim"` — o Jaime lê essa nota.
Rode `maestri list` para ver quem está conectado. Responda curto, em português."""

PAPEIS_BASE = {
    "codigo": "Você é um desenvolvedor sênior. Missão: {missao}. Branch própria no worktree; testes verdes antes de dizer pronto; commits pequenos.",
    "pesquisa": "Você é um pesquisador metódico. Missão: {missao}. Pesquise na web e em docs, faça experimentos reproduzíveis na sua pasta e entregue: conclusão em 3 frases, evidências, fontes datadas, o que falta.",
    "mvp": "Você é um fundador técnico. Missão: {missao}. Construa o MVP mais simples que funciona na sua pasta (git init, README com como rodar, testes mínimos), sem enfeite; entregue rodando.",
    "operacao": "Você é o braço operacional. Missão: {missao}. Execute passo a passo na sua pasta, verifique cada passo, e relate o que fez, o que falhou e o que precisa do João.",
}

@dataclass
class Filho:
    nome: str
    tipo: str
    missao: str
    preset: str
    pasta: str
    papel: str
    criado_em: str = field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y %H:%M"))
    estado: str = "vivo"                 # vivo | dispensado
    ultimo_relatorio: str = ""
    tarefas: int = 0

    def linha(self) -> str:
        return (f"## {self.nome}\n- tipo: {self.tipo} · preset: {self.preset} · estado: {self.estado} · criado: {self.criado_em}\n"
                f"- missão: {self.missao}\n- pasta: {self.pasta}\n- papel: {self.papel}\n- tarefas: {self.tarefas}\n"
                f"- último relatório: {self.ultimo_relatorio[:300]}\n")

class Equipe:
    def __init__(self, jaime, repo_root: Path, maestri: Maestri | None = None, vigia=None):
        self.jaime, self.repo, self.vigia = jaime, Path(repo_root), vigia
        self.maestri = maestri or Maestri()
        self.filhos: dict[str, Filho] = {}
        self._relatorios_vistos: set[str] = set()
        self._carregar()

    # ── persistência ───────────────────────────────────
    def _carregar(self) -> None:
        txt = ""
        try:
            txt = self.jaime.vault.read(ARQUIVO) or ""
        except Exception:
            return
        for bloco in re.split(r"^## ", txt, flags=re.M)[1:]:
            linhas = bloco.splitlines()
            nome = linhas[0].strip()
            campos = {m.group(1): m.group(2).strip() for l in linhas[1:] if (m := re.match(r"^- ([^:]+): (.*)$", l))}
            meta = campos.get("tipo", "")
            m = re.match(r"(\w+) · preset: ([^·]+) · estado: (\w+) · criado: (.*)$", meta)
            if not m:
                continue
            self.filhos[nome] = Filho(nome, m.group(1), campos.get("missão", ""), m.group(2).strip(), campos.get("pasta", ""), campos.get("papel", ""),
                                      m.group(4).strip(), m.group(3), campos.get("último relatório", ""), int(campos.get("tarefas", "0") or 0))

    def _salvar(self) -> None:
        try:
            self.jaime.vault.write(ARQUIVO, "# Equipe — filhos do J.A.I.M.E\n\n> Terminais que o Jaime criou no Maestri. Relatórios chegam pela nota `equipe-relatorios`.\n\n"
                                   + "\n".join(f.linha() for f in self.filhos.values()))
        except Exception:
            pass
        bus.emitir("equipe", filhos=[{"nome": f.nome, "tipo": f.tipo, "estado": f.estado, "preset": f.preset, "tarefas": f.tarefas} for f in self.filhos.values()])

    # ── consulta ───────────────────────────────────────
    @property
    def vivos(self) -> list[Filho]:
        return [f for f in self.filhos.values() if f.estado == "vivo"]

    def resumo(self) -> str:
        if not self.filhos:
            return "Nenhum filho ainda." + ("" if self.maestri.disponivel else " (Maestri indisponível agora.)")
        return "\n".join(f"- {f.nome} · {f.tipo} · {f.preset} · {f.estado} · {f.missao[:60]}" + (f" · último: {f.ultimo_relatorio[:80]}" if f.ultimo_relatorio else "")
                         for f in self.filhos.values())

    # ── criação ────────────────────────────────────────
    def _pasta(self, tipo: str, slug: str, projeto: str = "") -> Path:
        if projeto:
            return Path(projeto).expanduser()
        if tipo == "codigo":
            pasta = WORKTREES / slug
            if not pasta.exists():
                WORKTREES.mkdir(parents=True, exist_ok=True)
                r = subprocess.run(["git", "worktree", "add", "-b", f"jaime/{slug}", str(pasta), "main"], cwd=self.repo, capture_output=True, text=True)
                if r.returncode != 0:
                    r = subprocess.run(["git", "worktree", "add", str(pasta), f"jaime/{slug}"], cwd=self.repo, capture_output=True, text=True)
                if r.returncode != 0:
                    raise RuntimeError(f"git worktree: {r.stderr[-200:]}")
            return pasta
        if tipo == "mvp":
            base = Path(getattr(self.jaime.s, "workspace", "~/projetos")).expanduser() if hasattr(self.jaime, "s") else Path("~/projetos").expanduser()
            pasta = base / slug
        else:
            pasta = LABORATORIOS / slug
        pasta.mkdir(parents=True, exist_ok=True)
        return pasta

    def papel_para(self, nome: str, tipo: str, missao: str, pasta: Path, extra: str = "") -> str:
        base = PAPEIS_BASE.get(tipo, PAPEIS_BASE["operacao"]).format(missao=missao)
        return (base + ("\n" + extra if extra else "") + REGRAS_COMUNS.format(pasta=pasta, nota=NOTA_RELATORIOS, nome=nome)).strip()

    def criar(self, nome: str, missao: str, tipo: str = "codigo", preset: str = "claude", projeto: str = "", papel_extra: str = "") -> Filho:
        tipo = tipo if tipo in TIPOS else "operacao"
        preset_nome = PRESETS.get(preset.lower(), preset) if preset else "Claude Code"
        if len(self.vivos) >= MAX_FILHOS:
            raise RuntimeError(f"já há {len(self.vivos)} filhos vivos (limite JAIME_FILHOS_MAX={MAX_FILHOS}); dispense um antes")
        if nome in self.filhos and self.filhos[nome].estado == "vivo":
            raise RuntimeError(f"já existe um filho vivo chamado {nome}")
        slug = fazer_slug(nome)
        pasta = self._pasta(tipo, slug, projeto)
        papel_nome = f"Filho: {nome}"
        papel = self.papel_para(nome, tipo, missao, pasta, papel_extra)
        try:
            self.maestri.criar_papel(papel_nome, papel)
        except RuntimeError as e:
            if "already" in str(e).lower() or "já" in str(e).lower():
                self.maestri.escrever_papel(papel_nome, papel)
            else:
                raise
        self._garantir_nota()
        self.maestri.recrutar(nome, papel_nome, preset_nome, str(pasta))
        try:
            self.maestri.conectar(NOTA_RELATORIOS, nome)
        except RuntimeError:
            pass
        f = Filho(nome, tipo, missao, preset_nome, str(pasta), papel_nome)
        self.filhos[nome] = f; self._salvar()
        self.jaime.vault.diario(f"Filho criado: {nome} ({tipo}, {preset_nome}) — {missao[:120]} · pasta {pasta}", "Decisões")
        return f

    def _garantir_nota(self) -> None:
        try:
            self.maestri.nota_ler(NOTA_RELATORIOS)
        except RuntimeError:
            try:
                self.maestri.nota_criar(NOTA_RELATORIOS, "# Relatórios dos filhos do J.A.I.M.E\n\n## fim\n")
            except RuntimeError:
                pass

    # ── delegação ──────────────────────────────────────
    def delegar(self, nome: str, tarefa: str, esperar_s: float = 0) -> str:
        f = self.filhos.get(nome)
        if not f or f.estado != "vivo":
            raise RuntimeError(f"não há filho vivo chamado {nome}")
        f.tarefas += 1; self._salvar()
        prompt = f"{tarefa}\n\nAo terminar, relate na nota `{NOTA_RELATORIOS}` como manda o seu papel."
        if esperar_s > 0:
            return self.maestri.pedir(nome, prompt, timeout=esperar_s)
        # sem esperar: dispara e volta; se o agente ainda estiver subindo, o Enter é reenviado
        def _disparar():
            try:
                self.maestri.pedir(nome, prompt, timeout=15)
            except RuntimeError:
                pass
            try:
                time.sleep(2); self.maestri.enter(nome)
            except RuntimeError:
                pass
        import threading
        threading.Thread(target=_disparar, name=f"delegar-{nome}", daemon=True).start()
        return f"Tarefa enviada a {nome}. O relatório chega pela nota {NOTA_RELATORIOS}."

    def checar(self, nome: str) -> str:
        saida = self.maestri.checar(nome)
        linhas = [l for l in saida.splitlines() if l.strip()]
        return "\n".join(linhas[-25:])

    def dispensar(self, nome: str, motivo: str = "") -> str:
        f = self.filhos.get(nome)
        if not f:
            return f"Não conheço {nome}."
        try:
            self.maestri.dispensar(nome)
        except RuntimeError as e:
            if "not" not in str(e).lower():
                raise
        f.estado = "dispensado"; self._salvar()
        self.jaime.vault.diario(f"Filho dispensado: {nome}" + (f" — {motivo}" if motivo else ""), "Decisões")
        return f"{nome} dispensado. A pasta {f.pasta} fica; a branch (se houver) também."

    # ── relatórios ─────────────────────────────────────
    def ler_relatorios(self) -> list[tuple[str, str]]:
        """[(nome, texto)] dos relatórios novos na nota compartilhada."""
        try:
            txt = Maestri.texto_da_nota(self.maestri.nota_ler(NOTA_RELATORIOS))
        except RuntimeError:
            return []
        novos = []
        for bloco in re.split(r"^## ", txt, flags=re.M)[1:]:
            cab, _, corpo = bloco.partition("\n")
            if cab.strip().lower() == "fim" or not corpo.strip():
                continue
            nome = cab.split("·")[0].strip()
            chave = f"{cab.strip()}|{corpo.strip()[:80]}"
            if chave in self._relatorios_vistos:
                continue
            self._relatorios_vistos.add(chave)
            novos.append((nome, corpo.strip()))
            if nome in self.filhos:
                self.filhos[nome].ultimo_relatorio = corpo.strip()[:300]
        if novos:
            self._salvar()
        return novos

    async def vigiar_relatorios(self, intervalo_s: int = 60, falar=None):
        """Task do servidor: lê a nota a cada minuto; relatório novo → diário + HUD (+ voz, se `falar`)."""
        primeira = True
        while True:
            try:
                if self.vivos and self.maestri.disponivel:
                    for nome, texto in await asyncio.to_thread(self.ler_relatorios):
                        if primeira:
                            continue        # o que já estava na nota antes de subir não é novidade
                        self.jaime.vault.diario(f"Relatório de {nome}: {texto[:200]}", "Feito")
                        bus.emitir("equipe", relatorio={"nome": nome, "texto": texto[:400]})
                        if falar and re.search(r"\b(pronto|terminei|concluí|falhou|preciso do jo[aã]o)\b", texto, re.I):
                            await asyncio.to_thread(falar, f"{nome} relatou: {texto[:120]}")
                primeira = False
            except asyncio.CancelledError:
                return
            except Exception as e:
                bus.emitir("equipe", erro=f"{type(e).__name__}: {e}"[:160])
            await asyncio.sleep(intervalo_s)
