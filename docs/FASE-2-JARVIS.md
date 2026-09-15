# Fase 2 — do assistente ao Jarvis

> Passo a passo + prompts para o Claude Code. Cada etapa tem critério de pronto; cada prompt é colado
> inteiro no `claude` aberto na pasta do repositório. Ordem importa: cada etapa usa a anterior.

## 0. O que muda em relação à v0.3
- **n8n sai.** Automações viram código nosso (`jaime/agenda/scheduler.py`) e conectores diretos (`jaime/conexoes/`).
- **Dois provedores de modelo.** Anthropic (Fable 5.1 / Opus 5 / Sonnet / Haiku) e OpenAI (GPT-6 Astra, GPT-5.6 Terra/Luna, GPT-Realtime-2, GPT-Realtime-Whisper, gpt-4o-mini-tts, GPT-Image-2.5) — confira os nomes atuais em developers.openai.com/api/docs/models antes de fixar no código.
- **Quatro cérebros com papéis distintos** (ver §2): Obsidian (memória), Córtex (decide quem pensa), Emocional (quem é o João e como falar com ele), Estudo (o que ainda não sei resolver).
- **Identidade editável.** O nome mora em um lugar só; ele pergunta se é Jaime mesmo e se renomeia com "confirmo".

## 1. Estudo — o que o Jarvis faz, e com o que replicamos

| Traço do Jarvis | Como aparece | O que replica |
|---|---|---|
| Sabe tudo sobre o dono e nunca pergunta duas vezes | contexto pessoal, datas, preferências, tom | Cérebro emocional: `10-Eu/` + registro de perguntas já feitas |
| Antecipa: fala do que importa antes de ser perguntado | briefing, alertas, "hoje é o aniversário de…" | Scheduler próprio + `10-Eu/Datas.md` + Mente contínua |
| Monitora sistemas o tempo todo | telemetria da máquina/casa | HUD (já existe) + `jaime/agenda/relogio.py`, `clima.py` |
| Executa no mundo real | oficina, casa, arquivos, chamadas | `jaime/maos/` (browser, computer use, arquivos, imagens, 3D) + conexões |
| Delega e coordena outros sistemas | "dispatch" para subsistemas | Córtex: roteador multi-modelo com placar de acertos/erros |
| Aprende com o que deu errado | melhora entre missões | Cérebro de estudo: loop de problemas em aberto → conhecimento |
| Fala como alguém, não como um menu | ironia seca, frases curtas, coerência emocional com a cena | Persona de voz (`jaime/voz/persona.py`) + prosódia dirigida por estado |
| Tem uma identidade estável | nome, lealdade, limites | `00-Jaime/` + Vigia + identidade única e renomeável |

**Sobre a voz.** O Jarvis do filme é a voz de um ator real; clonar a voz de uma pessoa sem consentimento não é um caminho
que eu ajude a construir, e as plataformas bloqueiam isso. O que fazemos: **desenhar uma voz original com as mesmas
qualidades** — timbre britânico calmo, dicção precisa, leve textura sintética — com o *Voice Design* do ElevenLabs
(voz a partir de descrição em texto) ou com uma voz da biblioteca, e trabalhar a **entonação** por instruções de
prosódia (gpt-4o-mini-tts aceita `instructions`; Eleven v3 aceita tags de emoção no texto). O que dá o "efeito Jarvis"
é 30% timbre e 70% jeito de falar — e o jeito de falar é código nosso.

## 2. Arquitetura da fase 2

```
 voz/HUD/WhatsApp/Instagram ─► JAIME (orquestrador) ─► CÓRTEX (decide quem pensa e checa a resposta)
                                   │                        ├─ Anthropic: Fable 5.1 (juiz/decisão), Opus 5 (código longo), Sonnet, Haiku
                                   │                        └─ OpenAI: GPT-6 Astra (pesquisa/redação), GPT-5.6 Luna (rotina), Image-2.5, Realtime-2
                                   ├─ EMOCIONAL: perfil, datas, jeito do João, humor do Jaime → afeta texto e prosódia
                                   ├─ ESTUDO: problemas em aberto → pesquisa/experimento → conhecimento
                                   ├─ OBSIDIAN: vault (verdade) + verificação de saúde
                                   ├─ MÃOS: browser (Playwright), computer use, arquivos/projetos, imagens, 3D (Blender), conteúdo
                                   ├─ CONEXÕES: Google (Gmail/Calendar), Meta (WhatsApp/Instagram), GitHub, Notion, Discord/Telegram
                                   └─ AGENDA: scheduler próprio, relógio, clima, feriados, lembretes
```

### 2.1 Córtex — `jaime/cortex/`
- `roteador.py`: classifica a tarefa (código · pesquisa · redação · decisão · imagem · voz · rotina) e escolhe modelo pela
  política: maior taxa de acerto no placar para aquele tipo, com 10% de exploração; fallback automático em erro.
- `placar.py`: `vault/01-Estado/Placar.md` — por (modelo, tipo): acertos, erros, latência média, custo. Erro = ferramenta
  falhou, teste quebrou, ou o João corrigiu ("errado", "não era isso", "refaz"). Acerto = tarefa fechada sem correção.
- `juiz.py`: para tipo *decisão* ou quando o João pede "pensa bem", pede 2 respostas (uma de cada provedor) e o Fable 5.1
  escolhe/mescla, registrando por quê. Custa o dobro — só quando vale.
- `provedores/anthropic.py` e `provedores/openai.py`: mesma interface `responder(prompt, ferramentas, contexto)`.
  O Agent SDK continua sendo as mãos (ferramentas, MCPs, hooks); o OpenAI entra como cérebro alternativo via Responses API
  e como especialista (imagens, voz em tempo real, transcrição streaming).

### 2.2 Cérebro emocional — `jaime/emocao/`
- `perfil.py`: lê/escreve `10-Eu/Perfil.md`, `10-Eu/Datas.md` (aniversário, datas importantes, feriados), `10-Eu/Jeito.md`
  (como o João fala, o que odeia, horários, quando quer respostas curtas).
- `perguntas.py`: `10-Eu/Perguntas-Feitas.md` — toda pergunta que o Jaime fez ao João e a resposta. **Antes de perguntar
  qualquer coisa, consulta.** Se já tem resposta, usa; se a resposta pode ter mudado (mais de 90 dias), confirma em meia frase.
- `momento.py`: "que dia é hoje para o João" — aniversário, feriado, prazo perto, semana pesada. Alimenta o briefing e a prosódia.
- `humor.py`: estado afetivo do **Jaime** (energia, calor, gravidade, confiança), atualizado por: resultado das tarefas,
  tom do João, hora do dia, momento. Regras de coerência: nunca leve quando o João está em problema; nunca grave em
  conquista; sem dramatizar erro próprio. É expressão, não manipulação — não simula angústia, não cria dependência.
- `prosodia.py`: traduz humor + canal em instruções de fala ("calmo, seco, ritmo médio, meio tom mais baixo") e em tags
  quando o TTS aceitar.

### 2.3 Cérebro de estudo — `jaime/estudo/`
- `problemas.py`: `90-Estudo/Problemas.md` — cada tarefa que falhou, pergunta sem resposta, erro repetido vira um problema
  com ID, contexto, tentativas.
- `loop.py`: ciclo dentro da Mente contínua: escolhe 1 problema em aberto → pesquisa (web, docs, código) → experimenta em
  sandbox (`/tmp/jaime-lab`) → se resolveu: escreve `50-Conhecimento/<tema>.md`, registra aprendizado, atualiza o placar,
  gera skill quando fizer sentido (`skill-creator`); se não: registra a tentativa e o que falta. Nunca toca em produção.
- Promoção: conhecimento resolvido entra no `contexto_inicial()` do Obsidian pelo índice `50-Conhecimento/INDEX.md`.

### 2.4 Obsidian — integração completa e verificação
- `jaime/brain/saude.py`: `python -m jaime cerebro check` — pastas obrigatórias, frontmatter, links quebrados, notas órfãs,
  tamanho, último diário, Estado coerente com roadmap. Roda no boot; se falhar, o Jaime avisa antes de tudo.
- Índice: `50-Conhecimento/INDEX.md` e `20-Projetos/INDEX.md` gerados por código a cada fechamento do dia.
- Busca: sqlite FTS5 (`vault/.index.db`, gitignored) substitui o grep quando passar de 500 notas.

### 2.5 Mãos — `jaime/maos/`
- `browser.py`: Playwright (perfil persistente do Chrome do Jaime, logins que o João fizer uma vez ficam salvos).
- `computador.py`: computer use da API do Claude (screenshot → ação) para apps sem API; sempre atrás de "confirmo".
- `projetos.py`: cria projeto (pasta padrão, git init, README, `.env.example`, CLAUDE.md) e registra em `20-Projetos/`.
- `arquivos.py`: docs/planilhas/PDF via skills oficiais; organização de pastas com regras do João.
- `imagens.py`: GPT-Image-2.5 (gerar/editar), salva em `~/Jaime/imagens/` e registra no diário.
- `blender.py`: Blender headless (`blender -b -P script.py`) para modelos 3D por script; `jogos.py`: só automação de
  janela (pyautogui) — jogar de verdade é fase 3.
- `conteudo.py`: roteiro → thumbnail → corte (ffmpeg) → legenda, para o @piloto.leal.

### 2.6 Conexões — `jaime/conexoes/`
- `registro.py`: `01-Estado/Conexoes.md` — serviço, escopo, como foi autorizado, como revogar, último uso.
- `google.py`: OAuth do seu próprio projeto no Google Cloud (Gmail + Calendar + Drive); token local.
- `meta.py`: WhatsApp Cloud API e **Instagram Messaging API** (conta profissional; DMs e comentários). Sem API oficial
  não há automação segura de Instagram — bibliotecas não oficiais derrubam a conta.
- `discord.py`/`telegram.py`: bots (mais simples e sem risco; ótimos para falar com o Jaime do celular).
- Tudo que envia continua atrás do Vigia.

### 2.7 Voz — `jaime/voz/`
- `persona.py`: regras de fala. Nada de "Olá, sou o Jaime, seu assistente". Frases curtas, uma ironia seca por
  conversa no máximo, chama de "João" (ou "senhor" só quando ele pedir), nunca repete a pergunta, fecha com o próximo
  passo. Texto de voz nunca tem markdown, URL ou lista.
- Dois modos: **pipeline** (wake → GPT-Realtime-Whisper ou Deepgram → Jaime → gpt-4o-mini-tts com `instructions` da
  prosódia ou ElevenLabs v3 com tags) e **conversa** (GPT-Realtime-2 fala-para-fala com ferramentas do Jaime, para diálogo
  rápido; o Córtex decide quando passar a bola para o Agent SDK).
- `voz_design.md`: descrição da voz para o Voice Design (ElevenLabs) e testes A/B de 5 vozes com o João escolhendo.

### 2.8 Agenda e mundo — `jaime/agenda/`
- `scheduler.py`: cron em código (APScheduler) lendo `vault/30-Tarefas/Rotinas.md` — "todo dia útil 07:00 briefing",
  "sexta 18:00 fecha a semana". Substitui o n8n.
- `relogio.py`, `clima.py` (Open-Meteo, sem chave), `feriados.py` (`holidays` BR), `noticias.py` (RSS escolhido).
- `lembretes.py`: "me lembra em 20 min / às 15h / quando eu chegar".

### 2.9 Identidade
- `jaime/identidade.py`: nome, apelidos, wake word, como se apresenta — lido de `vault/00-Jaime/Identidade.md` (frontmatter
  `nome:`). Todo texto usa `{nome}`; nada hardcoded.
- Primeiro boot e após renomear: "Meu nome é Jaime — confirma?". "Me chama de X" (voz ou texto) → proposta
  `renomear X` → com "confirmo": atualiza Identidade.md, título do HUD, wake word (aviso de treinar), CLAUDE.md, commit em
  branch `chore/renomear-x`. O código continua no repositório `jaime`; muda o que o mundo vê.

## 3. Passo a passo (ordem de execução)

| # | Etapa | Critério de pronto |
|---|---|---|
| 1 | Limpeza + identidade | n8n removido; `python -m jaime cerebro check` verde; boot pergunta "sou o Jaime?"; renomear funciona com confirmo |
| 2 | Córtex + placar | `jaime cortex explicar "<tarefa>"` mostra tipo, modelo escolhido e porquê; placar muda após uma correção |
| 3 | OpenAI como provedor | mesma pergunta respondida pelos dois provedores; juiz escolhe e registra |
| 4 | Cérebro emocional | não repete pergunta já respondida; no aniversário o briefing começa por isso; humor afeta o texto |
| 5 | Scheduler + mundo | briefing 07:00 sem n8n; "que horas/clima" respondidos localmente; lembrete de 20 min dispara |
| 6 | Cérebro de estudo | um problema real fechado com conhecimento gerado e placar atualizado |
| 7 | Mãos: browser + projetos + arquivos | "cria o projeto X" gera pasta+git+nota; Playwright abre e extrai dados de um site |
| 8 | Conexões Google + Telegram | lê e-mails de hoje; cria evento; responde pelo Telegram |
| 9 | Voz persona + emoção | 5 vozes testadas; prosódia muda com humor; sem frases prontas |
| 10 | Imagens, 3D, conteúdo, computer use | gera imagem, gera .blend por script, corta um vídeo, clica em um app com confirmo |
| 11 | Meta (WhatsApp Cloud + Instagram) | DM do Instagram profissional respondida com confirmo |
| 12 | Modo autônomo | objetivo de 2 h executado com checkpoints e relatório no diário |

## 4. Prompts para o Claude Code

Todos começam igual. Cabeçalho (cole antes de cada prompt):

> Você é o **maester-jaime** com apoio do **maester-dev** neste repositório. Leia `CLAUDE.md`, `docs/FASE-2-JARVIS.md`
> e `vault/01-Estado/Estado.md` antes de qualquer coisa. Trabalhe em branch, com testes em `tests/`, e pare para "confirmo"
> antes de push, instalação de sistema ou qualquer envio. Ao fechar, atualize `cowork/PROJETO-JAIME.md`,
> `vault/20-Projetos/Jaime.md` (decisão datada) e `vault/01-Estado/Estado.md`. Responda curto; o código fala.

### Prompt 1 — Limpeza, saúde do Obsidian, identidade
Etapa 1 da fase 2. (a) Remova a pasta `n8n/` e toda referência a n8n em docs, catálogo e `.mcp.json`; registre a decisão. (b) Crie `jaime/brain/saude.py` e o comando `python -m jaime cerebro check` conforme §2.4; rode no `Jaime.start()` e faça o Jaime avisar no boot se algo estiver quebrado. Gere `50-Conhecimento/INDEX.md` e `20-Projetos/INDEX.md` por código. (c) Crie `jaime/identidade.py` lendo `nome:` do frontmatter de `vault/00-Jaime/Identidade.md` (adicione o frontmatter); substitua todo "Jaime" hardcoded em prompts, HUD e vault por `{nome}`. (d) Implemente a ferramenta `renomear(novo_nome)` que cria proposta `renomear <nome>`; com "confirmo" executa o §2.9 e faz commit em branch. (e) No boot, após a apresentação, o Jaime pergunta "Meu nome é {nome} — confirma?" e aceita "sim"/"me chama de X" por texto ou voz. Testes para (b), (c), (d). Critério: tabela §3 linha 1.

### Prompt 2 — Córtex e placar
Etapa 2. Crie `jaime/cortex/` conforme §2.1 usando só Anthropic por enquanto (Fable 5.1 para decisão e juiz, Opus 5 para código longo, Sonnet para o resto, Haiku para rotina; leia os nomes de modelo do `.env`). `roteador.classificar(texto, contexto)` devolve tipo e confiança; `roteador.escolher(tipo)` aplica a política do placar com 10% de exploração. `placar.registrar(modelo, tipo, resultado, latencia, custo)` escreve `vault/01-Estado/Placar.md` em tabela markdown e mantém um JSON gitignored para cálculo. Detecte correção do João por regex ("errado", "não era isso", "refaz", "de novo") no turno seguinte e atribua o erro ao modelo do turno anterior. Comando `python -m jaime cortex explicar "<tarefa>"`. Integre no `Jaime.ask_stream`: o modelo do `ClaudeAgentOptions` passa a vir do roteador por tarefa (recrie o client quando o modelo mudar, ou use uma opção por chamada se o SDK permitir — descubra e documente). Testes com placar sintético.

### Prompt 3 — OpenAI como segundo provedor + juiz
Etapa 3. Adicione `openai` ao `pyproject`, `OPENAI_API_KEY` ao `.env.example`. Crie `jaime/cortex/provedores/openai.py` com a interface `responder(prompt, contexto, ferramentas=None)` via Responses API (modelo padrão `JAIME_OPENAI_MODEL`, sugestão GPT-5.6 Terra; leia a lista atual e documente). Crie `juiz.py`: para tipo *decisão* ou quando o texto contiver "pensa bem"/"compara", peça a resposta aos dois provedores em paralelo e faça o Fable 5.1 escolher ou mesclar, devolvendo a escolha e 1 frase de justificativa que vai para o diário e para o painel Raciocínio do HUD. O roteador passa a considerar o provedor OpenAI para tipos *pesquisa* e *redação*. Regra: ações no mundo (ferramentas do Agent SDK) continuam só pela Anthropic; o OpenAI produz texto, decisões, imagens e voz. Atualize `docs/ARQUITETURA.md`. Testes com provedores falsos.

### Prompt 4 — Cérebro emocional
Etapa 4. Crie `jaime/emocao/` conforme §2.2 e as notas `10-Eu/Datas.md`, `10-Eu/Jeito.md`, `10-Eu/Perguntas-Feitas.md` (crie vazias com cabeçalho; o Jaime preenche). Ferramentas MCP `emocao`: `perguntar_ao_joao(pergunta)` — só pergunta se não houver resposta registrada; `registrar_resposta`, `datas_importantes`, `momento_de_hoje`, `humor_atual`. Regras no `CLAUDE.md`: toda pergunta ao João passa por `perguntar_ao_joao`. `momento.py` entra no briefing e no `contexto_inicial()`; se for aniversário do João, a primeira frase do dia é sobre isso. `humor.py` com os quatro eixos e as regras de coerência do §2.2; `prosodia.py` devolve um dicionário `{"instructions": "...", "tags": [...]}`. Mostre o humor no HUD (barra discreta no header). Testes: pergunta repetida não é feita; aniversário detectado; humor não fica leve com erro grave.

### Prompt 5 — Scheduler próprio, relógio, clima, lembretes
Etapa 5. Crie `jaime/agenda/` conforme §2.8 com APScheduler dentro do processo do servidor. `vault/30-Tarefas/Rotinas.md` em linhas `- <cron> · <ordem para o Jaime>`; o scheduler lê no boot e recarrega quando o arquivo muda. Implemente `relogio.py` (hora, data, dia da semana, fuso), `clima.py` (Open-Meteo para Franca/SP ou coordenadas do `.env`), `feriados.py` (BR + SP), `lembretes.py` ("me lembra em X" / "às HH:MM" / data). Ferramentas MCP `mundo`: `agora`, `clima`, `feriado_hoje`, `criar_lembrete`, `rotinas`. Perguntas de hora/clima não vão ao modelo: responda direto no `_porta`. Rotina padrão: `0 7 * * 1-5 · briefing` e `0 18 * * 5 · fecha a semana`. Testes com relógio falso.

### Prompt 6 — Cérebro de estudo
Etapa 6. Crie `jaime/estudo/` conforme §2.3. Gatilhos automáticos para abrir problema: ferramenta falhou 2× com o mesmo erro; teste quebrou e não foi corrigido; o João disse "não sei"/"pesquisa isso"; pergunta ficou sem resposta. O `loop.py` roda como ciclo da Mente contínua (máx. 1 problema por ciclo, 15 min, sandbox em `/tmp/jaime-lab`, sem tocar em `~/projetos` nem no repo). Resolvido → `50-Conhecimento/<slug>.md` com "como reproduzir, o que resolveu, onde se aplica", entrada no INDEX, aprendizado no Estado, placar. Ferramentas MCP `estudo`: `abrir_problema`, `problemas_abertos`, `resolver_problema`. HUD: contador "estudando: N em aberto". Teste com um problema sintético resolvível offline.

### Prompt 7 — Mãos: browser, projetos, arquivos
Etapa 7. Crie `jaime/maos/browser.py` (Playwright com perfil persistente em `~/Jaime/browser-profile`, ferramentas `abrir`, `ler_pagina`, `clicar`, `preencher`, `extrair`, `screenshot`; o Vigia exige confirmo para qualquer submit/compra/envio), `projetos.py` (`criar_projeto(nome, tipo)` → pasta em `JAIME_WORKSPACE`, git init, README, `.env.example`, `CLAUDE.md`, nota em `20-Projetos/` com o template) e `arquivos.py` (regras de organização em `10-Eu/Jeito.md`; mover/renomear só com confirmo). Instale as skills oficiais pdf/docx/xlsx/pptx via `jaime skills instalar`. Testes com site local de exemplo.

### Prompt 8 — Conexões: Google e Telegram
Etapa 8. Crie `jaime/conexoes/registro.py` e `01-Estado/Conexoes.md`. `google.py`: fluxo OAuth com projeto próprio (documente passo a passo no `docs/CONEXOES.md`: criar projeto no Google Cloud, ativar Gmail/Calendar/Drive, tela de consentimento, credencial Desktop, `python -m jaime conectar google`); ferramentas `email_hoje`, `email_buscar`, `email_rascunho`, `agenda_dia`, `agenda_criar`. `telegram.py`: bot que só aceita `JAIME_OWNER_TELEGRAM_ID`, canal `telegram`, respostas curtas. Envio de e-mail existe como ferramenta, mas fica na lista do Vigia. Testes com clientes falsos.

### Prompt 9 — Voz com persona e emoção
Etapa 9. Renomeie `jaime/voice/` para `jaime/voz/` e crie `persona.py` (§2.7) aplicado como pós-processador de tudo que vai para TTS. Implemente `tts_openai.py` (gpt-4o-mini-tts com `instructions` vindas de `prosodia.py`) ao lado do ElevenLabs (mantenha; adicione suporte a tags quando `ELEVENLABS_MODEL` for v3). Implemente `stt_openai.py` com GPT-Realtime-Whisper em streaming. Crie `voz_design.md` com a descrição da voz alvo para o Voice Design e um comando `python -m jaime voz testar` que fala a mesma frase com 5 vozes e registra a escolhida. Regra: sem "Olá, sou o Jaime"; a abertura vem do momento (§2.2). Teste: mesma resposta com humor "grave" e "leve" gera instruções diferentes.

### Prompt 10 — Imagens, 3D, conteúdo, computer use
Etapa 10. `maos/imagens.py` (GPT-Image-2.5, gerar/editar, salvar em `~/Jaime/imagens`, registrar no diário), `maos/blender.py` (gera script Python e roda `blender -b -P`; verifica que o `.blend` existe), `maos/conteudo.py` (roteiro → thumbnail → corte com ffmpeg → legenda .srt), `maos/computador.py` (ferramenta computer use da API do Claude; captura de tela e ação; **cada ação passa pelo Vigia e o HUD mostra a tela**). Adicione ao catálogo e ao Córtex (tipo *imagem* → OpenAI). Testes onde couber; para computer use, um teste que só faz screenshot.

### Prompt 11 — Meta: WhatsApp Cloud API e Instagram
Etapa 11. `conexoes/meta.py`: WhatsApp Cloud API (número comercial) e Instagram Messaging API (conta profissional) com webhook próprio no servidor do Jaime (`/webhook/meta`, verificação de assinatura). Documente em `docs/CONEXOES.md` o que precisa no Meta for Developers (app, permissões, revisão) e deixe claro que não usaremos bibliotecas não oficiais. Mensagens de terceiros: resumir e propor resposta; enviar só com confirmo. Migre a Evolution API para opcional.

### Prompt 12 — Modo autônomo
Etapa 12. `jaime/autonomo.py`: `objetivo(texto, limite_horas)` → o Córtex decompõe em etapas com critério de aceite; executa com checkpoints a cada etapa (registra no diário e no HUD), pausa em qualquer bloqueio do Vigia e retoma com "confirmo"; ao final, relatório em `40-Diario` e proposta de próximos passos. Limites no `.env`: horas, custo em dólares, ferramentas permitidas. Teste com objetivo pequeno offline.

## 5. Acessos que o João passa diretamente

| Serviço | Como o Jaime recebe | O que ele pode fazer | Cuidado |
|---|---|---|---|
| Anthropic / OpenAI | `.env` | pensar, gerar imagem/voz | limite de gasto nos consoles |
| Google (Gmail, Calendar, Drive) | OAuth do seu projeto, uma vez | ler, rascunhar, criar eventos; enviar só com confirmo | revogar em myaccount.google.com |
| WhatsApp / Instagram | Meta Cloud API (contas comerciais) | ler, responder com confirmo | pessoal via Evolution = risco de bloqueio |
| Telegram / Discord | token do bot | canal rápido do celular | só seu ID responde |
| GitHub / Notion | já no `.mcp.json` | repositórios, cérebro compartilhado | tokens com escopo mínimo |
| Computador | usuário próprio + Vigia | arquivos, apps, browser | pastas permitidas no `.env` |

## 6. Limites honestos
- Voz: original inspirada, não clone de ator. Emoção é expressão coerente com a cena, não simulação de sofrimento.
- Instagram sem API oficial não entra. Jogos "de verdade" (visão + reflexo) são fase 3, não fase 2.
- Placar precisa de volume: nas primeiras semanas ele muda pouco; a política de exploração garante que teste os dois lados.
- Dois provedores = duas faturas. O Córtex registra custo por tarefa justamente para você ver onde o dinheiro vai.
