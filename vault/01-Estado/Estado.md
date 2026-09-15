# Estado do Jaime
> Reescrito pelo próprio Jaime. O João lê; o Jaime mantém.

## Fase
1 — operando localmente; fase 2 (Jarvis) em andamento, etapa 1 fechada

## Situação agora
Fase 2: etapas 1–5 fechadas. Tenho agenda própria: rotinas em 30-Tarefas/Rotinas.md (briefing 07:00 dias úteis, fecha a semana sexta 18:00), lembretes por voz, e respondo hora, data, clima e feriado sem gastar modelo. n8n saiu de vez.

## Última conversa
- canal: voice
- quando: 15/09/2026 08:16 em MacBookPro
- tema: Me adora o que está acontecendo com o Mama.

## Em andamento
- Esperando o João digitar no teclado do HUD ou trocar o áudio de entrada (fone com microfone) — a voz segue chegando embaralhada
- Revogar a chave da ElevenLabs que o João colou em texto puro no chat e guardar a nova só no .env
- Religar o espelho do Notion (NOTION_TOKEN vazio no .env, embora o conector MCP do Notion esteja conectado)
- Corrigir a URL do MCP Server Trigger do n8n (HTTP 404)
- Autorizar Banco MCP, Canva e Meta Ads nos conectores do claude.ai (só o João consegue, em sessão interativa)
- Trabalho da branch feat/voz-direta-hud-3d ainda não commitado

## Próximos passos
1) Voltar a entender o João: fone com microfone ou o teclado do HUD; se persistir, olhar o VAD e o ganho de entrada em jaime/voice/escuta.py. 2) João revoga a chave da ElevenLabs exposta e gera outra. 3) Preencher NOTION_TOKEN no .env. 4) Corrigir a URL do MCP Server Trigger do n8n. 5) Autorizar os conectores pendentes no claude.ai. 6) Fechar a branch feat/voz-direta-hud-3d. Só então avanço para a fase 1. (O build iOS da BUB saiu do caminho — está rodando no simulador.)

## Aprendizados recentes
Microfone ligado não é o mesmo que estar entendendo. Quando duas ou três falas seguidas chegam sem sentido, o problema é a transcrição, não o João — o certo é dizer isso na hora e chamar pedir_teclado, em vez de responder a um palpite. Também não vale "confirmar" uma ação que eu não bloqueei: quando ele disse "confirmo, pode executar a ação que o Vigia bloqueou" não havia nada bloqueado, e eu disse isso em vez de inventar uma ação para executar.

Quando a transcrição vem ruim mas dá para extrair o alvo (BUB, simulador), vale checar o estado real antes de perguntar: o build tinha morrido com a sessão anterior, e eu só descobri olhando o log e o derivedData. Processo em background morre junto com a sessão que o criou — se é para durar, precisa sobreviver por conta própria.

Quando o João disser que não estou escutando, a primeira coisa a checar é /hud/estado — o campo voz.ativa. Com ouvido.ativo=false o Ouvido descarta todo frame antes do VAD, então não há erro nem sinal no HUD: só silêncio.

Corrigindo o que eu vinha repetindo: o mpv não é necessário. O TTS toca por sounddevice/PortAudio e cai no afplay quando a placa falha (jaime/voice/tts.py).

O João cola segredos direto no chat quando está com pressa (foi assim com a chave da ElevenLabs) — melhor pedir que escreva no .env ou avisar na hora para revogar. Ele não quer que eu silencie a apresentação de boot. Nos canais voice e cli ele pede resposta curta de verdade, e quando fixa um limite de palavras é para cumprir. A STT erra nomes próprios com frequência ("BUB app" virou "Ubuntu app", "Jaime" virou "jardim") — vale confirmar o alvo antes de agir em projeto.

Sobre a máquina: MacBook Pro Intel i9, Xcode 26.5, CocoaPods 1.17 só em ~/.gem/ruby/2.6.0/bin (fora do PATH) e rodando em Ruby 2.6 — por isso o Expo precompiled falha com filter_map e todos os módulos compilam da fonte (build lento, mas passa). Só havia Python 3.9.6 (uso 3.12 via uv), bash 3.2, cryptography em <49. O Vigia bloqueia comandos encadeados com ; e alguns pipes — rodar um comando por vez ou via script.
