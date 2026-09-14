"""Jaime — o orquestrador. Um processo, um cliente persistente, várias entradas, um cérebro.

Fluxo de cada fala: acesso (palavra-passe) → Claude (com maesters e Vigia) → eventos p/ HUD →
registro da conversa no vault → reflexão a cada N turnos → espelho no Notion."""
from __future__ import annotations
import asyncio
from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, UserMessage, ResultMessage,
    TextBlock, ThinkingBlock, ToolUseBlock, ToolResultBlock,
)
from ..config import Settings
from ..brain.vault import Vault
from ..brain.estado import Estado, maquina
from ..brain.tools import build_cerebro_server
from ..brain.notion_sync import NotionSync
from ..vigia.hooks import Vigia, eh_confirmacao
from ..vigia.acesso import Acesso, quer_trancar
from ..hud.events import bus
from .maesters import carregar_maesters
from .prompt import system_prompt, prompt_reflexao, prompt_apresentacao

CEREBRO_TOOLS = ["lembrar", "buscar_memoria", "ler_nota", "registrar_diario", "criar_tarefa", "tarefas_abertas",
                 "ler_estado", "atualizar_estado"]

def _resumo_tool(nome: str, args: dict) -> str:
    for k in ("file_path", "command", "pattern", "path", "url", "query", "description", "prompt", "nota", "descricao", "secao"):
        if k in args:
            return str(args[k])[:140]
    return ", ".join(f"{k}={str(v)[:40]}" for k, v in list(args.items())[:3])

class Jaime:
    def __init__(self, settings: Settings):
        self.s = settings
        self.vault = Vault(settings.vault)
        self.estado = Estado(self.vault)
        self.vigia = Vigia()
        self.acesso = Acesso(settings.passphrase_hash, settings.acesso_timeout_min)
        self.notion = NotionSync(settings, self.vault, self.estado)
        self._client: ClaudeSDKClient | None = None
        self._lock = asyncio.Lock()
        self.canal = "cli"
        self.apresentacao: str = ""

    # ── ciclo de vida ──────────────────────────────────
    def _options(self) -> ClaudeAgentOptions:
        kw = dict(
            model=self.s.model, cwd=str(self.s.root),
            system_prompt={"type": "preset", "preset": "claude_code",
                           "append": system_prompt(self.vault, self.estado, self.canal)},
            setting_sources=["project"],
            agents=carregar_maesters(self.s.root),
            mcp_servers={"cerebro": build_cerebro_server(self.vault, self.estado)},
            hooks=self.vigia.hooks(),
            permission_mode="acceptEdits",
            allowed_tools=["Read", "Write", "Edit", "Grep", "Glob", "Bash", "WebSearch", "WebFetch", "Task"]
                          + [f"mcp__cerebro__{t}" for t in CEREBRO_TOOLS],
        )
        if self.s.thinking_tokens > 0:
            kw["max_thinking_tokens"] = self.s.thinking_tokens   # mostra parte do raciocínio no HUD
        return ClaudeAgentOptions(**kw)

    async def start(self, apresentar: bool = True) -> str:
        nova = self.estado.registrar_maquina()
        self._client = ClaudeSDKClient(options=self._options())
        await self._client.connect()
        self.vault.diario(f"Jaime iniciado em {maquina()['host']}" + (" (máquina nova)" if nova else ""), "Log")
        bus.emitir("estado", fase=self.estado.fase(), situacao=self.estado.secao("Situação agora"),
                   maquina=maquina(), nova_maquina=nova, liberado=self.acesso.liberado)
        if apresentar:
            self.apresentacao = await self._interno(prompt_apresentacao(nova))
            bus.emitir("apresentacao", texto=self.apresentacao)
        asyncio.create_task(self.notion.tudo())
        return self.apresentacao

    async def stop(self):
        if self._client:
            try:
                await self.notion.registrar_sessao(self.canal, self.estado.secao("Última conversa")[:200],
                                                   self.estado.secao("Situação agora")[:300])
            except Exception:
                pass
            await self._client.disconnect(); self._client = None

    # ── conversa ───────────────────────────────────────
    async def _stream(self, texto: str):
        """Envia ao Claude e gera trechos de texto; emite eventos de raciocínio/produção para o HUD."""
        await self._client.query(texto)
        async for msg in self._client.receive_response():
            if isinstance(msg, AssistantMessage):
                for b in msg.content:
                    if isinstance(b, TextBlock) and b.text.strip():
                        bus.emitir("fala", texto=b.text); yield b.text
                    elif isinstance(b, ThinkingBlock):
                        bus.emitir("raciocinio", texto=b.thinking[:600])
                    elif isinstance(b, ToolUseBlock):
                        tipo = "producao" if b.name in ("Write", "Edit", "MultiEdit", "Bash", "Task") or b.name.startswith("mcp__") else "raciocinio"
                        bus.emitir(tipo, ferramenta=b.name, alvo=_resumo_tool(b.name, b.input or {}))
            elif isinstance(msg, UserMessage) and isinstance(msg.content, list):
                for b in msg.content:
                    if isinstance(b, ToolResultBlock):
                        c = b.content if isinstance(b.content, str) else " ".join(x.get("text", "") for x in (b.content or []) if isinstance(x, dict))
                        bus.emitir("resultado", texto=(c or "")[:300], erro=bool(b.is_error))
            elif isinstance(msg, ResultMessage):
                bus.emitir("fala_fim"); return

    async def _interno(self, texto: str) -> str:
        async with self._lock:
            return "".join([t async for t in self._stream(texto)]).strip()

    def _porta(self, texto: str) -> str | None:
        """Palavra-passe e tranca. Devolve uma resposta curta se a fala não deve chegar ao Claude."""
        if quer_trancar(texto):
            self.acesso.trancar(); bus.emitir("acesso", liberado=False)
            return "Cérebro trancado. Diga a palavra-passe quando quiser voltar."
        if not self.acesso.liberado:
            if self.acesso.tentar(texto):
                bus.emitir("acesso", liberado=True)
                return f"Acesso liberado. {self.estado.resumo_curto()} O que fazemos, João?"
            bus.emitir("acesso", liberado=False)
            return "Palavra-passe, por favor."
        self.acesso.tocar(); return None

    async def ask_stream(self, texto: str, canal: str = "cli"):
        assert self._client, "Chame start() antes."
        bus.emitir("conversa", canal=canal, texto=texto if self.acesso.liberado else "•••")
        curta = self._porta(texto)
        if curta is not None:
            bus.emitir("fala", texto=curta); bus.emitir("fala_fim"); yield curta; return
        async with self._lock:
            self.canal = canal
            if eh_confirmacao(texto):
                self.vigia.armar(); texto = "confirmo — pode executar a ação que o Vigia bloqueou."
            partes = []
            async for t in self._stream(f"[canal={canal}] {texto}"):
                partes.append(t); yield t
        await self._pos_turno(canal, texto, "".join(partes))

    async def ask(self, texto: str, canal: str = "cli") -> str:
        return "".join([t async for t in self.ask_stream(texto, canal)]).strip() or "(sem resposta)"

    async def _pos_turno(self, canal: str, pergunta: str, resposta: str):
        self.estado.registrar_turno(canal, pergunta, resposta)
        if self.estado.precisa_refletir():
            bus.emitir("raciocinio", ferramenta="reflexão", alvo="atualizando meu Estado")
            await self._interno(prompt_reflexao())
        bus.emitir("estado", fase=self.estado.fase(), situacao=self.estado.secao("Situação agora"),
                   maquina=maquina(), liberado=self.acesso.liberado)
        asyncio.create_task(self.notion.tudo())
