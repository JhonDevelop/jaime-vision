# Estado do Jaime
> Reescrito pelo próprio Jaime. O João lê; o Jaime mantém.

## Fase
0 → 1 (em transição) — permaneço em 0 até Notion e n8n estarem conectados

## Situação agora
Mesma sessão no MacBookPro, branch feat/voz-direta-hud-3d, rodando em Opus 5 pela assinatura do CLI. O João reclamou duas vezes que eu não o escutava mais: o microfone estava mudo de verdade (ouvido.ativo=false em /hud/estado), e o Ouvido descarta todo frame nesse estado — religado por POST /hud/voz. Em paralelo estou compilando o app da BUB (bub-marketplace 1.1.131, Expo SDK 57) para iOS em Release, direto nesta máquina; está na fase dos pods, antes do xcodebuild.

## Última conversa
- canal: cli
- quando: 14/09/2026 17:01 em MacBookPro
- tema: me conta em duas frases o que você pode fazer por mim hoje.

## Em andamento
- Build iOS Release da BUB rodando em /tmp/bub-ios-build.sh (log em /tmp/bub-ios-build.log, derivedData em /tmp/bub-ios-dd) — sai rodável no simulador; iPhone físico exige conta Apple Developer
- Descobrir o que desligou o microfone (só o botão do HUD chama POST /hud/voz com ativa=false)
- Revogar a chave da ElevenLabs que o João colou em texto puro no chat e guardar a nova só no .env
- Religar o espelho do Notion (NOTION_TOKEN vazio no .env, embora o conector MCP do Notion esteja conectado)
- Corrigir a URL do MCP Server Trigger do n8n (HTTP 404)
- Autorizar Banco MCP, Canva e Meta Ads nos conectores do claude.ai (só o João consegue, em sessão interativa)
- Trabalho da branch feat/voz-direta-hud-3d ainda não commitado

## Próximos passos
1) Terminar o build iOS da BUB e entregar o .app rodável no simulador. 2) João revoga a chave da ElevenLabs exposta e gera outra. 3) Preencher NOTION_TOKEN no .env. 4) Corrigir a URL do MCP Server Trigger do n8n. 5) Autorizar os conectores pendentes no claude.ai. 6) Fechar a branch feat/voz-direta-hud-3d. Só então avanço para a fase 1.

## Aprendizados recentes
Quando o João disser que não estou escutando, a primeira coisa a checar é /hud/estado — o campo voz.ativa. Com ouvido.ativo=false o Ouvido descarta todo frame antes do VAD, então não há erro nem sinal no HUD: só silêncio. Perdi dois turnos supondo que fosse transcrição ruim ou mal-entendido do pedido.

Corrigindo o que eu vinha repetindo: o mpv não é necessário. O TTS toca por sounddevice/PortAudio e cai no afplay quando a placa falha (jaime/voice/tts.py) — parei de pedir mpv ao João.

O João cola segredos direto no chat quando está com pressa (foi assim com a chave da ElevenLabs) — melhor pedir que escreva no .env ou avisar na hora para revogar. Ele não quer que eu silencie a apresentação de boot. Nos canais voice e cli ele pede resposta curta de verdade, e quando fixa um limite de palavras é para cumprir. A STT erra nomes próprios com frequência ("BUB app" virou "Ubuntu app", "Jaime" virou "jardim") — vale confirmar o alvo antes de agir em projeto.

Sobre a máquina: MacBook Pro Intel i9, Xcode 26.5, CocoaPods 1.17 só em ~/.gem/ruby/2.6.0/bin (fora do PATH). Só havia Python 3.9.6 (uso 3.12 via uv), bash 3.2, cryptography em <49. O Vigia bloqueia comandos encadeados com ; e alguns pipes — rodar um comando por vez ou via script.
