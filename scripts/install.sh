#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "▶ Python >= 3.11"
PY_BIN=""
for c in python3.14 python3.13 python3.12 python3.11 python3; do
  command -v "$c" >/dev/null 2>&1 || continue
  if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
    PY_BIN="$(command -v "$c")"; break
  fi
done
if [[ -z "$PY_BIN" ]]; then
  echo "  nenhum Python >= 3.11 encontrado — instalando via uv"
  command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  uv python install 3.12
  PY_BIN="$(uv python find 3.12)"
fi
echo "  usando $PY_BIN ($("$PY_BIN" --version))"

echo "▶ Python venv"
"$PY_BIN" -m venv .venv
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -e ".[dev]"

# JAIME_VOICE=1 instala sem perguntar (bash 3.2 do macOS não tem "${v,,}")
voz="${JAIME_VOICE:-}"
if [[ -z "$voz" ]]; then
  read -r -p "Instalar dependências de voz (Porcupine, Whisper, ElevenLabs)? [s/N] " voz
fi
voz="$(printf '%s' "$voz" | tr '[:upper:]' '[:lower:]')"
if [[ "$voz" == "s" || "$voz" == "1" || "$voz" == "sim" ]]; then
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
echo "Para autenticar os MCPs remotos (GitHub, Notion), abra 'claude' nesta pasta e use /mcp."
