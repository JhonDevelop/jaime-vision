# PR — Fase 2, etapa 8: conexões Google e Telegram

**Branch:** `feat/fase2-conexoes` → `main`

## O que muda
- `jaime/conexoes/registro.py` → `01-Estado/Conexoes.md` (serviço, escopo, autorizado, revogar, último uso).
- `jaime/conexoes/google.py` + `tools.py`: OAuth do projeto próprio (`python -m jaime conectar google`), token local;
  MCP `google`: `email_hoje`, `email_buscar`, `email_rascunho`, `email_enviar` (Vigia), `agenda_dia`, `agenda_criar`, `conexoes`.
- `jaime/conexoes/telegram.py`: bot por long polling, só o dono (`JAIME_OWNER_TELEGRAM_ID`), canal `telegram`.
- `docs/CONEXOES.md`: passo a passo Google Cloud (projeto, APIs, consentimento, credencial Desktop) e BotFather.
- Vigia: `email_enviar`/`enviar` na lista de ações que esperam "confirmo".
- Voz: reserva masculina `Eddy (Português (Brasil))`; ElevenLabs volta sozinha 10 min após 3 falhas.

## Como testar
```
pytest -q                                   # 76 testes; Gmail/Calendar com dublês, Telegram só do dono, Vigia no envio
python -m jaime conectar google             # depois de salvar ~/Jaime/google-client-secret.json
```

## Critério §3 linha 8
Lê e-mails de hoje; cria evento; responde pelo Telegram — código e testes prontos; ao vivo depende da credencial
Google e do token do bot, que só o João pode criar.
