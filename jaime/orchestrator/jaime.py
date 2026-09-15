"""Jaime — o orquestrador. Um processo, um cliente persistente, várias entradas, um cérebro.

Fluxo de cada fala: acesso (palavra-passe) → Claude (com maesters e Vigia) → eventos p/ HUD →
registro da conversa no vault → reflexão a cada N turnos → espelho no Notion."""
from __future__ import annotations
import asyncio
from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, UserMessage, ResultMessage, StreamEvent,
    TextBlock, ThinkingBlock, ToolUseBlock, ToolResultBlock,
)
from ..config import Settings
from ..brain.vault import Vault
from ..brain.estado import Estado, maquina
from ..brain.tools import build_cerebro_server
from ..brain.notion_sync import NotionSync
from ..vigia.hooks import Vigia, eh_confirmacao
from ..vigia.acesso import Acesso, quer_trancar
from ..voice.escuta import quer_teclado, usar_nome
from ..identidade import Identidade, quer_renomear, eh_sim
from ..brain.saude import verificar, gerar_indices, relatorio, resumo_falado
from ..hud.events import bus
from .maesters import carregar_maesters
from .prompt import system_prompt, prompt_reflexao, prompt_apresentacao

CEREBRO_TOOLS = ["lembrar", "buscar_memoria", "ler_nota", "registrar_diario", "criar_tarefa", "tarefas_abertas",
                 "ler_estado", "atualizar_estado", "pedir_teclado"]

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
        self.identidade = Identidade(settings.vault, settings.root)
        self._client: ClaudeSDKClient | None = None
        self._lock = asyncio.Lock()
        self.canal = "cli"
        self.apresentacao: str = ""
        self.proposta_renomear: str = ""      # nome proposto, à espera do "confirmo"
        self.aguardando_nome: bool = False    # boot: "Meu nome é X — confirma?"
        self.saude: list = []
        usar_nome(self.identidade.variantes())

    # ── ciclo de vida ──────────────────────────────────
    def _options(self) -> ClaudeAgentOptions:
        kw = dict(
            model=self.s.model, cwd=str(self.s.root),
            system_prompt={"type": "preset", "preset": "claude_code",
                           "append": system_prompt(self.vault, self.estado, self.canal)},
            setting_sources=["project"],
            agents=carregar_maesters(self.s.root),
            mcp_servers={"cerebro": build_cerebro_server(self.vault, self.estado, self)},
            hooks=self.vigia.hooks(),
            # Acesso total à máquina: nenhuma ferramenta pede permissão. O irreversível continua
            # passando pelo Vigia (hook PreToolUse), que exige o "confirmo" do João.
            permission_mode="bypassPermissions",
            include_partial_messages=True,   # texto chega token a token: a voz começa na primeira frase
        )
        if self.s.thinking_tokens > 0:
            kw["max_thinking_tokens"] = self.s.thinking_tokens   # mostra parte do raciocínio no HUD
        return ClaudeAgentOptions(**kw)

    async def start(self, apresentar: bool = True) -> str:
        nova = self.estado.registrar_maquina()
        # saúde do cérebro antes de confiar nele; índices entram no contexto inicial
        self.saude = verificar(self.s.vault, self.s.root)
        gerar_indices(self.s.vault)
        if self.saude:
            self.vault.diario("Saúde do cérebro: " + relatorio(self.saude).replace("\n", " · ")[:400], "Log")
        bus.emitir("saude", problemas=[str(p) for p in self.saude], erros=sum(p.nivel == "erro" for p in self.saude))
        self._client = ClaudeSDKClient(options=self._options())
        await self._client.connect()
        self.vault.diario(f"{self.identidade.nome} iniciado em {maquina()['host']}" + (" (máquina nova)" if nova else ""), "Log")
        bus.emitir("estado", fase=self.estado.fase(), situacao=self.estado.secao("Situação agora"),
                   maquina=maquina(), nova_maquina=nova, liberado=self.acesso.liberado)
        if apresentar:
            self.apresentacao = await self._interno(prompt_apresentacao(nova, self.identidade.nome, resumo_falado(self.saude)))
            if not self.identidade.confirmado:
                # primeiro boot (ou depois de renomear): ele confere o próprio nome
                self.aguardando_nome = True
                if "confirma" not in self.apresentacao.lower():
                    self.apresentacao = f"{self.apresentacao} Meu nome é {self.identidade.nome} — confirma?"
            bus.emitir("apresentacao", texto=self.apresentacao)
        asyncio.create_task(self.notion.tudo())
        return self.apresentacao

    # ── identidade ─────────────────────────────────────
    def propor_renomear(self, novo: str) -> str:
        novo = novo.strip().capitalize()
        if novo.lower() == self.identidade.nome.lower():
            return f"Já me chamo {novo}."
        self.proposta_renomear = novo
        bus.emitir("identidade", nome=self.identidade.nome, msg=f"proposta: renomear para {novo} — diga 'confirmo'")
        return f"Proposta: passar a me chamar {novo}. Diga 'confirmo' e eu troco em tudo que o mundo vê."

    def _executar_renomear(self) -> str:
        novo, self.proposta_renomear = self.proposta_renomear, ""
        antigo = self.identidade.nome
        alterados = self.identidade.renomear(novo, git=True)
        usar_nome(self.identidade.variantes())
        self.aguardando_nome = True
        self.vault.diario(f"Renomeado: {antigo} → {novo} ({len(alterados)} arquivos; branch chore/renomear-{novo.lower()})", "Decisões")
        bus.emitir("identidade", nome=novo, msg=f"agora me chamo {novo}")
        return (f"Pronto: agora me chamo {novo}. Atualizei a identidade, o CLAUDE.md e o .env, em uma branch própria. "
                f"Para me chamar por voz, diga '{novo}'; se um dia houver wake word treinada, ela precisa ser treinada de novo. "
                f"Meu nome é {novo} — confirma?")

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
        por_delta = False          # texto já foi entregue token a token? então o bloco inteiro não repete
        pensando = ""
        async for msg in self._client.receive_response():
            if isinstance(msg, StreamEvent):
                if msg.parent_tool_use_id:      # fala de subagente (maester) não é fala do Jaime
                    continue
                ev = msg.event or {}
                if ev.get("type") == "content_block_delta":
                    d = ev.get("delta") or {}
                    if d.get("type") == "text_delta" and d.get("text"):
                        por_delta = True
                        bus.emitir("fala", texto=d["text"]); yield d["text"]
                    elif d.get("type") == "thinking_delta" and d.get("thinking"):
                        pensando += d["thinking"]
                        if len(pensando) > 240:
                            bus.emitir("raciocinio", texto=pensando[:600]); pensando = ""
                continue
            if isinstance(msg, AssistantMessage):
                for b in msg.content:
                    if isinstance(b, TextBlock) and b.text.strip():
                        if not por_delta:
                            bus.emitir("fala", texto=b.text); yield b.text
                    elif isinstance(b, ThinkingBlock):
                        if pensando:
                            bus.emitir("raciocinio", texto=pensando[:600]); pensando = ""
                        elif not por_delta:
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
        if quer_teclado(texto):
            bus.emitir("teclado", aberto=True, motivo="você pediu")
            return "Pode escrever."
        # identidade: "me chama de X" propõe; "confirmo" com proposta pendente executa; "sim" no boot confirma o nome
        if (novo := quer_renomear(texto)):
            return self.propor_renomear(novo)
        if self.proposta_renomear and eh_confirmacao(texto):
            return self._executar_renomear()
        if self.aguardando_nome and eh_sim(texto):
            self.aguardando_nome = False; self.identidade.confirmar()
            bus.emitir("identidade", nome=self.identidade.nome, msg="nome confirmado")
            return f"{self.identidade.nome} confirmado. O que fazemos, João?"
        if not self.acesso.liberado:
            if self.acesso.tentar(texto):
                bus.emitir("acesso", liberado=True)
                return f"Acesso liberado. {self.estado.resumo_curto()} O que fazemos, João?"
            bus.emitir("acesso", liberado=False)
            return "Palavra-passe, por favor."
        self.acesso.tocar(); return None

    async def ask_stream(self, texto: str, canal: str = "cli", contexto: str = ""):
        """contexto: o que o João está vendo na tela agora (app/janela) — vai só ao modelo, não ao diário."""
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
            prefixo = f"[canal={canal}]" + (f" [contexto: {contexto}]" if contexto else "")
            async for t in self._stream(f"{prefixo} {texto}"):
                partes.append(t); yield t
        await self._pos_turno(canal, texto, "".join(partes))

    async def ask(self, texto: str, canal: str = "cli", contexto: str = "") -> str:
        return "".join([t async for t in self.ask_stream(texto, canal, contexto)]).strip() or "(sem resposta)"

    async def _pos_turno(self, canal: str, pergunta: str, resposta: str):
        self.estado.registrar_turno(canal, pergunta, resposta)
        if self.estado.precisa_refletir():
            bus.emitir("raciocinio", ferramenta="reflexão", alvo="atualizando meu Estado")
            asyncio.create_task(self._interno(prompt_reflexao()))   # em segundo plano: não segura a resposta
        bus.emitir("estado", fase=self.estado.fase(), situacao=self.estado.secao("Situação agora"),
                   maquina=maquina(), liberado=self.acesso.liberado)
        asyncio.create_task(self.notion.tudo())
