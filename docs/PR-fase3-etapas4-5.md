# PR — Fase 3, etapas 4 e 5: casa/câmera e visão contínua

**Branch:** `feat/fase3-casa-visao` → `main`

## O que muda
- `jaime/casa/`: cliente REST do Home Assistant (`estados`, `achar`, `ligar`, `desligar`, `servico`, `snapshot_camera`),
  câmera (webcam via ffmpeg/avfoundation ou câmera do HA), MCP `casa` (`casa_estado`, `casa_ligar`, `casa_desligar`,
  `casa_servico`, `camera_ver`).
- `jaime/maos/visao.py` + MCP `visao` (`jogar`, `parar_visao`, `situacao_visao`): sessão de visão contínua com decisão do
  modelo por imagem, limites (`JAIME_VISAO_MAX_PASSOS`, `JAIME_VISAO_INTERVALO_S`) e kill switch "para"/"chega" no `_porta`
  (também interrompe objetivo autônomo). Vigia libera ações de tela só com sessão ativa.
- `docs/CONEXOES.md` › Home Assistant e câmera; `.env.example`: `HA_URL`, `HA_TOKEN`, `JAIME_CAMERA`, limites de visão.

## Como testar
```
pytest -q                                   # 99 testes; HA com HTTP dublê, visão com decisor offline, Vigia por sessão
# HUD (com HA): "Jaime, apaga a luz do escritório" · "Jaime, o que tem na câmera?" · "Jaime, joga: passe de fase no jogo aberto" → "para"
```
