# Rotinas

> Uma por linha: `- <cron> · <ordem para o Jaime>`. Cron de 5 campos (min hora dia mês dia-da-semana), fuso America/Sao_Paulo.
> O scheduler lê no boot e recarrega quando este arquivo muda. A ordem é dita ao Jaime como se fosse o João.
> Tabela da fase 3 (docs/FASE-3-TEMPO-REAL.md §5). Dia da semana por nome (mon…sun): no APScheduler 0 é segunda, não domingo.

## Dia

- 30 6 * * mon-fri · preparar o dia: clima, agenda, aniversários e pendências; deixa o briefing pronto antes de eu acordar
- 0 7 * * mon-fri · briefing
- 0 13 * * mon-fri · revisão de tarefas: o que venceu, o que trava; uma pergunta só se precisar
- 0 18 * * mon-thu,sat,sun · fecha o dia: diário → projetos → Estado → Notion; três linhas para mim
- 0 18 * * fri · fecha o dia e depois fecha a semana: pensamentos → aprendizados; placar; propostas; Uso.md
- 0 20 * * sun · auto-avaliação: o que melhorei, o que quero estudar, o que quero criar; atualiza Estado e Fase
- 0 22 * * * · consolida o que ouvi hoje

## Mantidas da fase 2

- 0 9 * * mon · propor melhoria
- 30 23 * * * · estuda os projetos

## Janelas (não são cron — vivem em jaime/agenda/scheduler.py)

- 08h–18h · modo atento: prioridade total às demandas; nada de estudo/criação se houve fala nos últimos 15 min (`modo_atento`)
- ocioso > 15 min · um ciclo de estudo (90-Estudo/Prioridades.md) ou um ciclo da Mente (`pode_estudar`)
- 21h–06h · noite criativa: projetos autônomos e criações próprias, sem tocar em nada meu (`noite_criativa` / `pode_criar`)

Orçamento diário: `JAIME_ORCAMENTO_DIA_USD` no .env, dividido 60% demandas · 25% estudo · 15% criação (01-Estado/Orcamento.md). Quando acaba, só demandas.
