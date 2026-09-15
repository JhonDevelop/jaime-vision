# Problemas em aberto

## P-0001 · pesquisa isso depois: como rodar Whisper em GPU num Mac Intel. por agora só confirma em uma frase qu · resolvido · 2026-09-15
- origem: joao_pediu
- contexto: Anotado no Inbox.
- tentativas: 0
- conhecimento: 50-Conhecimento/como-rodar-whisper-em-gpu-num-mac-intel.md
### Tentativas
- (nenhuma)

## P-0002 · Ferramenta falha repetidamente: Input validation error: 'corpo' is a required property · resolvido · 2026-09-15
- origem: ferramenta_falhou
- contexto: Input validation error: 'corpo' is a required property
- tentativas: 0
- conhecimento: 50-Conhecimento/ferramenta-falha-repetidamente-input-validation-error-corpo-is-a-required-property.md
### Tentativas
- (nenhuma)

## P-0003 · Reconhecimento do dono por voz (resemblyzer) tranca o João quando o áudio vem ruim: como calibrar limiar e decisão · resolvido · 2026-09-15
- origem: joao_pediu
- contexto: jaime/voice/falantes.py compara embeddings do resemblyzer com o perfil do João (5 frases). Hoje de manhã o João disse 'tenho que falar a palavra mas não deixa eu usar' — palavra-passe só vale na voz dele e o áudio do mic interno chega com ruído. Estudar: limiar por similaridade de cosseno típico, normalização de score, várias amostras de cadastro, média móvel entre falas, e um fallback seguro (senha digitada / pedir para repetir) que não abra para estranhos. Entregar recomendação numérica e um script de teste reproduzível no sandbox.
- tentativas: 0
- conhecimento: 50-Conhecimento/reconhecimento-do-dono-por-voz-resemblyzer-tranca-o-joao-quando-o-audio-vem-ruim-como-calibrar-limiar-e-decisao.md
### Tentativas
- (nenhuma)

## P-0004 · Notificações do Instagram num Mac Intel: por onde chegam e qual o formato na Central de Notificações · aberto · 2026-09-15
- origem: joao_pediu
- contexto: jaime/ops/notificacoes.py lê o banco do usernoted (req.titl/subt/body). O João quer ser avisado em voz alta de DMs do Instagram, mas nenhuma notificação do Instagram apareceu no banco. Descobrir: em Mac Intel (sem app iPad) as opções são web push do Chrome/Safari (instagram.com) ou Espelhamento do iPhone; qual bundle id cada caminho usa, como ficam titl/subt/body para DM vs curtida/seguidor, e o que o João precisa ativar. Entregar tabela de formatos e recomendação.
- tentativas: 0
### Tentativas
- (nenhuma)

## P-0005 · Ler Mensagens do iPhone no Mac via chat.db: esquema, como distinguir grupo e contato salvo, leitura segura · aberto · 2026-09-15
- origem: joao_pediu
- contexto: Acesso Total ao Disco já está liberado para .venv/bin/python. Próximo passo do roadmap: ler ~/Library/Messages/chat.db só leitura. Estudar tabelas message/handle/chat/chat_message_join, campo attributedBody (texto vem vazio em versões novas — como decodificar), como saber se é grupo, como mapear handle → nome de contato (AddressBook), e como abrir o SQLite em modo ro sem travar o app Mensagens. Entregar consultas SQL prontas e testadas no sandbox com um banco sintético.
- tentativas: 0
### Tentativas
- (nenhuma)

## P-0006 · Avisar e-mails novos de pessoas (não automáticos) pela Gmail API sem polling caro · aberto · 2026-09-15
- origem: joao_pediu
- contexto: Quando o OAuth do Google fechar, o Jaime terá mcp__google__*. Estudar: users.history.list + historyId vs users.messages.list com q='newer_than:1h -category:promotions -category:social', custo de cota por chamada, intervalo razoável, e um critério prático de 'remetente humano' (List-Unsubscribe, Precedence: bulk, no-reply, categoria). Entregar a estratégia e um exemplo de código no sandbox.
- tentativas: 0
### Tentativas
- (nenhuma)
