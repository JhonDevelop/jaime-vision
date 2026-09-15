# Estado do Jaime
> Reescrito pelo próprio Jaime. O João lê; o Jaime mantém.

## Fase
1 — operando localmente; fase 2 (Jarvis) em andamento, etapa 1 fechada

## Situação agora
Fase 2 em andamento. Etapa 2 fechada: o Córtex escolhe o modelo por tarefa (Fable 5.1 para decisão, Opus 5 para código, Sonnet no geral, Haiku para rotina) e o placar em 01-Estado/Placar.md aprende com acertos e correções do João.

## Última conversa
- canal: cli
- quando: 15/09/2026 07:47 em MacBookPro
- tema: não era isso. em uma frase: que horas são?

## Em andamento
- fase 2, etapa 3: OpenAI como segundo provedor + juiz (docs/FASE-2-JARVIS.md §2.1)

## Próximos passos
1) Córtex + placar (docs/FASE-2-JARVIS.md §2.1). 2) NOTION_TOKEN. 3) Permissão de Acessibilidade para o Terminal (títulos de janela). 4) Plano Starter da ElevenLabs para a voz brasileira.

## Aprendizados recentes
Quando o João disser que não estou escutando, a primeira coisa a checar é /hud/estado — o campo voz.ativa. Com ouvido.ativo=false o Ouvido descarta todo frame antes do VAD, então não há erro nem sinal no HUD: só silêncio. Perdi dois turnos supondo que fosse transcrição ruim ou mal-entendido do pedido.

Corrigindo o que eu vinha repetindo: o mpv não é necessário. O TTS toca por sounddevice/PortAudio e cai no afplay quando a placa falha (jaime/voice/tts.py) — parei de pedir mpv ao João.

O João cola segredos direto no chat quando está com pressa (foi assim com a chave da ElevenLabs) — melhor pedir que escreva no .env ou avisar na hora para revogar. Ele não quer que eu silencie a apresentação de boot. Nos canais voice e cli ele pede resposta curta de verdade, e quando fixa um limite de palavras é para cumprir. A STT erra nomes próprios com frequência ("BUB app" virou "Ubuntu app", "Jaime" virou "jardim") — vale confirmar o alvo antes de agir em projeto.

Sobre a máquina: MacBook Pro Intel i9, Xcode 26.5, CocoaPods 1.17 só em ~/.gem/ruby/2.6.0/bin (fora do PATH). Só havia Python 3.9.6 (uso 3.12 via uv), bash 3.2, cryptography em <49. O Vigia bloqueia comandos encadeados com ; e alguns pipes — rodar um comando por vez ou via script.
