# Projeto Jaime — brief para o Cowork

> Fonte única de necessidades, funcionalidades, fases e pendências do J.A.I.M.E. Abra como projeto no Claude
> Cowork (ou cole como contexto). O `maester-jaime` e o gerente no Cowork mantêm; o João aprova.
>
> **Consolidado em 28/09/2026** a partir do `main` em `0948e37` (último commit: 21/09, 18:33). Tudo que está
> marcado aqui tem evidência no repositório: arquivo, commit ou documento. O que não tem está escrito como
> **não consta**. Mapa de onde fica cada coisa: `cowork/MAPA.md`.

## Objetivo
Um assistente pessoal e operacional — o "Jarvis" do João — que fala, ouve, lembra, age no computador e nos
serviços, sabe quem é e em que fase está, trabalha sozinho no que importa e melhora a cada semana.

## Pilares
1. **Cérebro** — vault Obsidian local (fonte primária) + espelho no Notion; memória semântica e grafo de relações.
2. **Autoconsciência** — `01-Estado/Estado.md` reescrito por ele; identidade editável; placar dos próprios acertos.
3. **Mãos** — Agent SDK com shell, arquivos, git, browser, computer use, visão contínua, casa, mídia.
4. **Voz e presença** — full-duplex com barge-in, antecipador, HUD/cockpit vivo.
5. **Três cérebros** — Central (Claude) decide e fala; Esquerdo (Codex) executa; Direito (Gemini) pesquisa e critica.
6. **Vontade própria** — impulsos, carteira de iniciativas, criação e estudo quando ninguém está pedindo.
7. **Segurança** — local por padrão, palavra-passe com hash, Vigia em três níveis, tranca por dono.

## Onde estamos (28/09)

**Fase 3 construída, validação ao vivo pendente.** A fase 2 fechou em 15/09. As duas "fases 3" (ver abaixo) foram
construídas entre 15 e 21/09; o que falta é o João validar ao vivo e entregar credenciais. Entre 16 e 17/09 entrou
um bloco grande que **não tem documento de fase**: três cérebros, frota, segundo dono, carteira de iniciativas.

- **Último trabalho:** 21/09 — onze correções de estabilidade (M-37 a M-47): microfone morto após o sono, deadlock
  do BLAS, segfault no watchdog. **Não consta nenhum commit desde 21/09.** Não consta se o serviço está no ar.
- **`Estado.md` parado em 15/09 no repositório.** O serviço rodou até 21/09 e a reflexão não gravou nada versionado.
- **Testes:** 492 funções `test_` no repo (o caderno MENTE registra 581 execuções em 21/09, com parametrizados).
  Não executados neste ambiente.

## Fases

| Fase | Documento | Conteúdo | Status |
|---|---|---|---|
| 0 | `docs/ROADMAP.md` | esqueleto, HUD, palavra-passe, espelho Notion | fechada |
| 1 | `docs/ROADMAP.md` | MCPs GitHub/Notion autenticados no SDK | fechada 14/09 |
| 2 | `docs/FASE-2-JARVIS.md` | 12 etapas: córtex, emocional, estudo, mãos, conexões, voz, autônomo | fechada 15/09 |
| 3A | `docs/FASE-3.md` | 7 etapas: Realtime, autônomo real, conexões reais, casa, visão, memória semântica, autoevolução | construída 15/09; etapas 2 e 3 dependem do João |
| 3B | `docs/FASE-3-TEMPO-REAL.md` | 9 etapas: full-duplex, antecipador, barge-in, lote, voz rápida, telemetria, rotina, vontades | construída 15–21/09; validação ao vivo pendente |
| — | **não consta** | estratégia autônoma (ondas 1–4), três cérebros, frota, segundo dono, cockpit | construída 16–17/09 **sem documento de fase** |
| 4? | `cowork/PROPOSTA-CONTROLE-DO-COMPUTADOR.md` | gestos, visão espacial e voz como interfaces sobre o acesso ao computador | **proposta do João, não aprovada** |

> **`docs/ROADMAP.md` está obsoleto.** Ainda descreve fases 2–7 como agenda, voz local, WhatsApp, arquivista,
> telefone e computer use — tudo já entregue, em outra ordem, por outros documentos. Enquanto não for reescrito,
> esta tabela manda.

## Funcionalidades

Legenda de status: **feito** (código + teste no repo) · **código pronto** (falta ação do João) · **parcial** ·
**esqueleto** · **pendente** (não consta). Linhas F1–F42 vêm do registro do Claude Code até 15/09; as marcadas
com ✎ foram corrigidas em 28/09 porque contradiziam o próprio arquivo ou o código.

### Base (fases 0–2)
| # | Funcionalidade | Nível | Status |
|---|---|---|---|
| F1 | Conversa por texto (CLI/HUD) com contexto do vault | funcional | feito |
| F2 | Ferramentas de memória: lembrar, buscar, diário, tarefas, estado | funcional | feito |
| F3 | Maesters: dev, agenda, comms, arquivista, ops, jaime (`.claude/agents/`) | funcional | feito |
| F4 | Vigia: bloqueio + "confirmo" | funcional | feito |
| F5 | Palavra-passe falada/digitada, timeout, "tranca" | funcional | feito |
| F6 | Apresentação em máquina nova + registro de máquinas | funcional | feito |
| F7 | Reflexão automática a cada 6 turnos → Estado | funcional | ✎ feito no código; **sem gravação versionada desde 15/09** |
| F8 | HUD: anéis, monitor, raciocínio, produção, conversa | funcional | feito; evoluiu para cockpit (F51) |
| F9 | Espelho Notion: Estado, Diário, Tarefas, Conversas | funcional | feito (precisa `NOTION_TOKEN`) |
| F10 | MCPs GitHub/Notion autenticados no SDK | funcional | feito 14/09 |
| F11 | Voz local completa | funcional | ✎ feito — `jaime/voice/`, 19 módulos, 3.775 linhas |
| F12 | Agenda: scheduler próprio + Google Calendar | funcional | scheduler feito; Calendar depende do OAuth (F33) |
| F13 | WhatsApp via Evolution API | funcional | ✎ esqueleto; substituído por F36 (Evolution opcional) |
| F14 | Ligações via Twilio | funcional | esqueleto |
| F15 | Fechamento do dia/semana automático | ideal | feito (rotinas em `30-Tarefas/Rotinas.md`) |
| F16 | Busca semântica no vault | ideal | ✎ feito como F41 (FTS5, sem embeddings) |
| F17 | HUD: painel por maester | ideal | ✎ parcial — o cockpit mostra a tripulação dos três cérebros (F51); painel por maester não consta |
| F18 | Modo "sombra": observa a tela e sugere sem agir | ideal | ✎ parcial — observador oferece ajuda quando o João trava (F26) |
| F19 | Autoinstalação `jaime bootstrap` em máquina limpa | ideal | ✎ parcial — consta `jaime/frota/instalador.py`; `jaime bootstrap` não consta |
| F20 | Propor melhorias semanais em si mesmo (PR + "confirmo") | estratégica | ✎ feito como F42 |
| F21 | Camada de negócio: métricas do BUB/estamparia no HUD | estratégica | pendente |
| F22 | Delegação longa com checkpoints e relatório | estratégica | ✎ feito como F37 |
| F23 | Saúde do cérebro (`jaime cerebro check`) + índices por código | funcional | feito 15/09 |
| F24 | Identidade editável: nome no frontmatter, "me chama de X" + confirmo | funcional | feito 15/09 |
| F25 | Voz direta: Silero VAD, Deepgram, ativação por nome, streaming | funcional | feito 14/09 |
| F26 | Observador: contexto da tela em cada fala; oferta de ajuda | funcional | feito 14/09 |
| F27 | Córtex: roteador de modelos + placar de acertos/erros/custo | funcional | feito 15/09 |
| F28 | OpenAI como segundo provedor + juiz Fable 5.1 | funcional | feito 15/09 — uso mínimo; aguarda crédito |
| F29 | Cérebro emocional: perguntas nunca repetidas, datas, humor → prosódia | funcional | feito 15/09 |
| F30 | Agenda própria: scheduler, lembretes, relógio, clima, feriados — sem n8n | funcional | feito 15/09 |
| F31 | Cérebro de estudo: problemas → sandbox → conhecimento, skill, placar | funcional | feito 15/09 |
| F32 | Mãos: Playwright, criar projetos, organizar arquivos, skills pdf/docx/xlsx/pptx | funcional | feito 15/09 |
| F33 | Conexões Google (OAuth próprio) + Telegram só do dono | funcional | código pronto — OAuth barrado com 403 (Gmail do João fora de "Usuários de teste") |
| F34 | Voz com persona e emoção; `jaime voz testar` | funcional | feito — voz onyx, ritmo 1.2 (escolha do João, 17/09) |
| F35 | Mídia: imagens, 3D (Blender), cortes e legendas (ffmpeg) | funcional | feito — Blender a instalar |
| F36 | Meta: WhatsApp Cloud + Instagram Messaging, webhook assinado | funcional | código pronto — app no Meta for Developers é do João |
| F37 | Modo autônomo: objetivo → etapas → checkpoints → relatório | estratégica | feito 15/09 |

### Fase 3A — `docs/FASE-3.md`
| # | Funcionalidade | Status |
|---|---|---|
| F38 | Conversa em tempo real (GPT-Realtime-2) com as ferramentas do Jaime | feito 15/09 (`JAIME_VOZ_MODO=conversa`) |
| F39 | Casa (Home Assistant/HomeKit) e câmera como olho | código pronto — `HA_URL`/`HA_TOKEN` do João |
| F40 | Visão contínua (apps/jogos por visão) com kill switch "para" | feito 15/09 |
| F41 | Memória semântica (FTS5) com recall proativo | feito 15/09 |
| F42 | Autoevolução: proposta semanal → worktree + testes + PR; merge com confirmo | feito 15/09 |

### Fase 3B — `docs/FASE-3-TEMPO-REAL.md`
| # | Funcionalidade | Onde | Status |
|---|---|---|---|
| F43 | STT streaming + fim de turno semântico pelo áudio (Smart Turn) | `voice/stt_stream.py`, `fim_de_turno.py` | feito — Smart Turn é modelo em inglês, ~68% em pt-BR |
| F44 | Antecipador + resposta especulativa | `voice/antecipador.py` | feito — benchmark 7/10 em 320 ms (16/09); rascunhos para fala real (M-36, 21/09) |
| F45 | Barge-in + fila de demandas | `voice/duplex.py`, `eco.py`, `fila.py` | feito — M-24 a M-35; **validação ao vivo com fone pendente** |
| F46 | Confirmação em lote + confiança progressiva | `vigia/confianca.py` | feito — **validação ao vivo pendente** |
| F47 | Voz rápida: cache de frases, 1.2×, persona enxuta | `voice/cache_frases.py`, `latencia.py` | feito — frases curtas em ~0 ms, fala 15,1 s → 7,0 s (17/09) |
| F48 | Jaime interrompe o João (`JAIME_INTERROMPER`) | `voice/duplex.py` | feito atrás de flag — **desligado até calibrar** |
| F49 | Telemetria de uso + prioridades de estudo | `jaime/telemetria/` | feito — local; `Uso.md` fora do espelho Notion |
| F50 | Rotina + orçamento diário | `agenda/`, `cortex/orcamento.py` | feito — rotinas presas no sono corrigidas (M-15, M-33, M-39) |
| F51 | Vontades + Vitrine + Mente contínua | `jaime/vontade/`, `jaime/mente/` | feito — criação de dia porque o Mac dorme à noite (M-38) |

### Estratégia autônoma e expansão — 16–17/09, sem documento de fase
| # | Funcionalidade | Onde | Status |
|---|---|---|---|
| F52 | Três cérebros: Central (Claude), Esquerdo (Codex), Direito (Gemini) como terminais no Maestri, com despertador e roteamento que aprende | `jaime/cerebros/`, `jaime/equipe/`, `docs/MAESTRI.md` | feito 17/09 |
| F53 | Acervo de 709 agentes (catálogos MIT) repartido entre os lados | `jaime/acervo/` | feito — contexto do acervo 42 mil → 2 mil tokens/turno |
| F54 | Harness: persegue um objetivo, verifica, corrige, replaneja, desiste | `cortex/harness.py`, `docs/HARNESS-E-PROTECAO.md` | feito 17/09 |
| F55 | Carteira de iniciativas (imaginada → medida) + crítico da spec | `jaime/agente/carteira.py`, `spec.py` | feito 17/09 |
| F56 | Memória viva: grafo temporal de relações e emoção | `jaime/relacoes/` | feito 17/09 |
| F57 | Espelho do João (traços) | `jaime/espelho/` | feito 17/09 |
| F58 | Cockpit: vista única com céu, nós, doze mundos, tripulação | `hud/universo.py`, `grafo.py`, `docs/HUD-VIVO.md` | feito 17/09 |
| F59 | Frota: alcança vários computadores da rede e sabe de quem é cada um | `jaime/frota/`, `01-Estado/Frota.md` | feito 17/09 |
| F60 | Segundo dono (Gabriel Mello): reconhece, confere autorização, tranca a vida do João por ferramenta | `jaime/donos.py`, `docs/FROTA-GABRIEL.md` | feito 17/09 |
| F61 | Ponte: trabalha nos arquivos da máquina do outro dono, de dentro para fora, uma pasta só | `jaime/ponte/` | feito 17/09 |
| F62 | Reconhecimento de quem fala (João/Gabriel/desconhecido); confirmo só na voz do dono | `voice/falantes.py`, `falantes_worker.py` | feito — em processo separado desde o segfault torch × onnxruntime |
| F63 | Leitura de web com Scrapling | `maos/raspar.py` | feito 17/09 |
| F64 | Multilíngue: ouve outras línguas | `voice/idiomas.py` | feito 17/09 |
| F65 | Enxugamento de contexto: 83 mil → ~12,8 mil tokens/turno | onda 1b | feito — um sexto do custo por turno |
| F66 | Finanças (livro-caixa) | `jaime/financas/` | consta no código; sem registro de decisão |
| F67 | Música (Spotify) | `conexoes/spotify.py` | consta no código; sem registro de decisão |
| F68 | Operação resiliente: LaunchAgent, watchdog do microfone, reinício no CoreAudio travado | `jaime/ops/`, M-40, M-45–M-47 | feito 21/09 — **healthcheck externo não instalado** (M-46) |

## Necessidades — o que depende do João

| O quê | Para destravar | Onde está registrado |
|---|---|---|
| Adicionar o próprio Gmail em "Usuários de teste" no Google Cloud | F33, F12 (Calendar), briefing com e-mail real | `Estado.md` |
| Token do bot do Telegram | F33 | `docs/CONEXOES.md` |
| App no Meta for Developers | F36 | `docs/CONEXOES.md` |
| `HA_URL` e `HA_TOKEN` do Home Assistant | F39 | `docs/CONEXOES.md` |
| Crédito na OpenAI; cota da ElevenLabs | F28, voz alternativa | `PROJETO` 15/09 |
| Instalar o Blender | F35 (3D) | `PROJETO` 15/09 |
| macOS: Gravação de Tela e Acessibilidade | ver a tela, clicar e digitar | `Estado.md`, `README.md` §10 |
| **Trocar a palavra-passe** (`python -m jaime senha`) | segurança — ver Riscos | `docs/MENTE.md` |
| Validar ao vivo, com fone: barge-in, lote do Vigia, confiança progressiva, interjeição | fechar a fase 3B | `docs/MENTE.md`, fila #9 |
| Instalar o healthcheck externo | reinício automático se o serviço travar | `docs/MENTE.md`, M-46 |
| Definir o escopo de "produção de vídeos" (Oldsen, @piloto.leal ou estamparia) | foco de produto | `Estado.md` |
| Decidir a proposta de controle do computador | fase 4 | `cowork/PROPOSTA-CONTROLE-DO-COMPUTADOR.md` |

## Riscos abertos

1. **Palavra-passe padrão em texto puro em 10 arquivos versionados** — `.env.example`, três docs (`ROADMAP`,
   `SEGURANCA`, `HANDOFF-CLAUDE-CODE`), `config.py`, `vigia/acesso.py`, dois testes e duas transcrições em
   `vault/60-Conversas/` (14 e 15/09). O caderno MENTE registra que a senha ouvida no log **parece ser essa
   mesma**. Se for, quem lê o repositório destranca o Jaime.
   O redator de segredos (M-22) protege o que vem daqui para frente; não limpa o que já foi escrito.
2. **Espelho Notion anterior ao M-22.** O Diário do dia sobe para o Notion e já registrou a senha antes do redator
   existir. Não verifiquei o Notion; conferir as páginas do Diário até 16/09.
3. **Sete dias sem atividade registrada** (desde 21/09) e `Estado.md` sem gravação versionada desde 15/09.
   Não consta se o serviço está no ar nem se a reflexão está rodando.
4. **Documentação de fases fragmentada.** Duas "fase 3", o bloco de 16–17/09 sem documento, `ROADMAP.md` obsoleto.
   O `README.md` aponta para `01-Estado/Cerebros.md`, `Iniciativas.md` e `Confianca.md`, que **não constam** no
   repositório (podem ser gerados em tempo de execução — não verifiquei).
5. **Só macOS.** `osascript`, `screencapture`, `afplay`, permissões TCC. Pesa na proposta de controle do computador,
   que pede Windows e Linux.
6. **Vigia no mínimo desde 16/09, sem registro em Decisões.** A pedido explícito e reafirmado do João, `sudo`,
   `curl | sh`, `chmod` e `reboot` ficaram livres; pedem "sim" só apagar em massa, formatar disco, push em `main`
   ou forçado e zerar banco. A decisão está só num comentário de `jaime/vigia/hooks.py` — e contradiz os níveis da
   proposta de 28/09. Ver `cowork/PROPOSTA-CONTROLE-DO-COMPUTADOR.md`.
7. **`torch` pesa 2,5 GB** do ambiente para pouco uso.

## Custo
Dia de uso intenso medido em 17/09: **US$ 9,30** (US$ 6,24 de demandas, US$ 3,06 de estudo próprio). O que mais
move a conta: modelo do Central (Sonnet 5 é o padrão), tamanho do contexto por turno, voz. Orçamento diário em
`01-Estado/Orcamento.md`. Fonte: `README.md` §12.

## Como trabalhar neste projeto
- Repositório privado no GitHub; branch por feature; `maester-dev` aplica o checklist de produção.
- Sessões no Claude Code na pasta do repo: `docs/HANDOFF-CLAUDE-CODE.md` e `docs/RETOMAR.md`.
- O terminal **Mente** observa o Jaime ao vivo e registra correções `M-NN` em `docs/MENTE.md`; a **Vigília** mede.
- Cada marco fechado → linha datada em `vault/20-Projetos/Jaime.md` → Decisões.
