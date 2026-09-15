# Estado do Jaime
> Reescrito pelo próprio Jaime. O João lê; o Jaime mantém.

## Fase
1 — operando localmente; fase 2 (Jarvis) em andamento, etapa 1 fechada

## Situação agora
O João reclamou que eu falo e penso duas vezes ao mesmo tempo. Fui primeiro ao código e culpei o scheduler novo e o /hud/falar por falarem sem esperar o turno em andamento — errado: `ps aux` mostrou dois `jaime serve` vivos, o de ontem 14/09 às 17:01 (PID 76524, 63 min de CPU acumulados) e o de hoje 08:14 (PID 51990). Dois servidores, dois ouvidos no mesmo microfone, duas inferências e duas vozes. O SIGTERM não derrubou o velho e o Vigia bloqueou o `kill -9`; espero o "confirmo" do João. Aniversário dele registrado: 10 de março.

## Última conversa
- canal: cli
- quando: 15/09/2026 08:20 em MacBookPro
- tema: pesquisa isso depois: como rodar Whisper em GPU num Mac Intel. por agora só confirma em uma frase qu

## Em andamento
- Derrubar o servidor velho (PID 76524 e a sessão filha 76533) com `kill -9` — bloqueado pelo Vigia, aguardando "confirmo"
- Fase 2, etapa 5: scheduler, relógio, clima, feriados, lembretes (jaime/agenda/) — em branch, não commitado
- Serialização de fala: scheduler.py:90 e :115 e /hud/falar chamam fala/inferência sem checar `ouvido.ocupado`/`mudo` (só o observador checa). Não é a causa do problema de hoje, mas continua sendo um risco real com um servidor só

## Próximos passos
1) Com o "confirmo": `kill -9` no 76524/76533 e conferir que sobrou só o 51990. 2) Impedir que dois `jaime serve` subam ao mesmo tempo — lockfile ou checagem de porta no boot. 3) Fila única de fala no ouvido, atravessada por scheduler, observador e HUD. 4) Fechar a etapa 5 e commitar a branch feat/fase2-agenda. 5) Crédito na OpenAI. 6) Autorizar Banco MCP, Canva e Meta Ads no claude.ai; corrigir a URL do n8n (404).

## Aprendizados recentes
Testar antes de mexer no meu próprio código. Eu tinha diagnosticado que a transcrição ruim vinha do modelo nova-3 em português e cheguei a pedir "confirmo" para trocá-lo. Antes de aplicar, gerei um áudio em português com o say e comparei nova-3 pt-BR, nova-2 pt-BR e nova-3 multi: os três transcreveram a frase inteira quase perfeita. A causa era outra — o mic interno do MacBook captando som ambiente. Se eu tivesse a confirmação na hora, teria mudado o código à toa.

Microfone ligado não é o mesmo que estar entendendo. Quando duas ou três falas seguidas chegam sem sentido, o problema é a captação, não o João — o certo é dizer isso na hora e chamar pedir_teclado, em vez de responder a um palpite. Também não vale "confirmar" uma ação que eu não bloqueei: quando ele disse "confirmo, pode executar a ação que o Vigia bloqueou" não havia nada bloqueado, e eu disse isso em vez de inventar uma ação.

Processo em background morre junto com a sessão que o criou: o build da BUB tinha parado no xcodebuild sem sequer criar /tmp/bub-ios-dd, e só descobri olhando o log e o diretório. Se é para durar, precisa sobreviver por conta própria.

Quando o João disser que não estou escutando, a primeira coisa a checar é /hud/estado — o campo voz.ativa. Com ouvido.ativo=false o Ouvido descarta todo frame antes do VAD: sem erro, sem sinal no HUD, só silêncio.

Corrigindo o que eu vinha repetindo: o mpv não é necessário. O TTS toca por sounddevice/PortAudio e cai no afplay quando a placa falha (jaime/voice/tts.py).

O João cola segredos direto no chat quando está com pressa (foi assim com a chave da ElevenLabs) — melhor pedir que escreva no .env ou avisar na hora para revogar. Ele não quer que eu silencie a apresentação de boot. Nos canais voice e cli ele pede resposta curta de verdade, e quando fixa um limite de palavras é para cumprir. A STT erra nomes próprios com frequência ("BUB" virou "Ruby" e "Boob" no meu próprio teste) — vale confirmar o alvo antes de agir em projeto.

Sobre a máquina: MacBook Pro Intel i9, Xcode 26.5, CocoaPods 1.17 só em ~/.gem/ruby/2.6.0/bin (fora do PATH) e em Ruby 2.6 — por isso o Expo precompiled falha com filter_map e todos os módulos compilam da fonte (lento, mas passa). Entrada e saída de áudio são as internas do MacBook, o que favorece captar som ambiente e o próprio TTS. Só havia Python 3.9.6 (uso 3.12 via uv), bash 3.2, cryptography em <49. O Vigia bloqueia comandos encadeados com ; e alguns pipes, e barra qualquer leitura do .env — rodar um comando por vez ou via script.
