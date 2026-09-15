# Saúde, passos e sono no Jaime

Não há API do Apple Health/Google Fit acessível de um Mac. O caminho oficial e que funciona é o **celular enviar** os
dados para o Jaime, uma vez por dia (ou quando você quiser), por HTTP.

## iPhone — atalho automático (Shortcuts), 5 minutos
1. App **Atalhos** › Automação › **Hora do dia** (ex.: 22:30, diariamente) › Executar imediatamente.
2. Ações, nesta ordem:
   - *Localizar amostras de saúde* → Tipo **Passos**, Período **Hoje** → *Calcular estatística* (Soma) → variável `passos`
   - *Localizar amostras de saúde* → **Frequência cardíaca** (Hoje) → Média → `fc`
   - *Localizar amostras de saúde* → **Análise do sono** (Últimas 24 h) → Soma da duração → `sono`
   - *Obter conteúdo da URL* → `https://macbookpro.<tailnet>.ts.net/ask` (ver docs/REMOTO.md) · método **POST** ·
     cabeçalho `X-Jaime-Token: <JAIME_SERVER_TOKEN>` · corpo JSON:
     `{"texto": "saúde de hoje: passos=<passos>, fc média=<fc>, sono=<sono> min", "canal": "saude"}`
3. O Jaime registra no diário (`registrar_diario`), guarda em `10-Eu/Saude.md` (`lembrar`) e comenta só se algo fugir do
   normal (ex.: sono < 5 h três dias seguidos) — a regra está no prompt de rotina; ajuste em `30-Tarefas/Rotinas.md`.

## Android
Google Fit/Health Connect → app **MacroDroid** ou **Tasker** (gatilho diário → ler Health Connect → HTTP POST igual acima).

## Apple Watch / anel
Tudo passa pelo Health do iPhone; o atalho acima já cobre.

## O que ele faz com isso
- Briefing das 07:00 cita passos e sono de ontem quando existem.
- "como estou de saúde?" → resumo da semana a partir de `10-Eu/Saude.md`.
- Cérebro emocional: sono ruim → tom mais cuidadoso, sem cobrança.
