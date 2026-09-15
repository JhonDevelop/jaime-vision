# Voz do Jaime — onde encontrar uma voz "Jarvis" e como escolher

O Jarvis do filme é a voz de um ator; clonar voz de gente sem consentimento não entra (e as plataformas bloqueiam).
O caminho é uma **voz original com as mesmas qualidades** — timbre masculino grave e calmo, dicção precisa, leve
textura sintética — e o jeito de falar, que é código nosso (`jaime/voice/persona.py` + prosódia pelo humor).

## Hoje (ligado): OpenAI gpt-4o-mini-tts — voz `onyx`
- Já está no `.env`: `JAIME_TTS=openai`, `JAIME_OPENAI_VOZ=onyx`. A instrução de estilo vai em cada frase
  (`JAIME_VOZ_ESTILO_BASE` + a prosódia do humor: "calmo e sério" / "animado" / "caloroso"…).
- Para ouvir 5 vozes masculinas com a mesma frase e escolher: `python -m jaime voz testar` (grava a escolha no `.env`).
- Vozes masculinas disponíveis: **onyx** (grave, a mais Jarvis), **ash** (mais quente), **echo** (mais jovem), verse, ballad.
- Custo: ~US$ 0,015 por mil caracteres — 1 h de fala do Jaime ≈ US$ 1.

## ElevenLabs — quando a cota voltar (15/10) ou com o Starter (US$ 5/mês)
1. **Voice Design** (elevenlabs.io → Voices → *Create* → *Voice Design*): descreva a voz e gere 3 amostras.
   Prompt que funciona: *"Calm, deep male voice, precise diction, slightly synthetic texture like a refined AI butler;
   neutral Brazilian Portuguese accent; measured pace; dry, polite tone."* Salve a que gostar → ⋯ → *Copy voice ID* →
   `ELEVENLABS_VOICE_ID` no `.env` e `JAIME_TTS=auto`.
2. **Voice Library** (elevenlabs.io → Voices → *Library*): pesquise "AI assistant", "butler", "narrator deep calm";
   filtre *Portuguese (Brazil)*. As brasileiras que você já tem (Elvis, Marcos, Yuri, Matheus) são "professional" e só
   funcionam via API com plano pago. Voice ID → `.env`.
3. Modelo **Eleven v3** aceita tags de emoção no texto (`[calm]`, `[serious]`); a prosódia já gera as tags
   (`prosodia()["tags"]`) — ative com `JAIME_TTS_MODELO=eleven_v3` quando o plano permitir.

## Reserva local (sem internet ou sem crédito)
`say -v "Eddy (Português (Brasil))"` — masculina, pt-BR, grátis. Outras: Reed, Rocko. (Luciana é feminina — era o
padrão antigo.)

## Como a fala fica "Jarvis" independentemente do timbre
- `persona.py`: tira "Olá, sou o Jaime, seu assistente", saudações repetidas, "Como posso ajudar?", muletas
  ("Claro!", "Ótima pergunta"); chama de João; frases curtas; fecha com o próximo passo.
- `prosodia.py`: humor → instrução de estilo (OpenAI) / estabilidade e estilo (ElevenLabs) / tags (v3).
- Streaming por token + primeira frase falada cedo; "Deixa eu ver…" se demorar mais de 1,6 s.
