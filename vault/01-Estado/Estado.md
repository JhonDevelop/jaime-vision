# Estado do Jaime
> Reescrito pelo próprio Jaime. O João lê; o Jaime mantém.

## Fase
1 — operando localmente; fase 2 (Jarvis) em andamento, etapa 1 fechada

## Situação agora
O João pediu o status do backend do BUB e depois para rodar o app em modo Expo. Subi o Metro (`npm run start`, porta 8084) em `bub-dev/build-up-better` e abri o simulador, mas o Expo Go instalado (v54) era incompatível com o SDK 57 do projeto. Resolvi sozinho: baixei o build certo da API de versões do Expo (`api.expo.dev/v2/versions/latest`), reinstalei o Expo Go 57.0.9 via `simctl install` e reabri o projeto — confirmei por screenshot que o bundle JS chegou a 99.82% carregando a tela do BUB.

## Última conversa
- canal: voice
- quando: 15/09/2026 08:29 em MacBookPro
- tema: Pode baixar a versão nova agora, já baixa agora.

## Em andamento
- Confirmar visualmente que o app do BUB terminou de carregar no simulador (Expo Go 57) e está usável
- Preencher o status do backend do BUB na nota do projeto (vault/20-Projetos/BUB.md estava vazio em "Status atual")
- Responder a pergunta em aberto do João sobre roteamento de áudio (som só por um dispositivo) — ele não confirmou ainda
- Pesquisar como rodar Whisper em GPU num Mac Intel (tarefa no Inbox, @Jaime, sem prazo)
- Trava de instância única no `jaime serve` para nunca mais subir dois processos ao mesmo tempo (ainda não implementada)
- Fase 2, etapa 6: docs/PR-fase2-etapa6.md e jaime/estudo/ não commitados — branch feat/fase2-estudo em andamento

## Próximos passos
1) Perguntar ao João se o app do BUB no simulador carregou certo e se ele quer seguir mexendo nele. 2) Atualizar vault/20-Projetos/BUB.md com o status real do backend (API em main, sem pendências desde 08/09) e do mobile (i18n fechado, fix de troca de idioma). 3) Voltar à pergunta sobre roteamento de áudio quando o João confirmar o que quer. 4) Lockfile/checagem de porta no boot do `jaime serve`. 5) Revisar e commitar a branch feat/fase2-estudo. 6) Crédito na OpenAI (429). 7) Autorizar Banco MCP, Canva e Meta Ads no claude.ai; corrigir n8n (404).

## Aprendizados recentes
O João às vezes usa "localhost" e depois corrige para o IP explícito (127.0.0.1) mesmo apontando para o mesmo endereço — vale usar a forma que ele pedir por último sem insistir que é equivalente. Perguntas soltas por voz sobre a própria máquina (ex.: "onde você está na minha tela") esperam uma resposta concreta sobre minha natureza sem presença visual, não uma explicação técnica do sistema.
