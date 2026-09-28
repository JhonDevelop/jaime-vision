# Relatório — expansão espacial (branch `feat/espacial`, base `0948e37`)

28/09/2026. Números abaixo foram **medidos** onde dito; metas do pacote não são tratadas como resultado.
Ambiente de medição: container Linux x86_64, Python 3.12, sem GPU/câmera/monitor (mesma versão de Python do Mac:
3.12.14). O que depende do hardware do João está marcado **PENDENTE** — nada aqui alega validação física.

## Auditoria

- HEAD local = HEAD do pacote (`0948e37`), então os pontos de integração não mudaram. `CLAUDE.md`, `README.md`,
  `pyproject.toml`, `docs/SEGURANCA.md`, `server.py`, `orchestrator/jaime.py`, `hud/events.py`, `maos/computador.py`,
  `vigia/hooks.py`, `evolucao.py`, `cortex/*` lidos antes de editar.
- **Achados no repositório (não mexidos):**
  - `jaime/server.py` no HEAD importa `jaime/ops/hotreload.py`, que existe só na cópia de trabalho do Mac (não
    commitado, junto com `tests/test_hotreload.py` e alterações em `ops/notificacoes.py`). Um clone limpo do GitHub
    — como o da reinstalação no Windows — quebra no boot. Commitar esses arquivos resolve.
  - `tests/test_cache_frases.py::test_cache_poda_lru_e_ignora_texto_longo` falha no Linux (LRU por `mtime` com
    `sleep(0.01)`: resolução de timestamp do sistema de arquivos). Pré-existente; no Mac provavelmente passa.
  - Os worktrees (`jaime-codex`, `jaime-hud`, …, `~/Jaime/worktrees/*`) aparecem como *prunable* quando o repositório
    é visto de fora do Mac. **Não** rode `git worktree prune` fora do Mac.
- **Inventário do host (Mac):** macOS Darwin 25.5 x86_64 (Intel — **sem CUDA**), Python 3.12.14 via uv; no `.venv`:
  pyobjc/Quartz, numpy 1.26.4, sympy 1.14, torch 2.2.2; **sem** OpenCV e **sem** MediaPipe. Frota (`01-Estado/Frota.md`)
  **vazia** — nenhum nó RTX. Câmeras, monitores, escala e GPU exata: o shell remoto roda numa VM Linux e não enxerga o
  hardware do Mac → rode `python -m jaime espacial inventario` no Mac (só leitura, sem seriais nem segredos).
- Pacote: `docs/*`, `overlay/`, `agents/` lidos; contratos conferidos contra a base e adaptados (ver abaixo).

## Suíte

| momento | resultado |
|---|---|
| antes (HEAD `0948e37`) | 577 passaram, 1 falhou (cache_frases, ambiente), 3 pulados |
| depois (`feat/espacial`) | **711 passaram**, 1 falhou (a mesma), 3 pulados — +134 testes novos, 0 regressão |

## Fase 0 — núcleo, flag, bus, simulador, HUD

- **Arquivos:** `jaime/spatial/{core,gestures,filtro,landmarks,simulador,servico,config,metricas,integracao,rotas}.py`
  + do pacote `{geometry,scene,policy,learner,benchmark,inference}.py`; `hud/events.py` (`_efemero`),
  `hud/static/espacial.js`, `cockpit.html` (+2 linhas), `server.py` (montagem no lifespan + rotas).
- **Adaptações ao pacote:** histórico de eventos era `list` sem limite (vazamento a 30 fps) → `deque`; seleção ganhou
  tempo e origem (TTL da fase 2); pinça ganhou clique, cooldown, cancelamento que devolve o objeto, escala a duas mãos;
  o bus existente recebeu eventos efêmeros para cursor/arrasto não expulsarem os 300 do histórico.
- **Testes:** `test_spatial_core.py` (os 6 do pacote), `test_espacial_servico.py` (14), `test_espacial_integracao.py` (7).
- **Demo reproduzível:** `python -m jaime espacial hud` → cockpit com a mão simulada (captura em `jaime-espacial-hud-fase0.png`),
  sem câmera e sem ação no SO. Com a flag off, `/espacial/estado` = `ativo:false` e o JS não instala nada.

## Fase 1 — rastreamento em tempo real

- **Arquivos:** `fontes.py` (sim/replay/OpenCV/MediaPipe, imports preguiçosos), `cli.py`, `inventario.py`, `telas.py`.
- **Medido** (`python -m jaime espacial bench 20`, 30 fps, landmarks simulados — **sem** o custo do MediaPipe):
  captura→evento p50 **0,22 ms** / p95 **0,35 ms**; fila p95 0,07 ms; 0 frames descartados.
  No cockpit em Chromium headless, 16 s: frame→evento no navegador p50 **0,7 ms** / p95 **3,2 ms** (n=388), 30,2 fps.
- **Fila bounded:** com rastreador de 20 ms e câmera a 200 fps a fila nunca passa de 2 e o p95 de espera fica < 150 ms
  (teste). Perda de rastreamento, câmera que cai e kill switch testados.
- **PENDENTE:** câmera real (instalar `opencv-python` + `mediapipe` é decisão sua; no Mac Intel a wheel do MediaPipe
  precisa ser conferida — no Windows é direto) e as "10 sessões de 2 min" do critério de aceite.

## Fase 2 — voz contextual

- **Arquivos:** `referencias.py`; gancho de 8 linhas em `Jaime._ask_stream` (só com a flag).
- **Testes:** `test_espacial_referencias.py` (14), incluindo o orquestrador real perguntando "Qual deles: SeventyOne ou
  BUB?" sem chamar o modelo, e o lote do Vigia com "faz isso" não sendo desviado.
- **Medido:** resolvedor p50 0,024 ms / p95 0,040 ms (3000 frases) — atraso extra desprezível na voz.
- **PENDENTE:** medir barge-in e fala→1ª frase com a flag ligada no Mac (o gancho não toca o pipeline de áudio).

## Fase 3 — ações reais

- **Arquivos:** `acoes.py`, `intencoes.py`, `tools.py` (MCP `espacial`), rotas de confirmar/desfazer; `_options` do
  orquestrador registra o MCP só com a flag.
- **Testes:** `test_espacial_acoes.py` (20): dry-run, idempotência, dono/confiança, `..`/symlink/vault, Lixeira com
  confirmação e Undo, janela que o SO ignorou vira erro, hotplug suspende, Vigia real, duplo clique, lixeira virtual.
- **PENDENTE:** AppleScript (System Events/Finder) e Win32 no hardware — exigem permissão de Acessibilidade.
  `JAIME_SPATIAL_DRY_RUN=on` até lá.

## Fases 4–5 — monitores e câmeras

- **Arquivos:** `telas.py` (Quartz/Win32/xrandr, hotplug, alvo por monitor, calibração presa ao layout), `multicamera.py`.
- **Testes:** `test_espacial_telas_cameras.py` (13) + 1 em ações ("monitor da direita").
- **Medido (sintético):** DLT com 2 câmeras e 1 px de ruído: erro p50 **3,2 mm** / p95 **8,5 mm**; calibração com 2°
  de erro é rejeitada pela reprojeção; câmeras fora da janela de 25 ms caem para 2D.
- **PENDENTE:** tabuleiro de calibração (OpenCV), grade física, 2–3 monitores reais com escala mista.

## Fase 6 — Air Canvas

- **Arquivos:** `canvas.py`, `matematica.py`. **Testes:** `test_espacial_canvas.py` (14).
- 4 nós + 4 arestas desenhados, confirmados, salvos, reabertos e exportados em Mermaid; `2x+3=11` e `x²−5x+6=0`
  resolvidos e verificados por substituição; 7 entradas maliciosas recusadas sem `eval`.
- **PENDENTE:** reconhecimento de escrita/LaTeX a partir do traço (hoje entra texto confirmado).

## Fase 7 — gestos ensináveis

- **Arquivos:** `gestos_pessoais.py`. **Testes:** `test_espacial_gestos_pessoais.py` (15).
- Gesto "Z" com 8 demonstrações: recall 1,0, precisão 1,0, 0 falsas ativações/h (fluxo sintético de 240 movimentos);
  um segundo "Z" é recusado por ambiguidade. Ações sensíveis recusadas na hora de ensinar.

## Fase 8 — IA local

- **Arquivos:** `cortex/provedores/local.py`, `cortex/bench_local.py`, `cortex/roteador.py` (rota explícita),
  orquestrador (ramo `local:`). **Testes:** `tests/test_ia_local.py` (16).
- Estrito: servidor local caído → aviso, **0 chamadas à nuvem** (teste no orquestrador real).
- **PENDENTE:** não há GPU NVIDIA no Mac Intel nem nó RTX na frota. Próximo passo: PC Windows com RTX roda Ollama/LM
  Studio → `JAIME_LOCAL_AI_BASE_URL`/`HOSTS`/`TOKEN` → `python -m jaime cortex bench-local` → você decide os tipos.
  PAIR só se instalado e compatível (RTX 20+); não inventamos API do Portable Computer.

## Fase 9 — evolução medida

- **Arquivos:** `spatial/experimentos.py`, `jaime/evolucao.py` (+gate opcional, sem mudança quando ausente).
- **Testes:** `test_espacial_experimentos.py` (15). **Demo:** `dwell_s 0,09→0,06` promovido (acerto 1,0 = baseline,
  0 falsos/h); `close_ratio 0,34` rejeitado (acerto 0,74, 1452 falsas ativações/h no replay); `reverter` volta.

## Próximo passo sugerido

1. Commitar `ops/hotreload.py` (+teste) no `main` para o clone limpo subir.
2. Rodar no Mac: `python -m jaime espacial inventario` e `python -m jaime espacial hud` (porta 8788, sem tocar no serviço).
3. Decidir: instalar OpenCV + MediaPipe (fase 1 física) já no Mac ou só no Windows novo.
