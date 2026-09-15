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

## Como o Jaime roda agora (15/09, 14:10)
- **O serviço roda dentro do Maestri**, no nó "J.A.I.M.E · serviço" (preset Shell, `python -u -m jaime serve | tee -a ~/Jaime/jaime.log`,
  pasta jaime-vision). O LaunchAgent `com.jaime` foi **parado** (`servico.sh parar`) para não disputar a porta; se o Maestri fechar,
  o Jaime cai — para voltar ao modo serviço: `bash jaime/ops/servico.sh ligar`. Não rode os dois.
- O serviço age no canvas pelo Maestro "Cerebro Principal J.A.I.M.E" (descoberta automática em `jaime/equipe/maestri.py`).
- **"J.A.I.M.E · mente"** (Claude Code, papel "Mente do J.A.I.M.E", worktree `../jaime-mente`, branch `feat/mente`): lê log, diário
  e problemas, escreve `docs/MENTE.md` (problema → hipótese → solução → validação), implementa melhorias com testes e avisa o
  Cérebro Principal; pode recrutar Codex. Só o Cérebro Principal (esta sessão) faz merge e reinicia o serviço.
- Nós conectados: Bússola, Fagulha (ociosos), nota `fase3-progresso`, papel "Codex do Jaime" pronto para recrutas Codex.
- `main` = fase 3 completa (merge 621a0f1); **push pendente** (`git push origin main` no terminal do João).

## Fase 3 — tempo real (branch `feat/fase3-duplex`, 15/09 tarde) — A, B, C, D, E prontos
- Tese e prompts em `docs/FASE-3-TEMPO-REAL.md`; Maestri em `docs/MAESTRI.md`; prompt do Codex em `docs/PROMPT-CODEX.md`.
- **A (ouvido em tempo real)**: `voice/stt_stream.py` (Deepgram ao vivo, OpenAI Realtime, Whisper pseudo), `voice/antecipador.py`
  (heurística imediata + modelo em segundo plano, gpt-4o-mini por padrão; nenhum modelo de nuvem responde em < 2 s), `voice/duplex.py`
  (`DetectorFim` 450/700/1200 ms, `OuvidoDuplex`, barge-in com guarda de eco, interjeição opcional `JAIME_INTERROMPER`).
- **B**: `voice/fila.py` (demanda interrompida → "Voltando: …" ou "Continuo o que eu dizia sobre X?"), `vigia/hooks.py` por LOTE
  ("Você deseja que eu X, Y e Z?" → "sim" libera exatamente aquelas), `vigia/confianca.py` (5 aprovações → "posso fazer sem perguntar?",
  `01-Estado/Confianca.md`), barge-in interrompe o modelo (`ClaudeSDKClient.interrupt`).
- **C**: `tts.py` toca em streaming a partir do 1º byte, `pre_sintetizar`/`tocar_pronto`/`parar()`, velocidade 1.15; `persona.py` sem
  preâmbulos; prompt de voz 1–2 frases + "Quer o detalhe?"; `python -m jaime voz latencia` (say → Deepgram → antecipador → TTS).
  **Medido 15/09 (2ª rodada)**: fala→texto 316 ms · TTS 1º byte 1,38 s (gpt-4o-mini-tts) · fala→1ª frase 1,7 s. A meta de 700 ms
  depende de um TTS mais rápido: **ElevenLabs Flash (falta ELEVENLABS_API_KEY)** ou antecipação acertando (cache = ~0 ms).
- **D (Bússola, Codex-like via Claude)**: `telemetria/uso.py` + `prioridades.py`, `cortex/orcamento.py` (60/25/15), Rotinas §5,
  modo atento, noite criativa como janela, `01-Estado/Uso.md`, `90-Estudo/Prioridades.md`.
- **E (Fagulha)**: `vontade/impulsos.py`, `mente.py`, `criacoes.py`; Vitrine `GET /hud/vitrine` + voto; CLAUDE.md §Vontades.
- **Filhos (equipe)**: `jaime/equipe/` — o Jaime cria terminais no Maestri (Claude Code, Codex, OpenCode, shell) com papel, missão
  e pasta (worktree `~/Jaime/worktrees/<slug>` para código; `~/Jaime/filhos/<slug>` para pesquisa; `~/projetos/<slug>` para MVP),
  delega, lê relatórios pela nota `equipe-relatorios` (task a cada 60 s) e dispensa (Vigia). Ferramentas `mcp__equipe__*`; registro em
  `01-Estado/Equipe.md`. Identidade: socket em $TMPDIR/maestri-*/ e terminal Maestro do workspace (auto-descoberta).
- Testes: 179 verdes. Serviço reiniciado com tudo às ~15:00 (`JAIME_VOZ_MODO=duplex` no .env).
- Maestri hoje: workspace "Jaime-assist", Maestro "Cerebro Principal J.A.I.M.E"; recrutas Bússola (jaime-telemetria) e Fagulha
  (jaime-vontades) vivos e ociosos; papéis "Telemetria e Rotina do Jaime", "Vontades e Vitrine do Jaime", "Codex do Jaime".
  Worktrees em `../jaime-telemetria` e `../jaime-vontades` (branches já mergeadas em `feat/fase3-duplex`; podem ser removidos:
  `git worktree remove ../jaime-telemetria`).
- **Falta**: validar ao vivo (falar com ele; ler "Latência (voz)" no diário; testar barge-in com fone), merge de `feat/fase3-duplex`
  em `main` (o auto-push do João leva ao GitHub), ELEVENLABS_API_KEY para a meta de latência, calibrar o antecipador antes de ligar
  `JAIME_INTERROMPER`.

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
