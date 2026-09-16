# MENTE — caderno do terminal que observa o Jaime e o melhora

> Mantido pela Mente (terminal Maestri, worktree `jaime-mente`, branch `feat/mente`). Fontes: `~/Jaime/jaime.log`,
> diário do dia, `01-Estado/*`, `90-Estudo/Problemas.md`, docs da fase 3. Só o Cérebro Principal faz merge e reinicia.
> Formato de cada entrada: **problema → hipótese → solução proposta → como validar**.

## Primeira leitura — 15/09/2026 ~14:20

### O que está funcionando
- Fase 3 A–E no chão e mergeada (`feat/fase3-duplex` → `feat/mente` em dia; 181 testes verdes).
- Transcrição viva por Deepgram: fala→texto 0,18–0,53 s (mediana ~0,28 s) — dentro da meta de 300 ms.
- Latência registrada no diário a cada turno (`Latência (voz)`), medição sintética (`voz latencia`) funcionando.
- Vontades reagindo aos eventos (Utilidade sobe com fila, Maestria mexe com placar); noite criativa entregou 1 criação.
- Notificações filtradas (só pessoa em conversa direta) e registradas; Vigia por lote sem reclamação no log.
- Loop de crash da manhã (torch+onnx) resolvido com o `falantes_worker`: nenhum crash desse tipo depois das 10:16.

### O que falha (por ordem do que mais atrapalha o João hoje)
1. **Serviço CAÍDO desde 14:06** (SIGSEGV; porta 8787 muda; nenhum `jaime serve` vivo). → M-01, corrigido.
2. **Tranca fala com todo mundo**: enquanto trancado, cada frase ambiente ("Veado.", "vai para o caralho", conversa
   de terceiros) vira "Palavra-passe, por favor." em voz alta — dezenas de vezes entre 13:33 e 13:52, cada uma com
   1,5–3 s de TTS. E a palavra-passe do João é recusada quando a voz chega com ruído (`desconhecido` ≠ `João`).
   É a irritação relatada de manhã ("tenho que falar a palavra mas não deixa eu usar"). → M-02.
3. **Latência texto→1ª frase 1,1–2,6 s** (meta 0,7 s): TTS gpt-4o-mini-tts com 1º byte ~1,4 s; ElevenLabs Flash sem chave.
   Um outlier de 14,2 s às 14:03 (modelo pensando com ferramenta, sem muleta a tempo). → M-03.
4. **Antecipador 0/10 acertos** nas duas medições sintéticas; nenhum `antecipacao usado=True` no diário. O cache de
   1ª frase nunca toca — a meta de 700 ms só se alcança por aí sem trocar o TTS. → M-04.
5. **Notion 404 a cada sincronização** (página não compartilhada com a integração): 1 linha de erro por evento no
   log. Não é código; é pendência do João. Mas o log vira ruído. → M-05.
6. **Transcrições ruins**: "Grand rabos", "Ludinossauro", "Hunchen", "O bergão me me esquente do bota" — a maioria é
   conversa de outras pessoas captada pelo mic interno, não fala do João. O problema real é o item 2 (responder a
   quem não falou com ele), não o STT.
7. `FutureWarning: np.long` em `falantes.py:50` a cada subida — cosmético. → M-06.
8. `Uso.md` e `Prioridades.md` vazios (telemetria sem amostras, placar sem erros na semana): a janela ativa não
   está sendo amostrada ou o serviço reiniciou demais para acumular. → M-07 (observar mais um dia antes de mexer).

### Entradas

#### M-01 · Barge-in derruba o processo (SIGSEGV) — **CORRIGIDO em feat/mente (10ff5ea)**
- Problema: crash report `python3.12-2026-09-15-140601.ips`: `PaUtil_WriteRingBuffer` ← `WriteStream` ← cffi, thread 11.
  Diferente da manhã (torch+onnx). Última fala antes: "Você consegue abrir sua interface para mim?" por cima da resposta.
- Hipótese: `duplex._barge()` roda na thread de captura e chama `tts.parar()` → `_fechar_stream()` → `abort()/close()`
  do `RawOutputStream` enquanto a thread `_reprodutor` está dentro de `st.write()`. PortAudio não tolera isso.
  Segundo bug no mesmo caminho: `parar()` seta e logo limpa `_parando`; a frase antiga, presa no `write()`, ao voltar
  via `_parando` já baixado, reabria o aparelho e continuava falando.
- Solução: `RLock` no stream; abrir+escrever por bloco (50 ms) sob o lock; `_fechar_stream()` espera o bloco acabar;
  `_tocar(pcm, g)` descarta pela geração, não só pelo evento. Teste `tests/test_tts_barge_in.py` com `sounddevice`
  falso que acusa write depois de close — falha no código antigo (9 writes após parar, writes em stream fechado), passa no novo.
- Validar ao vivo: com fone (`JAIME_BARGE_IN=fone`), falar por cima 10× seguidas; nenhum crash; áudio cala < 150 ms;
  nada da frase antiga volta a tocar. Até o merge: `JAIME_BARGE_IN=off` no .env evita a repetição.

#### M-02 · Tranca responde a conversa ambiente; senha recusada com voz ruidosa — **CORRIGIDO em feat/mente**
- Problema: em `escuta._tratar_texto`, o filtro "não era comigo" (`sem_nome` + janela inativa) só vale se `acesso.liberado`.
  Trancado, tudo vai a `_porta` → "Palavra-passe, por favor." falado. Além disso `_porta` recusa a senha se
  `falante_atual` ∈ {outro, "desconhecido"} — e `identificar()` devolve "desconhecido" para qualquer score < 0,75,
  inclusive o João com ruído. O P-0003 (resolvido pelo estudo) recomendou 3 zonas (aceita ≥ 0,76 · incerto 0,55–0,76 ·
  rejeita < 0,55), EMA 0,6 entre tentativas, 2 repetições e fallback para senha digitada — nada disso entrou no código.
  Terceiro detalhe: a senha digitada no HUD passa por `_porta` com o `falante_atual` da última fala → também recusada.
- Solução: (a) trancado + sem nome + janela inativa + não é a senha → ignorar em silêncio (HUD apagado, sem ouvido
  passivo, sem TTS); (b) `identificar()` com 3 zonas e EMA curta: "incerto" em vez de "desconhecido" na zona do meio;
  (c) `_porta`: senha certa com voz "incerta" → 1ª vez pede para repetir, 2ª vez abre o teclado do HUD; voz de outra
  pessoa conhecida → continua "só com o João"; (d) canal ≠ voz ignora `falante_atual`; (e) cadastro passa a guardar as
  5 amostras (`<nome>.amostras.npy`) e o score usa max(centróide, melhor amostra).
- Validar: testes em `test_falantes.py` (3 zonas, EMA, amostras) e `test_escuta_tranca.py` (silêncio trancado, senha
  incerta 2×, senha digitada). Ao vivo: trancar, deixar gente conversar 1 min — zero "Palavra-passe"; dizer a senha
  com ruído — ou abre, ou pede uma repetição, nunca "isso só com o João" para o próprio João.

#### M-03 · texto→1ª frase 1,1–2,6 s
- Hipótese: 1º byte do gpt-4o-mini-tts ≈ 1,4 s domina. `optimize_streaming_latency=3` só vale na ElevenLabs.
- Proposta: (1) pedir ao João `ELEVENLABS_API_KEY` (Flash v2.5 ~75 ms → meta batida sem antecipador); (2) enquanto
  isso, resposta especulativa (M-04) e muleta mais cedo quando há ferramenta (o outlier de 14 s ficou mudo).
- Validar: `python -m jaime voz latencia` mediana < 700 ms; diário sem `texto→1ª frase` > 5 s.

#### M-04 · Antecipador nunca acerta (0/10; nenhum `usado=True`) — **CORRIGIDO em feat/mente (rascunho local)**
- Medido (15:20, chave do serviço, 2 frases × 2 modelos): gpt-4o-mini 3,9 s e 5,4 s; gpt-4.1-nano 5,3 s e 3,7 s.
  Ou seja: o parecer chega depois do turno inteiro (fala 1,5–3 s + 450 ms) e metade das vezes depois do timeout de 4 s.
  Em `voz latencia` o `esperar=True` espera o modelo, mas o rascunho vinha vazio (completude 0,5 para "quem me mandou
  mensagem") — logo 0/10. Nenhum modelo em nuvem serve para a 1ª frase; o comentário do próprio arquivo já dizia isso.
- Solução: `rascunho_local()` no antecipador (abrir app/site, mensagens, mandar mensagem para X, clima, criar tarefa,
  resumo do dia, dólar, lembrete); `duplex._pre_sintetizar` dispara a síntese no instante em que o rascunho aparece
  (teto 2 por turno); `_turno` espera até 1,2 s por síntese em curso (mais rápido que modelo + TTS do zero) e apaga cache
  de outra intenção (bug: sobrava para o turno seguinte). O modelo continua refinando em segundo plano, como antes.
- Fora: "que horas são" (a hora muda entre a síntese e a fala) e "está aí" (caminho "chamou" não usa cache) → M-08.
- Validar: `python -m jaime voz latencia` → antecipados ≥ 7/10 e mediana fala→1ª frase < 700 ms nas frases cobertas;
  no diário, `antecipacao usado=True` em "abre o Finder". Custo: 1 chamada de TTS extra por pedido reconhecido.

#### M-09 · Tarefas com ferramenta: 1º som em ~4,5 s — **CORRIGIDO em feat/mente**
- Diário 14:22–14:23: «quem me mandou mensagem?» 4,44 s e «você sabe sobre o meu» 4,47 s de texto→1ª frase. A muleta
  ("deixa eu ver…") esperava a ferramenta (até 3 s) e depois mais 2 s; o narrador só fala a partir de 5 s.
- Solução: muleta 0,4 s depois da 1ª ferramenta, se a resposta não começou (`MULETA_APOS_FERRAMENTA_S`). Testes em
  `tests/test_muleta.py`. Com M-08 (cache) a muleta passa a custar ~0 de TTS.
- Validar: no diário, turnos com ferramenta com texto→1ª frase < 2 s.

#### M-10 · Diário cego sobre a antecipação (pedido da Vigília) — **CORRIGIDO em feat/mente**
- A linha "Latência (voz)" ganha `antecipação: usada «…» | não bateu «parcial» ≠ «final» | sem rascunho (origem, completude) |
  rascunho «…» sem áudio a tempo | nenhuma`; e `antecipado` agora significa que o cache tocou de fato.
- Validar: depois do merge, cada turno de voz no diário traz o motivo; contar "usada" por dia.

#### M-11 · Fim de turno corta o João no meio — **CORRIGIDO (bf538e3, já na main)**
- Diário 14:20 «…parabéns mas eu preciso» e 14:22 «você sabe sobre o meu» → "Fala truncada". A heurística marcava `frase_fechou`
  para qualquer parcial de 3+ palavras sem conjunção no fim → turno em 450 ms. Agora: 450 ms só com pontuação ou pedido
  reconhecido; finais em aberto ganham verbos/preposições que pedem complemento; frase claramente aberta espera 1,5 s.
- Validar: sumir "Fala truncada"/"Não peguei o final" em falas com pausa de pensamento.

#### M-12 · Áudio do Jaime cortado antes do fim (14:23, 1 ocorrência) — observar
- «Você não terminou de falar.» após resposta de 2 frases; barge-in OFF; sem "⚠ placa de som". Hipóteses: `st.stop()` sem
  drenar; 2ª frase enfileirada depois de `vazio`; TTS streaming da OpenAI encerrando cedo. Se repetir, instrumentar `_reprodutor`.

#### M-13 · Vigília 18:04: ainda 0/10 — **causa achada e corrigida em feat/mente**
- O código no ar já gera rascunho para "abre o Finder"/"dólar"/"clima" (testado no checkout do serviço). As ~35 linhas
  "sem rascunho" ao vivo são conversa livre ("Pode encerrar então", "tem 3 cérebros") — correto. O 0/10 do `voz latencia`
  vem de `esperar=True`: o parecer do modelo (completude 0,5, rascunho vazio) **substituía** o da heurística em `_refinar`.
  Ao vivo o mesmo bug apagaria o cache nos turnos longos. Corrigido: rascunho do modelo quando existe, senão o local.
- Validar: `voz latencia` → antecipados ≥ 7/10 (abre o Finder, tempo, lembrete, tarefa, dólar, resumo, site da Oldsen;
  "está aí", "que horas são" e "agenda" ficam de fora por desenho).
- Também às 18:06–18:08: texto→1ª frase 7,6–9,5 s **sem ferramenta** ("Quais são suas últimas funções", "sala do futuro"):
  é o tempo até o 1º token do modelo em perguntas reflexivas — a muleta não entra sem ferramenta. Candidato M-14: muleta
  também quando o 1º token demora > 2,5 s, ou modelo rápido no roteador para "conversa".

#### M-15 · Nenhuma rotina do Rotinas.md disparou, em nenhum dia — **CORRIGIDO em feat/mente (f7c2e96)**
- Zero "Rotina disparada" em todos os diários; `parse_rotinas`/`CronTrigger` corretos. Reproduzido 18:32 com marcações de
  5 s: entre dois ticks o relógio de parede andou **876 s** e o do loop 6 s — o Mac dormiu. No macOS `time.monotonic()`
  não conta o sono, o `call_later` do APScheduler acorda atrasado e o job é descartado pelo `misfire_grace_time` padrão
  de 1 s (`Run time of job … was missed by 0:14:29`). Lembretes só disparavam quando o Mac estava acordado no minuto.
- Solução: rotinas com `misfire_grace_time=3 h` + `coalesce`; lembretes 30 min. Validar: amanhã "Rotina disparada:
  preparar o dia" (06:30) e "briefing" (07:00) no diário mesmo que o Mac tenha dormido; "fecha o dia" às 18:00.
- Fica para o Cérebro: com o Mac dormindo, nada roda — para rotinas da madrugada vale um `caffeinate`/`pmset` ou
  aceitar que rodem ao acordar (é o que a tolerância de 3 h faz).

#### M-16 · Vontades saturadas (Vigília 22:04, etapa 9) — **CORRIGIDO em feat/mente (38de1d5)**
- Curiosidade e Vínculo em 1,00 subindo +0,03/+0,05 a cada sonda de 10 min pela MESMA pergunta sem resposta; Maestria
  presa em 0,00 (cada "acerto" descia 0,05 sem piso). Com três impulsos em 1,00 a Mente não discrimina.
- Solução: perguntas, datas, Inbox e desordem só empurram quando a contagem **cresce** (idempotente; zera quando some);
  acerto relaxa Maestria até o repouso 0,20, nunca a zero; "estudo resolvido" sobe Maestria 0,05.
- Validar: `Vontades.md` — Vínculo/Curiosidade param de subir com a mesma pergunta e decaem para o repouso; Maestria ≥ 0,20.
- Registro positivo (Vigília): fila + barge-in ao vivo (22:04, "Continuo o que eu dizia…?"), transcrição viva no stream
  (75 eventos/60 s), "quero atender o João porque demanda pendente" no diário (21:57).

#### M-14 · Perguntas reflexivas sem ferramenta: 5–9 s até o 1º som, sem muleta — **CORRIGIDO (07665d8)**
- A muleta só entrava com ferramenta. Agora entra também após 3 s de silêncio sem ferramenta; com o cache M-08 custa ~0.
- Validar: no diário, turnos sem ferramenta com texto→1ª frase ≤ ~4,5 s (muleta) em vez de 7–9 s.

#### M-17 · Trancado, "Palavra-passe, por favor." a cada frase solta dentro da janela dos 25 s — **CORRIGIDO (07665d8)**
- Log 23:40: depois de um "Jaime", cada fragmento ambiente recebia a resposta em voz alta. Agora, trancado, só a senha
  ou o nome passam, com ou sem janela. Destrancado, a janela segue valendo.

#### M-18 · Vigília 23:44: ainda 0/10 com o M-13 no ar — **CORRIGIDO (8e71b28)**
- Offline (fluxo falso, sem modelo) o benchmark dá 7/10. Ao vivo o modelo está ligado e `esperar=True` espera por ele: quando
  o modelo devolve rascunho **próprio** com completude baixa (nano: "Quem enviou mensagem para você?", 0,2), ele substituía o
  local e a antecipação deixava de ser especulável. Agora o modelo só substitui o local se o parecer dele for especulável.
- "está aí" (→ "Estou aqui, senhor.") e "agenda/compromissos" (→ "Deixa eu ver a agenda.") entram na lista; "aí" em "está aí"
  deixa de contar como fim em aberto. `voz latencia` imprime por turno origem/especulável/completude/ação/rascunho/parcial.
- Teste do caminho completo de `medir_turno` exige ≥ 9/10 sem modelo. Exit 1 do comando é por desenho (mediana > 700 ms).
- Validar: `voz latencia` ≥ 7/10 ao vivo com Deepgram (o `say` troca ~3/10 frases: "Finder"→"vender"; isso é o STT do
  benchmark, não o antecipador).

#### M-19 · Rotinas perdidas no sono do Mac não rodam ao acordar (Vigília 16/09 07:22) — **CORRIGIDO (5b7fcd9)**
- 06:30 "preparar o dia" e 07:00 "briefing" caíram com o processo morto (subiu 07:14). `misfire_grace_time` só vale com
  o processo vivo; jobstore em memória. Agora `start()` olha 3 h para trás: rotina prevista na janela e sem "Rotina
  disparada" no diário de hoje é agendada uma vez, 20 s depois do boot (uma por vez). Diário: "Rotina perdida enquanto eu
  estava desligado, vou rodar agora: …". Validar: no próximo boot após sono, as duas linhas no diário.

#### M-20 · Benchmark cego: "antecipação: nenhuma" 10/10 (Vigília 07:22) — **CORRIGIDO (fac9c82)**
- Reproduzido 07:40 com o Deepgram real. O `voz latencia` empurra o áudio inteiro em milissegundos e avaliava
  `parciais[-1]` **antes** do `finalizar()`; nesse instante só existia o 1º parcial ("Jaime", 5 caracteres < 6) → None.
  O resto chegava durante a espera do `finalizar()`. Agora cada parcial é avaliado ao chegar (como o duplex), o texto
  final também, espera-se o modelo e usa-se `confere(texto)`. Print mostra nº de parciais e o último.
- Isso NÃO afetava o vivo (o duplex sempre avaliou cada parcial); o vivo estava preso no M-13/M-18.
- Validar: `voz latencia` com a Mente → antecipados ≥ 7/10 (rodando agora, resultado abaixo).
- Fora do meu escopo, para a Bússola: `tests/test_telemetria.py::test_prioridade_formula_frequencia_x_erro_x_tempo`
  falha desde 16/09 (depende da data de hoje vs. 2026-09-15 fixo no teste); igual na main.

#### M-21 · Texto cresce enquanto o modelo pensa → rascunho local do texto novo se perdia — **CORRIGIDO (3735934)**
- Benchmark real com fac9c82 (07:55): 3/10. Os 7 restantes terminavam "modelo · completude 0,0 · rascunho «»" em frases
  completas ("quanto está o dólar?"). O refinamento encadeado (`_refinar` → texto mudou → `_refinar` de novo) partia do
  parecer do modelo como base, sem rascunho; a heurística do texto atual nunca era recalculada.
- Solução: `_refinar` recalcula `heuristico(texto atual)` e usa esse rascunho/ação/completude como candidato local.
- Validar: benchmark real abaixo (bench4). Artefatos do STT do benchmark que não são do antecipador: "está aí?" vazando
  para o turno seguinte (segmentação do Deepgram entre turnos sintéticos) e "site da." (Oldsen sumiu).

#### M-22 · Palavra-passe escrita em texto puro no diário (16/09 07:24) — **CORRIGIDO (redator no Vault)**
- Uma reflexão do próprio Jaime registrou "destrancado por senha digitada no HUD (dígitos)". Regra 2 violada; o espelho
  do Notion pode ter levado. Cérebro avisado para apagar a linha ao vivo (só ele edita o vault do serviço).
- Solução: `Vault.write` mascara qualquer sequência de dígitos/números por extenso cujo SHA-256 bata com
  `JAIME_PASSPHRASE_HASH` (diário, conversas, ouvido passivo, tudo). Validar: `grep` da senha no vault → nada novo.
- Recomendação ao João: trocar a senha (`python -m jaime senha`) — ainda é a padrão do `.env.example`.

#### Benchmark real com a Mente (16/09 08:05, código 3735934): **antecipados 7/10 · mediana fala→1ª frase 320 ms · meta < 700 ms OK · exit 0**
- Os 3 que faltam são STT do `say`: "pior ação" (= que horas são), "previsão do tempo para" (cortada), "cria 1 tarefa
  para ligar para o c" (cortada; "1 tarefa" agora casa). Etapa 2 atendida no benchmark; ao vivo, conferir "antecipação:
  usada" no diário depois do merge.

#### M-24 · Barge-in não cortou o briefing (16/09 07:4x, prioridade do Cérebro) — **CORRIGIDO + instrumentado**
- Log: "Não Jaime, não precisa, isso eu estou fazendo…" por cima do briefing; o briefing seguiu até o fim.
- Causas no código: (1) com `afplay`, `ao_tocar` recebia a frase inteira de uma vez → a referência de eco (300 ms)
  era o fim da frase durante a fala toda; similaridade inútil. (2) calibração de eco nos 320 ms após `mudo` = latência
  do TTS (silêncio) → limiar no chão ou, na rotina, herdado de outra fala. (3) nenhum dado para ajustar limiares.
- Solução: referência entregue por tempo decorrido no afplay (e por bloco no sounddevice); calibra só com áudio tocando
  e zera a cada fala; evento `barge` no bus (0,5 s) e linha "Barge-in não cortou: voz por N ms (acima do eco …, vetada …;
  rms máx X vs eco Y×1,8; sim máx Z)" no diário ao fim de cada fala com ≥ 400 ms de voz sem corte.
- Validar ao vivo: o João fala por cima → corta em < 200 ms. Se não cortar, a linha do diário diz qual limiar segura
  (`acima_ms` baixo → baixar `BARGE_IN_ECO_X`; `veto_ms` alto → subir `BARGE_IN_ECO_SIM`). Se cortar sozinho (eco), o
  inverso. Só então mexer em `jaime/voice/duplex.py`.
- Delegado ao Gemini (M-23): markdown/emoji lidos em voz alta nas rotinas + briefing frase a frase.

#### M-25 · Rotina segura o orquestrador e o João espera 1–2 min (Vigília 07:56, etapas 5/8) — **CORRIGIDO (3907b96)**
- Diário 07:39–07:40: 4 turnos com texto→1ª frase de 66/100/120/122 s logo após "preparar o dia" e "briefing".
  `jaime.ask(ordem, canal="rotina")` segura `_lock` até o modelo terminar; a voz espera na fila.
- Solução: `ask_stream` de demanda (voz/HUD/Telegram) com rotina em curso → `interrupt()` do SDK (o mesmo do barge-in),
  espera o lock (≤ 5 s), diário "Rotina «…» interrompida: demanda do João; volto a ela em 10 min", `agenda.reagendar`;
  `_rodar_ordem` não fala o resto da rotina cedida e registra "Rotina concluída em N s".
- Validar: falar durante o briefing → resposta em < 3 s e, 10 min depois, "Rotina disparada: briefing" de novo.
- Em aberto (Vigília, etapa 7): `Uso.md`/`Prioridades.md` só são reescritos nos ganchos "fecha o dia"/"fecha a semana";
  ontem o fecha-dia não rodou (M-15) e hoje só chega às 18:00. Se as rotinas rodarem hoje, resolve-se sozinho.

#### M-26 · Barge-in ainda não corta ao vivo (Vigília 08:27, com os dados do M-24) — **CORRIGIDO (17f30b3)**
- 6 linhas "Barge-in não cortou" 08:13–08:16: voz 416–3296 ms; rms máx 1202–1603 vs eco 486–1026 (1,2–2,5×, e o limiar
  era 1,8×); vetos por similaridade a 0,82–0,88 (limiar 0,80) que eram o João. Alto-falante, sem fone, sem AEC.
- Solução: `BARGE_IN_ECO_X` 1,8 → 1,25; `BARGE_IN_ECO_SIM` 0,80 → 0,92; regra nova: voz contínua ≥ 1,0× o eco por 700 ms
  corta (eco não fica 2–3 s acima da própria média). Cada corte também vai ao diário com o motivo (energia/sustentado)
  para flagrar corte pelo próprio eco.
- Não fiz (por ora) a sugestão 2 da Vigília (STT durante a fala do Jaime): os frames enviados ao Deepgram entrariam no
  turno do João com o eco transcrito junto (contaminação) — exigiria um 2º stream só de detecção. Fica como M-27 se
  os limiares novos não bastarem.
- Validar: linhas "Barge-in cortou (energia|sustentado)" quando o João fala por cima; zero "Barge-in cortou" sem o João
  falar (seria eco); "Você não terminou de falar" não volta.

#### M-28 · "texto→1ª frase 14 s" com a muleta soando aos 3 s — **CORRIGIDO (medição)**
- `enfileirar()` zera `t_inicio_audio` a cada resposta; a muleta acabava antes da 1ª frase real e a medida pulava para
  a frase real. `TTS.novo_turno()` + `t_primeiro_som`: o 1º som do turno é o que o João percebe. Validar: no diário,
  turnos com ferramenta/pensamento longo mostram texto→1ª frase ≈ 3–4 s (muleta), não 7–14 s.
- Observação do mesmo diário (08:15): João falou por cima por 3,3 s (rms 1603 vs eco 1026, sim 0,88) sem corte e
  pediu "Continua o que você estava falando" — é o caso exato do M-26.

#### M-29 · Corte pelo próprio eco após o M-26 (Vigília 08:57) — **CORRIGIDO (7d9d4c6)**
- Diário 08:46–08:47: "Barge-in cortou (energia): voz 224 ms, rms 1255 vs eco 717" e "voz 160 ms, rms 1116 vs eco 390", sem
  nenhum "🎙 você" — o Jaime se calou sozinho. Nenhum "não cortou" novo (veto 0,92 está bom).
- Solução: `BARGE_IN_ECO_X` 1,25 → 1,4 (meu critério) e `BARGE_IN_MS` 160 → 320 ms de voz qualificada no caminho por
  energia (sugestão da Vigília: as falas reais por cima tinham 416–3296 ms). Caminho de voz sustentada (700 ms a 1,0×) segue.
- Validar: zero "Barge-in cortou" sem o João falar; "cortou (energia|sustentado)" quando ele fala por cima; se voltar
  "não cortou" com acima_ms ≥ 320, aí o problema é o 1,4× e o caminho sustentado deve pegar.

#### M-30 · Energia e sustentação passam e nada corta (Vigília 09:27) — **CORRIGIDO**: contagem por janela
- 8 "não cortou" 09:15–09:21 com 352–1376 ms acima do eco, veto 0, rms com folga. O contador `_barge_ms` somava 32 ms por
  frame bom e subtraía 32 por frame ruim; a sustentação zerava em qualquer frame ruim. prob/rms oscilam a cada 32 ms →
  nunca chegava a 320/700 (a 09:19, 81% dos frames bons: 1376/1696 ms).
- Solução: janelas deslizantes — 320 ms qualificados em 640 ms (energia) ou 700 ms a 1,0× em 1000 ms (sustentado); corte
  avaliado a cada frame. "Não cortou" diz o gate que faltou: `janela máx N/320 ms, sustentada máx N/700 ms`.
- Validar: com o João falando por cima ≥ 0,5 s, "cortou (energia)" em ≤ 640 ms; sem ele falar, nenhum corte.
- Registro positivo (Vigília): etapa 5 PASSA ao vivo (fala→1ª frase 0,60–0,96 s em 7 turnos); fila com 8 itens sem perda.
- Aberto para o estudo: P-0008 (ferramenta 'corpo' obrigatório, recorrência do P-0002) — não é meu; anotado.

#### M-08 · Frases fixas sintetizadas uma vez — **entregue pelo Codex, mergeado na main (7a767c7)**
- "Estou aqui, senhor.", "Palavra-passe, por favor.", "Pode escrever.", "Certo, João. Estou aqui se precisar.", muletas —
  hoje cada uma custa ~1,4 s de TTS. Um cache em disco (`~/Jaime/vozes/frases/<hash>.pcm`) por texto+voz+velocidade,
  consultado em `enfileirar`/`tocar_pronto`, faz essas responderem em ~150 ms. Candidato a delegar ao Codex.

#### M-05 · Notion 404 em toda sincronização — **CORRIGIDO** (1ª, 3ª e depois 1×/h com contagem)
- Não é código: página não compartilhada com a integração. Proposta: depois de 3 falhas iguais seguidas, silenciar
  o log por 1 h e registrar 1 linha no diário ("espelho parado: compartilhe a página com a integração"). Validar: log limpo.

#### M-06 · FutureWarning np.long — **CORRIGIDO**: o próprio `hasattr(np, "long")` emitia o aviso; envolto em `catch_warnings`.

#### M-07 · Telemetria sem amostras — **resolvido pelo tempo**: `vault/.jaime/telemetria.json` já acumula (1 hora, 5 títulos, 9 pedidos às 14:28); `Uso.md` só é reescrito no fecha-semana.

### Fila de melhorias (por impacto)
| # | Item | Impacto hoje | Estado |
|---|---|---|---|
| 1 | M-01 barge-in segfault | serviço morto | pronto, aguardando merge |
| 2 | M-02 tranca/senha por voz | irritação diária | pronto, aguardando merge |
| 3 | M-04 antecipador | meta 700 ms | pronto, aguardando merge |
| 4 | M-03 TTS 1º byte | meta 700 ms | depende de chave |
| 5 | M-05 Notion ruído no log | observabilidade | pronto |
| 6 | M-06 FutureWarning | cosmético | pronto |
| 7 | M-07 telemetria vazia | estudo dirigido | resolvido (acumulando) |
| 7b | M-09 muleta tardia | 4,5 s → ~2 s com ferramenta | mergeado |
| 7c | M-11 corta o João no meio | irritação diária | mergeado |
| 7d | M-13 modelo apaga rascunho local | 0/10 no voz latencia | pronto, aguardando merge |
| 7e | M-15 rotinas não disparam | etapa 8 | pronto, aguardando merge |
| 7f | M-16 vontades saturadas | etapa 9 | pronto, aguardando merge |
| 7g | M-14 muleta sem ferramenta · M-17 tranca na janela | latência/ruído | pronto, aguardando merge |
| 7h | M-18 modelo fraco derruba rascunho local | 0/10 ao vivo | mergeado |
| 7i | M-19 rotinas perdidas no sono · M-20 benchmark cego · M-21 refinamento encadeado | etapas 8 e 2 | pronto, aguardando merge |
| 7j | M-22 senha no diário | segurança | mergeado |
| 7k | M-24 barge-in com afplay (referência, calibração, dados) | prioridade do dia | pronto, aguardando merge |
| 7l | M-23 markdown na fala das rotinas | qualidade da voz | delegado ao Gemini |
| 7m | M-25 rotina bloqueia a demanda | 1–2 min de espera | mergeado |
| 7n | M-26 limiares do barge-in | prioridade do dia | pronto, aguardando merge |
| 7o | M-28 latência conta a muleta | medição da etapa 5 | pronto, aguardando merge |
| 7p | M-29 corte por eco (mín. 320 ms, 1,4×) | etapa 3 | mergeado |
| 7q | M-30 contagem por janela deslizante | etapa 3 | pronto, aguardando merge |
| 8 | M-08 frases fixas em cache | 1,4 s → 0,15 s nas respostas curtas | mergeado (Codex) |
| 9 | Fase 3 ao vivo: barge-in com fone, lote do Vigia, confiança progressiva, interjeição (`JAIME_INTERROMPER`) | validação | esperar João |

### Observações para o Cérebro Principal
- **Feito**: o log agora tem uma linha `🔈 jaime ›` por resposta (🔒 quando trancado). Antes só aparecia o que o João disse.
- A palavra-passe em uso ainda parece ser a padrão do `.env.example` (ouvida no log). Sugerir ao João trocar com `python -m jaime senha`.

## Ciclos
- 14:10 — leitura inicial; serviço caído detectado; Cérebro avisado; M-01 corrigido e commitado (10ff5ea).
- 14:45 — M-02 implementado (3 zonas + EMA + amostras; silêncio trancado; senha digitada sem voz) e M-06; 187 testes; Cérebro avisado.
- 15:05 — serviço voltou às 14:10 (Cérebro, JAIME_BARGE_IN=off). No log pós-reinício o João repete a senha 3× e pede a interface 3× sem ser atendido — é o M-02; merge urgente. Commitados: `🔈 jaime ›` no log e M-05 (Notion).
- 15:35 — Cérebro mergeou os 5 commits na main (194 testes, serviço no ar com barge-in ligado). `git merge main` feito. M-04 medido e corrigido com rascunho local (commits WIP + testes); 200 testes.
- 15:55 — M-09 (muleta logo após a ferramenta) commitado; 205 testes. M-08 aguardando o Codex.
- 16:05 — Vigília reportou etapas 2 e 5 falhando (mesma leitura: 0/10, TTS OpenAI). Respondi; M-10 (motivo da antecipação no diário) commitado; 206 testes.
- 18:15 — retomada após pausa. Cérebro mergeou M-09/M-10/M-11 e o M-08 do Codex. Vigília: 0/10 persiste → causa era o modelo apagando o rascunho local em `_refinar`; corrigido (216 testes). Rotinas do dia nunca dispararam (M-15) — investigando.
- 23:50 — M-15 reproduzido (Mac dormiu 876 s; grace 1 s) e corrigido; M-16 (vontades idempotentes, piso da Maestria) corrigido; 219 testes. Cérebro avisado: 22aec49, f7c2e96, 38de1d5 aguardam merge.
- 00:05 (16/09) — M-14 e M-17 commitados (07665d8); 220 testes. Quatro commits aguardam merge: 22aec49, f7c2e96, 38de1d5, 07665d8.
- 00:30 (16/09) — Vigília: 0/10 persistia com 22aec49 no ar. Causa: rascunho fraco do modelo derrubava o local. M-18 commitado (8e71b28); 222 testes. Fila de merge: 22aec49, f7c2e96, 38de1d5, 07665d8, 8e71b28.
- 07:50 (16/09) — Vigília: 'nenhuma' 10/10 e 06:30/07:00 sem disparar. Reproduzi o benchmark cego com o Deepgram real (1º parcial só chega em ~216 ms, depois de todo o áudio) — fac9c82; catch-up de rotinas no boot — 5b7fcd9. 227 testes (+1 alheio, data-dependente).
- 08:10 (16/09) — benchmark real com a Mente: 7/10, 320 ms, meta OK. M-21 (refinamento encadeado) e M-22 (redator de segredos) commitados; 231 testes. Fila de merge: fac9c82, 5b7fcd9, 3735934, redator, regex.
- 08:00 (16/09) — main mergeada (tudo meu já está nela). Prioridade do Cérebro: áudio liso + barge-in. Barge-in não cortou o briefing: 3 causas achadas, corrigidas e instrumentadas (M-24); M-23 delegado ao Gemini. 233 testes.
- 08:25 (16/09) — Vigília: rotina bloqueia o João (66–122 s). M-25: demanda interrompe a rotina e a reagenda; 237 testes.
- 08:40 (16/09) — Vigília trouxe os números do M-24: limiares recalibrados + regra de voz sustentada (M-26); 242 testes.
- 08:35 (16/09) — M-28 (1º som do turno, muleta incluída); 243 testes. Fila de merge: 5f0e06d, 17f30b3, M-28.
- 09:05 (16/09) — 2 cortes por eco (160/224 ms) → M-29; 248 testes. Fila de merge: 8bd2ffb (M-28), 7d9d4c6 (M-29).
- 09:35 (16/09) — Vigília: energia/sustentação passam, não corta → contador consecutivo era o bug; janelas deslizantes (M-30); 254 testes.
