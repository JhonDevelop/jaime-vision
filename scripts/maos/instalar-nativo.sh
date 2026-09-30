#!/bin/bash
# Rastreador nativo das mãos (controle do computador com o Safari escondido). Decisão do João: rodar quando quiser.
# Instala opencv-python e mediapipe no .venv do Jaime (~60 MB). Não mexe em mais nada.
set -e
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
[ -x "$PY" ] || { echo "não achei .venv/bin/python"; exit 1; }
echo "→ versão do Python: $($PY --version)  ·  máquina: $(uname -m)"
$PY -m pip install --upgrade "opencv-python<5" "mediapipe==0.10.14" || {
  echo "✗ o mediapipe não instalou (Mac Intel + Python $($PY -c 'import sys;print(sys.version[:4])') pode não ter wheel)."
  echo "  O controle pela aba do Jarvis continua funcionando; deixe a janela dele visível."
  exit 1; }
$PY -c "import cv2, mediapipe; print('✔ opencv', cv2.__version__, '· mediapipe', mediapipe.__version__)"
echo "Agora: acrescente JAIME_MAOS_NATIVO=on no .env, reinicie o Jaime e dê permissão de Câmera ao Python dele"
echo "(Ajustes do Sistema › Privacidade e Segurança › Câmera) quando o macOS pedir."
