# PR — Fase 2, etapas 11 e 12: Meta (WhatsApp Cloud + Instagram) e modo autônomo

**Branch:** `feat/fase2-meta-autonomo` → `main`

## Etapa 11 — Meta
- `jaime/conexoes/meta.py`: webhook `/webhook/meta` (GET handshake; POST com `X-Hub-Signature-256` verificada),
  parsing de WhatsApp Cloud API e Instagram Messaging; dono responde direto; terceiro → resumo + rascunho pendente
  (`mensagens_pendentes`), envio só com "confirmo" (`enviar_whatsapp`, `enviar_instagram` no Vigia).
- `docs/CONEXOES.md` › Meta: app, produtos, token permanente, app secret, webhook, revisão para DMs de qualquer pessoa.
- Evolution API (WhatsApp pessoal) documentada como opcional, com o risco explícito.

## Etapa 12 — modo autônomo
- `jaime/autonomo.py`: `objetivo(texto, limite_horas)` → o Jaime decompõe em 3–8 etapas com critério de aceite → executa
  etapa a etapa com checkpoint (diário + HUD) → pausa quando o Vigia bloqueia; o "confirmo" retoma sem gastar turno →
  relatório em 40-Diario com próximos passos. Limites: `JAIME_AUTONOMO_HORAS`, `JAIME_AUTONOMO_CUSTO_USD`,
  `JAIME_AUTONOMO_FERRAMENTAS`. MCP `autonomo`: `objetivo`, `situacao`.

## Como testar
```
pytest -q                                   # 89 testes; Meta com HTTP dublê e assinatura real; autônomo com pausa/retomada e limite de custo
# HUD: "objetivo: prepara o lançamento da coleção nova, limite 1 hora" → painel Produção mostra etapa N/M
```

## Critérios §3 linhas 11–12
DM de terceiro respondida com confirmo (fluxo testado com dublês; ao vivo depende do app Meta). Objetivo de 2 h com
checkpoints e relatório no diário (teste offline cobre plano, pausa pelo Vigia, retomada por "confirmo", limite).
