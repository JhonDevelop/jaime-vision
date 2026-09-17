#!/bin/bash
# Mede o que o J.A.I.M.E CARREGA por turno — não quantos arquivos existem no disco. A diferença é o ponto:
# o acervo guarda centenas de agentes e skills fora do contexto, alcançáveis por mcp__acervo__buscar.
#
#   bash jaime/ops/enxugar-acervo.sh                  # mede
#   bash jaime/ops/enxugar-acervo.sh --lados          # mede e mostra por hemisfério
#   bash jaime/ops/enxugar-acervo.sh --tirar windows powershell azure
#   git checkout .claude/                             # desfaz (está tudo versionado)
set -euo pipefail
cd "$(dirname "$0")/../.."

peso() { .venv/bin/python jaime/ops/medir_acervo.py; }
lados() { .venv/bin/python - <<'PY'
from pathlib import Path
from jaime.cerebros.tripulacao import classificar
c = classificar(Path("."))
for lado in ("central", "esquerdo", "direito"):
    print(f"  {lado:<9} {len(c[lado]):>4} agentes")
PY
}

if [ "${1:-}" = "--lados" ]; then peso; echo; lados; exit 0; fi
if [ "${1:-}" != "--tirar" ]; then
  peso; echo; lados; echo
  echo "cortar por palavra:  bash $0 --tirar windows powershell azure"
  echo "teto de carregados:  JAIME_AGENTES_MAX no .env (hoje 40; os maesters entram sempre)"
  exit 0
fi
shift
echo "antes:"; peso
for termo in "$@"; do
  [ "$termo" = "maester" ] && { echo "recusado: os maesters são a casa"; continue; }
  find .claude/agents .claude/acervo/agents -iname "*${termo}*.md" ! -iname "maester-*" -print -delete 2>/dev/null || true
  find .claude/skills .claude/acervo/skills -maxdepth 1 -type d -iname "*${termo}*" -print -exec rm -rf {} + 2>/dev/null || true
done
echo; echo "depois:"; peso
echo; echo "reinicie:  launchctl kickstart -k gui/\$(id -u)/com.jaime"
