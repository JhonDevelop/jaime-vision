# Expansão espacial do J.A.I.M.E

Gestos, cena virtual no HUD, voz contextual ("abre isso"), ações no computador com recibo e Undo, várias telas,
várias câmeras, Air Canvas, gestos ensináveis, IA local e evolução medida. Tudo **desligado por padrão**: com
`JAIME_SPATIAL=off` nada é criado — nem task, nem câmera, nem ferramenta nova — e o Jaime roda exatamente como antes.

Base: pacote *JAIME_Spatial_Expansion_Claude_Code* (gerado sobre o commit `0948e37`), adaptado à casa na branch
`feat/espacial`. Relatório de cada fase com números medidos: [`docs/espacial/RELATORIO.md`](espacial/RELATORIO.md).

## Ligar em 30 segundos (sem câmera)

```bash
# demo isolada: cockpit + mão simulada, sem cérebro/voz, porta 8788 (não mexe no serviço da 8787)
python -m jaime espacial hud
# no terminal, sem navegador:
python -m jaime espacial demo            # eventos + métricas
python -m jaime espacial bench 20        # 20 s em tempo real a 30 fps: p50/p95 do caminho quente
python -m jaime espacial inventario      # SO/CPU/GPU/câmeras/monitores/engines/frota (só leitura)
```

No serviço de verdade: `JAIME_SPATIAL=sim` no `.env` e reiniciar. O chip **✋** aparece no canto do cockpit;
**X** (ou "Jaime, desliga o rastreamento") é o kill switch.

## Modos (`JAIME_SPATIAL`)

| valor | o que faz |
|---|---|
| `off` (padrão) | nada existe |
| `sim` | mão sintética em laço (cenário `JAIME_SPATIAL_CENARIO`: `demo`, `pinca`, `clique`, `perda`, `parcial`, `duas_maos`) |
| `replay` | reproduz um JSONL de landmarks (`JAIME_SPATIAL_REPLAY=…`) — só pontos, nunca imagem |
| `camera` | webcam real + MediaPipe. Exige `pip install opencv-python mediapipe` (decisão do João) e roda **só** com o cérebro destrancado e sem convidado na linha |

Outras: `JAIME_SPATIAL_DRY_RUN=on` (ações no SO só em prévia), `JAIME_SPATIAL_FRAME_QUEUE=2`,
`JAIME_SPATIAL_MIN_CONFIDENCE=0.85`, `JAIME_SPATIAL_RAIZES` (pastas onde gesto/voz podem abrir ou mandar para a
Lixeira; padrão `JAIME_WORKSPACE`), `JAIME_SPATIAL_TTL_S=20` (quanto tempo "isso" vale), `JAIME_SPATIAL_CAMERA_IDS`,
`JAIME_SPATIAL_CALIBRATION_FILE`. Todas em `.env.example`.

## Como funciona

```
câmera/sim/replay ─► fila (1–2, descarta o velho) ─► landmarks (thread) ─► One Euro ─► pinça ─► bus "espacial" ─► HUD
                                                                                         │
                     voz ("abre isso") ─► Resolvedor (seleções + TTL) ─► contexto do turno / pergunta de 1 frase
                                                                                         │
            gesto/voz/ferramenta ─► prévia ─► política + recurso canônico ─► Vigia ─► execução|dry-run ─► recibo ─► Undo
```

- **Sem LLM por frame.** O reflexo (pinça, arrasto, seleção) é local e mede frações de milissegundo; o cérebro só
  entra quando há fala ou intenção complexa.
- **Um bus só.** Eventos `espacial` vão pelo `Bus` existente; cursor e arrasto são efêmeros (`_efemero=True`) e não
  apagam o histórico de 300 que o HUD recarrega.
- **Gestos:** apontar = hover; pinça curta e parada = clique (só seleção); pinça sustentada = agarrar/arrastar
  (virtual); duas mãos = escala; mão some = `tracking_lost` + cancelamento (o objeto volta). Histerese, dwell e
  cooldown evitam disparo por tremor.
- **"Isso":** a seleção mais recente dentro do TTL. Duas seleções quase juntas + verbo de ação → "Qual deles: A ou B?"
  sem chamar o modelo; a resposta ("o BUB", "a da esquerda", "a primeira") resolve e devolve o pedido original.
  Cuidado com o português: "está aí?" não é "esta"; "isso"/"isso mesmo" é concordância; com lote do Vigia aguardando,
  "faz isso" é aprovação e não passa pelo espacial.
- **Ações no SO** (abrir pasta, mover janela, mover para a Lixeira): sempre prévia; só o dono destrancado; confiança
  mínima; caminho canônico dentro das raízes (sem `..`, sem symlink escapando; vault, `.env` e `jaime/vigia` proibidos);
  o **mesmo Vigia** das ferramentas; recibo idempotente (repetir o evento devolve o mesmo recibo); Undo. Lixeira é
  sempre revisão: pelo HUD (botão Confirmar) ou pela voz (ferramenta `apagar`, que o Vigia segura até o "sim").
  Apagar definitivo, publicar, enviar, instalar: **não existem como gesto**.
- **Monitores:** geometria lógica por backend (Quartz no Mac, Win32 no Windows, xrandr no Linux), impressão digital do
  layout; plugou/desplugou/girou/mudou escala → ações de janela suspensas até validar. "Manda para o monitor da
  direita" calcula o destino mantendo a posição relativa.
- **Câmeras:** 3D só com ≥2 câmeras calibradas, sincronizadas, com erro de reprojeção abaixo do limite; senão, 2D.
- **Air Canvas:** modo desenho explícito; formas são sugestões até você rotular; grafo com evidência; Mermaid/JSON;
  matemática por parser próprio (nunca `eval`) + SymPy num processo com prazo, com verificação por substituição.
- **Gestos ensináveis:** consentimento, 5–12 demonstrações, ≥3 negativos, validação separada, ≤1 falsa ativação/h,
  sem ambiguidade; só ações reversíveis; "esquece o gesto X" apaga os exemplos.
- **IA local:** `JAIME_LOCAL_AI=on` + modelo + endpoint do dono. Nunca troca o Central sozinha: rota só por
  `JAIME_LOCAL_AI_TIPOS` (depois do `python -m jaime cortex bench-local`) ou "…pelo modelo local". Estrito = sem nuvem
  escondida. Fora do loopback exige HTTPS (HTTP na LAN só com token + `JAIME_LOCAL_AI_LAN_HTTP=on`); confirmação do
  Vigia nunca vai ao local. PAIR/OpenShell são proxies opcionais para um nó RTX da frota; o Mac Intel não roda CUDA.
- **Evolução medida:** `python -m jaime espacial experimento dwell_s=0.06 "hipótese"` mede em replay contra o atual e
  promove só se passar (acerto, falsos/h, latência); `python -m jaime espacial reverter` volta. Só limiares se
  promovem sozinhos; o resto vira PR com o mesmo gate (`Evolucao(gate=…)`).

## Ferramentas do cérebro (MCP `espacial`, só com a flag ligada)

`estado`, `selecionar`, `criar_objeto`, `propor_acao` (open, move_window com `x,y` ou `monitor`), `executar`,
`apagar` (Lixeira, segurado pelo Vigia), `desfazer`.

## Rotas

`GET /espacial/estado` · `POST /espacial/ligar|desligar` · `POST /espacial/selecionar` · `POST /espacial/latencia` ·
`GET /espacial/acoes` · `POST /espacial/acoes/{id}/confirmar` · `POST /espacial/recibos/{id}/desfazer` ·
`POST /espacial/descartes/{token}/desfazer` · `POST /espacial/telas/validar`. Rotas que mudam estado (ligar, selecionar, confirmar, desfazer, validar) só da própria máquina e do próprio HUD
(checagem de Origin). Abrir programa/script por gesto é sempre revisão.

## Privacidade

Frames vivem um ciclo, em memória. Nada de imagem em SSE, vault, log ou treino. Replays e gestos guardam só
landmarks. Recibos (`~/Jaime/espacial/recibos.jsonl`) guardam decisão, IDs e latência — não conteúdo. O vault não é
escrito por esta camada; os objetos de projeto usam só o **nome** das notas de `20-Projetos/`.

## Windows (reinstalação)

A camada espacial já tem backends Windows (monitores e janelas por Win32, Lixeira com Undo do sistema, câmeras por
DirectShow no inventário). O resto do Jaime ainda assume macOS em alguns pontos — `maos/computador.py`
(screencapture), `ops/notificacoes.py` e `ops/observador.py` (APIs do Mac), `voice/tts.py`/`narrador.py` (afplay/say),
`casa/camera.py` (avfoundation), `ops/permissoes.py` e o serviço (LaunchAgent). Esses precisam de equivalentes
Windows antes da reinstalação; num PC com RTX, o mesmo host serve a IA local.
