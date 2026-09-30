#!/usr/bin/env bash
# Hermes Agent ao lado do J.A.I.M.E (macOS/Linux) — rode VOCÊ, João, no terminal: bash scripts/hermes/instalar.sh
# O que faz (docs/HERMES.md): instala o Hermes pelo instalador oficial da Nous Research (pergunta antes), liga a API
# local dele (127.0.0.1:8642) com uma chave aleatória, põe aprovação MANUAL de comandos perigosos (quem aprova é você,
# pelo Vigia do Jaime), grava HERMES_API_KEY e JAIME_HERMES=on no .env do Jaime SEM mostrar a chave, e deixa o gateway
# do Hermes como serviço (LaunchAgent com.jaime.hermes no Mac). Nada aqui roda sozinho: cada passo pergunta.
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_JAIME="$RAIZ/.env"
pergunta() { read -r -p "$1 [s/N] " r; case "$r" in [sS]*) return 0;; *) return 1;; esac; }

if [[ "$(uname)" == "Darwin" && "$(uname -m)" == "x86_64" ]]; then
  echo "⚠ Mac Intel: o Hermes atual não suporta (cryptography 50 não tem versão para Intel; o instalador tenta compilar e"
  echo "  falha sem OpenSSL). Testado em 30/09/2026 neste Mac. Use o Windows (scripts/hermes/instalar.ps1) ou um Mac Apple Silicon."
  pergunta "Tentar mesmo assim?" || exit 0
fi
if ! command -v hermes >/dev/null 2>&1; then
  echo "Hermes não encontrado. Instalador oficial: curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"
  pergunta "Rodar o instalador oficial agora?" || { echo "ok, nada instalado."; exit 0; }
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
  export PATH="$HOME/.local/bin:$HOME/.hermes/bin:$PATH"
fi
hermes --version | head -1

echo "→ modelo: se ainda não escolheu o provedor (Anthropic/OpenRouter/Nous Portal/Ollama), o setup pergunta agora."
if ! hermes config get model 2>/dev/null | grep -q .; then hermes setup; fi

echo "→ segurança: aprovação manual + negações duras"
hermes config set approvals.mode manual
hermes config set approvals.deny '["git push --force*", "git push*main*", "*curl*|*sh*", "sudo *", "rm -rf /*", "mkfs*", "shutdown*"]'

echo "→ API local do Hermes (só 127.0.0.1)"
CHAVE="$(openssl rand -hex 24)"
hermes config set API_SERVER_ENABLED true >/dev/null
hermes config set API_SERVER_KEY "$CHAVE" >/dev/null
hermes config set API_SERVER_HOST 127.0.0.1 >/dev/null
touch "$ENV_JAIME"; chmod 600 "$ENV_JAIME"
grep -v -E '^(HERMES_API_KEY|JAIME_HERMES|HERMES_URL)=' "$ENV_JAIME" > "$ENV_JAIME.tmp" || true
{ cat "$ENV_JAIME.tmp"; echo "JAIME_HERMES=on"; echo "HERMES_URL=http://127.0.0.1:8642"; echo "HERMES_API_KEY=$CHAVE"; } > "$ENV_JAIME"
rm -f "$ENV_JAIME.tmp"; unset CHAVE
echo "  chave gravada no .env do Jaime e no ~/.hermes/.env (não mostrada)."

if pergunta "Importar skills, MCPs e instruções do Claude Code (~/.claude) para o Hermes?"; then
  hermes import-agent claude-code --dry-run && pergunta "Aplicar?" && hermes import-agent claude-code --yes
fi

if [[ "$(uname)" == "Darwin" ]] && pergunta "Deixar o gateway do Hermes sempre ligado (LaunchAgent com.jaime.hermes)?"; then
  bash "$RAIZ/jaime/ops/hermes.sh" instalar
else
  echo "Para subir na mão: hermes gateway   (API em http://127.0.0.1:8642)"
fi
echo "Pronto. Reinicie o Jaime (bash jaime/ops/servico.sh parar && ligar) e pergunte: 'Jaime, o Hermes está no ar?'"
