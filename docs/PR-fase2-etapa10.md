# PR — Fase 2, etapas 9 e 10: voz com persona/emoção; imagens, 3D, conteúdo, computer use

**Branches:** `feat/fase2-conexoes` (etapa 9) e `feat/fase2-imagens-3d-computador` (etapa 10) → `main`

## Etapa 9 — voz
- Motor `openai` (gpt-4o-mini-tts, voz `onyx`) com instrução de estilo = base "mordomo britânico em português" + prosódia do
  humor; ElevenLabs volta sozinha (auto) quando houver cota; reserva `say` masculina (Eddy).
- `jaime/voice/persona.py`: sem "Olá, sou o Jaime, seu assistente", sem muletas e fechos de atendente, "João" em vez de "senhor".
- `python -m jaime voz testar`: 5 vozes, escolha gravada no `.env`. `docs/VOZ-DESIGN.md`: onde achar uma voz Jarvis
  (OpenAI hoje; ElevenLabs Voice Design/Library com Starter).

## Etapa 10 — mídia e computer use
- `maos/imagens.py` (gpt-image-2.5 → `~/Jaime/imagens`), `maos/blender.py` (headless; script salvo mesmo sem Blender),
  `maos/conteudo.py` (ffmpeg estático: cortar, extrair áudio; Deepgram → .srt; roteiro → cortes),
  `maos/computador.py` (`tela_capturar` livre; `tela_clicar/digitar/tecla` atrás do Vigia; HUD mostra a captura).
- MCPs `midia` e `tela`; Vigia atualizado; `.env.example` com `JAIME_OPENAI_IMAGEM` e `JAIME_BLENDER`.
- Instalados: `static-ffmpeg` (ffmpeg 8.0 sem Homebrew), `pyautogui`.

## Como testar
```
pytest -q                                   # 85 testes; corte real de vídeo sintético, imagem com dublê, captura de tela
# HUD: "gera uma thumbnail para o vídeo do capacete" · "captura a tela e me diz o que está aberto"
```

## Critérios §3 linhas 9–10
5 vozes testadas (`jaime voz testar`); prosódia muda com humor (teste); sem frases prontas (persona). Gera imagem
(validado ao vivo com gpt-image-2.5), gera .blend por script (script sim; .blend quando o Blender estiver instalado),
corta vídeo (teste real com ffmpeg), clica com confirmo (Vigia).
