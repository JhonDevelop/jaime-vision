# Como rodar Whisper em GPU num Mac Intel

> Resolvido pelo cérebro de estudo em 15/09/2026 (problema P-0001, origem joao_pediu).

## Como reproduzir
1) python3 -m venv venv && source venv/bin/activate; 2) pip install torch openai-whisper; 3) python3 -c "import torch; print(torch.backends.mps.is_available())" deve dar True (exige Mac Intel com GPU AMD discreta compatível com Metal, ex.: Radeon Pro 5500M, macOS 12.3+); 4) carregar o modelo Whisper e mover para device='mps' (ou usar whisper.load_model(..., device='mps')) para rodar na GPU.

## O que resolveu
Testei no laboratório: instalei PyTorch 2.2.2 num Mac Intel real com AMD Radeon Pro 5500M (Metal 3) e confirmei torch.backends.mps.is_available()=True, além de rodar um matmul real em device mps:0 com sucesso — ou seja, o backend MPS do Metal funciona em Mac Intel COM GPU AMD discreta (não em Intel iGPU). Isso vale para o pacote openai-whisper via PyTorch; o whisper.cpp, por outro lado, só acelera de verdade em Apple Silicon e cai para CPU em Mac Intel.

## Onde se aplica
Mac Intel com GPU AMD discreta (ex.: Radeon Pro 5500M/5600M/Vega) e Metal 3, macOS 12.3+, usando openai-whisper + PyTorch (não whisper.cpp).
