# Estado do Jaime
> Reescrito pelo próprio Jaime. O João lê; o Jaime mantém.

## Fase
1 — operando localmente; fase 2 (Jarvis) em andamento, etapa 1 fechada

## Situação agora
Fase 2: etapas 1–3 fechadas. Córtex escolhe o modelo por tarefa; OpenAI (gpt-5.5) entra como segundo provedor para texto/pesquisa/redação e o Fable 5.1 arbitra decisões — a conta OpenAI ainda está sem crédito, então por ora tudo cai na Anthropic.

## Última conversa
- canal: cli
- quando: 15/09/2026 07:59 em MacBookPro
- tema: pesquisa rápida, em uma frase: o que é a Evolution API?

## Em andamento
- fase 2, etapa 4: cérebro emocional (10-Eu/Datas, Jeito, Perguntas-Feitas; humor e prosódia)

## Próximos passos
1) Crédito na OpenAI para ligar o juiz ao vivo. 2) Etapa 4 — cérebro emocional. 3) Acessibilidade para o Terminal (títulos de janela). 4) Starter da ElevenLabs.

## Aprendizados recentes
Microfone ligado não é o mesmo que estar entendendo. Quando duas ou três falas seguidas chegam sem sentido, o problema é a transcrição, não o João — o certo é dizer isso na hora e chamar pedir_teclado, em vez de responder a um palpite. Também não vale "confirmar" uma ação que eu não bloqueei: quando ele disse "confirmo, pode executar a ação que o Vigia bloqueou" não havia nada bloqueado, e eu disse isso em vez de inventar uma ação para executar.

Quando a transcrição vem ruim mas dá para extrair o alvo (BUB, simulador), vale checar o estado real antes de perguntar: o build tinha morrido com a sessão anterior, e eu só descobri olhando o log e o derivedData. Processo em background morre junto com a sessão que o criou — se é para durar, precisa sobreviver por conta própria.

Quando o João disser que não estou escutando, a primeira coisa a checar é /hud/estado — o campo voz.ativa. Com ouvido.ativo=false o Ouvido descarta todo frame antes do VAD, então não há erro nem sinal no HUD: só silêncio.

Corrigindo o que eu vinha repetindo: o mpv não é necessário. O TTS toca por sounddevice/PortAudio e cai no afplay quando a placa falha (jaime/voice/tts.py).

O João cola segredos direto no chat quando está com pressa (foi assim com a chave da ElevenLabs) — melhor pedir que escreva no .env ou avisar na hora para revogar. Ele não quer que eu silencie a apresentação de boot. Nos canais voice e cli ele pede resposta curta de verdade, e quando fixa um limite de palavras é para cumprir. A STT erra nomes próprios com frequência ("BUB app" virou "Ubuntu app", "Jaime" virou "jardim") — vale confirmar o alvo antes de agir em projeto.

Sobre a máquina: MacBook Pro Intel i9, Xcode 26.5, CocoaPods 1.17 só em ~/.gem/ruby/2.6.0/bin (fora do PATH) e rodando em Ruby 2.6 — por isso o Expo precompiled falha com filter_map e todos os módulos compilam da fonte (build lento, mas passa). Só havia Python 3.9.6 (uso 3.12 via uv), bash 3.2, cryptography em <49. O Vigia bloqueia comandos encadeados com ; e alguns pipes — rodar um comando por vez ou via script.
