---
name: avisar-e-mails-novos-de-pessoas-nao-automaticos-pela-gmail-api-sem-polling-caro
description: Qualquer notificação futura de 'e-mail novo relevante' do Jaime via mcp__google__* (Gmail), assim que o OAuth do Google fechar; o mesmo filtro de reme
---

Para qualquer 'avisar X novo via API de terceiro sem polling caro': 1) checar se a API tem um endpoint de 'delta/cursor' (tipo historyId) mais barato que listar tudo; 2) medir custo real de cota/rate-limit via docs oficiais antes de supor; 3) separar 'polling barato de detecção' (delta) de 'polling caro de detalhe' (get completo), rodando o caro só nos candidatos; 4) construir o filtro de relevância como função pura testável com dados sintéticos, sem depender de credenciais reais.
