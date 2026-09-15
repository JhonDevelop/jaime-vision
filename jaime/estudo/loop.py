"""Loop de estudo — o ciclo da Mente contínua que fecha problemas em aberto.

Um problema por ciclo, no máximo 15 minutos, dentro de `/tmp/jaime-lab` (sandbox). A pesquisa/experimento é
um turno avulso do Agent SDK (WebSearch, WebFetch, Read, Write, Bash) com um hook que nega qualquer escrita ou
comando fora do sandbox — nunca toca em `~/projetos`, no repositório nem no vault. Só o resultado volta:
  resolvido  → `50-Conhecimento/<slug>.md` (como reproduzir · o que resolveu · onde se aplica), INDEX, aprendizado
               no Estado, placar; skill em `.claude/skills/<slug>/SKILL.md` quando o estudo achar que vale.
  não        → tentativa registrada em Problemas.md com o que falta.

`pesquisador` é injetável: os testes passam uma função que "resolve" offline."""
from __future__ import annotations
import asyncio, json, re, time
from pathlib import Path
from ..hud.events import bus
from ..identidade import slug as fazer_slug
from .problemas import Problemas, Problema

SANDBOX = Path("/tmp/jaime-lab")
LIMITE_S = 15 * 60
MAX_TURNOS = 30
INTERVALO_S = 30 * 60

PROMPT = """Você está no seu laboratório ({sandbox}). Estude e tente resolver este problema em aberto:

ID: {id}
Título: {titulo}
Origem: {origem}
Contexto: {contexto}
Tentativas anteriores:
{tentativas}

Regras: trabalhe SÓ dentro de {sandbox} (crie arquivos, rode comandos, instale o que precisar ali). Pesquise na web
e em docs se ajudar. Não toque em nada fora do laboratório. Tempo máximo: 15 minutos — se não fechar, pare e
diga o que falta. Termine SEMPRE com um JSON (e nada depois dele):
{{"resolvido": true|false, "titulo": "...", "como_reproduzir": "...", "o_que_resolveu": "...", "onde_se_aplica": "...",
  "tentativa": "o que você tentou, em 1-3 frases", "falta": "o que ainda falta (se não resolvido)",
  "skill": "" ou texto de uma skill reutilizável (passo a passo) se isso vai se repetir}}"""

def _fora_do_sandbox(caminho: str) -> bool:
    if not caminho:
        return False
    p = Path(caminho).expanduser()
    return not (p.is_absolute() and (SANDBOX == p or SANDBOX in p.parents))

PERIGO_RX = re.compile(r"(~/projetos|/Users/[^/\s]+/Documents|jaime-vision|\bgit\s+push|\brm\s+-rf\s+/|\bsudo\b|>\s*/Users/)", re.I)

async def _hook_sandbox(input_data: dict, tool_use_id, context) -> dict:
    nome = input_data.get("tool_name", ""); args = input_data.get("tool_input", {}) or {}
    motivo = ""
    if nome in ("Write", "Edit", "MultiEdit", "NotebookEdit") and _fora_do_sandbox(args.get("file_path", "")):
        motivo = f"escrita fora do laboratório: {args.get('file_path')}"
    elif nome == "Bash" and PERIGO_RX.search(args.get("command", "")):
        motivo = f"comando fora do laboratório: {args.get('command', '')[:60]}"
    if motivo:
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": f"LABORATÓRIO: {motivo}. Só /tmp/jaime-lab."}}
    return {}

async def pesquisar_com_sdk(problema: Problema, modelo: str) -> dict:
    """Turno avulso do Agent SDK no sandbox. Devolve o JSON final (ou {'resolvido': False, 'falta': erro})."""
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock, HookMatcher
    SANDBOX.mkdir(parents=True, exist_ok=True)
    opts = ClaudeAgentOptions(
        model=modelo, cwd=str(SANDBOX), max_turns=MAX_TURNOS, permission_mode="bypassPermissions",
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebSearch", "WebFetch"],
        hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[_hook_sandbox])]},
        system_prompt="Você é o cérebro de estudo do Jaime: metódico, curto, honesto sobre o que não fechou.")
    prompt = PROMPT.format(sandbox=SANDBOX, id=problema.id, titulo=problema.titulo, origem=problema.origem,
                           contexto=problema.contexto or "(sem contexto)",
                           tentativas="\n".join(problema.tentativas) or "(nenhuma)")
    partes = []
    try:
        async def rodar():
            async for msg in query(prompt=prompt, options=opts):
                if isinstance(msg, AssistantMessage):
                    partes.extend(b.text for b in msg.content if isinstance(b, TextBlock))
        await asyncio.wait_for(rodar(), timeout=LIMITE_S)
    except asyncio.TimeoutError:
        return {"resolvido": False, "tentativa": "estourou os 15 minutos", "falta": "continuar de onde parou; ver /tmp/jaime-lab"}
    except Exception as e:
        return {"resolvido": False, "tentativa": f"falhou: {type(e).__name__}", "falta": str(e)[:160]}
    texto = "".join(partes)
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        return {"resolvido": False, "tentativa": texto[-300:], "falta": "não devolveu o JSON final"}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"resolvido": False, "tentativa": texto[-300:], "falta": "JSON final inválido"}

class Estudo:
    def __init__(self, vault, estado=None, placar=None, repo_root: Path | None = None, modelo: str = "claude-sonnet-5", pesquisador=None):
        self.vault, self.estado, self.placar, self.repo_root, self.modelo = vault, estado, placar, repo_root, modelo
        self.problemas = Problemas(vault)
        self.pesquisador = pesquisador or (lambda p: pesquisar_com_sdk(p, self.modelo))
        self.ocupado = False
        self.ultimo_ciclo = 0.0

    def emitir(self, msg: str = "") -> None:
        bus.emitir("estudo", abertos=len(self.problemas.abertos()), msg=msg)

    # ── gatilhos ──────────────────────────────────────
    def abrir(self, titulo: str, contexto: str = "", origem: str = "manual") -> Problema:
        p = self.problemas.abrir(titulo, contexto, origem)
        self.vault.diario(f"Problema aberto {p.id}: {p.titulo} ({origem})", "Pendente")
        self.emitir(f"aberto {p.id}: {p.titulo[:60]}")
        return p

    # ── ciclo ─────────────────────────────────────────
    async def ciclo(self) -> dict | None:
        """Estuda UM problema. Devolve o resultado, ou None se não havia o que estudar."""
        p = self.problemas.proximo()
        if not p or self.ocupado:
            return None
        self.ocupado = True; self.ultimo_ciclo = time.time()
        self.emitir(f"estudando {p.id}: {p.titulo[:60]}")
        try:
            r = await self.pesquisador(p)
        finally:
            self.ocupado = False
        r = r or {}
        if r.get("resolvido"):
            rel = self._escrever_conhecimento(p, r)
            self.problemas.resolver(p.id, rel)
            self.vault.diario(f"Problema {p.id} resolvido → {rel}", "Feito")
            if self.estado:
                atual = self.estado.secao("Aprendizados recentes")
                linha = f"- {r.get('titulo') or p.titulo}: {str(r.get('o_que_resolveu', ''))[:160]}"
                self.estado.atualizar_secao("Aprendizados recentes", (atual + "\n" + linha).strip() if atual and "nenhum" not in atual.lower() else linha)
            if self.placar:
                self.placar.registrar("estudo", "pesquisa", "acerto", 0, 0, p.titulo[:80])
            if r.get("skill") and self.repo_root:
                self._escrever_skill(p, r)
            try:
                from ..brain.saude import gerar_indices
                gerar_indices(self.vault.root)
            except Exception:
                pass
            self.emitir(f"resolvido {p.id} → {rel}")
        else:
            self.problemas.registrar_tentativa(p.id, str(r.get("tentativa", "sem detalhes"))[:300], str(r.get("falta", ""))[:200])
            if self.placar:
                self.placar.registrar("estudo", "pesquisa", "erro", 0, 0, p.titulo[:80])
            self.emitir(f"{p.id} sem solução ainda: falta {str(r.get('falta', ''))[:60]}")
        return r

    async def rodar_em_ciclos(self, pode_rodar=lambda: True, intervalo: int = INTERVALO_S):
        """Mente contínua (mínima): a cada `intervalo`, se estiver ocioso e houver problema, estuda um."""
        while True:
            await asyncio.sleep(intervalo)
            try:
                if pode_rodar() and self.problemas.abertos():
                    await self.ciclo()
            except Exception as e:
                bus.emitir("estudo", abertos=len(self.problemas.abertos()), msg=f"ciclo falhou: {type(e).__name__}: {e}"[:160])

    # ── saídas ────────────────────────────────────────
    def _escrever_conhecimento(self, p: Problema, r: dict) -> str:
        s = fazer_slug(r.get("titulo") or p.titulo)
        rel = f"50-Conhecimento/{s}.md"
        corpo = (f"# {r.get('titulo') or p.titulo}\n\n> Resolvido pelo cérebro de estudo em {time.strftime('%d/%m/%Y')} (problema {p.id}, origem {p.origem}).\n\n"
                 f"## Como reproduzir\n{r.get('como_reproduzir', '—')}\n\n## O que resolveu\n{r.get('o_que_resolveu', '—')}\n\n"
                 f"## Onde se aplica\n{r.get('onde_se_aplica', '—')}\n")
        self.vault.write(rel, corpo)
        return rel

    def _escrever_skill(self, p: Problema, r: dict) -> None:
        s = fazer_slug(r.get("titulo") or p.titulo)
        d = Path(self.repo_root) / ".claude" / "skills" / s
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(f"---\nname: {s}\ndescription: {str(r.get('onde_se_aplica', p.titulo))[:150]}\n---\n\n{r['skill']}\n", encoding="utf-8")
