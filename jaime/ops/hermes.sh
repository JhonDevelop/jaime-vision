#!/usr/bin/env bash
# Gateway do Hermes Agent como LaunchAgent (com.jaime.hermes): sobe no login, reinicia se cair. Log em ~/Jaime/hermes.log.
#   bash jaime/ops/hermes.sh instalar | ligar | parar | status | remover
set -euo pipefail
PLIST="$HOME/Library/LaunchAgents/com.jaime.hermes.plist"
LOG="$HOME/Jaime/hermes.log"
HERMES="$(command -v hermes || echo "$HOME/.local/bin/hermes")"
mkdir -p "$HOME/Jaime" "$HOME/Library/LaunchAgents"
case "${1:-status}" in
  instalar)
    cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.jaime.hermes</string>
  <key>ProgramArguments</key><array><string>$HERMES</string><string>gateway</string></array>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string></dict>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/><key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$LOG</string><key>StandardErrorPath</key><string>$LOG</string>
</dict></plist>
PL
    launchctl bootout "gui/$(id -u)/com.jaime.hermes" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST"; echo "✔ Hermes como serviço (log: $LOG)";;
  ligar)   launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || launchctl kickstart -k "gui/$(id -u)/com.jaime.hermes"; echo ligado;;
  parar)   launchctl bootout "gui/$(id -u)/com.jaime.hermes" 2>/dev/null && echo parado || echo "já estava parado";;
  remover) launchctl bootout "gui/$(id -u)/com.jaime.hermes" 2>/dev/null || true; rm -f "$PLIST"; echo removido;;
  status)  launchctl list | grep com.jaime.hermes || echo "não instalado"; curl -s -m 3 http://127.0.0.1:8642/health || true; echo;;
  *) echo "uso: hermes.sh instalar|ligar|parar|status|remover"; exit 2;;
esac
