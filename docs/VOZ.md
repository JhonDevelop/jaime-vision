# Como funciona a voz

```
microfone ─► Silero VAD (voz humana?) ─► grava até 0,7 s de silêncio ─► Whisper local (ou Deepgram)
          ─► "tem Jaime na frase?" ─► Jaime.ask_stream ─► ElevenLabs PCM streaming ─► alto-falante
                                          │                    │
                                     legenda no HUD     evento "voz" (cérebro pulsa)
```

O microfone vive **dentro do servidor**: `python -m jaime hud` já liga a escuta. Não existe wake word
por modelo — a ativação é pela transcrição.

## Falar com ele
- **"Jaime, está aí?"** → "Estou aqui, João." (sem passar pelo modelo).
- **"Jaime, abre o Finder"** → executa. Depois de chamado ele fica **90 s ativo**: dá para continuar
  sem repetir o nome (`JAIME_JANELA_ATIVA_S`).
- Frases sem "Jaime" fora da janela aparecem apagadas no HUD ("ouvi, não era comigo") e são ignoradas.
- `JAIME_ATIVACAO=sempre` faz ele responder a tudo que ouvir.
- **"teclado"** / "deixa eu escrever" abre o teclado do HUD. Ele mesmo pede o teclado (`pedir_teclado`)
  quando precisa de algo digitado: senha, chave, URL.
- A palavra-passe funciona falada: "um dois três quatro, um dois três quatro".

## As peças (`jaime/voice/`)
1. **`escuta.py` — ouvido.** Frames de 32 ms → **Silero VAD** (vem dentro do faster-whisper, ~1 ms por frame):
   probabilidade de voz humana. Ventoinha, ar-condicionado e a própria caixa de som ficam em 0,0x;
   gate por energia (a versão anterior) não distinguia e deixava o Jaime surdo ou ouvindo ruído.
   Segmentador com pré-roll de 320 ms, histerese (começa em 0,5, termina abaixo de 0,35) e fim por 0,7 s
   de silêncio. Microfone mudo enquanto ele fala (não se ouve). Descarta as alucinações clássicas do
   Whisper em silêncio ("legendas pela comunidade…").
2. **`stt.py` — transcrição.** `DEEPGRAM_API_KEY` → nuvem, ~0,3 s, o melhor pt-BR. Sem chave →
   `faster-whisper` local em thread. Neste MacBook Intel: `base` ≈ 1 s por frase, `small` ≈ 3,6 s
   (mais lento que tempo real). `JAIME_WHISPER_MODELO`.
3. **`tts.py` — fala.** ElevenLabs `eleven_flash_v2_5` em **PCM 22 kHz direto no `sounddevice`** —
   sem mpv, sem arquivo: começa a soar no primeiro chunk. Frase a frase enquanto o modelo ainda gera.
   Se a ElevenLabs falhar (voz bloqueada pelo plano, cota, rede) cai no `say` do macOS em pt-BR.

## ElevenLabs — o que o plano libera
- **Free (10 mil caracteres/mês):** só vozes *premade* (inglês; falam pt-BR com sotaque). Padrão
  `nPczCjzI2devNBz1zQrb` (Brian, grave). As brasileiras da sua biblioteca — Elvis `zNEsdgTUa3ndwKry8Xcq`,
  Marcos, Yuri, Matheus… — devolvem **HTTP 402** via API.
- **Starter (US$ 5/mês, 30 mil caracteres):** libera as vozes da biblioteca. Aí é só trocar
  `ELEVENLABS_VOICE_ID` no `.env`.

## Latência esperada nesta máquina
fim da fala → transcrição ≈ 1 s (Whisper base) · primeira frase falada ≈ 2–3 s (Opus 5 pela assinatura,
raciocínio limitado a `JAIME_THINKING_TOKENS=1500`) · o resto flui em streaming.
Com Deepgram: transcrição ≈ 0,3 s.

## Testar cada peça
```bash
.venv/bin/python -c "from jaime.voice.tts import TTS; from jaime.config import settings; TTS(settings).falar('Oi, João. Estou online.')"
.venv/bin/python -m jaime voice        # só voz, sem HUD
.venv/bin/python -m jaime hud          # HUD + voz (o normal)
```

## Wake word por modelo (opcional, depois)
`openwakeword`/`microwakeword` está registrado como MCP nesta pasta. Estimativa gratuita: `"jaime"`
sozinho pontua 24 (curto demais); `"ô jaime"` pontua 79. Treinar custa CHF 6 e só se faz com "confirmo".
Não é necessário: a ativação por transcrição já resolve.
