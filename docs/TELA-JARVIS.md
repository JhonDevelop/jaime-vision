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
