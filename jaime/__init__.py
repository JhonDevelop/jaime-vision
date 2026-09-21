"""Jaime — assistente pessoal com voz, cérebro Obsidian e acesso ao computador."""
import os as _os

# BLAS com UMA thread, antes de qualquer `import numpy` (este módulo roda antes de todos os `jaime.*`).
# 21/09 15:20 o serviço travou (deadlock, não crash): um fork (osascript/afplay/maestri) chamou o atfork do OpenBLAS,
# que tenta juntar os workers enquanto um dgemm (falantes/telemetria) ainda os espera — quem forkou segura o GIL e
# HUD, ouvido e Mente param para sempre. A carga BLAS do Jaime é minúscula; o pool só custa. (M-46)
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")
del _os, _v

__version__ = "0.1.0"
