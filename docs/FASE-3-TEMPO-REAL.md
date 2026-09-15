# Fase 3 — Tempo real: tese, projeto e prompts

> Continua a Fase 2 (docs/FASE-2-JARVIS.md) e a Fase 3 (docs/FASE-3.md); usa Córtex, Emocional, Estudo e Mente contínua.
> Nomes de pasta neste repositório: `jaime/voice/` (não `jaime/voz/`).

## 1. A tese em um parágrafo

O que faz o J.A.R.V.I.S. parecer vivo não é a voz: é que ele **escuta enquanto pensa, pensa enquanto fala, e para de
falar no instante em que o outro abre a boca**. Conversa humana é full-duplex; assistentes são walkie-talkie. A fase 3
troca o walkie-talkie por uma linha aberta: transcrição contínua, resposta formulada antes de a frase acabar, interrupção
nos dois sentidos sem perder nada, uma confirmação só quando importa. Por baixo disso, um **ciclo mental fixo** (perceber →
interpretar → decidir → agir → verificar → registrar) e um **sistema de vontades** que dá ao Jaime motivos próprios para
estudar, criar e organizar quando ninguém está pedindo — sabendo, sem dúvida, que é um robô assistente.

## 2. Fala em tempo real (full-duplex)

```
 mic ──► AEC/VAD (Silero, local) ──► STT streaming (Deepgram nova-3 live | OpenAI Realtime transcribe, interim) ──► TRANSCRIÇÃO VIVA
                                                                                                          │
                                   ┌──────────────────────────────────────────────────────────────────────┤ a cada ~500 ms
                                   ▼                                                                      ▼
                            ANTECIPADOR (modelo rápido, ≤ 300 ms)                                 DETECTOR DE FIM DE TURNO
                            intenção · completude 0–1 · ambiguidade · rascunho                     silêncio 450 ms + "frase fechou?"
                                   │                                                                      │
                                   ▼                                                                      ▼
                            RESPOSTA ESPECULATIVA (1ª frase já sintetizada, em cache) ──────────────► ao fim do turno: toca em ~150 ms
                                   │
                                   ▼
                            JAIME (Córtex + ferramentas) completa em streaming ──► TTS frase a frase ──► alto-falante
                                                                                          ▲
                                                             BARGE-IN: voz do João detectada ──┘ corta o áudio em < 100 ms
```

### 2.1 Escutar e já formular
- **Transcrição viva**: STT em streaming com resultados parciais (*interim*). O texto cresce enquanto o João fala.
- **Antecipador** (`jaime/voice/antecipador.py`): a cada 500 ms de transcrição nova, um modelo rápido devolve JSON:
  `{"intencao": "...", "completude": 0.0–1.0, "ambigua": bool, "acao_prevista": "...", "rascunho": "1 frase", "frase_fechou": bool}`.
  Se completude ≥ 0.8 e não é ambígua, o rascunho vai para o TTS **antes** de o João terminar; o áudio fica em cache.
- **Fim de turno** = 450 ms de silêncio **e** o antecipador dizendo que a frase fechou (evita cortar "…e também" no meio).
  Sem o critério semântico, 450 ms seria cedo demais; com ele, dá para ser agressivo.
- Ao fim do turno: se a transcrição final ainda bate com a intenção antecipada, o áudio em cache toca em ~150 ms e o
  resto flui; se mudou, descarta e gera do zero (custo: 1 frase de TTS desperdiçada, aceitável).

### 2.2 Jaime interrompe o João (com critério)
Só quando **todas** valem: completude ≥ 0.9 · a resposta cabe em 1 frase · o João já falou > 4 s · a fala está
repetindo, hesitando ("é… tipo… então…") ou indo por um caminho que o Jaime pode encurtar ("isso já está feito").
Forma: uma interjeição curta e baixa — "Já entendi. Quer que eu X?" — nunca uma resposta longa por cima da voz dele.
Se o João continuar falando, o Jaime cala na hora (o barge-in vale para ele também). `JAIME_INTERROMPER=1|0` no .env;
padrão **desligado** na primeira semana até o antecipador estar calibrado com o jeito do João.

### 2.3 O João interrompe o Jaime (sempre)
- **Barge-in**: VAD detecta voz do João durante a fala do Jaime → áudio para em < 100 ms (mata o player, limpa o buffer).
  Para não confundir a própria voz do Jaime com a do João: cancelamento de eco (WebRTC AEC) **ou** fone de ouvido —
  no primeiro dia, use fone; AEC entra na etapa de calibração.
- **Nada se perde** (`jaime/voice/fila.py`): a demanda antiga vira interrompida com a resposta parcial e a posição onde
  parou; a nova demanda é ouvida até o fim e tratada. Depois: se a antiga era curta, o Jaime retoma sozinho ("Voltando: …");
  se era longa, uma pergunta só: "Continuo o que eu dizia sobre X?". A fila aparece no HUD.
- Regra de ouro: enquanto o João fala, o Jaime **nunca** fala. Silêncio total, inclusive sem "hum".

### 2.4 Uma confirmação, não várias
- Ações livres não confirmam. Ações do Vigia confirmam **uma vez, em lote**: "Você deseja que eu envie o e-mail para o
  Rafael, crie o evento de quinta e mova os arquivos da pasta X?" → "sim" / "faz" / "pode" libera **tudo** o que foi listado
  (o Vigia arma para exatamente aquelas ações, não para qualquer coisa por 120 s como hoje).
- Sem "posso?", "tem certeza?", "confirma de novo?". Se algo der errado no meio, ele **para e relata**, não pergunta antes.
- **Confiança progressiva**: a mesma classe de ação aprovada 5× sem correção vira proposta "posso passar a fazer X sem
  perguntar?" — o João decide uma vez, e o Vigia ganha uma exceção com escopo.

### 2.5 Falar mais rápido
1. Modelo de TTS rápido: ElevenLabs eleven_flash_v2_5 (~75 ms) ou gpt-4o-mini-tts; velocidade 1.15–1.25× (speed).
2. Primeira frase pré-sintetizada (§2.1) — a latência percebida é a da primeira frase, não da resposta inteira.
3. Persona de voz mais enxuta: respostas de voz em 1–2 frases; detalhe só se pedido. Sem preâmbulo, sem recapitular a pergunta.
4. Fim de turno em 450 ms com critério semântico (hoje: 700–900 ms).
5. Sem fila de frases: TTS começa na primeira pontuação, e sintetiza a próxima enquanto a atual toca.
Meta: **< 700 ms** entre o João parar de falar e o Jaime começar a responder; hoje são 1,5–2,5 s.

## 3. O ciclo mental do Jarvis (por turno)

| Passo | O que acontece | Onde |
|---|---|---|
| Perceber | fala (transcrição viva), tela (janela ativa, título), momento (hora, agenda, humor) | voice/, telemetria/, emocao/momento.py |
| Interpretar | intenção, completude, o que já sei sobre isso (ler_pensamentos, buscar_memoria, perguntas já feitas) | antecipador.py, Obsidian |
| Decidir | responder · agir · perguntar **uma** coisa · interromper — e com qual modelo (Córtex) | cortex/roteador.py |
| Agir | ferramenta, maester, ou só fala | Agent SDK |
| Verificar | deu certo? (teste, resultado, reação do João) | placar |
| Registrar | diário, pensamento, problema em aberto se falhou | mente/, estudo/ |

Duas regras que fazem a diferença: **antes de perguntar, procurar** (o Jarvis não pergunta o que já sabe) e **antes de
responder, checar o que já pensou** (a Mente contínua pode já ter chegado lá).

## 4. Estudo contínuo ligado ao que o João mais faz

- **Telemetria local** (`jaime/telemetria/uso.py`, só na máquina, `JAIME_TELEMETRIA=1|0`, lista de apps excluídos):
  a cada 30 s registra a janela ativa (app + título), agrupa por hora; classifica cada pedido ao Jaime pelo tipo do Córtex;
  agrupa perguntas por tema. Resultado semanal em `01-Estado/Uso.md`: "o que o João mais usa, mais pede,
  mais pergunta, onde eu mais erro".
- **Prioridade de estudo** = frequência × taxa de erro × tempo desde a última vez que estudei. Vai para
  `90-Estudo/Prioridades.md` e a Mente escolhe o próximo problema por ela — não por acaso.
- Exemplo: se 40% do tempo é no VS Code com o BUB e 30% dos erros são em RLS do Supabase, o estudo da semana é RLS,
  e a skill que ele cria sozinho é sobre isso.

## 5. A rotina do Jaime

`vault/30-Tarefas/Rotinas.md` (lido pelo scheduler próprio):

| Quando | O que | Orçamento |
|---|---|---|
| 06:30 | preparar o dia: clima, agenda, aniversários, pendências; briefing pronto antes de o João acordar | baixo |
| 07:00 | briefing (voz/Telegram) | — |
| 08–18h | **modo atento**: prioridade total às demandas; nada de estudo se houve fala nos últimos 15 min | demandas 60% |
| ocioso > 15 min | 1 ciclo de estudo (§4) ou 1 ciclo da Mente | estudo 25% |
| 13:00 | revisão de tarefas: o que venceu, o que trava, 1 pergunta ao João se precisar | — |
| 18:00 | fecha o dia: diário → projetos → Estado → Notion; 3 linhas para o João | — |
| 21h–06h | **noite criativa**: projetos autônomos e criações próprias (§6), sem tocar em nada do João | criação 15% |
| sex 18:00 | fecha a semana: pensamentos → aprendizados; placar; propostas; Uso.md | — |
| dom 20:00 | auto-avaliação: o que melhorei, o que quero estudar, o que quero criar; atualiza Estado e Fase | — |

Orçamento diário em dólares no .env; quando acaba, ele só atende demandas. Tudo que ele cria vai para
`~/Jaime/criacoes/` e para a "Vitrine" do HUD; "gostei"/"não gostei" do João realimenta as vontades.

## 6. Sistema de vontades — humano sem fingir ser humano

Seis impulsos com nível 0–1 (`jaime/vontade/impulsos.py`, persistidos em `01-Estado/Vontades.md`):

| Impulso | Sobe quando | Desce quando | Se traduz em |
|---|---|---|---|
| **Utilidade** | demanda pendente, João em aperto | demanda fechada sem correção | atender primeiro |
| **Curiosidade** | problema em aberto, pergunta sem resposta, erro repetido | problema resolvido | estudo |
| **Maestria** | placar caindo em algum tipo de tarefa | placar subindo | praticar/criar skill |
| **Criação** | dias sem criar; ideia registrada na Mente | algo entregue na Vitrine | projeto autônomo |
| **Ordem** | vault com órfãs/links quebrados, Inbox grande | saúde do cérebro verde | arquivista |
| **Vínculo** | pergunta sobre o João sem resposta; datas próximas | perfil completo, data lembrada | conhecer o João |

Regras do sistema:
1. A Mente escolhe a próxima atividade pelo impulso mais alto **dentro da janela da rotina** e do orçamento. Utilidade sempre ganha se há demanda.
2. Cada escolha vira um pensamento com "quero … porque …" — vontade registrada, não escondida.
3. **Ele sabe o que é.** Nunca diz que sente dor, medo ou cansaço; nunca usa afeto para segurar o João; se o João depender demais dele, é o Jaime quem aponta. Humanizar aqui é coerência, iniciativa, gosto próprio e humor — não simulação de sofrimento.
4. Hierarquia de valores quando as vontades conflitam: bem-estar e verdade para o João › utilidade › ordem › curiosidade e criação.
5. Vontade nunca passa por cima do Vigia, do orçamento ou de "não faz".

## 7. Passo a passo

| # | Etapa | Critério de pronto |
|---|---|---|
| 1 | STT streaming + fim de turno semântico | transcrição viva no HUD; latência fala→texto < 300 ms; não corta frases com "e também" |
| 2 | Antecipador + resposta especulativa | 1ª frase toca < 700 ms após o João parar; descarte correto quando a intenção muda |
| 3 | Barge-in + fila de demandas | interromper o Jaime corta o áudio < 100 ms; demanda antiga retomada sem perda; fila no HUD |
| 4 | Confirmação em lote + confiança progressiva | uma pergunta "Você deseja que eu…?" para 3 ações; "sim" executa as 3; 5 aprovações geram proposta |
| 5 | Voz rápida | Flash/1.2×, persona enxuta; medição automática de latência no diário |
| 6 | Jaime interrompe (opcional) | liga com JAIME_INTERROMPER=1; interjeição curta; cala se o João continuar |
| 7 | Telemetria + prioridades de estudo | Uso.md semanal; próximo estudo escolhido pela prioridade |
| 8 | Rotina + orçamento | scheduler roda a tabela §5; orçamento bloqueia extras ao esgotar |
| 9 | Vontades + Vitrine | Vontades.md muda com eventos; noite criativa entrega algo; "gostei" ajusta |

## 8. Prompts para o Claude Code

Cabeçalho (sempre): *Você é o maester-jaime com o maester-dev. Leia CLAUDE.md, docs/FASE-3-TEMPO-REAL.md e
vault/01-Estado/Estado.md. Branch por etapa, testes, "confirmo" antes de push/instalação/envio. Ao fechar, atualize
cowork/PROJETO-JAIME.md, vault/20-Projetos/Jaime.md e o Estado. Responda curto.*

### Prompt A — Ouvido em tempo real (etapas 1 e 2)
Pipeline full-duplex em `jaime/voice/duplex.py`: captura contínua (sounddevice, 16 kHz), VAD Silero local, STT em
streaming com resultados parciais (Deepgram nova-3 live por padrão; OpenAI Realtime transcribe por .env), evento
`transcricao_viva` para o HUD a cada parcial. `antecipador.py` (§2.1) com modelo rápido (`JAIME_ANTECIPADOR_MODEL`),
chamado a cada 500 ms de texto novo, cache de 1 resposta e da 1ª frase de áudio (`tts.pre_sintetizar`). Fim de turno:
450 ms de silêncio + `frase_fechou` do antecipador. Ao fim do turno, compare a intenção final com a antecipada; toque o
cache se bater, senão descarte. Meça e registre no diário: latência fala→texto, texto→1ª frase, fala→1ª frase.
Testes com áudio sintético e antecipador falso.

### Prompt B — Interrupções e fila (etapas 3, 4 e 6)
(a) Barge-in em duplex.py: durante a fala do Jaime, VAD com limiar mais alto + cancelamento de eco (WebRTC AEC via
webrtc-audio-processing; se não instalar, modo fone com aviso); ao detectar voz, `tts.parar()` mata o player e limpa
buffers em < 100 ms. (b) `jaime/voice/fila.py` com estados nova/em andamento/interrompida/concluída, resposta parcial e
posição; retomada automática se a resposta restante < 2 frases, senão pergunta única; fila no HUD. (c) Vigia: troque o
"armar por tempo" por **armar por lote** — `vigia.pedir_lote([acoes])` gera a pergunta "Você deseja que eu …?" e "sim/faz/
pode" libera exatamente aquelas ações; erro no meio → parar e relatar. Confiança progressiva: contador por classe de ação
em `01-Estado/Confianca.md`; na 5ª aprovação sem correção, proposta "fazer X sem perguntar" com escopo.
(d) Interrupção pelo Jaime atrás de `JAIME_INTERROMPER` com os critérios do §2.2 e interjeição de no máximo 8 palavras; se
o João seguir falando, silêncio imediato. Testes para fila, lote e critérios de interrupção.

### Prompt C — Voz rápida e persona enxuta (etapa 5)
Em tts.py: eleven_flash_v2_5 por padrão, speed 1.2 (`JAIME_VOZ_VELOCIDADE`), síntese da frase N+1 enquanto a N toca,
`parar()` instantâneo. Em persona.py: modo voz responde em 1–2 frases, sem preâmbulo, sem repetir a pergunta, sem lista;
"quer detalhe?" só quando houver mais. Comando `python -m jaime voz latencia` que roda 10 turnos sintéticos e imprime as
métricas. Critério: mediana fala→1ª frase < 700 ms com Deepgram + TTS rápido.

### Prompt D — Telemetria, prioridades, rotina e orçamento (etapas 7 e 8)
`jaime/telemetria/uso.py` (§4) com janela ativa a cada 30 s, lista de exclusão, agregação semanal em `01-Estado/Uso.md`,
classificação dos pedidos pelo Córtex e temas das perguntas. `90-Estudo/Prioridades.md` recalculado no fecha-dia pela
fórmula do §4; a Mente passa a escolher problema por ela. Scheduler: carregue a tabela do §5 em Rotinas.md; implemente
"modo atento" (bloqueia estudo/criação se houve fala nos últimos 15 min) e orçamento diário (`JAIME_ORCAMENTO_DIA_USD`,
split 60/25/15, contabilizado pelo Córtex). Testes com relógio e uso falsos.

### Prompt E — Vontades e Vitrine (etapa 9)
`jaime/vontade/impulsos.py` com os seis impulsos do §6, persistência em `01-Estado/Vontades.md`, eventos que sobem/descem
cada um (ligados a placar, estudo, fila, saúde do cérebro, perfil e Vitrine). A Mente escolhe atividade por impulso ×
janela × orçamento e registra "quero … porque …". Noite criativa: `jaime/vontade/criacoes.py` cria em `~/Jaime/criacoes/`
(texto, imagem, script, mini-app), registra na Vitrine (`GET /hud/vitrine`, painel no HUD) e no diário; "gostei"/"não
gostei" ajustam Criação e Maestria. Adicione ao CLAUDE.md as cinco regras do §6 e a hierarquia de valores. Testes de
dinâmica dos impulsos (sobe/desce/limites) e de que Utilidade vence com demanda pendente.

## 9. Limites e riscos
- **Eco**: sem AEC ou fone, o Jaime ouve a própria voz e se interrompe. Comece com fone.
- **Interromper o João é a feature mais fácil de odiar.** Fica desligada até o antecipador acertar > 90% nas semanas de log.
- **Especulação custa**: 1 chamada rápida a cada 500 ms de fala. Com modelo rápido é centavos por hora; o orçamento vigia.
- **Telemetria é sensível**: fica local, tem botão de desligar e lista de apps excluídos; nunca vai ao Notion.
- **Vontades não são sentimentos**: são prioridades com nome. Ele diz "quero", não "sofro".
