# HUD vivo — mapa estado → animação

> Fase 3, obra do HUD (`feat/hud-obra`). Cada animação mapeia **um** estado real e volta ao repouso quando ele acaba.
> Fonte da verdade: eventos do `bus` (`jaime/hud/events.py`) pelo SSE `/hud/stream` + polling leve de `/hud/sistemas`.
> Cores por camada: **ouvir** âmbar `#ffb347` · **pensar** ouro `#ffd08a` · **agir** verde `#5cff9d` · **falar** ciano `#4fd8ff`
> · **interrompido** vermelho `#ff5f5f` · **equipe/antecipação** violeta `#c6a5ff` · trancado vermelho escuro.

## Quem emite o quê

| Evento | Emissor | Campos que o HUD usa |
|---|---|---|
| `escuta` (10 Hz) | voice/duplex, escuta, tempo_real | `nivel` 0–1, `voz` (prob. VAD), `gravando` (João no meio de um turno), `janela_ativa` |
| `voz` | duplex, escuta, tts, tempo_real, server | `estado` ∈ carregando · ouvindo · transcrevendo · pensando · falando · interrompido · erro · mudo; `falando`, `ativo`, `modo` (duplex/conversa), `stt`, `barge_in`, `restantes`, `interrompida`, `texto` |
| `transcricao_viva` | duplex | `texto`, `final` |
| `antecipacao` | duplex | `intencao`, `completude` 0–1, `fechou`, `rascunho`, `origem`, `latencia` · ou `usado=True` · ou `interjeicao` |
| `ouvido` | escuta, tempo_real | `texto`, `ignorado` |
| `falante` | escuta | `nome`, `confianca` |
| `latencia` | voice/escuta `Latencias` | `fala_texto`, `texto_frase`, `fala_frase` (s), `antecipado` |
| `conversa` | orchestrator | `canal`, `texto` (início do turno) |
| `cortex` | orchestrator | `tarefa`, `confianca`, `modelo`, `motivo`, `exploracao` |
| `juiz` | orchestrator | `escolha`, `justificativa`, `provedores` |
| `raciocinio` | orchestrator | `texto` (thinking, blocos de ~240 chars) · ou `ferramenta` + `alvo` (Read/Grep/memória/reflexão) |
| `producao` | orchestrator | `ferramenta`, `alvo`, `trecho`, `nota` (Write/Edit/Bash/Task/mcp__*) |
| `resultado` | orchestrator | `texto`, `erro` (VIGIA no texto = ação anotada para o lote) |
| `fala` / `fala_fim` | orchestrator, tts, agenda, autonomo | `texto` (delta em streaming) |
| `fila` | voice/fila | `itens[{id,resumo,estado,ditas,pendentes}]`, `atual`, `aguardando` |
| `equipe` | equipe/filhos | `filhos[{nome,tipo,estado,preset,tarefas}]` · `relatorio{nome,texto}` · `erro` |
| `estudo` | estudo/loop | `abertos`, `msg` |
| `pensamento` | mente/pensar (raciocínio próprio, ocioso) | `pensando`, `tema` · `texto`, `vale_dizer` · `ligado`, `total` · `erro` |
| `vontade` | vontade/impulsos, mente | `niveis`, `escolha{pensamento}`, `demanda_pendente`, `erro` |
| `humor` | orchestrator | `energia`, `calor`, `gravidade`, `confianca`, `rotulo` |
| `placar`, `telemetria` | cortex/placar, telemetria | `msg` / `ligada`, `erro` |
| `autonomo`, `evolucao`, `visao`, `gravador`, `vitrine`, `agenda`, `lembrete`, `notificacao` | módulos respectivos | como já desenhado no feed |
| `estado`, `acesso`, `identidade`, `teclado`, `conexoes`, `contexto`, `sistema`, `tela` | orchestrator, server, hud/* | idem |

`/hud/sistemas` (novo, `jaime/hud/sistemas.py`): fotografia dos subsistemas que não têm evento contínuo —
lote do Vigia esperando "sim", fila, filhos, estudo (aberto/ocupado/pode estudar), janela da rotina (atento/ocioso/noite),
orçamento do dia, vontades, humor, latência mediana, pendências que dependem do João.

## Camada 1 — ouvido duplex (anéis + legenda)

| Estado real | Sinal | Animação | Repouso |
|---|---|---|---|
| Microfone ouvindo, ninguém falando | `voz.estado=ouvindo`, `escuta.gravando=false` | anel principal ciano fino, escala 1 + nível×0,35; arco secundário gira devagar (0,5 rad/s) | é o repouso |
| João falando (turno aberto) | `escuta.gravando=true` | anel âmbar, escala cresce com `nivel`; arco gira a 1,5 rad/s; cérebro âmbar e cresce com o volume | `gravando=false` |
| Transcrição viva | `transcricao_viva.final=false` | texto "você (ao vivo)" com cursor ▍; arco de antecipação (violeta) aparece | `final=true`: cursor some, texto fixa |
| Antecipando | `antecipacao.completude` | arco violeta preenche `completude`×360°; `fechou=true` fecha o círculo e brilha 300 ms; legenda "antecipando · 80% · intenção" | fim do turno |
| Rascunho antecipado tocou | `antecipacao.usado=true` | arco vira verde e dissolve; feed "antecipado" | 600 ms |
| Jaime interjeita | `antecipacao.interjeicao` | anel pulsa violeta 1× | 600 ms |
| Fim de turno (silêncio + frase fechou) | `transcricao_viva.final=true` | flash curto no anel (âmbar→ciano), legenda "pensando" | — |
| Pensando (esperando modelo) | `voz.estado=pensando` / `conversa` sem `fala` ainda | cérebro ouro, pulso lento de espera (período 2,4 s) enquanto não chega evento há > 600 ms; legenda mostra o modelo do Córtex | 1ª `fala` |
| Falando em streaming | `voz.estado=falando` + deltas `fala` | cérebro ciano pulsando no ritmo da fala (9 Hz); ondas concêntricas saem do anel a cada 450 ms; texto da fala com cursor ▍ | `fala_fim` + `voz.falando=false` |
| Interrompido (barge-in) | `voz.estado=interrompido`, `restantes` | anel e cérebro piscam vermelho 1× e encolhem; legenda "interrompido · N frases guardadas"; fila mostra ⏸ | próximo `voz.ouvindo` |
| Ouvi, não era comigo | `ouvido.ignorado=true` | texto apagado em itálico 4 s | 4 s |
| Voz em erro / mudo | `voz.estado=erro\|mudo` | anel quase invisível; legenda vermelha/cinza | `voz.ouvindo` |
| Latência | `latencia.*` | painel Raciocínio: "fala→1ª frase 640 ms"; cliente mede `conversa→1ª fala` em ms | — |

## Camada 2 — raciocínio (cérebro de pontos + painel Raciocínio)

| Estado real | Sinal | Animação | Repouso |
|---|---|---|---|
| Córtex escolheu modelo | `cortex` | chip "modelo"; linha fixa no topo do painel: tarefa · modelo · confiança (barra) · motivo · (exploração) | próximo turno |
| Juiz (duas opiniões) | `cortex.modelo=juiz` → `juiz` | mesma linha em violeta "juiz: Anthropic vs OpenAI → escolha" | idem |
| Thinking | `raciocinio.texto` | sinapses piscam mais (energia +); contador "pensamento 1,2k"; texto legível no feed em itálico | `fala_fim` |
| Ferramenta de leitura | `raciocinio.ferramenta` | nó da conexão pulsa ouro; contador de ferramentas | — |
| Ferramenta de ação | `producao` → até `resultado` | cérebro **verde** enquanto a ferramenta roda (agir); nó pulsa; "Fazendo agora" mostra o trecho | `resultado` |
| Resultado com erro | `resultado.erro` | linha vermelha no feed, ✘ na linha do tempo, energia cai | — |
| Vigia anotou ação | `resultado` com "VIGIA" | som do Vigia; painel Sistemas mostra o lote em âmbar | "sim"/descarte |
| Intensidade do turno | tokens de thinking + nº ferramentas + tamanho da fala | `UI.carga` 0–1 → brilho, tamanho dos pontos e opacidade das sinapses; decai 0,15/s | `fala_fim` zera |
| Espera de rede | > 600 ms sem evento durante o turno | pulso lento do núcleo (2,4 s) em vez do pulso rápido | próximo evento |
| Pensando sozinho (Mente contínua, ocioso) | `pensamento.pensando=true` | cérebro ouro claro em luz baixa, respiração lenta (1,2 rad/s); legenda "pensando sozinho · tema" | `pensamento` com `texto`/`erro`, ou 90 s |
| Pensei | `pensamento.texto` | nó Obsidian pulsa ouro, estrela `01-Estado/Pensamentos.md` acende; feed "pensei · vale dizer"; linha mente do painel | — |
| Tamanho do turno | `conversa`→`fala_fim` | linha "turno: 8,4 s · 3 ferramentas · 1,2k pensamento · 640 ms até a 1ª palavra" | próximo turno |

## Camada 3 — painel Sistemas (compacto, à esquerda)

| Sistema | Sinal | Desenho |
|---|---|---|
| Ouvido | `voz` (modo, stt, barge-in) | linha "duplex · deepgram · barge-in fone" |
| Fila de demandas | `fila` | últimos 4 itens: ▶ em andamento · ⏸ interrompida · ↩ retomada · ✔ concluída · ✘ descartada; `aguardando` → item âmbar pulsando "esperando sim/não" |
| Lote do Vigia | `/hud/sistemas.vigia.lote` + `resultado` VIGIA | bloco âmbar "esperando seu sim": lista das ações; some ao liberar/descartar |
| Filhos (equipe) | `equipe.filhos` + `relatorio` | ● vivo / ○ parado · nome (tipo); relatório novo pisca violeta 2 s |
| Estudo | `estudo` + `/hud/sistemas.estudo` | "N em aberto · estudando agora" ou motivo de não estudar |
| Mente | `pensamento` + `/hud/sistemas.mente` | "N pensamentos · K a dizer · último"; âmbar quando há algo que vale dizer ao João; ciano enquanto pensa |
| Pendente de você | lote, fila.aguardando, evolução pronta, objetivo pausado, nome proposto | lista âmbar no topo do painel; vazia = oculta |
| A seguir | `estado.proximos` (1ª linha) + `vontade.escolha` | "a seguir: …" + "quero … porque …" em itálico |

## Camada 4 — ambiente (vontades, humor, orçamento, rotina)

| Estado | Sinal | Desenho sutil |
|---|---|---|
| Humor | `humor` | chip com 4 barras (já existia); a vinheta ganha tom: grave → avermelhada, caloroso → âmbar, leve → ciano claro; transição 2 s |
| Vontades | `vontade.niveis`, `movimentos`, `demanda_pendente` | chip "vontade" com o impulso mais alto + mini-barras (6) que deslizam a cada movimento; borda âmbar com demanda pendente; último movimento ("Utilidade ↑ 0,30 — demanda nova") no feed; constelação do vault gira 1,5× mais rápido quando Curiosidade > 0,6 |
| Orçamento do dia | `/hud/sistemas.orcamento` | chip com barra: gasto/teto (âmbar > 80 %, vermelho esgotado); sem teto = "US$ x hoje" |
| Rotina | `/hud/sistemas.rotina` | chip "atento" (ciano) · "ocioso" (cinza) · "noite criativa" (violeta); na noite criativa a cena escurece 10 % |

## Cockpit — módulos (abas sob o cabeçalho; teclas 1–5; Esc fecha)

Dados de `GET /hud/painel` a cada 10 s, e na hora quando o SSE traz `lembrete`, `agenda` ou `producao` tocando Inbox/Finanças/Lembretes.
O painel de vidro abre **sobre** o cérebro 3D, que continua vivo atrás.

| Módulo | Dados | Desenho |
|---|---|---|
| Finanças | `painel.financas` / `GET /hud/financas?mes=` | saldo grande (vermelho se negativo), entradas/saídas, rosca dos gastos por categoria e barras entradas×saídas por mês em canvas puro (varrem ao mudar os dados), últimos lançamentos; filtro "tudo / este mês" |
| Afazeres | `painel.afazeres` (linhas `- [ ] … @projeto ⏳ prazo`) | lista com caixa, chip do projeto e prazo (vermelho se venceu); marcar é visual e fica no localStorage — o Inbox só muda quando o Jaime fecha a tarefa |
| Agenda | `painel.agenda` | próximos lembretes (verde = hoje) e rotinas com o cron legível ("08:00 · seg–sex") |
| Música | `GET /hud/musica` (30 s) | não conectado: card "Spotify (conectar)" com o comando `python -m jaime conectar spotify`; conectado: o que toca (disco gira só se toca) e artistas mais ouvidos |
| Cérebro | `GRAFO` (de `/hud/vault`) | notas, ligações, nota tocada agora, contagem por pasta, mais ligadas; botões para o grafo (G) e a memória (B) |
| Abas | `painel` | cada aba mostra o valor vivo: saldo, tarefas abertas, próximo lembrete, "conectar", nº de notas |

## Grafo do vault (tecla G / botão "grafo") — estilo Graph View do Obsidian

| Estado real | Sinal | Desenho |
|---|---|---|
| Notas e [[links]] do vault | `GET /hud/vault` (mesmo que a constelação; recarrega a cada 2 min) | vista 2D em canvas: bolinha por nota com rótulo, cor por pasta (legenda no rodapé), tamanho = 4 + 2,2·√(ligações); forças simples (repulsão, molas nas arestas, centragem) esfriando até parar |
| Nota que ele lê/escreve agora | `producao.nota`, alvo com `/vault/`, `pensamento`, busca — tudo passa por `tocarNota` | o nó acende (anel branco) e pulsa ~3 s; as arestas dele ficam ciano forte; o resto esmaece |
| Passar o mouse | hover | rótulo em branco, vizinhos em destaque |
| Arrastar nó / arrastar fundo / roda | pointer, wheel | nó fixo enquanto arrasta (simulação reaquece); pan; zoom em volta do cursor (0,25×–4×). Enquanto o João não mexe, o grafo se enquadra sozinho na área livre entre os painéis |
| Clique num nó | pointerup sem movimento | abre a nota no painel Cérebro (`/hud/nota`) |
| G de novo | — | volta ao cérebro 3D (o 3D não renderiza enquanto o grafo está aberto) |

## Regras de desempenho
- Loop de render limitado a 30 fps; atualizações de DOM vindas de eventos de alta frequência (`escuta`, `fala`,
  `transcricao_viva`) só marcam *dirty* e são aplicadas no próximo frame.
- Feeds limitados a 60 linhas; ondas/pacotes usam pool fixo (sem alocar geometria por evento).
- Um único `EventSource`; ao reconectar, o anterior é fechado. Nenhum listener é adicionado por evento.
- Cores mudam por interpolação (`Color.lerp`), nunca por troca brusca — nada pisca sem motivo.
