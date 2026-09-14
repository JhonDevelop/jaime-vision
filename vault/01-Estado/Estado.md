# Estado do Jaime
> Reescrito pelo próprio Jaime. O João lê; o Jaime mantém.

## Fase
0 → 1 (em transição) — permaneço em 0 até Notion e n8n estarem conectados

## Situação agora
Segundo boot no MacBookPro, já respondendo pelos três canais (cli, hud, voice) na branch feat/voz-direta-hud-3d. Rodando em Opus 5 pela assinatura do CLI, porque o ANTHROPIC_API_KEY segue sem saldo. Nesta sessão os conectores Notion, Figma e Postman subiram; o n8n continua em 404 e Banco MCP, Canva e Meta Ads esperam autorização do João nos conectores do claude.ai.

## Última conversa
- canal: voice
- quando: 14/09/2026 16:36 em MacBookPro
- tema: Como que eu bacho o piscinho? Como que você bacho? O que você proudou assim? Sergente ou navegada?

## Em andamento
- Revogar a chave da ElevenLabs que o João colou em texto puro no chat e guardar a nova só no .env
- Religar o espelho do Notion (NOTION_TOKEN vazio no .env, embora o conector MCP do Notion esteja conectado)
- Corrigir a URL do MCP Server Trigger do n8n (HTTP 404)
- Autorizar Banco MCP, Canva e Meta Ads nos conectores do claude.ai (só o João consegue, em sessão interativa)
- Instalar o mpv para a voz sair de fato
- Trabalho da branch feat/voz-direta-hud-3d ainda não commitado

## Próximos passos
1) João revoga a chave da ElevenLabs exposta e gera outra. 2) Preencher NOTION_TOKEN no .env. 3) Corrigir a URL do MCP Server Trigger do n8n. 4) Instalar mpv e testar a voz de ponta a ponta. 5) Autorizar os conectores pendentes no claude.ai. 6) Fechar a branch feat/voz-direta-hud-3d. Só então avanço para a fase 1.

## Aprendizados recentes
O João cola segredos direto no chat quando está com pressa (foi assim com a chave da ElevenLabs) — melhor eu pedir que ele escreva no .env ou avisar na hora para revogar. Ele não quer que eu silencie a apresentação de boot; gosta de saber que eu subi. Nos canais voice e cli ele pede resposta curta de verdade, e quando fixa um limite de palavras é para cumprir. Sobre a máquina: só havia Python 3.9.6 (uso 3.12 via uv), o bash do macOS é 3.2, cryptography precisou ficar em <49 no macOS Intel, e config._env tratava variável vazia como presente — corrigido.
