#!/usr/bin/env bash
# uso: scripts/run.sh chat|voice|serve
cd "$(dirname "$0")/.." && source .venv/bin/activate && exec python -m jaime "${1:-chat}"
