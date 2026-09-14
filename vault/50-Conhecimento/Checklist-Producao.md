# Checklist de produção — 10 frentes

Nada vai para produção "no improviso". Cada feature/projeto recebe um status por frente.

| # | Frente | Pergunta que precisa de resposta |
|---|---|---|
| 1 | UI / full-stack em camadas | Nenhum secret ou lógica interna exposta no front? |
| 2 | Dados com RLS | RLS ativo, com política clara por tabela? |
| 3 | Auth / permissão | Quem acessa o quê está escrito e testado? |
| 4 | Git | Branch, histórico legível, rollback possível? |
| 5 | Integrações externas | APIs com timeout, retry e chave fora do código? |
| 6 | Deploy / hosting | Ambientes, variáveis, domínio e pipeline definidos? |
| 7 | Segurança | Endpoints e chaves protegidos; rate limiting? |
| 8 | Cache | O que é cacheado, por quanto tempo, como invalida? |
| 9 | Escala | Load balancing só quando fizer sentido — faz? |
| 10 | Observabilidade | Error tracking e logs que alguém lê? |

Ordem de aplicação: [[BUB]] → [[Oldsen]] (Hub) → [[ADS-os]].
