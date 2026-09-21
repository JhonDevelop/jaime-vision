#!/usr/bin/env bash
# Jaime sempre ligado: LaunchAgent do macOS (sobe no login, reinicia se cair).
#   bash jaime/ops/servico.sh instalar   # cria ~/Library/LaunchAgents/com.jaime.plist e liga
#   bash jaime/ops/servico.sh parar | ligar | status | remover | saude (healthcheck 1×) | vigiar (healthcheck de minuto em minuto)
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
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin</string>
    <!-- M-46: BLAS com 1 thread — fork (osascript/afplay/maestri) × pool do OpenBLAS travava o processo inteiro -->
    <key>OPENBLAS_NUM_THREADS</key><string>1</string><key>OMP_NUM_THREADS</key><string>1</string><key>MKL_NUM_THREADS</key><string>1</string>
  </dict>
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
  saude)
    # Healthcheck externo (M-46): o LaunchAgent só religa processo MORTO; um deadlock (fork × OpenBLAS, 21/09 15:20) fica
    # vivo para sempre com a porta muda. Se /hud/sistemas não responder em 10 s, 3 vezes seguidas (~30 s), mata o
    # processo (kill -9) e o KeepAlive religa. Para rodar de minuto em minuto: `servico.sh vigiar`.
    for tentativa in 1 2 3; do
      if curl -s -m 10 -o /dev/null http://127.0.0.1:8787/hud/sistemas; then echo "ok"; exit 0; fi
      sleep 5
    done
    PID="$(pgrep -f 'python -u -m jaime serve' | head -1 || true)"
    if [ -n "$PID" ]; then
      echo "$(date '+%Y-%m-%d %H:%M:%S') ⚠ healthcheck: serviço travado (pid $PID, porta muda por ~30 s); matando para o LaunchAgent religar" | tee -a "$LOG"
      kill -9 "$PID" 2>/dev/null || true
      pkill -f falantes_worker 2>/dev/null || true
    else
      echo "porta muda e nenhum 'jaime serve' vivo — o LaunchAgent deve religar sozinho" | tee -a "$LOG"
    fi;;
  vigiar)
    VPLIST="$HOME/Library/LaunchAgents/com.jaime.saude.plist"
    cat > "$VPLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.jaime.saude</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$RAIZ/jaime/ops/servico.sh</string><string>saude</string></array>
  <key>StartInterval</key><integer>60</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$HOME/Jaime/saude.log</string>
  <key>StandardErrorPath</key><string>$HOME/Jaime/saude.log</string>
</dict></plist>
EOF
    launchctl bootout "gui/$(id -u)/com.jaime.saude" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$VPLIST"
    echo "✔ healthcheck de minuto em minuto (log: ~/Jaime/saude.log); remover: launchctl bootout gui/$(id -u)/com.jaime.saude";;
  *) echo "uso: servico.sh instalar|ligar|parar|status|remover|saude|vigiar"; exit 2;;
esac
