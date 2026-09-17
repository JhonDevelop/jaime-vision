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
from ..vigia.hooks import Vigia, eh_confirmacao, eh_aprovacao_lote
from ..vigia.confianca import Confianca
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
from ..equipe.tools import build_equipe_server
from ..mente.pensar import Pensar
from ..mente.tools import build_mente_server
from ..financas.livro import Livro
from ..financas.tools import build_financas_server
from ..conexoes.spotify import Spotify
from ..conexoes.tools_musica import build_musica_server
from ..maos.tools import build_maos_server
from ..conexoes.registro import Registro
from ..conexoes.google import GoogleConta
from ..conexoes.tools import build_google_server
from ..maos.imagens import Imagens
from ..maos.tools_midia import build_midia_server, build_tela_server
from ..conexoes.meta import Meta
from ..conexoes.tools_meta import build_meta_server
from ..autonomo import Autonomo
from ..tools_autonomo import build_autonomo_server
from ..casa.homeassistant import Casa
from ..casa.tools import build_casa_server
from ..maos.visao import Visao, quer_parar
from ..maos.tools_visao import build_visao_server
from ..brain.indice import Indice
from ..brain import ouvido_passivo
from ..emocao.vinculo import Vinculo
from ..maos.gravador import Gravador, interpretar as gravador_interpretar
from ..evolucao import Evolucao
from ..tools_evolucao import build_evolucao_server
from ..hud.events import bus
from ..hud.tools import build_interface_server
from ..cerebros import Cerebros
from ..cerebros.tools import build_cerebros_server
from ..espelho import Espelho
from ..espelho.tools import build_espelho_server
from ..maos.raspar import build_raspar_server
from ..cortex.harness import Harness
from ..cortex.tools_harness import build_harness_server
from ..donos import Porteiro, eh_o_socio_se_apresentando, boas_vindas, roteiro_texto
from ..ponte import Ponte, build_ponte_server
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
        self.confianca = Confianca(self.vault)      # fase 3: classes de ação já liberadas pelo João
        self.vigia = Vigia(self.confianca)
        self.acesso = Acesso(settings.passphrase_hash, settings.acesso_timeout_min)
        self.notion = NotionSync(settings, self.vault, self.estado)
        self.identidade = Identidade(settings.vault, settings.root)
        self._client: ClaudeSDKClient | None = None
        self._lock = asyncio.Lock()
        self._ordem_em_curso = ""        # rotina que está com o orquestrador agora (canal "rotina"); "" fora disso
        self._rotina_cedida = ""         # rotina interrompida para atender o João — não se fala o que sobrou dela
        self._ultima_espera_lock = 0.0   # segundos que a última demanda esperou pelo lock (vai para a linha de latência)
        self.canal = "cli"
        self.apresentacao: str = ""
        self.proposta_renomear: str = ""      # nome proposto, à espera do "confirmo"
        self.aguardando_nome: bool = False    # boot: "Meu nome é X — confirma?"
        self.saude: list = []
        # Córtex: o modelo é escolhido por tarefa; o placar aprende com acertos e correções
        self.placar = Placar(settings.vault)
        # OpenAI: texto, pesquisa e decisões; nunca as mãos. Sem chave → o roteador nem a lista.
        self.openai = ProvedorOpenAI(settings.openai_key, settings.openai_model)
        # uso mínimo da OpenAI (pedido do João): o roteador nem lista os modelos dela; o juiz só com "pensa bem"
        self.roteador = Roteador({"decisao": settings.model_decisao, "codigo": settings.model_codigo,
                                  "padrao": settings.model_padrao, "rotina": settings.model_rotina},
                                 self.placar, settings.cortex_exploracao,
                                 openai=settings.openai_model if (self.openai.disponivel and settings.openai_uso == "normal") else "")
        self.juiz = Juiz(ProvedorAnthropic(settings.model_padrao, str(settings.root)), self.openai,
                         ProvedorAnthropic(settings.model_decisao, str(settings.root)))
        self.modelo_atual = settings.model
        self._custo_turno = 0.0
        self._custo_sessao = 0.0
        self._erros_turno = 0
        self._parar_repeticao = False
        # cérebro emocional: quem é o João, o que já perguntei, que dia é hoje, como estou
        self.perfil = Perfil(self.vault)
        self.perguntas = Perguntas(self.vault)
        self.humor = Humor()
        self.momento = calcular_momento(self.perfil)
        # agenda própria (rotinas, lembretes) — o servidor liga o scheduler depois do boot
        self.agenda = Agenda(self)
        # cérebro de estudo: problemas em aberto → ciclos em /tmp/jaime-lab
        self.estudo = Estudo(self.vault, self.estado, self.placar, settings.root, settings.model_padrao)
        # fase 3: filhos — terminais que ele cria no Maestri (Claude Code, Codex…) para trabalhar em paralelo
        from ..equipe.filhos import Equipe
        self.equipe = Equipe(self, settings.root, vigia=self.vigia)
        self.cerebros = Cerebros(self.vault, self.equipe, repo=settings.root)   # central Claude · esquerdo Codex · direito Gemini
        self.espelho = Espelho(self.vault)                  # o que ele aprendeu do jeito do João
        self.harness = Harness(self)                        # persegue objetivo: age, verifica, corrige, replaneja
        self.porteiro = Porteiro()                          # o Gabriel montando a cópia dele (jaime/donos.py)
        self.ponte = Ponte()                                # acesso à máquina do outro dono (jaime/ponte/)
        # raciocínio próprio: a Mente contínua pensa sobre o mundo do João quando ocioso (jaime/mente/pensar.py)
        self.pensar = Pensar(self.vault, s=settings)
        self.financas = Livro(self.vault)      # livro-caixa pessoal do João (painel Finanças)
        self.spotify = Spotify(settings.spotify_token, settings.spotify_client_id, settings.spotify_client_secret)  # música/gosto
        self._erros_vistos: dict[str, int] = {}
        # conexões: registro do que ele acessa + Google pelo OAuth próprio (token local)
        self.conexoes = Registro(self.vault)
        self.google = GoogleConta(settings.google_token)
        self.meta = Meta(settings.meta_token, settings.meta_app_secret, settings.meta_verify_token, settings.meta_whatsapp_phone_id,
                         settings.meta_instagram_id, self, dono_whatsapp=settings.owner_phone)
        self.autonomo = Autonomo(self, settings.autonomo_horas, settings.autonomo_custo_usd, settings.autonomo_ferramentas)
        # fase 3: casa (Home Assistant), câmera e visão contínua (jogos/apps); o Vigia libera a tela só com sessão ativa
        self.casa = Casa(settings.ha_url, settings.ha_token)
        self.visao = Visao(self, settings.visao_max_passos, settings.visao_intervalo_s)
        self.vigia.sessao_livre = lambda: self.visao.ativa
        # fase 3: memória semântica (FTS5 no vault, recall proativo) e autoevolução por PR
        self.indice = Indice(settings.vault)
        self.indice.atualizar()
        self.vault.indice = self.indice
        self.evolucao = Evolucao(self, settings.root)
        # gravador de processos ("grava esse processo" / "repete o processo X"); o observador entra pelo servidor
        self.gravador = Gravador(self)
        self._avisos_entregues_em: str = ""
        # vínculo com o dono: familiaridade, pessoas próximas, acompanhamentos — vira contexto e calor
        self.vinculo = Vinculo(self.vault)
        self.humor.e.calor = max(self.humor.e.calor, self.vinculo.calor())
        self.falante_atual: str = ""     # quem está falando agora (voz reconhecida): "", "João", "Gabriel", "desconhecido", "incerto"
        self._senha_incerta = 0          # palavra-passe certa mas voz "incerta": 1ª vez repete, 2ª vez digita
        usar_nome(self.identidade.variantes())

    # ── autoconsciência ────────────────────────────────
    def quem_sou(self) -> str:
        """O que eu sou, por que existo e como estou agora (jaime/brain/eu.py) — entra em todo prompt."""
        try:
            from ..brain.eu import quem_sou
            return quem_sou(self)
        except Exception as e:
            return f"(autoconsciência falhou: {type(e).__name__})"

    # ── ciclo de vida ──────────────────────────────────
    def _options(self) -> ClaudeAgentOptions:
        kw = dict(
            model=self.s.model, cwd=str(self.s.root),
            system_prompt={"type": "preset", "preset": "claude_code",
                           "append": system_prompt(self.vault, self.estado, self.canal, self.quem_sou())},
            setting_sources=["project"],
            agents=carregar_maesters(self.s.root),
            mcp_servers={"cerebro": build_cerebro_server(self.vault, self.estado, self),
                         "emocao": build_emocao_server(self.perfil, self.perguntas, self.humor),
                         "mundo": build_mundo_server(self.agenda, self.s.lat, self.s.lon),
                         "estudo": build_estudo_server(self.estudo),
                         "maos": build_maos_server(self.vault, self.s.workspace),
                         "google": build_google_server(self.google, self.conexoes),
                         "midia": build_midia_server(Imagens(self.s.openai_key, self.vault), self.s.deepgram_key),
                         "tela": build_tela_server(),
                         "meta": build_meta_server(self.meta),
                         "autonomo": build_autonomo_server(self.autonomo),
                         "casa": build_casa_server(self.casa, self.s.camera),
                         "visao": build_visao_server(self.visao),
                         "evolucao": build_evolucao_server(self.evolucao, self.indice),
                         "equipe": build_equipe_server(self.equipe),
                         "mente": build_mente_server(self.pensar),
                         "financas": build_financas_server(self.financas),
                         "musica": build_musica_server(self.spotify),
                         "interface": build_interface_server(),
                         "cerebros": build_cerebros_server(self.cerebros),
                         "espelho": build_espelho_server(self.espelho),
                         "web": build_raspar_server(),
                         "harness": build_harness_server(self.harness),
                         "ponte": build_ponte_server(self.ponte)},
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
        from ..brain.eu import registrar_despertar
        registrar_despertar(self)      # ele se reconhece antes de agir
        bus.emitir("estado", fase=self.estado.fase(), situacao=self.estado.secao("Situação agora"),
                   maquina=maquina(), nova_maquina=nova, liberado=self.acesso.liberado)
        self.momento = calcular_momento(self.perfil)
        self.humor.registrar_hora(datetime.now().hour)
        self.humor.registrar_momento(self.momento.peso, self.momento.aniversario)
        bus.emitir("humor", **self.humor.dados())
        marca = self.s.root / ".jaime-boot"
        ja_hoje = marca.exists() and marca.read_text(encoding="utf-8").strip() == datetime.now().strftime("%Y-%m-%d")
        if apresentar and ja_hoje and not nova:
            # reiniciou no mesmo dia: sem se apresentar de novo — uma linha e pronto
            self.apresentacao = "Sistemas operacionais, senhor." + (" " + resumo_falado(self.saude) if resumo_falado(self.saude) else "")
        elif apresentar:
            self.apresentacao = await self._interno(prompt_apresentacao(nova, self.identidade.nome, resumo_falado(self.saude),
                                                                        self.momento.texto() if self.momento.aniversario or self.momento.hoje_e or self.momento.feriado else ""))
            marca.write_text(datetime.now().strftime("%Y-%m-%d"), encoding="utf-8")
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
                        txt = d["text"]
                        if re.search(r"\b(hit your session limit|session limit|rate limit exceeded|overloaded_error)\b", txt, re.I):
                            raise RuntimeError(f"anthropic_session_limit: {txt}")
                        por_delta = True
                        bus.emitir("fala", texto=txt); yield txt
                    elif d.get("type") == "thinking_delta" and d.get("thinking"):
                        pensando += d["thinking"]
                        if len(pensando) > 240:
                            bus.emitir("raciocinio", texto=pensando[:600]); pensando = ""
                continue
            if isinstance(msg, AssistantMessage):
                for b in msg.content:
                    if isinstance(b, TextBlock) and b.text.strip():
                        if re.search(r"\b(hit your session limit|session limit|rate limit exceeded|overloaded_error)\b", b.text, re.I):
                            raise RuntimeError(f"anthropic_session_limit: {b.text}")
                        if not por_delta:
                            bus.emitir("fala", texto=b.text); yield b.text
                    elif isinstance(b, ThinkingBlock):
                        if pensando:
                            bus.emitir("raciocinio", texto=pensando[:600]); pensando = ""
                        elif not por_delta:
                            bus.emitir("raciocinio", texto=b.thinking[:600])
                    elif isinstance(b, ToolUseBlock):
                        tipo = "producao" if b.name in ("Write", "Edit", "MultiEdit", "Bash", "Task") or b.name.startswith("mcp__") else "raciocinio"
                        args = b.input or {}
                        # trecho visível no HUD: o código/texto que ele está escrevendo, o comando, a nota do vault
                        trecho = ""
                        if b.name in ("Write",): trecho = str(args.get("content", ""))[:1200]
                        elif b.name in ("Edit", "MultiEdit"): trecho = "- " + str(args.get("old_string", ""))[:500] + "\n+ " + str(args.get("new_string", ""))[:700]
                        elif b.name == "Bash": trecho = str(args.get("command", ""))[:600]
                        elif b.name.startswith("mcp__cerebro__"): trecho = str(args.get("texto") or args.get("corpo") or args.get("descricao") or "")[:600]
                        nota = str(args.get("nota") or args.get("caminho") or "") if b.name.startswith("mcp__cerebro__") else ""
                        bus.emitir(tipo, ferramenta=b.name, alvo=_resumo_tool(b.name, args), trecho=trecho, nota=nota)
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

    def _porta(self, texto: str, canal: str = "voice") -> str | None:
        """Palavra-passe e tranca. Devolve uma resposta curta se a fala não deve chegar ao Claude."""
        # voz reconhecida e não é o João: palavra-passe, "confirmo", renomear e tranca são só dele.
        # Texto digitado (HUD, Telegram) não tem voz: o falante da última fala não vale para ele.
        falante = self.falante_atual if canal == "voice" else ""
        if falante and falante not in ("João", "incerto") and (eh_confirmacao(texto) or quer_trancar(texto) or quer_renomear(texto)
                                                                 or (not self.acesso.liberado and self.acesso.confere(texto))):
            quem = falante if falante != "desconhecido" else ""
            self.vault.diario(f"{quem or 'Voz desconhecida'} tentou algo só do João: {texto[:60]}", "Log")
            return f"Isso só com o João{', ' + quem if quem else ''}."
        if quer_trancar(texto):
            self.acesso.trancar(); bus.emitir("acesso", liberado=False)
            return "Cérebro trancado. Diga a palavra-passe quando quiser voltar."
        if quer_teclado(texto):
            bus.emitir("teclado", aberto=True, motivo="você pediu")
            return "Pode escrever."
        if (g := gravador_interpretar(texto)) and self.acesso.liberado:
            acao, nome = g
            if acao == "gravar":
                return self.gravador.iniciar(nome)
            if acao == "parar":
                return self.gravador.parar()
            asyncio.get_event_loop().run_in_executor(None, lambda: self.gravador.repetir(nome, deve_parar=lambda: self._parar_repeticao))
            self._parar_repeticao = False
            return f"Repetindo o processo {nome}. Diga 'para' se algo sair errado."
        if (mi := re.match(r"^\s*implementa(?:r)?\s+(M-\d{4})\b", texto, re.I)):
            asyncio.get_event_loop().create_task(self.evolucao.implementar(mi.group(1).upper()))
            return f"Implementando {mi.group(1).upper()} num worktree isolado; te aviso quando a branch estiver pronta."
        if quer_parar(texto):
            # kill switch: visão contínua, objetivo autônomo e repetição de processo param na hora, sem modelo
            self._parar_repeticao = True
            parou = [n for n, ok in (("visão", self.visao.parar()), ("objetivo", self.autonomo.interromper()),
                                     ("gravação", self.gravador.gravando and bool(self.gravador.parar()))) if ok]
            return f"Parei: {', '.join(parou)}." if parou else "Nada rodando para parar."
        # identidade: "me chama de X" propõe; "confirmo" com proposta pendente executa; "sim" no boot confirma o nome
        # ── o sócio se apresentando: portão próprio, que NÃO abre o cérebro do João ──
        porteiro = getattr(self, "porteiro", None)   # dublês de teste da tranca não montam o portão
        if porteiro is not None and porteiro.etapa in ("confirmando", "senha"):
            resposta = porteiro.responder(texto, self.acesso)
            if porteiro.barrado:
                self.vault.diario("Alguém disse ser o Gabriel e errou a palavra-passe 3×. Barrei.", "Decisões")
                porteiro.fechar()
            if resposta is not None:
                return resposta
            self.vault.diario("Gabriel Mello se identificou e provou a autorização; entreguei o roteiro da cópia dele.", "Decisões")
            bus.emitir("dono", quem="Gabriel Mello", etapa="roteiro")
            return boas_vindas() + "\n\n" + roteiro_texto()
        if porteiro is not None and eh_o_socio_se_apresentando(texto):
            return porteiro.apresentou()

        if (novo := quer_renomear(texto)):
            return self.propor_renomear(novo)
        if self.proposta_renomear and eh_confirmacao(texto):
            return self._executar_renomear()
        if self.aguardando_nome and eh_sim(texto):
            self.aguardando_nome = False; self.identidade.confirmar()
            bus.emitir("identidade", nome=self.identidade.nome, msg="nome confirmado")
            return f"{self.identidade.nome} confirmado. O que fazemos, João?"
        if eh_sim(texto) and not self.proposta_renomear and self.acesso.liberado and not self.vigia.lote and not self.confianca.pendente:
            # "sim" solto, sem pergunta pendente: um "sim" já custou 216 s de modelo implementando roadmap sozinho
            return "Sim ao quê, João?"
        if not self.acesso.liberado:
            if falante == "incerto" and self.acesso.confere(texto):
                # senha certa, voz na zona incerta (áudio ruim): repete uma vez; na segunda troca de fator — digita.
                self._senha_incerta += 1
                if self._senha_incerta == 1:
                    return "Não reconheci bem a sua voz. Repete a palavra-passe?"
                self._senha_incerta = 0
                bus.emitir("teclado", aberto=True, motivo="voz não reconhecida")
                self.vault.diario("Palavra-passe certa com voz incerta duas vezes: pedi para digitar", "Log")
                return "Não consegui confirmar a sua voz. Digita a palavra-passe no painel."
            if self.acesso.tentar(texto):
                self._senha_incerta = 0
                bus.emitir("acesso", liberado=True)
                # posicionamento: cumprimento curto de Jarvis, sem despejar Fase/Situação em voz alta (isso é do HUD)
                return "Bem-vindo de volta, João. Estou às ordens."
            bus.emitir("acesso", liberado=False)
            return "Palavra-passe, por favor."
        self.acesso.tocar(); return None

    async def ask_stream(self, texto: str, canal: str = "cli", contexto: str = ""):
        """Resposta em fluxo. Ao terminar (ou ser cortada), deixa UMA linha `🔈 jaime ›` no log — sem ela, o log
        mostra só o que o João disse e ninguém consegue observar o que o Jaime respondeu (Mente, 15/09)."""
        partes: list[str] = []
        lock = getattr(self, "_lock", None)
        if canal != "rotina" and getattr(self, "_ordem_em_curso", "") and lock is not None and lock.locked():
            # Utilidade sempre ganha se há demanda (CLAUDE.md §Vontades 1): a rotina que segura o orquestrador cede a vez.
            # Vigília 16/09 07:56: 4 turnos do João esperaram 66–122 s pelo briefing.
            await self._ceder_rotina(canal)
        try:
            async for t in self._ask_stream(texto, canal, contexto):
                partes.append(t); yield t
        finally:
            if canal == "rotina":
                self._ordem_em_curso = ""
            resposta = re.sub(r"\s+", " ", "".join(partes)).strip()
            if resposta:
                tranca = "" if self.acesso.liberado else " 🔒"
                print(f"🔈 jaime{tranca} › {resposta[:160]}{'…' if len(resposta) > 160 else ''}")

    async def _ceder_rotina(self, canal: str) -> None:
        """Interrompe a rotina em curso (mesmo `interrupt` do barge-in), espera o orquestrador liberar e reagenda a rotina."""
        ordem = self._ordem_em_curso
        self._rotina_cedida = ordem
        try:
            self.vault.diario(f"Rotina «{ordem[:50]}» interrompida: demanda do João ({canal}); volto a ela em 10 min", "Log")
        except Exception:
            pass
        cli = getattr(self, "_client", None)
        if cli is not None and hasattr(cli, "interrupt"):
            try:
                await cli.interrupt()
            except Exception:
                pass
        for _ in range(50):                      # até 5 s pelo modelo parar; depois entra na fila normal
            if not self._lock.locked():
                break
            await asyncio.sleep(0.1)
        agenda = getattr(self, "agenda", None)
        if agenda is not None and hasattr(agenda, "reagendar"):
            try:
                agenda.reagendar(ordem, minutos=10)
            except Exception:
                pass

    def _quem_esta_na_linha(self, canal: str) -> str:
        """Quem está falando: "" é o João, qualquer outra coisa é visita — e visita não lê a vida dele.
        Vale para a voz reconhecida e para quem chega de fora desta máquina (canal `remoto`)."""
        falante = (getattr(self, "falante_atual", "") or "").strip()
        if canal == "remoto" or (self.porteiro.aberto if getattr(self, "porteiro", None) else False):
            return falante or "visita"
        if falante and falante.lower() not in ("joão", "joao", "dono"):
            return falante
        return ""

    async def _ask_stream(self, texto: str, canal: str = "cli", contexto: str = ""):
        try:
            self.vigia.convidado = self._quem_esta_na_linha(canal)
        except Exception:
            pass
        """contexto: o que o João está vendo na tela agora (app/janela) — vai só ao modelo, não ao diário."""
        assert self._client, "Chame start() antes."
        self.acesso.tocar()      # QUALQUER interação renova a sessão — respostas rápidas não deixam mais o cérebro trancar sozinho no meio do uso
        bus.emitir("conversa", canal=canal, texto=texto if self.acesso.liberado else "•••")
        curta = self._porta(texto, canal)
        if curta is None and self.acesso.liberado:
            curta = await self._mundo(texto)     # hora, clima, lembrete: sem modelo
        if curta is not None:
            bus.emitir("fala", texto=curta); bus.emitir("fala_fim"); yield curta; return
        t_lock = asyncio.get_event_loop().time()
        async with self._lock:
            self._ultima_espera_lock = asyncio.get_event_loop().time() - t_lock   # quanto esta demanda esperou o orquestrador
            self.canal = canal
            self._ordem_em_curso = texto if canal == "rotina" else ""
            self.vigia.lote_executado = False
            if (r := self.confianca.responder(texto)) and not self.vigia.lote:
                # resposta à proposta "posso passar a fazer X sem perguntar?"
                self.vault.diario(f"Confiança: {r}", "Decisões")
                bus.emitir("fala", texto=r); bus.emitir("fala_fim"); yield r; return
            if self.vigia.lote and eh_aprovacao_lote(texto):
                # confirmação em lote (fase 3): "sim" libera exatamente as ações anotadas neste turno
                acoes = self.vigia.liberar_lote()
                self.vault.diario("Lote liberado pelo João: " + "; ".join(a.descricao for a in acoes), "Decisões")
                texto = ("sim — execute agora, na ordem e sem perguntar de novo, exatamente as ações que o Vigia anotou: "
                         + "; ".join(a.descricao for a in acoes) + ". Se alguma falhar, pare e relate o que aconteceu.")
            elif eh_confirmacao(texto):
                self.vigia.armar(); texto = "confirmo — pode executar a ação que o Vigia bloqueou."
                if self.autonomo.confirmar():
                    # a missão autônoma pausada retoma sozinha; não precisa de um turno do modelo
                    bus.emitir("fala", texto="Confirmado. Retomando o objetivo."); bus.emitir("fala_fim")
                    yield "Confirmado. Retomando o objetivo."; return
            elif eh_correcao(texto):
                # o turno anterior estava errado: o placar tira o acerto provisório daquele modelo
                if (u := self.placar.corrigir_ultimo(f"o João disse: {texto[:60]}")):
                    bus.emitir("placar", msg=f"correção: {u['modelo']} errou em '{u['tipo']}'")
                self.humor.registrar_resultado(False)
                self.confianca.corrigir(self.vigia.ultimo_lote_classes)
                self.vigia.descartar_lote()
            else:
                if (n := self.vigia.descartar_lote()):
                    bus.emitir("resultado", texto=f"lote de {n} ação(ões) descartado: o João não confirmou", erro=False)
            # o tom do João muda o humor antes da resposta (e a prosódia da voz)
            self.humor.registrar_tom(detectar_tom(texto)); self.humor.registrar_hora(datetime.now().hour)
            bus.emitir("humor", **self.humor.dados())
            escolha = self.roteador.decidir(texto, contexto, canal)
            partes, inicio = [], asyncio.get_event_loop().time()
            self._custo_turno = 0.0; self._erros_turno = 0
            if self.openai.disponivel and (pede_juiz(texto, "") if self.s.openai_uso == "minimo" else pede_juiz(texto, escolha.tipo)):
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
        resposta = "".join(partes)
        # Vigia por lote: se o modelo esqueceu de perguntar, a pergunta única vai no fim da resposta
        if self.vigia.lote and (pergunta := self.vigia.pedir_lote()) and "você deseja que eu" not in resposta.lower():
            bus.emitir("fala", texto=" " + pergunta); partes.append(" " + pergunta); yield " " + pergunta
            resposta = "".join(partes)
        elif self.vigia.lote_executado and self._erros_turno == 0 and (prop := self.confianca.aprovar(self.vigia.ultimo_lote_classes)):
            self.vault.diario(f"Proposta de confiança: {prop}", "Pendente")
            bus.emitir("fala", texto=" " + prop); partes.append(" " + prop); yield " " + prop
            resposta = "".join(partes)
        # gatilhos do cérebro de estudo: o João pediu pesquisa, ou a resposta admitiu não saber
        if (mp := re.search(r"\b(pesquisa isso|estuda isso|descobre isso|n[aã]o sei como|vê como faz)\b[:,\s]*(?:depois[:,\s]*)?(.*)", texto, re.I)):
            titulo = re.split(r"[.;]\s|\bpor agora\b", mp.group(2), 1)[0].strip() or texto
            self.estudo.abrir(titulo[:100], f"pedido: {texto[:200]}", "joao_pediu")
        elif re.search(r"\b(n[aã]o sei|n[aã]o tenho como|n[aã]o consegui descobrir|n[aã]o encontrei)\b", resposta[:300], re.I) and escolha.tipo in ("pesquisa", "código"):
            self.estudo.abrir(texto[:100], resposta[:400], "sem_resposta")
        await self._pos_turno(canal, texto, "".join(partes))

    def _memoria(self, texto: str) -> str:
        """Recall proativo: o que o vault já sabe sobre o assunto, em uma linha por lembrete (fora do diário de hoje)."""
        try:
            self.indice.atualizar()
            hits = self.indice.recordar(texto)
        except Exception:
            return ""
        if hits:
            bus.emitir("raciocinio", ferramenta="memória", alvo="; ".join(h.split(":")[0] for h in hits))
        return " | ".join(hits)

    async def _turno_anthropic(self, escolha, texto: str, canal: str, contexto: str, inicio: float):
        """O caminho normal: cliente persistente da Anthropic, com as mãos."""
        await self._usar_modelo(escolha.modelo)
        bus.emitir("cortex", tarefa=escolha.tipo, confianca=escolha.confianca, modelo=escolha.modelo,
                   motivo=escolha.motivo, exploracao=escolha.exploracao)
        memoria = self._memoria(texto) if canal in ("voice", "hud", "cli", "telegram", "whatsapp") else ""
        # antes de responder, checar o que já pensei (tese §3): raciocínio próprio guardado sobre o assunto
        try:
            pensei = self.pensar.recall_para_prompt(texto)
        except Exception:
            pensei = ""
        if pensei:
            bus.emitir("raciocinio", ferramenta="pensamentos", alvo=pensei[:80])
        prefixo = (f"[canal={canal}]" + (f" [contexto: {contexto}]" if contexto else "")
                   + (f" [memória do vault: {memoria}]" if memoria else "")
                   + (f" [você já pensou sobre isso: {pensei}]" if pensei else ""))
        try:
            async for t in self._stream(f"{prefixo} {texto}"):
                yield t
            # acerto provisório: vira erro se o próximo turno for uma correção
            self.placar.registrar(escolha.modelo, escolha.tipo, "acerto",
                                  asyncio.get_event_loop().time() - inicio, self._custo_turno, texto[:80])
        except Exception as e:
            msg_e = str(e).lower()
            if "anthropic_session_limit" in msg_e or "session limit" in msg_e or "rate limit" in msg_e or "overloaded" in msg_e:
                bus.emitir("placar", msg="Anthropic em limite de sessão/quota; acionando fallback OpenAI")
                self.vault.diario(f"Harness: failover automático Anthropic → OpenAI ({msg_e[:60]})", "Decisões")
                if self.openai.disponivel:
                    r = await self.openai.responder(texto, self._contexto_texto(contexto))
                    if r.ok and r.texto:
                        bus.emitir("fala", texto=r.texto); bus.emitir("fala_fim")
                        yield r.texto
                        self.placar.registrar(f"openai:{self.openai.modelo}", escolha.tipo, "acerto", r.latencia, r.custo, texto[:80])
                        return
                aviso = "Atingi temporariamente o limite de requisições da sessão. Retorno em instantes."
                bus.emitir("fala", texto=aviso); bus.emitir("fala_fim")
                yield aviso
                return
            raise

    def _contexto_texto(self, contexto: str = "") -> str:
        """Contexto para provedores de texto (sem as mãos): quem ele é, regras, perfil do João, estado."""
        base = system_prompt(self.vault, self.estado, self.canal, self.quem_sou())
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

    def avisos_do_dia(self) -> str:
        """No primeiro 'está aí' do dia: o que ele guardou de ontem (ouvido passivo) + tarefas do dia. Uma vez por dia."""
        hoje = datetime.now().strftime("%Y-%m-%d")
        if self._avisos_entregues_em == hoje:
            return ""
        frase = ouvido_passivo.frase_dos_pendentes(self.vault, self.vault.tarefas_abertas())
        if not frase:
            return ""
        self._avisos_entregues_em = hoje
        ouvido_passivo.marcar_entregues(self.vault)
        self.vault.diario("Avisos do dia entregues: " + frase[:160], "Log")
        return frase

    async def _mundo(self, texto: str) -> str | None:
        """Perguntas de hora/data/clima, cumprimentos e pedidos de lembrete são respondidos aqui, em milissegundos."""
        from ..voice.rapidas import responder as rapida
        if (r := rapida(texto, self)):
            return r
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
        if canal in ("voice", "hud", "cli", "telegram", "whatsapp"):
            self.vinculo.registrar_conversa()
        if self.estado.precisa_refletir():
            bus.emitir("raciocinio", ferramenta="reflexão", alvo="atualizando meu Estado")
            asyncio.create_task(self._interno(prompt_reflexao()))   # em segundo plano: não segura a resposta
        bus.emitir("estado", fase=self.estado.fase(), situacao=self.estado.secao("Situação agora"),
                   maquina=maquina(), liberado=self.acesso.liberado)
        asyncio.create_task(self.notion.tudo())
