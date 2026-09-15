# PR — Fase 2, etapa 5: agenda própria, relógio, clima, feriados, lembretes

**Branch:** `feat/fase2-agenda` → `main`

## O que muda
- `jaime/agenda/`: `scheduler.py` (APScheduler no processo; `30-Tarefas/Rotinas.md` com recarga automática),
  `lembretes.py` (linguagem natural → `30-Tarefas/Lembretes.md` + job de data), `relogio.py`, `clima.py` (Open-Meteo),
  `feriados.py` (`holidays` BR+SP), `tools.py` (MCP `mundo`: agora, clima, feriado_hoje, criar_lembrete, rotinas).
- `Jaime._mundo()`: hora, data, clima e "me lembra…" respondidos sem modelo (milissegundos), antes do Córtex.
- Rotinas padrão: `0 7 * * 1-5 · briefing`, `0 18 * * 5 · fecha a semana`. HUD mostra disparos e lembretes.
- `momento.py` passa a usar `holidays`. `.env.example`: `JAIME_LAT/LON`. `pyproject`: apscheduler, holidays.

## Como testar
```
pytest -q                                   # 62 testes (relógio falso, sem rede)
# no HUD: "que horas são?" / "vai chover hoje?" / "me lembra em 2 min de beber água" → resposta imediata; o lembrete
# dispara falado e aparece no HUD; 30-Tarefas/Lembretes.md marca [x].
```

## Critério §3 linha 5
Briefing 07:00 sem n8n (rotina no scheduler); "que horas/clima" respondidos localmente; lembrete de N min dispara.
