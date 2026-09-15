# Retomar — onde paramos (15/09/2026, ~11:00, sessão do Claude Code)

> Para a próxima sessão: cole "Leia docs/RETOMAR.md e continue de onde paramos" no `claude` aberto nesta pasta.

## Estado
- **Jaime roda como serviço** `com.jaime` (LaunchAgent; `bash jaime/ops/servico.sh status|parar|ligar`). Uma instância só —
  `jaime serve/hud` recusa subir se a porta 8787 já tem um Jaime. Log: `~/Jaime/jaime.log`.
- `main` está em dia com `origin/main` (algum app do João empurra os commits sozinho logo depois que aparecem; o shell do
  Claude Code não tem credencial HTTPS do GitHub nem chave SSH autorizada).
- Testes: `pytest -q` → 119 verdes.
- Fase 2: 12/12. Fase 3: etapas 1, 4, 5, 6, 7 feitas; **2** (objetivo autônomo real) espera um objetivo do João;
  **3** (conexões) espera o testador do Google e a página do Notion (abaixo).

## Fase 3 — tempo real (branch `feat/fase3-duplex`, 15/09 tarde)
- Tese e prompts em `docs/FASE-3-TEMPO-REAL.md`; guia do Maestri em `docs/MAESTRI.md`.
- **Prompt A pronto** (etapas 1 e 2): `jaime/voice/stt_stream.py` (Deepgram ao vivo com parciais; OpenAI Realtime; Whisper
  pseudo-stream), `antecipador.py` (heurística + modelo rápido OpenAI, cache, `confere()`), `duplex.py` (`DetectorFim`
  450/700/1200 ms conforme "frase fechou?", `OuvidoDuplex` com transcrição viva, resposta especulativa, barge-in com
  guarda de eco, métricas). `tts.py`: `pre_sintetizar`, `tocar_pronto`, `parar()` < 100 ms, velocidade 1.15×.
  `escuta.py`: `_tratar_texto` compartilhado + `Latencias` (linha por turno no diário, evento `latencia` no HUD).
  HUD: "você (ao vivo)" com cursor, feed do antecipador e da latência. `.env`: `JAIME_VOZ_MODO=duplex` (ligado 15/09 ~13:50).
  Testes: `tests/test_duplex.py` (13) — suíte 132 verdes. **Falta validar ao vivo** (falar com ele e ler as latências no diário).
- Próximos: Prompt B (fila de demandas `fila.py`, Vigia por lote + confiança progressiva, JAIME_INTERROMPER), C (persona
  enxuta por voz, `python -m jaime voz latencia`), D e E via recrutas no Maestri (precisa do toggle Maestro no terminal).
- Maestri: o CLI funciona daqui usando `MAESTRI_SOCKET` + `MAESTRI_TERMINAL_ID` do terminal "Cerebro Principal Jaime";
  recrutar exige Maestro ligado nesse terminal.

## Última rodada (15/09, manhã)
- **Loop de crash resolvido**: 24 segfaults (torch + onnxruntime no mesmo processo) até 10:14; `falantes_worker` separado; estável desde 10:16.
  O diário do dia tinha 51 linhas de "Jaime iniciado" + 27 de "Saúde do cérebro" (o aviso citava o próprio diário e se
  multiplicava a cada reinício) — consolidadas numa linha só.
- **Vigia afrouxado** (`jaime/vigia/hooks.py`, a pedido do João): segura só o irreversível — enviar/responder/encaminhar,
  pagar/comprar, apagar, `rm -rf`, `sudo`, push em `main`, `reset --hard`; `.env` e `jaime/vigia/` pedem "confirmo";
  `vault/00-Jaime/` continua só do João. **Livres**: ver a tela, clicar, digitar, teclar, mover/renomear, `killall`,
  editar o próprio código em `jaime/` (só vale após reiniciar o serviço). Janela do "confirmo": 5 min. Ver `docs/SEGURANCA.md`.
- **Notificações faladas com filtro** (`jaime/ops/notificacoes.py`): fala só mensagem de pessoa salva em conversa direta
  (WhatsApp/Mensagens/Telegram/ligação — subtítulo = grupo → cala; "~ nome" ou número → cala), e-mail de pessoa (sem
  no-reply/newsletter/promo), DM do Instagram (curtida/seguidor → cala), agenda/lembrete. Mensagens seguidas da mesma
  pessoa viram um aviso só ("Maria mandou 3 mensagens no WhatsApp: …"). `JAIME_AVISAR=off` silencia; `JAIME_AVISAR_TUDO=on` volta ao antigo.
  Tudo continua indo para o HUD e o diário.
- **Notion**: `NOTION_TOKEN` novo no `.env` (backup em `~/Jaime/.env.bak-*`); `users/me` responde "jaime". A página raiz
  `3db6fab2-…` existe (confirmado pelo MCP do Notion) mas **não está compartilhada com a integração** → 404 no espelho.
- **Google**: `~/Jaime/google-client-secret.json` atualizado com o secret atual do projeto `jaime-508712`; o consentimento
  devolve **403 access_denied** porque `joaovleal71@gmail.com` não está em *Usuários de teste*.
- Permissões do macOS (checadas 10:40 pelo binário do venv): Microfone, Câmera, Gravação de Tela (36 janelas com nome
  visíveis), Acessibilidade, Automação e Acesso Total ao Disco — **todas ✔**.

## Pendências do João (cada uma destrava uma função)
1. Google: console.cloud.google.com › APIs e serviços › Tela de permissão OAuth › **Público › Usuários de teste › + joaovleal71@gmail.com**
   (projeto `jaime-508712`). Depois: `.venv/bin/python -m jaime conectar google`.
2. Notion: abrir "Jaime — Cérebro compartilhado" › ⋯ › **Conexões › jaime**. O 404 some sozinho no próximo `sincronizar_estado`.
3. As regras dos maesters `maester-jaime` e `maester-ops` (pasta `.claude/agents/`) ainda dizem que mover arquivo e editar o
   próprio código pedem "confirmo" — o classificador do Claude Code não deixou o assistente editar esses dois arquivos;
   alinhar o texto com `docs/SEGURANCA.md` à mão.
4. Tranca por voz: de manhã o João se irritou ("tenho que falar a palavra mas não deixa eu usar") — com o perfil de voz do
   dono ativo, palavra-passe só vale na voz dele; áudio ruim → não reconhece. Investigar limiar em `jaime/voice/falantes.py` ou `JAIME_FALANTES=off`.
5. Tailscale (docs/REMOTO.md); Atalho de saúde (docs/SAUDE-PASSOS.md); aniversário em `10-Eu/Datas.md`; `10-Eu/Pessoas.md`
   (o link `[[Gabriel]]` em `20-Projetos/BUB.md` ainda gera 1 aviso por subida).
6. Opcionais: Home Assistant token, app Meta, Blender, VPS para Evolution (WhatsApp pessoal — parado por decisão do João).

## Próximos passos de código (ordem sugerida)
1. Etapa 2 da fase 3: primeiro objetivo autônomo real supervisionado (o João dá o objetivo).
2. Diário: as notificações de WhatsApp vão todas para o Log (e para o Notion quando o espelho voltar) — decidir se só as
   faladas devem ser registradas (privacidade).
3. Saúde: rotina "resumo de saúde" + `10-Eu/Saude.md` quando o atalho começar a enviar.
4. Mensagens do iPhone (chat.db) — Acesso Total ao Disco já está liberado.
5. Embeddings na memória quando o vault passar de 500 notas; ElevenLabs Voice Design em 15/10.

## Como o João usa
"Jaime, está aí?" liga (fica ligado até "encerrado"/"pode descansar"). "bom dia", "tudo bem?", "como está o dia?" respondem
na hora. "para" corta qualquer coisa. Teclado: T. Cérebro interativo: B. Sons: S. Painéis: H.
