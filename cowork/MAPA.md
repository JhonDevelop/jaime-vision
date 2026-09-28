# Mapa do projeto Jaime

> Onde fica cada coisa no repositório, para o Cowork navegar sem abrir tudo. Estado de `main` em `0948e37`
> (28/09/2026). Status e pendências ficam em `cowork/PROJETO-JAIME.md`; aqui é só o endereço.

## Comece por aqui
| Para saber… | Leia |
|---|---|
| o que o Jaime é, como funciona, quanto pesa e quanto custa | `README.md` (institucional, 17 seções) |
| o que ele diz sobre si mesmo | `vault/01-Estado/Estado.md` — **parado em 15/09 no repo** |
| decisões com data | `vault/20-Projetos/Jaime.md` → Decisões |
| o que quebrou ao vivo e como foi corrigido | `docs/MENTE.md` (correções M-01 a M-47) |
| como retomar uma sessão do Claude Code | `docs/RETOMAR.md`, `docs/HANDOFF-CLAUDE-CODE.md` |

## Documentos (`docs/`)

**Fases e planos**
| Arquivo | Conteúdo |
|---|---|
| `ROADMAP.md` | fases 0–7 originais — **obsoleto**, ver a tabela de fases no PROJETO |
| `FASE-2-JARVIS.md` | fase 2: do assistente ao Jarvis (12 etapas, fechada 15/09) |
| `FASE-3.md` | fase 3A: Realtime, autônomo, conexões, casa, visão, memória, autoevolução |
| `FASE-3-TEMPO-REAL.md` | fase 3B: full-duplex, antecipador, barge-in, vontades |
| `PR-fase2-etapa*.md`, `PR-fase3-*.md` | um resumo de PR por etapa entregue |

**Arquitetura e comportamento**
| Arquivo | Conteúdo |
|---|---|
| `ARQUITETURA.md` | como as peças conversam |
| `JARVIS.md` | estudo de comportamento do J.A.R.V.I.S. e o que o Jaime copia (e não copia) |
| `HARNESS-E-PROTECAO.md` | governança, blindagem de runtime, poupança de tokens, divisão de tarefas |
| `MAESTRI.md` | a árvore de terminais dos três cérebros no Maestri |
| `HUD-VIVO.md` | mapa estado → animação do cockpit |
| `VOZ.md`, `VOZ-DESIGN.md` | pipeline de voz; como escolher uma voz original |

**Segurança, acesso e operação**
| Arquivo | Conteúdo |
|---|---|
| `SEGURANCA.md` | o que o Vigia bloqueia e por quê |
| `CONEXOES.md` | como o Jaime recebe cada acesso (Google, Telegram, Meta, Home Assistant) |
| `FROTA-GABRIEL.md` | o Jaime na máquina do Gabriel sem disputar o som |
| `REMOTO.md` | acesso de fora de casa por Tailscale |
| `SAUDE-PASSOS.md` | saúde, passos e sono |

**Prompts para outros agentes**
| Arquivo | Para quem |
|---|---|
| `PROMPT-CLAUDE-CODE.md` | modelo de ordem de serviço para o Claude Code |
| `PROMPT-CODEX.md` | o Codex (hemisfério esquerdo) |
| `PROMPT-GABRIEL.md` | o Gabriel colar no Claude Code dele |

## Código (`jaime/`)

| Módulo | Linhas | O que faz |
|---|---|---|
| `orchestrator/` | 1.021 | o Jaime: cliente persistente do Agent SDK, maesters, prompt |
| `voice/` | 3.775 | ouvido e fala: STT em fluxo, fim de turno, antecipador, barge-in, eco, fila, falantes, persona, TTS |
| `brain/` | 1.055 | vault, estado, índice FTS5, saúde, espelho Notion, ouvido passivo |
| `maos/` | 1.115 | browser, computer use, visão contínua, arquivos, projetos, imagens, Blender, conteúdo, raspagem |
| `frota/` | 892 | alcançar e instalar em outros computadores da rede |
| `cortex/` | 837 | roteador de modelos, placar, juiz, orçamento, harness |
| `vontade/` | 791 | impulsos, criações, laço de escolha |
| `agenda/` | 776 | scheduler, rotinas, lembretes, relógio, clima, feriados |
| `emocao/` | 680 | perfil, perguntas feitas, momento, humor, prosódia, vínculo |
| `hud/` | 674 | cockpit: eventos, monitor, sistemas, grafo, universo |
| `cerebros/` | 663 | três cérebros: hemisférios, tripulação, despertador |
| `conexoes/` | 630 | Google, Meta, Telegram, Spotify, registro |
| `ops/` | 624 | observador, notificações, permissões, serviço |
| `relacoes/` | 607 | grafo temporal de relações e curiosidade |
| `telemetria/` | 503 | uso local e prioridades de estudo |
| `equipe/` | 435 | filhos e integração com o Maestri |
| `agente/` | 420 | carteira de iniciativas e crítico da spec |
| `vigia/` | 396 | hooks, acesso por palavra-passe, confiança progressiva |
| `estudo/` | 364 | problemas em aberto e ciclo de estudo |
| `ponte/` | 303 | trabalhar nos arquivos da máquina do outro dono |
| `mente/` | 240 | pensamento contínuo |
| `acervo/` | 220 | busca nos 709 agentes |
| `espelho/` | 186 | traços do João |
| `casa/` | 168 | Home Assistant e câmera |
| `financas/` | 133 | livro-caixa |
| `channels/` | 53 | WhatsApp (Evolution) e Twilio — esqueletos |

Arquivos soltos: `autonomo.py` (objetivo longo), `evolucao.py` (autoevolução), `donos.py` (segundo dono),
`identidade.py` (nome editável), `server.py` (API e webhooks), `config.py`.

## Memória (`vault/`)
| Pasta | Conteúdo | Quem escreve |
|---|---|---|
| `00-Jaime/` | identidade, regras, comandos, origem | **só o João** |
| `01-Estado/` | Estado, Placar, Uso, Vontades, Orçamento, Frota, Máquinas, Vínculo, Agenda | o Jaime |
| `10-Eu/` | perfil, datas, jeito, perguntas feitas | o Jaime, com o João |
| `20-Projetos/` | uma nota por projeto | o Jaime |
| `30-Tarefas/` | Inbox, Rotinas, Lembretes | o Jaime |
| `40-Diario/` | um arquivo por dia — **sobe para o Notion** | o Jaime |
| `50-Conhecimento/` | referências e o que ele aprendeu | o Jaime |
| `60-Conversas/` | transcrições por dia | o Jaime |
| `90-Estudo/` | problemas em aberto e prioridades | o Jaime |

## Agentes e skills (`.claude/`)
- `agents/`: seis maesters — `jaime`, `dev`, `agenda`, `comms`, `arquivista`, `ops`.
- `skills/`: oficiais (`pdf`, `docx`, `xlsx`, `pptx`) e próprias (`ceo-founder`, `cmo-marketing`, `pesquisa-web`,
  `processos-empresariais`, `prestacao-de-servicos`, `como-rodar-whisper-em-gpu-num-mac-intel`).
