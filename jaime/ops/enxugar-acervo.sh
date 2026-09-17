#!/bin/bash
# Enxuga o acervo de agentes e skills. As descrições de TODOS entram no contexto a cada turno
# do Jaime — hoje ~41 mil tokens. Apagar o que você não usa devolve isso em latência e custo.
#
#   bash jaime/ops/enxugar-acervo.sh                  # só mostra o peso, não apaga nada
#   bash jaime/ops/enxugar-acervo.sh --tirar windows powershell azure blockchain
#   git checkout .claude/                             # desfaz tudo (está tudo versionado)
set -euo pipefail
cd "$(dirname "$0")/../.."
peso(){ python3 - <<'PY'
import re,pathlib
a=sum(len(p.stem)+len(m.group(1)) for p in pathlib.Path('.claude/agents').glob('*.md')
      if (m:=re.search(r'^description:\s*(.*)$',p.read_text(errors="ignore"),re.M)))
s=sum(len(p.name)+len(m.group(1)) for p in pathlib.Path('.claude/skills').iterdir() if p.is_dir()
      and (p/'SKILL.md').is_file() and (m:=re.search(r'^description:\s*(.*)$',(p/'SKILL.md').read_text(errors="ignore"),re.M)))
n=len(list(pathlib.Path('.claude/agents').glob('*.md')))-1
k=sum(1 for p in pathlib.Path('.claude/skills').iterdir() if p.is_dir())
print(f"{n} agentes · {k} skills · ~{(a+s)//4} tokens somados ao contexto de CADA turno")
PY
}
lados(){ .venv/bin/python - <<'PY2'
from pathlib import Path
from jaime.cerebros.tripulacao import classificar
c = classificar(Path("."))
for lado in ("central", "esquerdo", "direito"):
    print(f"  {lado:<9} {len(c[lado]):>4} agentes")
PY2
}
if [ "${1:-}" = "--lados" ]; then peso; echo; lados; exit 0; fi
if [ "${1:-}" != "--tirar" ]; then peso; echo; lados; echo
  echo "cortar por palavra:  bash $0 --tirar windows powershell azure"
  echo "teto sem apagar:     JAIME_AGENTES_MAX=200 no .env (maesters entram sempre)"
  exit 0; fi
shift
echo "antes:"; peso
for termo in "$@"; do
  [ "$termo" = "maester" ] && { echo "recusado: os maesters são a casa"; continue; }
  find .claude/agents -iname "*${termo}*.md" ! -iname "maester-*" -print -delete
  find .claude/skills -maxdepth 1 -type d -iname "*${termo}*" -print -exec rm -rf {} +
done
echo; echo "depois:"; peso
echo; echo "reinicie:  launchctl kickstart -k gui/\$(id -u)/com.jaime"
