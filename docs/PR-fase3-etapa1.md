# PR — Fase 3, etapa 1: conversa em tempo real (GPT-Realtime-2)

**Branch:** `feat/fase3-tempo-real` → `main`

## O que muda
- `docs/FASE-3.md`: as 7 etapas da fase 3 com critérios de pronto.
- `jaime/voice/tempo_real.py`: `Conversa` — WebSocket Realtime, VAD do servidor com `create_response=false` (nós decidimos
  quando responder), gate "é comigo?" igual ao da fase 2, palavra-passe/teclado/renomear pelo `_porta` (o Realtime repete),
  ferramentas `jaime` (Agent SDK), `hora`, `clima`, `lembrete`; áudio de saída no `sounddevice`; mic mudo enquanto fala.
- Microfone só transmitido com voz humana detectada pelo Silero local (pré-roll + cauda) — parado não custa.
- `server.py`: `JAIME_VOZ_MODO=conversa` liga a `Conversa` no lugar do `Ouvido`; `.env`: `JAIME_REALTIME_MODEL`, `JAIME_REALTIME_VOZ`.

## Validado ao vivo
Sonda do protocolo com `gpt-realtime-2`: sessão, item de texto, chamada de ferramenta (`hora`) com `call_id`,
`function_call_output`, 3,2 s de áudio de volta.

## Como testar
```
pytest -q                                   # 94 testes; Realtime com WebSocket falso
JAIME_VOZ_MODO=conversa python -m jaime hud  # "Jaime, que horas são?" em < 1 s; "Jaime, abre o Finder" → ferramenta jaime
```
