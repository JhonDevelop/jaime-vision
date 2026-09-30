# Tela Jarvis — as cenas dos vídeos

Abrir: `http://127.0.0.1:8787/hud/jarvis` (ou `JAIME_HUD_PADRAO=jarvis` para ser a tela principal em `/`).
Sem o Jaime inteiro: `python -m jaime jarvis demo` → `http://127.0.0.1:8792/hud/jarvis` e `/demo/briefing`,
`/demo/monitor`, `/demo/holograma`, `/demo/particulas` (dados do vídeo, voz simulada no ritmo real).

| Frase (voz ou teclado `/`) | Cena | Vídeo |
|---|---|---|
| "bom dia" (manhã, 1ª vez do dia) · "me dá o briefing" | Briefing matinal | o de 1:22 |
| "ativar monitor" | Rosto no orbe → "Identidade confirmada" → relatório do treino com ícones holográficos | o do treino |
| "cria um holograma do/da X" · "fecha o holograma" | Holograma 3D verde, controlado com a mão | o do carro |
| "modo partículas" · "modo fios" | Estilo do orbe | o da esfera de partículas |
| "aprende meu rosto" · "esquece meu rosto" | Cadastro do rosto (cortesia) | — |
| "qual sua capacidade máxima?" · "o que você consegue fazer?" | Inventário REAL do que está ligado agora (sentinela, filhos, Google, casa, Hermes) | o da esfera |
| "como estão os sistemas?" | Sentinela: sites, servidores e APIs vigiados, com latência e disponibilidade | o da esfera |

Ele também atende por **"Jarvis"** (além de "Jaime"). As cenas que precisam da tela acordam o monitor e abrem a
página sozinhas se ela não estiver aberta (`JAIME_JARVIS_ABRIR_TELA=off` desliga).

Todas passam sem modelo (frase inteira reconhecida → falas + eventos), só com o cérebro destrancado.
`JAIME_JARVIS=off` desliga; `JAIME_BRIEFING_BOM_DIA=off` faz o "bom dia" voltar a ser só cumprimento.

## Briefing (jaime/jarvis/briefing.py)
1. Fala na hora "Revisei o que já está consolidado desde ontem. Sem desvios relevantes…" (ou o desvio que achou:
   microfone com erro, aprovação do Hermes pendente) — enquanto isso coleta em paralelo: clima (Open-Meteo,
   `JAIME_CIDADE`, `JAIME_LAT/LON`), agenda e e-mails (Google, se conectado), notícias (RSS, `JAIME_NOTICIAS`),
   saúde (webhook).
2. Card BRIEFING MATINAL: as 5 etapas acendem, "Atualizando o radar de notícias…".
3. Segmentos: clima → agenda → e-mails (o modelo rápido resume o que pede AÇÃO) → uma notícia por tema, com foto e
   fonte → observações de saúde → linha de foco (primeira tarefa aberta do Inbox).
4. **Sincronia**: cada segmento traz a FRASE e o CARD; a tela mostra o card quando o TTS começa a dizer aquela frase
   (evento `voz` com o texto). Sem voz (canal de texto), mostra pelo tempo estimado da fala. O card anterior encolhe
   e encaixa na fileira embaixo do orbe; no fim, todos ficam enfileirados.

## Inteligência, não só aparência
- **Desvios de verdade** no começo do briefing: sistema que caiu de madrugada (sentinela), tarefa vencida no Inbox,
  falhas repetidas no diário de ontem, aprovação do Hermes parada, microfone com erro.
- **Notícias contadas com as palavras dele** (uma frase por notícia, modelo rápido), não a manchete crua.
- **E-mails**: o modelo separa o que pede AÇÃO e diz o quê e até quando.
- **Saúde contra a SUA média**: histórico diário em `~/Jaime/saude/historico.jsonl`; as observações comparam com os
  últimos 14 dias (distância, passos, FC de repouso, VFC, sono), não com tabela genérica.
- **Holograma de qualquer objeto**: fora do catálogo, o modelo descreve as peças (formas, posições, proporções,
  direção de explosão); a tela monta; fica guardado em `~/Jaime/hologramas/<nome>.json` (a 2ª vez é instantânea).
  O texto do modelo passa por validação (só 5 formas, limites de tamanho) e nunca vira código na página.
- **Sentinela** (`jaime/jarvis/sentinela.py`): `JAIME_SENTINELA="BUB|https://bubapp.com.br;API|https://…/health"`,
  checagem a cada `JAIME_SENTINELA_S` (60 s). Caiu (2 falhas seguidas) → fala, diário e card; voltou → quanto tempo
  ficou fora; lento → observação. Só olha, nunca mexe no servidor.

## Monitor (jaime/jarvis/monitor.py, rosto.py, saude.py)
- A tela abre a câmera dentro do orbe e extrai o descritor do rosto com face-api **no navegador desta máquina**; o
  servidor compara com o cadastro (`~/Jaime/identidade/rosto.json`, 0600). O descritor não volta para a página.
- Rosto confere → lê o treino. Rosto diferente → não lê dado de saúde em voz alta. Sem cadastro → vale a palavra-passe.
- **O rosto nunca destranca o cérebro, nunca aprova ação do Vigia e nunca dá privilégio.**
- Dados: `POST /webhook/saude` (X-Jaime-Token) com o JSON do app Health Auto Export (iPhone) ou um JSON simples
  `{"distancia_km", "duracao_min", "habitual_km", "fc_pico", "estresse", "recuperacao", "vfc", "calorias"}`.
  Com `JAIME_BIND=127.0.0.1` só a própria máquina entra: use um túnel autenticado ou um atalho local que repasse.

## Holograma (jaime/jarvis/holograma.py, hud/static/jarvis/holograma.js)
- Modelos montados por peças (explodem para fora e voltam): carro/SUV elétrico de 7 lugares (lataria, cabine,
  4 portas, bateria no assoalho, 2 motores, bancos, volante, rodas), moto, casa, drone, foguete, átomo, planeta.
- Objeto fora do catálogo: salve `~/Jaime/hologramas/<nome>.glb` e peça de novo. Nomes de marca viram o modelo
  genérico (não reproduzimos o desenho de nenhum fabricante).
- Mãos (MediaPipe Hand Landmarker no navegador): mão aberta movendo gira · pinça subindo/descendo dá zoom · duas
  mãos se afastando abrem as peças · mão fechada remonta. Sem câmera: arrastar, roda do mouse, `E`, `Esc`.
- Validado com mãos sintéticas (girar/abrir/fechar/zoom) e com o vídeo do carro como câmera falsa (mãos detectadas).

## Bibliotecas locais
`python -m jaime jarvis baixar` guarda em `~/Jaime/jarvis-vendor/` (JAIME_JARVIS_VENDOR): face-api 1.7.15,
MediaPipe tasks-vision 0.10.14 e o `hand_landmarker.task` (do Google; se não der, do pacote npm que o embute,
conferido pelo conteúdo). Sem isso a tela usa o CDN (jsdelivr/Google).

## Pendências físicas (não dá para validar daqui)
Câmera real (rosto e mãos em luz real), voz real sincronizando no Mac/Windows, webhook do iPhone chegando.

## Estúdio de holograma (criar → ver → mexer → estúdio 3D → impressora)

Qualquer objeto: "cria um holograma de X" (catálogo, peças geradas pelo modelo ou `~/Jaime/hologramas/X.glb`),
ou "quero desenhar" (prancheta 3D: o indicador esticado desenha no ar; gire com a mão aberta para desenhar em outro
plano) e depois "dá volume ao desenho, é uma cadeira".

| Mão (webcam) | Mouse | Efeito |
|---|---|---|
| indicador aponta | passar por cima | mira a peça (fica branca) |
| pinça rápida em cima | clique | seleciona (âmbar) / solta |
| pinça segurando + mover | Shift+arrastar | move a peça |
| girar o punho durante a pinça | — | gira a peça no eixo da visão |
| mão aberta movendo | arrastar | gira a peça selecionada (sem seleção: o objeto) |
| duas mãos afastando | roda (com seleção) | escala a peça (sem seleção: abre em peças) |
| punho fechado | Esc | solta a seleção (sem seleção: remonta) |
| olhar parado ~0,9 s | — | seleciona a peça ("liga o controle pelo olhar") |
| — | Delete · Ctrl/⌘+Z · E | esconde · desfaz · abre/fecha |

Voz com holograma aberto: "abre as portas dianteiras", "aumenta essa peça", "coloca uma antena em cima", "esconde
as rodas", "desfaz". O modelo recebe a lista de peças e devolve operações (`jaime/jarvis/estudio.py`), validadas no
servidor e aplicadas pela tela — nunca código.

Arquivos: "exporta em STL/OBJ/GLB" (as malhas saem da tela como o João deixou; sem tela, das peças descritas) →
`~/Jaime/hologramas/exportados/`. "abre no Blender" importa o GLB e abre o .blend. "manda para impressão com 12 cm"
gera STL de mesa (mm, Z para cima, apoiado em Z=0) em `exportados/impressao/` e abre no fatiador instalado (Bambu
Studio, OrcaSlicer, PrusaSlicer, Cura; `JAIME_FATIADOR` força um). Imprimir de verdade é o João quem aperta.

Controle por mão na tela toda ("liga o controle por mão"): o indicador é o cursor, pinça rápida clica em controles
marcados com `data-mao`, mão aberta parada 1,2 s fecha o que estiver aberto. Nada do Vigia tem `data-mao`.

Pendente de validação física: mãos e olhar com a webcam real e luz real (o olhar pela webcam é aproximado).

## Pessoas (rosto de várias pessoas)

"aprende o rosto da Ana, minha irmã" (com o consentimento dela) → rosto guardado com nome e relação, e a Ana entra
no grafo de relações (`~/Jaime/relacoes.db`) ligada ao João. "quem é esse?" reconhece e diz o que o grafo sabe;
"quais rostos você conhece?"; "esquece o rosto da Ana". Quem a câmera reconheceu vira contexto para o cérebro
(`[na câmera agora: Ana (irmã do João); memórias: …]`) — nunca permissão.

## Mãos individuais, profundidade e controle do computador (30/09)

**No holograma** cada mão é uma: a direita (ciano) e a esquerda (âmbar) aparecem como holograma na cena, espelhadas,
com um anel no chão e um fio mostrando a que profundidade estão. Profundidade = tamanho aparente da mão (a tela mede
o tamanho "neutro" nos primeiros 15 quadros em que a mão aparece): chegar a mão perto da câmera = entrar na cena.
- a mão ACENDE quando encosta numa peça (o raio da câmera até a pinça cruza a superfície real da peça na mesma
  profundidade — peça pequena ganha da grande atrás dela);
- pinça encostada = pega a peça (segue a mão em 3D; girar o punho gira); as duas mãos na mesma peça escalam e giram;
- pinça no vazio = mexe na cena: direita gira, esquerda aproxima/afasta; punho solta tudo;
- "mostra meus braços" liga o rastreador de pose (braços até o ombro); "me coloca no holograma" projeta a câmera
  atrás da peça, alinhada com a mão; "captura esse objeto" congela a imagem como peça de referência.

**Voz no holograma** (sem modelo, em milissegundos — `estudio.rapido`): "separa a roda da frente", "mostra só o
motor", "mostra a bateria inteira", "mostra tudo", "esconde as portas", "aumenta essa peça", "pinta a lataria de
vermelho", "gira o volante", "sobe a cabine", "volta a porta", "abre as portas", "explode", "junta tudo". O que
não se encaixa vai ao modelo, que devolve operações (inclui separar, isolar, focar, cor, mostrar_tudo).

**Controle do computador** ("liga o controle do computador" / botão MÃO): as mãos viram o mouse do Mac inteiro
(`jaime/jarvis/controle_maos.py` + `mouse_so.py`, Quartz no Mac, Win32 no Windows).
- direita = mouse (base do indicador guia; pinça clica, pinça dupla = clique duplo, segurar arrasta, médio+polegar =
  botão direito, punho = levanta o mouse); esquerda = rolagem (pinça + subir/descer, como joystick);
- 1ª vez: calibração de dois toques (cantos da área confortável), guardada em `~/Jaime/identidade/maos.json`;
- ENSAIO (mostra, não clica) até calibrar, sem a permissão de Acessibilidade do Python do Jaime, ou com
  `JAIME_MAOS_SO_ENSAIO=on`; `JAIME_MAOS_SO=off` desliga de vez;
- só com o cérebro destrancado e sem visita; trancou → desliga e solta o botão; mão sumiu 0,4 s → solta;
  as duas mãos abertas paradas 2 s → desliga; "troca as mãos" para canhoto; "recalibra a mão".
- pela aba do Jarvis a janela precisa estar visível em algum monitor. Com o Safari escondido: rastreador nativo
  (`bash scripts/maos/instalar-nativo.sh`, depois `JAIME_MAOS_NATIVO=on` e permissão de Câmera para o Python).

**Notícias**: o "bom dia" não traz mais notícias; elas vêm quando pedidas ("quais as notícias?", "me dá o
briefing"). Os cartões somem 75 s depois do último, e a tela não reencena mais o briefing quando reconecta.

Pendente de validação física: profundidade e pinça com a mão real, o lado certo de cada mão na câmera do Mac,
o mouse real (permissão de Acessibilidade) e o rastreador nativo.
