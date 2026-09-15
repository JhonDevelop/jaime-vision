"""Jaime — o orquestrador. Um processo, um cliente persistente, várias entradas, um cérebro.

Fluxo de cada fala: acesso (palavra-passe) → Claude (com maesters e Vigia) → eventos p/ HUD →
registro da conversa no vault → reflexão a cada N turnos → espelho no Notion."""
from __future__ import annotations
import asyncio, re
from datetime import datetime
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
from ..cortex.placar import Placar
from ..cortex.roteador import Roteador, eh_correcao
from ..cortex.juiz import Juiz, pede_juiz
from ..cortex.provedores.openai import ProvedorOpenAI
from ..cortex.provedores.anthropic import ProvedorAnthropic
from ..emocao.perfil import Perfil
from ..emocao.perguntas import Perguntas
from ..emocao.humor import Humor, detectar_tom
from ..emocao.momento import momento as calcular_momento
from ..emocao.prosodia import prosodia
from ..emocao.tools import build_emocao_server
from ..agenda.scheduler import Agenda
from ..agenda.tools import build_mundo_server
from ..agenda import relogio, clima, lembretes as lem
from ..estudo.loop import Estudo
from ..estudo.tools import build_estudo_server
from ..maos.tools import build_maos_server
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
        # Córtex: o modelo é escolhido por tarefa; o placar aprende com acertos e correções
        self.placar = Placar(settings.vault)
        # OpenAI: texto, pesquisa e decisões; nunca as mãos. Sem chave → o roteador nem a lista.
        self.openai = ProvedorOpenAI(settings.openai_key, settings.openai_model)
        self.roteador = Roteador({"decisao": settings.model_decisao, "codigo": settings.model_codigo,
                                  "padrao": settings.model_padrao, "rotina": settings.model_rotina},
                                 self.placar, settings.cortex_exploracao,
                                 openai=settings.openai_model if self.openai.disponivel else "")
        self.juiz = Juiz(ProvedorAnthropic(settings.model_padrao, str(settings.root)), self.openai,
                         ProvedorAnthropic(settings.model_decisao, str(settings.root)))
        self.modelo_atual = settings.model
        self._custo_turno = 0.0
        self._custo_sessao = 0.0
        self._erros_turno = 0
        # cérebro emocional: quem é o João, o que já perguntei, que dia é hoje, como estou
        self.perfil = Perfil(self.vault)
        self.perguntas = Perguntas(self.vault)
        self.humor = Humor()
        self.momento = calcular_momento(self.perfil)
        # agenda própria (rotinas, lembretes) — o servidor liga o scheduler depois do boot
        self.agenda = Agenda(self)
        # cérebro de estudo: problemas em aberto → ciclos em /tmp/jaime-lab
        self.estudo = Estudo(self.vault, self.estado, self.placar, settings.root, settings.model_padrao)
        self._erros_vistos: dict[str, int] = {}
        usar_nome(self.identidade.variantes())

    # ── ciclo de vida ──────────────────────────────────
    def _options(self) -> ClaudeAgentOptions:
        kw = dict(
            model=self.s.model, cwd=str(self.s.root),
            system_prompt={"type": "preset", "preset": "claude_code",
                           "append": system_prompt(self.vault, self.estado, self.canal)},
            setting_sources=["project"],
            agents=carregar_maesters(self.s.root),
            mcp_servers={"cerebro": build_cerebro_server(self.vault, self.estado, self),
                         "emocao": build_emocao_server(self.perfil, self.perguntas, self.humor),
                         "mundo": build_mundo_server(self.agenda, self.s.lat, self.s.lon),
                         "estudo": build_estudo_server(self.estudo),
                         "maos": build_maos_server(self.vault, self.s.workspace)},
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
        self.momento = calcular_momento(self.perfil)
        self.humor.registrar_hora(datetime.now().hour)
        self.humor.registrar_momento(self.momento.peso, self.momento.aniversario)
        bus.emitir("humor", **self.humor.dados())
        if apresentar:
            self.apresentacao = await self._interno(prompt_apresentacao(nova, self.identidade.nome, resumo_falado(self.saude),
                                                                        self.momento.texto() if self.momento.aniversario or self.momento.hoje_e or self.momento.feriado else ""))
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
                        if b.is_error:
                            self._erros_turno += 1
                            # mesmo erro duas vezes → problema para o cérebro de estudo
                            chave = re.sub(r"\d+", "#", (c or "")[:120]).strip()
                            self._erros_vistos[chave] = self._erros_vistos.get(chave, 0) + 1
                            if self._erros_vistos[chave] == 2:
                                self.estudo.abrir(f"Ferramenta falha repetidamente: {chave[:80]}", c or "", "ferramenta_falhou")
                        bus.emitir("resultado", texto=(c or "")[:300], erro=bool(b.is_error))
            elif isinstance(msg, ResultMessage):
                # total_cost_usd é acumulado da sessão: o custo do turno é a diferença
                total = float(msg.total_cost_usd or 0)
                self._custo_turno = max(0.0, total - self._custo_sessao); self._custo_sessao = total
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
        if eh_sim(texto) and not self.proposta_renomear and self.acesso.liberado:
            # "sim" solto, sem pergunta pendente: um "sim" já custou 216 s de modelo implementando roadmap sozinho
            return "Sim ao quê, João?"
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
        if curta is None and self.acesso.liberado:
            curta = await self._mundo(texto)     # hora, clima, lembrete: sem modelo
        if curta is not None:
            bus.emitir("fala", texto=curta); bus.emitir("fala_fim"); yield curta; return
        async with self._lock:
            self.canal = canal
            if eh_confirmacao(texto):
                self.vigia.armar(); texto = "confirmo — pode executar a ação que o Vigia bloqueou."
            elif eh_correcao(texto):
                # o turno anterior estava errado: o placar tira o acerto provisório daquele modelo
                if (u := self.placar.corrigir_ultimo(f"o João disse: {texto[:60]}")):
                    bus.emitir("placar", msg=f"correção: {u['modelo']} errou em '{u['tipo']}'")
                self.humor.registrar_resultado(False)
            # o tom do João muda o humor antes da resposta (e a prosódia da voz)
            self.humor.registrar_tom(detectar_tom(texto)); self.humor.registrar_hora(datetime.now().hour)
            bus.emitir("humor", **self.humor.dados())
            escolha = self.roteador.decidir(texto, contexto, canal)
            partes, inicio = [], asyncio.get_event_loop().time()
            self._custo_turno = 0.0; self._erros_turno = 0
            if self.openai.disponivel and pede_juiz(texto, escolha.tipo):
                # decisão: duas opiniões + árbitro (custa o dobro; só aqui)
                bus.emitir("cortex", tarefa=escolha.tipo, confianca=escolha.confianca, modelo="juiz",
                           motivo="duas opiniões (Anthropic + OpenAI) e o Fable 5.1 arbitra", exploracao=False)
                v = await self.juiz.julgar(texto, self._contexto_texto(contexto))
                bus.emitir("juiz", escolha=v.escolha, justificativa=v.justificativa,
                           provedores=[f"{r.provedor}/{r.modelo}" + ("" if r.ok else " ✘") for r in v.respostas])
                self.vault.diario(f"Juiz ({v.escolha}): {v.justificativa}", "Decisões")
                bus.emitir("fala", texto=v.texto); bus.emitir("fala_fim")
                partes.append(v.texto); yield v.texto
                self.placar.registrar(f"juiz:{v.escolha}", escolha.tipo, "acerto", v.latencia, v.custo, texto[:80])
            elif escolha.modelo.startswith("openai:"):
                # texto pela OpenAI; se falhar (sem crédito, rede), cai na Anthropic no mesmo turno
                bus.emitir("cortex", tarefa=escolha.tipo, confianca=escolha.confianca, modelo=escolha.modelo,
                           motivo=escolha.motivo, exploracao=escolha.exploracao)
                r = await self.openai.responder(texto, self._contexto_texto(contexto),
                                                ["web_search"] if escolha.tipo == "pesquisa" else None)
                if r.ok:
                    bus.emitir("fala", texto=r.texto); bus.emitir("fala_fim")
                    partes.append(r.texto); yield r.texto
                    self.placar.registrar(escolha.modelo, escolha.tipo, "acerto", r.latencia, r.custo, texto[:80])
                else:
                    self.placar.registrar(escolha.modelo, escolha.tipo, "erro", 0, 0, r.erro[:80])
                    bus.emitir("placar", msg=f"{escolha.modelo} falhou ({r.erro[:60]}); indo pela Anthropic")
                    escolha.modelo = self.s.model_padrao
                    async for t in self._turno_anthropic(escolha, texto, canal, contexto, inicio):
                        partes.append(t); yield t
            else:
                async for t in self._turno_anthropic(escolha, texto, canal, contexto, inicio):
                    partes.append(t); yield t
        # resultado do turno alimenta o humor: ferramentas falhando = erro próprio (grave se repetiu)
        self.humor.registrar_resultado(self._erros_turno == 0, grave=self._erros_turno >= 2)
        bus.emitir("humor", **self.humor.dados())
        # gatilhos do cérebro de estudo: o João pediu pesquisa, ou a resposta admitiu não saber
        resposta = "".join(partes)
        if (mp := re.search(r"\b(pesquisa isso|estuda isso|descobre isso|n[aã]o sei como|vê como faz)\b[:,\s]*(?:depois[:,\s]*)?(.*)", texto, re.I)):
            titulo = re.split(r"[.;]\s|\bpor agora\b", mp.group(2), 1)[0].strip() or texto
            self.estudo.abrir(titulo[:100], f"pedido: {texto[:200]}", "joao_pediu")
        elif re.search(r"\b(n[aã]o sei|n[aã]o tenho como|n[aã]o consegui descobrir|n[aã]o encontrei)\b", resposta[:300], re.I) and escolha.tipo in ("pesquisa", "código"):
            self.estudo.abrir(texto[:100], resposta[:400], "sem_resposta")
        await self._pos_turno(canal, texto, "".join(partes))

    async def _turno_anthropic(self, escolha, texto: str, canal: str, contexto: str, inicio: float):
        """O caminho normal: cliente persistente da Anthropic, com as mãos."""
        await self._usar_modelo(escolha.modelo)
        bus.emitir("cortex", tarefa=escolha.tipo, confianca=escolha.confianca, modelo=escolha.modelo,
                   motivo=escolha.motivo, exploracao=escolha.exploracao)
        prefixo = f"[canal={canal}]" + (f" [contexto: {contexto}]" if contexto else "")
        async for t in self._stream(f"{prefixo} {texto}"):
            yield t
        # acerto provisório: vira erro se o próximo turno for uma correção
        self.placar.registrar(escolha.modelo, escolha.tipo, "acerto",
                              asyncio.get_event_loop().time() - inicio, self._custo_turno, texto[:80])

    def _contexto_texto(self, contexto: str = "") -> str:
        """Contexto para provedores de texto (sem as mãos): quem ele é, regras, perfil do João, estado."""
        base = system_prompt(self.vault, self.estado, self.canal)
        return base + (f"\n\n[contexto agora: {contexto}]" if contexto else "") + \
            "\n\nResponda em português do Brasil, direto, sem markdown quando o canal for voice."

    async def _usar_modelo(self, modelo: str) -> None:
        """Troca o modelo do cliente persistente sem perder a conversa (ClaudeSDKClient.set_model).
        Descoberto no SDK 0.2.152: existe `set_model(model)`; recriar o cliente perderia o contexto."""
        if modelo == self.modelo_atual or not self._client:
            return
        try:
            await self._client.set_model(modelo)
            self.modelo_atual = modelo
        except Exception as e:
            bus.emitir("cortex", tarefa="", modelo=self.modelo_atual, motivo=f"não consegui trocar para {modelo}: {type(e).__name__}", exploracao=False)

    async def _mundo(self, texto: str) -> str | None:
        """Perguntas de hora/data/clima e pedidos de lembrete são respondidos aqui, em milissegundos."""
        if (r := relogio.responder(texto)):
            return r
        if clima.pergunta_de_clima(texto):
            return await clima.responder(texto, self.s.lat, self.s.lon)
        if (l := lem.interpretar(texto)):
            quando, o_que = l
            try:
                return self.agenda.criar_lembrete(quando, o_que)
            except Exception as e:
                return f"Não consegui agendar o lembrete ({type(e).__name__})."
        return None

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
