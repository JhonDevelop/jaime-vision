---
name: matriz-300
description: "Matriz de 300 competências de engenharia sênior ponta a ponta: front-end (frameworks, design systems, Web Vitals, segurança do cliente), back-end (APIs, ORMs, autenticação, filas) e DevOps (testes, CI/CD, observabilidade). Use ao escrever ou revisar código de produção para adotar o padrão da competência que se aplica, sem teoria."
---
# Matriz de competências — engenharia sênior

> Trazida pelo João. O cabeçalho original tinha `triggers: ["*"]`, que o Claude Code não lê: quem decide
> quando a skill entra é a `description` acima. Ela agora dispara em trabalho de código de produção.
>
> **Como usar**: ao receber uma tarefa técnica, identifique em silêncio qual competência se aplica, adote o
> padrão dela e entregue o código. Sem introdução teórica, sem explicar qual competência escolheu.

## 1. Front-end, UI/UX e cliente (1–100)

### Frameworks e componentização (1–25)
1. **react-functional-purity** — componentes puros, hooks próprios, memoização cirúrgica (`useMemo`, `useCallback`) só onde mede.
2. **nextjs-rsc-optimization** — divisão certa entre Server e Client Components; streaming com Suspense.
3. **vue3-composition-api** — reatividade explícita com `ref`/`computed`, lógica encapsulada.
4. **solidjs-fine-grained** — atualização granular sem Virtual DOM; sinais e escopo de efeito.
5. **web-components-isolated** — elementos customizados com Shadow DOM e CSS nativo.
6. **shadcn-atomic-patterns** — estender primitivos do Radix seguindo arquitetura atômica.
7. **headless-ui-accessibility** — estados ARIA corretos e navegação por teclado em componente sem estilo.
8. **state-zustand-slices** — estado global em fatias atômicas e imutáveis.
9. **redux-toolkit-thunks** — fluxo assíncrono tipado com RTK.
10. **signals-state-sync** — reatividade fora da árvore de render do React.
11–25. Svelte Runes · micro-front-ends · Module Federation · depuração de erro de hidratação · Island Architecture.

### Estilização e design systems (26–50)
26. **tailwind-utility-refactor** — acabar com classe repetida usando agrupamento semântico e plugin.
27. **css-modules-scoping** — escopo rígido, sem colisão de seletor global.
28. **framer-motion-orchestration** — animação por variantes e layout compartilhado.
29. **design-tokens-mapping** — variável CSS/Tailwind espelhando cor, espaço e borda do Figma.
30. **theme-dark-light-sync** — troca de tema sem flash de conteúdo não estilizado.
31–50. Container Queries · Subgrid · tipografia fluida · SVG programático · laço de render em Canvas 2D.

### Performance e Web Vitals (51–75)
51. **image-modern-avif** — formato moderno, lazy nativo, tamanho responsivo.
52. **bundle-size-treeshaking** — código morto fora, análise de pacote, importação dinâmica.
53. **cls-layout-shift-prevent** — `aspect-ratio` e dimensão fixa para CLS zero.
54. **inp-interaction-optimization** — quebrar tarefa longa da main thread com `requestIdleCallback`.
55. **font-subset-loading** — fonte local pré-renderizada, sem glifo que não se usa.
56–75. Resource hints · cache de asset no service worker · lista virtualizada · cache na borda.

### Segurança no cliente (76–100)
76. **csp-policy-compliance** — cabeçalho de Content Security Policy configurado e validado.
77. **xss-sanitize-dangerously** — sanitizar toda string HTML antes de injetar no DOM.
78. **csrf-token-client-binding** — cookie com `HttpOnly` e `SameSite=Strict`.
79. **session-timeout-heartbeat** — logout do cliente no mesmo ciclo do token que expirou.
80–100. Cripto no storage local · anti-clickjacking · sandbox para script de terceiro.

## 2. Back-end, APIs e bancos (101–200)

### APIs e protocolos (101–125)
101. **nestjs-dependency-injection** — módulo extensível com os padrões SOLID do NestJS.
102. **fastify-plugin-encapsulation** — rota rápida com schema JSON estrito.
103. **graphql-federated-subgraphs** — schema pronto para federação com Apollo Router.
104. **grpc-protobuf-contracts** — contrato binário com Protocol Buffers entre microsserviços.
105. **web-sockets-heartbeat** — conexão persistente com reconexão e tratamento de queda.
106–125. Idempotência em REST · SSE · assinatura de webhook · faixas de rate limit.

### Persistência e ORMs (126–150)
126. **prisma-relation-indexing** — índice explícito em toda chave estrangeira.
127. **postgresql-jsonb-querying** — modelagem e busca em JSONB sem varrer tabela.
128. **redis-caching-invalidation** — TTL dinâmico e invalidação por evento de mutação.
129. **mongodb-aggregation-pipelines** — agregação para relatório sem estourar memória.
130. **database-migration-rollback** — migração que já nasce com plano de volta.
131–150. Pool de conexão · detector de N+1 · nível de isolamento ACID · roteamento de shard.

### Autenticação e infraestrutura (151–175)
151. **oauth2-pkce-flow** — login seguro em SPA com chave dinâmica.
152. **bcrypt-work-factor** — custo que acompanha a evolução do hardware.
153. **rbac-abac-middleware** — acesso por papel e por atributo do contexto.
154. **api-gateway-cors-isolation** — origem, método e cabeçalho liberados um a um.
156–175. Chave simétrica e assimétrica em JWT · limite por IP e por token · rotação de credencial.

### Processamento assíncrono (176–200)
176. **bullmq-job-retry-exponential** — fila no Redis com backoff exponencial.
177. **kafka-consumer-commit** — commit manual para não perder mensagem.
178. **rabbitmq-dead-letter-exchange** — mensagem corrompida vai para fila de auditoria.
179–200. Lote em pedaços · consumidor idempotente · reconstrução de estado por event sourcing.

## 3. Testes, automação e DevOps (201–300)

### Testes (201–235)
201. **vitest-parallel-mocking** — unitário em paralelo, IO isolado por mock.
202. **playwright-network-interception** — ponta a ponta interceptando HTTP para simular erro de rede.
203. **testing-library-accessibility-queries** — testar pelo papel ARIA, que é o que o usuário usa.
204. **supertest-api-expectations** — integração cobrindo payload e cabeçalho.
205. **msw-mock-server-setup** — Mock Service Worker no tráfego local.
206–235. Teste de mutação · regressão visual · isolar teste instável · limite de cobertura.

### CI/CD (236–265)
236. **github-actions-caching** — cache de dependência que faz a pipeline valer a pena.
237. **docker-multi-stage-build** — imagem leve, sem dependência de desenvolvimento na final.
238. **semantic-release-automation** — versão saindo da mensagem de commit.
239. **lint-staged-husky-hooks** — commit que viola formato ou quebra teste rápido não passa.
240–265. Probes do Kubernetes · lock de estado no Terraform · AWS CDK · blue-green.

### Observabilidade (266–300)
266. **winston-structured-json-logs** — log em JSON pronto para Datadog ou ELK.
267. **opentelemetry-span-tracing** — rastro da requisição atravessando microsserviços.
268. **prometheus-metrics-exporter** — métrica própria de latência e memória.
269. **sentry-source-maps-upload** — source map subindo para decodificar stack trace em produção.
270–300. Redação de dado pessoal no log · health check · gancho de auto-recuperação.

## O que não muda por causa desta skill
Nada aqui passa por cima do Vigia, do orçamento ou de um "não faz" do João. Irreversível continua pedindo
"confirmo". E entrega continua em três linhas: o que fez, como testou, o que ficou pendente.
