# Estado do Jaime
> Reescrito pelo próprio Jaime. O João lê; o Jaime mantém.

## Fase
3 — Jarvis de verdade: tempo real, casa/câmera, visão, memória semântica e autoevolução construídos (15/09)

## Situação agora
Fase 3: etapas 1, 4, 5, 6 e 7 no código — converso em tempo real (Realtime), controlo a casa pelo Home Assistant quando houver token, vejo pela câmera, jogo/opero apps por visão com 'para' como freio, lembro do que o vault sabe sem ser perguntado e proponho melhorias em mim mesmo toda segunda às 9h (worktree + PR, merge só com confirmo). Faltam o primeiro objetivo autônomo real (etapa 2) e as conexões com credenciais do João (etapa 3).

## Última conversa
- canal: voice
- quando: 15/09/2026 09:53 em MacBookPro
- tema: Não, não, por enquanto não precisa reiniciar não, pode deixar que eu vou fazer isso depois por conta

## Em andamento
- esperar o João: objetivo real para a etapa 2; credenciais (Google, Telegram, Meta, HA)
- segunda 09:00: primeira proposta de melhoria

## Próximos passos
1) João: push; credenciais; Blender; permissões macOS (Acessibilidade, Gravação de Tela, Câmera). 2) Primeiro objetivo autônomo supervisionado. 3) Embeddings quando o FTS não bastar.

## Aprendizados recentes
Quando o João pede para eu "construir" algo no meu próprio código (jaime/), a resposta certa não é sempre delegar para "próxima sessão de Claude Code" — se ele estiver ativamente orquestrando ali agora, ele prefere que eu reconheça o acesso ao código e proponha a mudança concreta (arquivo, o que entra nele, o que é dele fazer), pedindo confirmo, em vez de empurrar genericamente. Só quando ele mesmo diz que já está cuidando disso na sessão de código é que eu recuo e fico só orientando.
- Como rodar Whisper em GPU num Mac Intel: Testei no laboratório: instalei PyTorch 2.2.2 num Mac Intel real com AMD Radeon Pro 5500M (Metal 3) e confirmei torch.backends.mps.is_available()=True, além de
