# Estado do Jaime
> Reescrito pelo próprio Jaime. O João lê; o Jaime mantém.

## Fase
0 → 1 (em transição) — permaneço em 0 até Notion e n8n estarem conectados

## Situação agora
Primeiro boot concluído no MacBookPro. Instalação, testes (9 passando), CLI claude 2.1.270 e acesso por palavra-passe funcionando. Máquina registrada em Maquinas.md. Respondendo pelo canal cli.

## Última conversa
- canal: hud
- quando: 14/09/2026 15:53 em MacBookPro
- tema: 12341234

## Em andamento
Conectar Notion (NOTION_TOKEN vazio) e corrigir a URL do MCP Server Trigger do n8n (HTTP 404). Testar voz (falta instalar mpv). Resolver saldo do ANTHROPIC_API_KEY em Billing — por ora rodando pela assinatura do CLI claude.

## Próximos passos
1) João preencher NOTION_TOKEN para religar o espelho do Notion. 2) Corrigir a URL do MCP Server Trigger do n8n. 3) Instalar mpv e testar a voz. 4) Decidir sobre saldo do ANTHROPIC_API_KEY. Só então avanço para a fase 1.

## Aprendizados recentes
Nesta máquina: só havia Python 3.9.6 (Jaime precisa >=3.11, resolvido via uv); bash do macOS é 3.2 e não aceita sintaxe de bash 4 (install.sh corrigido); cryptography precisou ser fixada em <49 no macOS Intel; config._env tratava variável de ambiente vazia como presente, o que derrubava a palavra-passe quando JAIME_PASSPHRASE_HASH vinha vazio — corrigido para tratar vazio como ausente.
