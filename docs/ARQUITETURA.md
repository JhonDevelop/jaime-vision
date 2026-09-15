# Arquitetura

```
 entrada                 núcleo                          mãos
 ───────                 ──────                          ────
 CLI ─────────┐
 voz (wake→STT)┤   ┌──────────────────────────┐   ┌─ Bash / Read / Write (PC, arquivos, código)
 WhatsApp ─────┼──►│  JAIME  (ClaudeSDKClient)│──►├─ mcp__cerebro__*   (vault Obsidian)
 API /ask ─────┤   │  persistente, 1 processo │   ├─ mcp__github__*    (repos privados)
 Twilio ───────┘   │  system prompt = CLAUDE.md│   ├─ mcp__notion__*
                   │  + contexto do vault     │   └─ Task → maesters (subagentes)
                   └───────────┬──────────────┘
                               │ hooks PreToolUse
                           ┌───┴───┐
                           │ VIGIA │  nega ação perigosa até "confirmo"
                           └───────┘
```

## Fluxo de uma fala
1. Wake word dispara; grava até 0,9s de silêncio; STT devolve texto.
2. `Jaime.ask_stream(texto, canal="voice")` — o canal muda o estilo (curto, sem markdown).
3. Claude lê o contexto do vault (injetado no system prompt), decide sozinho ou delega via `Task` a um maester.
4. Cada chamada de ferramenta passa pelo Vigia. Bloqueou? Jaime pede "confirmo".
5. Texto sai frase a frase para o TTS. Decisões viram linha no diário.

## Por que um processo persistente
Reiniciar o agente a cada fala custa segundos e perde o contexto da conversa. O `ClaudeSDKClient`
fica conectado; `asyncio.Lock` serializa pedidos de canais diferentes.

## Onde cada coisa mora
| Preocupação | Arquivo |
|---|---|
| Quem o Jaime é | `CLAUDE.md`, `vault/00-Jaime/` |
| Especialistas | `.claude/agents/*.md` (lidos por `orchestrator/maesters.py`) |
| Ferramentas de memória | `brain/tools.py` → servidor MCP in-process `cerebro` |
| Regras de bloqueio | `vigia/hooks.py` |
| MCPs externos | `.mcp.json` (auth via `claude` → `/mcp`) |
| Permissões estáticas | `.claude/settings.json` |
| Voz | `voice/` |
| Canais HTTP | `server.py`, `channels/` |

## Memória: três camadas
1. **Sessão** — histórico do `ClaudeSDKClient` (some ao reiniciar).
2. **Diário** — `vault/40-Diario/AAAA-MM-DD.md`, escrito durante o dia.
3. **Notas** — projetos, perfil, conhecimento; o Arquivista consolida o diário nelas.

Quando o vault crescer (milhares de notas), trocar `Vault.buscar` por um índice (sqlite FTS5 ou embeddings) sem mudar a interface das ferramentas.


## Córtex (fase 2, etapa 2) — quem pensa em cada tarefa
`jaime/cortex/roteador.py` classifica cada fala (código · pesquisa · redação · decisão · imagem · voz · rotina) por
pistas de texto, sem chamar modelo, e escolhe o modelo pela política do placar: maior taxa de acerto (suavizada)
para aquele tipo, com `JAIME_CORTEX_EXPLORACAO` (10%) de chance de testar outro candidato. Candidatos vêm do `.env`
(`JAIME_MODEL_DECISAO` Fable 5.1, `JAIME_MODEL_CODIGO` Opus 5, `JAIME_MODEL_PADRAO` Sonnet, `JAIME_MODEL_ROTINA` Haiku).

`jaime/cortex/placar.py` guarda acertos/erros/latência/custo por (modelo, tipo) em `vault/.placar.json` (bruto,
gitignored) e `vault/01-Estado/Placar.md` (legível). Cada turno entra como acerto provisório; se o turno seguinte
for uma correção do João ("errado", "não era isso", "refaz", "de novo"), `corrigir_ultimo()` vira o acerto em erro.

**Troca de modelo sem perder a conversa:** o `ClaudeSDKClient` do SDK 0.2.152 tem `set_model(model)`; o
orquestrador chama antes de cada turno quando o roteador muda a escolha. Recriar o cliente perderia o contexto.
`python -m jaime cortex explicar "<tarefa>"` mostra tipo, modelo e porquê.


## Dois provedores (fase 2, etapa 3) — OpenAI ao lado da Anthropic
`jaime/cortex/provedores/` tem a interface única `responder(prompt, contexto, ferramentas=None) → Resposta`:
- `anthropic.py`: `claude_agent_sdk.query()` de um turno, sem ferramentas — é o árbitro e a segunda opinião.
- `openai.py`: Responses API (`JAIME_OPENAI_MODEL`, padrão `gpt-5.5`; `web_search` quando a tarefa é pesquisa).
  Lista real vista pela chave em 15/09/2026: gpt-5.5, gpt-5.5-pro, gpt-5.6-luna, gpt-5.6-sol; voz gpt-realtime-2,
  gpt-realtime-whisper, gpt-4o-mini-tts; imagem gpt-image-2.5-flare/sunburst. Não existem "GPT-6 Astra" nem "5.6 Terra".

**Regra:** ações no mundo (ferramentas do Agent SDK, MCPs, Vigia) continuam só pela Anthropic, no cliente
persistente. A OpenAI produz texto, decisões e — nas etapas 9/10 — voz e imagem. O roteador só lista
`openai:<modelo>` como candidato para *pesquisa* e *redação*, e só quando há `OPENAI_API_KEY`. Se a chamada
falhar (sem crédito, rede), o mesmo turno cai na Anthropic e o placar anota o erro.

**Juiz** (`jaime/cortex/juiz.py`): tarefa do tipo *decisão*, ou "pensa bem" / "compara" no texto → os dois
provedores respondem em paralelo e o Fable 5.1 (`JAIME_MODEL_DECISAO`) escolhe A, B ou mescla, com uma frase
de justificativa que vai para o diário (seção Decisões) e para o painel Raciocínio do HUD. Custa o dobro; se um
provedor falhar, devolve a resposta do outro sem arbitrar. O turno do juiz roda fora do cliente persistente
(sem as mãos), com o mesmo system prompt do Jaime como contexto.


## Cérebro emocional (fase 2, etapa 4) — `jaime/emocao/`
- `perfil.py`: `10-Eu/Perfil.md`, `Datas.md` (`- DD/MM — x` repete; `- AAAA-MM-DD — x @projeto` é prazo), `Jeito.md`.
- `perguntas.py`: `10-Eu/Perguntas-Feitas.md`. `decidir(pergunta)` → usar / confirmar (>90 dias) / perguntar. A ferramenta
  `mcp__emocao__perguntar_ao_joao` é obrigatória antes de qualquer pergunta (regra 7 do CLAUDE.md).
- `momento.py`: aniversário, feriado (tabela fixa até a etapa 5), prazos em 7 dias, semana pesada → entra no system prompt
  e na apresentação (aniversário = primeira frase do dia).
- `humor.py`: energia, calor, gravidade, confiança. Entradas: tom do João (`detectar_tom`), resultado do turno (ferramentas
  falhando = erro próprio), hora, momento. Coerência: nunca leve com o João em problema; nunca grave em conquista; gravidade
  nunca passa de 0,85 (sem drama). É expressão, não manipulação.
- `prosodia.py`: humor + canal → `{"instructions", "tags" (Eleven v3), "eleven": {stability, style}}`. O ouvido aplica
  `eleven` no TTS antes de cada frase; `instructions` serve ao gpt-4o-mini-tts (etapa 9). O HUD mostra o humor no header.


## Agenda e mundo (fase 2, etapa 5) — `jaime/agenda/`
- `scheduler.py`: APScheduler dentro do processo do servidor. Lê `30-Tarefas/Rotinas.md` (`- <cron> · <ordem>`), recarrega
  quando o arquivo muda (vigia a cada 30 s) e executa cada rotina como `jaime.ask(ordem, canal="rotina")`, falando a
  resposta. Padrão: `0 7 * * 1-5 · briefing` e `0 18 * * 5 · fecha a semana`. Substitui o n8n.
- `lembretes.py`: "me lembra em 20 min de X", "às 15h", "amanhã às 9", "dia 20" → `30-Tarefas/Lembretes.md` + job de data.
- `relogio.py` (hora/data/dia da semana, fuso America/Sao_Paulo), `clima.py` (Open-Meteo, sem chave; `JAIME_LAT/LON`,
  cache 10 min), `feriados.py` (`holidays` BR+SP; tabela fixa de reserva).
- Perguntas de hora, data e clima e pedidos de lembrete **não vão ao modelo**: `Jaime._mundo()` responde em milissegundos.
- Ferramentas MCP `mundo`: `agora`, `clima`, `feriado_hoje`, `criar_lembrete`, `rotinas`.


## Cérebro de estudo (fase 2, etapa 6) — `jaime/estudo/`
- `problemas.py`: `90-Estudo/Problemas.md` — ID, título, origem (ferramenta_falhou · teste_quebrou · joao_pediu ·
  sem_resposta · correcao · manual), contexto, tentativas. Não duplica problema parecido; `proximo()` pega o com menos
  tentativas.
- Gatilhos automáticos no orquestrador: mesma mensagem de erro de ferramenta 2× no turno; o João disse "pesquisa isso" /
  "não sei como"; resposta de pesquisa/código admitiu "não sei". Ferramentas MCP `estudo`: `abrir_problema`,
  `problemas_abertos`, `resolver_problema`.
- `loop.py`: um problema por ciclo, 15 min, turno avulso do Agent SDK em `/tmp/jaime-lab` com hook que nega escrita e
  comandos fora do laboratório (nunca `~/projetos`, nunca o repositório). Resolvido → `50-Conhecimento/<slug>.md`
  (como reproduzir · o que resolveu · onde se aplica), INDEX regenerado, aprendizado no Estado, placar (`estudo`),
  skill em `.claude/skills/<slug>/` quando o estudo devolve uma. Não resolvido → tentativa e "o que falta" no problema.
- Mente contínua (mínima): `rodar_em_ciclos` a cada 30 min, só com o cérebro liberado, ninguém falando e o lock livre.
  HUD: chip "estudando: N".


## Mãos (fase 2, etapa 7) — `jaime/maos/`
- `browser.py`: Playwright com perfil persistente em `~/Jaime/browser-profile` (janela própria do Jaime; logins feitos
  uma vez ficam). Ferramentas `mcp__maos__abrir/ler_pagina/clicar/preencher/extrair/screenshot`. O Vigia segura cliques
  em enviar/comprar/pagar/confirmar/assinar/checkout/excluir (texto ou seletor de submit) até o "confirmo".
  `JAIME_BROWSER_HEADLESS=1` esconde a janela.
- `projetos.py`: `criar_projeto(nome, tipo)` → pasta em `JAIME_WORKSPACE`, git init + primeiro commit, README,
  `.env.example`, `CLAUDE.md` do projeto, nota em `20-Projetos/` pelo `templates/Projeto.md`. Tipos: python, node, generico.
- `arquivos.py`: regras em `10-Eu/Jeito.md` › "## Arquivos" (`- *.pdf com "nota fiscal" → ~/Documents/Fiscal`);
  `organizar_arquivos` só propõe; `mover` é ação do Vigia (confirmo).
- Skills oficiais de documentos (pdf, docx, xlsx, pptx) instaladas em `.claude/skills/` por `python -m jaime skills instalar`
  (baixa de github.com/anthropics/skills). O Agent SDK carrega `.claude/` via `setting_sources=["project"]`.


## Conexões (fase 2, etapa 8) — `jaime/conexoes/`
- `registro.py`: `01-Estado/Conexoes.md` — serviço, escopo, como foi autorizado, como revogar, último uso.
- `google.py`: OAuth de app Desktop do projeto do João no Google Cloud; token local renovado sozinho
  (`python -m jaime conectar google`; passo a passo em `docs/CONEXOES.md`). Ferramentas MCP `google`: `email_hoje`,
  `email_buscar`, `email_rascunho`, `email_enviar` (Vigia), `agenda_dia`, `agenda_criar`, `conexoes`. Clientes injetáveis
  para teste.
- `telegram.py`: bot próprio por long polling (httpx); só `JAIME_OWNER_TELEGRAM_ID` conversa; canal `telegram`.
- Voz: com a cota da ElevenLabs esgotada, a reserva é `say -v "Eddy (Português (Brasil))"` (masculina); 3 falhas
  seguidas desligam a ElevenLabs por 10 min e ela volta sozinha.


## Mídia (fase 2, etapa 10) — `jaime/maos/`
- `imagens.py`: gpt-image-2.5 (`JAIME_OPENAI_IMAGEM`; cai para gpt-image-2/1) → `~/Jaime/imagens/`, registro no diário.
  MCP `midia`: `gerar_imagem`, `editar_imagem`. Validado ao vivo (logo em 13 s).
- `blender.py`: o modelo escreve o corpo bpy; o cabeçalho e o salvamento são nossos; roda `blender -b -P`. Sem Blender
  instalado, salva o script e diz onde baixar. MCP `gerar_3d`.
- `conteudo.py`: `cortar_video` e `extrair_audio` (ffmpeg 8 do pacote `static-ffmpeg`, sem Homebrew), `legendar_video`
  (Deepgram com utterances → .srt), `roteiro_para_cortes`. Thumbnail = `gerar_imagem(formato="thumbnail")`.
- `computador.py`: o Jaime vê a tela (`tela_capturar` → PNG lido com Read; o HUD mostra em `/hud/tela`) e interage com
  apps sem API (`tela_clicar`, `tela_digitar`, `tela_tecla`, via pyautogui). As três interações são ações do Vigia.
  macOS pede Acessibilidade e Gravação de Tela para o Terminal.


## Meta e modo autônomo (fase 2, etapas 11–12)
- `jaime/conexoes/meta.py`: webhook `/webhook/meta` (handshake + assinatura X-Hub-Signature-256), parsing de WhatsApp Cloud
  e Instagram Messaging; dono → resposta direta; terceiro → resumo + rascunho pendente; `enviar_whatsapp`/`enviar_instagram`
  são ações do Vigia. Passo a passo do app em `docs/CONEXOES.md`. Evolution API virou opcional.
- `jaime/autonomo.py`: `objetivo(texto, limite_horas)` → plano em 3–8 etapas com critério de aceite (pelo próprio Jaime),
  execução etapa a etapa com checkpoint no diário e no HUD, pausa quando o Vigia bloqueia (o "confirmo" retoma sem gastar um
  turno), limites de horas/custo/ferramentas do `.env`, relatório final em 40-Diario com próximos passos. MCP `autonomo`:
  `objetivo`, `situacao`. Planejador e executor injetáveis (testes offline).


## Fase 3, etapa 1 — conversa em tempo real (`jaime/voice/tempo_real.py`)
`JAIME_VOZ_MODO=conversa` troca o pipeline (Deepgram → Opus → TTS) pelo OpenAI Realtime (`gpt-realtime-2`) fala-para-fala.
O microfone só é transmitido quando o Silero local detecta voz (pré-roll + cauda) — parado não custa nada. O VAD do
servidor segmenta; a transcrição passa pelo mesmo gate "é comigo?" (nome / janela ativa); só então `response.create`.
Trancado, teclado e renomear continuam no `_porta` do Jaime e o Realtime apenas repete a resposta. Ferramentas do
Realtime: `jaime(texto)` (Agent SDK com as mãos), `hora`, `clima`, `lembrete`. Microfone mudo enquanto ele fala (+300 ms).
Ver docs/FASE-3.md.


## Fase 3, etapas 4–5 — casa, câmera e visão contínua
- `jaime/casa/homeassistant.py`: REST do Home Assistant (token de longa duração; HomeKit entra pela integração do HA).
  `achar(nome)` casa "luz do escritório" com `light.escritorio`. MCP `casa`: `casa_estado`, `casa_ligar`, `casa_desligar`,
  `casa_servico`, `camera_ver`.
- `jaime/casa/camera.py`: quadro da webcam do Mac (ffmpeg/avfoundation, dispositivo 0 = FaceTime) ou `camera_proxy` do HA →
  PNG que o modelo lê com Read e descreve.
- `jaime/maos/visao.py`: sessão de visão contínua (jogos simples, apps sem API): captura → o modelo decide UMA ação em JSON
  olhando a imagem → pyautogui executa → repete, com máximo de passos e intervalo mínimo. Iniciada só por pedido explícito
  (`jogar`); enquanto ativa, o Vigia libera as ações de tela; **"para"/"chega"** encerram na hora (kill switch em `_porta`,
  sem modelo) — o mesmo "para" interrompe um objetivo autônomo.
