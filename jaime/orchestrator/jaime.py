"""Jaime — o orquestrador. Um processo, um cliente persistente, várias entradas."""
from __future__ import annotations
import asyncio
from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock, ResultMessage,
)
from ..config import Settings
from ..brain.vault import Vault
from ..brain.tools import build_cerebro_server
from ..vigia.hooks import Vigia, eh_confirmacao
from .maesters import carregar_maesters
from .prompt import system_prompt

class Jaime:
    def __init__(self, settings: Settings):
        self.s = settings
        self.vault = Vault(settings.vault)
        self.vigia = Vigia()
        self._client: ClaudeSDKClient | None = None
        self._lock = asyncio.Lock()
        self.canal = "cli"

    def _options(self) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            model=self.s.model,
            cwd=str(self.s.root),
            # preset "claude_code" mantém o conhecimento nativo das ferramentas; append injeta o cérebro
            system_prompt={"type": "preset", "preset": "claude_code", "append": system_prompt(self.vault, self.canal)},
            setting_sources=["project"],            # carrega CLAUDE.md, .claude/settings.json, .mcp.json, skills
            agents=carregar_maesters(self.s.root),   # maesters
            mcp_servers={"cerebro": build_cerebro_server(self.vault)},
            hooks=self.vigia.hooks(),
            permission_mode="acceptEdits",
            allowed_tools=["Read", "Write", "Edit", "Grep", "Glob", "Bash", "WebSearch", "WebFetch", "Task",
                           "mcp__cerebro__lembrar", "mcp__cerebro__buscar_memoria", "mcp__cerebro__ler_nota",
                           "mcp__cerebro__registrar_diario", "mcp__cerebro__criar_tarefa", "mcp__cerebro__tarefas_abertas"],
        )

    async def start(self):
        self._client = ClaudeSDKClient(options=self._options())
        await self._client.connect()
        self.vault.diario("Jaime iniciado", "Log")

    async def stop(self):
        if self._client:
            await self._client.disconnect()
            self._client = None

    async def ask(self, texto: str, canal: str = "cli") -> str:
        """Envia uma fala/texto ao Jaime e devolve a resposta em texto."""
        assert self._client, "Chame start() antes."
        async with self._lock:
            self.canal = canal
            if eh_confirmacao(texto):
                self.vigia.armar()
                texto = "confirmo — pode executar a ação que o Vigia bloqueou."
            prefixo = f"[canal={canal}] "
            await self._client.query(prefixo + texto)
            partes: list[str] = []
            async for msg in self._client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for b in msg.content:
                        if isinstance(b, TextBlock):
                            partes.append(b.text)
                elif isinstance(msg, ResultMessage):
                    break
            return "\n".join(partes).strip() or "(sem resposta)"

    async def ask_stream(self, texto: str, canal: str = "voice"):
        """Igual a ask(), mas gera os trechos de texto conforme chegam (para TTS em streaming)."""
        assert self._client
        async with self._lock:
            self.canal = canal
            if eh_confirmacao(texto):
                self.vigia.armar()
            await self._client.query(f"[canal={canal}] {texto}")
            async for msg in self._client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for b in msg.content:
                        if isinstance(b, TextBlock) and b.text.strip():
                            yield b.text
                elif isinstance(msg, ResultMessage):
                    return
