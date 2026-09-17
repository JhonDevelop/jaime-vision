---
name: como-rodar-whisper-em-gpu-num-mac-intel
description: Mac Intel com GPU AMD discreta (ex.: Radeon Pro 5500M/5600M/Vega) e Metal 3, macOS 12.3+, usando openai-whisper + PyTorch (não whisper.cpp).
---

Para checar se um Mac Intel roda algo em GPU via PyTorch: 1) confirmar que tem GPU AMD discreta (system_profiler SPDisplaysDataType) com Metal 3; 2) criar venv, pip install torch; 3) python3 -c 'import torch; print(torch.backends.mps.is_available())'; 4) se True, testar de verdade com um tensor real em device='mps' antes de confiar só no is_available(). Para libs específicas (como whisper.cpp), sempre checar se o backend GPU delas é genérico (PyTorch/MPS) ou otimizado só para Apple Silicon (ggml/Metal), pois o suporte pode divergir do PyTorch.
