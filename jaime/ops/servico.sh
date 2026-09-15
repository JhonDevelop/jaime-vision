#!/usr/bin/env bash
# Jaime sempre ligado: LaunchAgent do macOS (sobe no login, reinicia se cair).
#   bash jaime/ops/servico.sh instalar   # cria ~/Library/LaunchAgents/com.jaime.plist e liga
#   bash jaime/ops/servico.sh parar | ligar | status | remover
# Permissões (microfone, câmera, tela, acessibilidade) ficam ligadas ao binário .venv/bin/python — se o macOS não
# perguntar sozinho, adicione-o em Ajustes › Privacidade e Segurança. Logs em ~/Jaime/jaime.log.
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.jaime.plist"
LOG="$HOME/Jaime/jaime.log"
mkdir -p "$HOME/Jaime" "$HOME/Library/LaunchAgents"
case "${1:-status}" in
  instalar)
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.jaime</string>
  <key>ProgramArguments</key><array>
    <string>$RAIZ/.venv/bin/python</string><string>-u</string><string>-m</string><string>jaime</string><string>serve</string>
  </array>
  <key>WorkingDirectory</key><string>$RAIZ</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict></plist>
EOF
    launchctl bootout "gui/$(id -u)/com.jaime" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
    echo "✔ instalado e ligado (log: $LOG)";;
  ligar)   launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || launchctl kickstart -k "gui/$(id -u)/com.jaime"; echo "ligado";;
  parar)   launchctl bootout "gui/$(id -u)/com.jaime" 2>/dev/null && echo "parado" || echo "já estava parado";;
  remover) launchctl bootout "gui/$(id -u)/com.jaime" 2>/dev/null || true; rm -f "$PLIST"; echo "removido";;
  status)  launchctl print "gui/$(id -u)/com.jaime" 2>/dev/null | grep -E "state|pid" | head -3 || echo "não instalado";;
  *) echo "uso: servico.sh instalar|ligar|parar|status|remover"; exit 2;;
esac
