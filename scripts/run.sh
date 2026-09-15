#!/usr/bin/env bash
# Sobe o Jaime (HUD + voz + API) nesta janela do Terminal. É esta janela/app que o macOS vai perguntar sobre
# microfone, câmera, gravação de tela e acessibilidade — conceda ao Terminal e as permissões valem para o Jaime.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
lsof -ti tcp:8787 | xargs kill 2>/dev/null || true
pkill -f "_bundled/claude" 2>/dev/null || true
sleep 1
echo "▶ Jaime subindo em http://127.0.0.1:8787 — Ctrl+C encerra"
exec .venv/bin/python -u -m jaime hud
