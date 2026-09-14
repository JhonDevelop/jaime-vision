#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "▶ Python venv"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -e ".[dev]"

read -r -p "Instalar dependências de voz (Porcupine, Whisper, ElevenLabs)? [s/N] " voz
if [[ "${voz,,}" == "s" ]]; then
  pip install -e ".[voice]"
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "▶ Claude Code CLI não encontrado — instalando (o Agent SDK usa o CLI por baixo)"
  npm install -g @anthropic-ai/claude-code
fi

[[ -f .env ]] || cp .env.example .env
echo
echo "✔ Pronto. Preencha o .env (ANTHROPIC_API_KEY no mínimo) e rode:"
echo "   source .venv/bin/activate && python -m jaime chat"
echo
echo "Para autenticar os MCPs remotos (GitHub, Notion, n8n), abra 'claude' nesta pasta e use /mcp."
