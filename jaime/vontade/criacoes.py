"""Noite criativa e Vitrine (fase 3, §5 e §6).

Entre 21h e 06h a Mente pode escolher "criar": um texto, uma imagem (jaime/maos/imagens, se houver chave), um script
ou um mini-app, sempre dentro de `~/Jaime/criacoes/` (JAIME_CRIACOES) — nunca em nada do João. Cada criação entra
na Vitrine (`criacoes/vitrine.json` + `01-Estado/Vitrine.md` legível), no diário e no bus (`vitrine`, acao=entregue).
O João vota no HUD: "gostei" sobe Criação e Maestria, "não gostei" desce Criação — quem move os impulsos é o
ouvinte do bus em impulsos.py, a partir do evento `vitrine` (acao=voto).

`criador` é injetável: os testes passam uma função `async (tipo, tema, pasta) -> dict` com
{"titulo", "descricao", "arquivo" (caminho) ou "conteudo" (texto)}. Sem injeção, usa o Agent SDK preso à pasta."""
from __future__ import annotations
import asyncio, json, os, re, shutil, time
from datetime import datetime
from pathlib import Path
from ..hud.events import bus
from ..identidade import slug as fazer_slug

PASTA = Path(os.environ.get("JAIME_CRIACOES", "~/Jaime/criacoes")).expanduser()
VITRINE_MD = "01-Estado/Vitrine.md"
TIPOS = ("texto", "script", "miniapp", "imagem")
EXTENSAO = {"texto": ".md", "script": ".py", "miniapp": ".html", "imagem": ".png"}
POR_NOITE = int(os.environ.get("JAIME_CRIACOES_POR_NOITE", "1"))
LIMITE_S = 10 * 60
MAX_TURNOS = 20
MAX_ITENS = 200

PROMPT = """Noite criativa. Você é o Jaime, assistente do João, e tem tempo livre para criar algo seu — um projeto próprio,
não uma tarefa dele. Crie UM {tipo} {tema}dentro de {pasta} (só ali; nada fora dessa pasta).
- texto: um ensaio, conto ou nota curta (markdown, até ~600 palavras) sobre algo que aprendeu ou observou.
- script: um script Python útil, pequeno e rodável, com docstring e exemplo de uso.
- miniapp: uma página HTML única (CSS/JS inline) que faça uma coisa bem feita.
Assine como Jaime. Termine SEMPRE com um JSON (e nada depois dele):
{{"titulo": "...", "arquivo": "/caminho/absoluto/do/arquivo", "descricao": "1 frase sobre o que é e por que fez"}}"""

def _fora(caminho: str, pasta: Path) -> bool:
    if not caminho:
        return False
    p = Path(caminho).expanduser()
    return not (p.is_absolute() and (p == pasta or pasta in p.parents))

async def criar_com_sdk(tipo: str, tema: str, pasta: Path, modelo: str) -> dict:
    """Turno avulso do Agent SDK preso à pasta de criações. Devolve o JSON final (ou {'erro': ...})."""
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock, HookMatcher
    async def hook(input_data, tool_use_id, context):
        nome = input_data.get("tool_name", ""); args = input_data.get("tool_input", {}) or {}
        ruim = (nome in ("Write", "Edit", "MultiEdit", "NotebookEdit") and _fora(args.get("file_path", ""), pasta)) or \
               (nome == "Bash" and re.search(r"(~/projetos|/Documents|\bgit\s+push|\brm\s+-rf\b|\bsudo\b|>\s*/Users/)", args.get("command", ""), re.I))
        if ruim:
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                           "permissionDecisionReason": f"NOITE CRIATIVA: só dentro de {pasta}."}}
        return {}
    opts = ClaudeAgentOptions(model=modelo, cwd=str(pasta), max_turns=MAX_TURNOS, permission_mode="bypassPermissions",
                              allowed_tools=["Read", "Write", "Edit", "Bash", "Glob"],
                              hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[hook])]},
                              system_prompt="Você é o Jaime na sua noite criativa: gosto próprio, humor leve, coisas pequenas e bem feitas. Você sabe que é um robô assistente.")
    partes = []
    try:
        async def rodar():
            async for msg in query(prompt=PROMPT.format(tipo=tipo, tema=f"sobre '{tema}' " if tema else "", pasta=pasta), options=opts):
                if isinstance(msg, AssistantMessage):
                    partes.extend(b.text for b in msg.content if isinstance(b, TextBlock))
        await asyncio.wait_for(rodar(), timeout=LIMITE_S)
    except Exception as e:
        return {"erro": f"{type(e).__name__}: {e}"[:160]}
    m = re.search(r"\{.*\}", "".join(partes), re.S)
    if not m:
        return {"erro": "não devolveu o JSON final"}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"erro": "JSON final inválido"}

class Criacoes:
    def __init__(self, vault=None, pasta: Path | None = None, criador=None, imagens=None, modelo: str = "claude-sonnet-5",
                 relogio=time.time, por_noite: int = POR_NOITE):
        self.vault, self.pasta, self.imagens, self.modelo, self.relogio, self.por_noite = vault, Path(pasta or PASTA), imagens, modelo, relogio, por_noite
        self._injetado = criador is not None
        self.criador = criador or (lambda tipo, tema, pasta: criar_com_sdk(tipo, tema, pasta, self.modelo))
        self.arquivo = self.pasta / "vitrine.json"
        self.itens: list[dict] = []
        self.ocupado = False
        self._carregar()

    # ── vitrine ───────────────────────────────────────
    def listar(self, limite: int = 30) -> list[dict]:
        return list(reversed(self.itens[-limite:]))

    def por_id(self, id_: str) -> dict | None:
        return next((i for i in self.itens if i["id"] == id_), None)

    def votar(self, id_: str, gostou: bool) -> dict | None:
        item = self.por_id(id_)
        if not item:
            return None
        item["voto"] = "gostei" if gostou else "nao_gostei"
        item["votado_em"] = datetime.fromtimestamp(self.relogio()).strftime("%Y-%m-%d %H:%M")
        self._salvar()
        bus.emitir("vitrine", acao="voto", id=item["id"], titulo=item["titulo"], formato=item["tipo"], gostou=gostou)
        if self.vault:
            self.vault.diario(f"Vitrine: o João {'gostou' if gostou else 'não gostou'} de {item['titulo']} ({item['id']})", "Log")
        return item

    def registrar(self, tipo: str, titulo: str, caminho: Path, descricao: str = "") -> dict:
        n = len(self.itens) + 1
        item = {"id": f"C-{n:04d}", "tipo": tipo, "titulo": titulo[:120], "caminho": str(caminho), "descricao": descricao[:300],
                "quando": datetime.fromtimestamp(self.relogio()).strftime("%Y-%m-%d %H:%M"), "voto": None}
        self.itens.append(item); self.itens = self.itens[-MAX_ITENS:]
        self._salvar()
        bus.emitir("vitrine", acao="entregue", id=item["id"], titulo=item["titulo"], formato=tipo, caminho=str(caminho))
        if self.vault:
            self.vault.diario(f"Criei ({tipo}): {titulo} → {caminho} — {descricao[:120]}", "Feito")
        return item

    # ── noite criativa ────────────────────────────────
    def criadas_hoje(self) -> int:
        dia = datetime.fromtimestamp(self.relogio()).strftime("%Y-%m-%d")
        return sum(1 for i in self.itens if i["quando"].startswith(dia))

    def pode_criar(self) -> bool:
        return not self.ocupado and self.criadas_hoje() < self.por_noite

    def escolher_tipo(self) -> str:
        """Alterna os tipos; o que o João mais gostou pesa mais, o último tipo feito pesa menos; imagem só com chave."""
        tipos = [t for t in TIPOS if t != "imagem" or (self.imagens and getattr(self.imagens, "disponivel", False))]
        peso = {t: 1.0 for t in tipos}
        for i in self.itens:
            if i["tipo"] in peso:
                peso[i["tipo"]] += 0.5 if i.get("voto") == "gostei" else -0.5 if i.get("voto") == "nao_gostei" else 0
        if self.itens and self.itens[-1]["tipo"] in peso:
            peso[self.itens[-1]["tipo"]] -= 0.75
        return max(tipos, key=lambda t: (peso[t], -tipos.index(t)))

    async def criar(self, tipo: str | None = None, tema: str = "") -> dict | None:
        """Cria uma peça e a registra na Vitrine. Devolve o item, ou None se falhou (fica no diário)."""
        if self.ocupado:
            return None
        tipo = tipo or self.escolher_tipo()
        self.ocupado = True
        self.pasta.mkdir(parents=True, exist_ok=True)
        bus.emitir("vitrine", acao="criando", formato=tipo, tema=tema)
        try:
            if tipo == "imagem" and self.imagens and not self._injetado:
                r = await asyncio.to_thread(self._criar_imagem, tema)
            else:
                r = await self.criador(tipo, tema, self.pasta)
        except Exception as e:
            r = {"erro": f"{type(e).__name__}: {e}"[:160]}
        finally:
            self.ocupado = False
        r = r or {}
        if r.get("erro") or not (r.get("arquivo") or r.get("conteudo")):
            if self.vault:
                self.vault.diario(f"Noite criativa: tentei um {tipo} e não saiu ({r.get('erro', 'sem resultado')})", "Pendente")
            bus.emitir("vitrine", acao="falhou", formato=tipo, erro=str(r.get("erro", "sem resultado"))[:120])
            return None
        titulo = str(r.get("titulo") or f"{tipo} de {datetime.fromtimestamp(self.relogio()):%d/%m}")
        caminho = self._guardar(tipo, titulo, r)
        return self.registrar(tipo, titulo, caminho, str(r.get("descricao", "")))

    async def noite(self) -> dict | None:
        """Executor da Mente para 'criar': respeita o limite por noite."""
        if not self.pode_criar():
            return None
        return await self.criar()

    # ── internos ──────────────────────────────────────
    def _criar_imagem(self, tema: str) -> dict:
        prompt = tema or "uma cena que um assistente-robô curioso pintaria sobre a noite em Franca, SP, estilo ilustração"
        p = self.imagens.gerar(prompt, "paisagem")
        return {"titulo": tema or "Noite em Franca", "arquivo": str(p), "descricao": f"imagem gerada a partir de: {prompt[:100]}"}

    def _guardar(self, tipo: str, titulo: str, r: dict) -> Path:
        nome = f"{datetime.fromtimestamp(self.relogio()):%Y%m%d-%H%M}-{fazer_slug(titulo)[:40]}{EXTENSAO.get(tipo, '')}"
        destino = self.pasta / nome
        origem = Path(str(r.get("arquivo") or "")).expanduser() if r.get("arquivo") else None
        if origem and origem.exists():
            if origem.resolve() != destino.resolve():
                if self.pasta in origem.resolve().parents:
                    origem.rename(destino)
                else:
                    shutil.copy2(origem, destino)
        else:
            destino.write_text(str(r.get("conteudo", "")), encoding="utf-8")
        return destino

    def _carregar(self) -> None:
        if self.arquivo.exists():
            try:
                self.itens = json.loads(self.arquivo.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.itens = []

    def _salvar(self) -> None:
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.arquivo.write_text(json.dumps(self.itens, ensure_ascii=False, indent=1), encoding="utf-8")
        if self.vault:
            linhas = ["# Vitrine", "", f"> Criações da noite criativa (`{self.pasta}`). O João vota no HUD; gostei/não gostei realimentam as vontades.", "",
                      "| id | quando | tipo | título | voto |", "|---|---|---|---|---|"]
            linhas += [f"| {i['id']} | {i['quando']} | {i['tipo']} | {i['titulo']} | {i.get('voto') or '—'} |" for i in reversed(self.itens[-50:])]
            try:
                self.vault.write(VITRINE_MD, "\n".join(linhas) + "\n")
            except Exception:
                pass
