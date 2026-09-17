"""Gera amostras da voz do J.A.I.M.E para o João escolher de ouvido.

Existe porque voz é decisão de ouvido, não de código: eu posso descrever o timbre, mas quem julga é ele.
Cada amostra é a MESMA frase com uma instrução de estilo diferente, então a comparação é justa.

    .venv/bin/python -m jaime.ops.amostras_voz            # gera as cinco em ~/Jaime/amostras-voz
    .venv/bin/python -m jaime.ops.amostras_voz --frase "outra frase"

Escolheu? Ponha a instrução em JAIME_VOZ_ESTILO_BASE e a voz em JAIME_OPENAI_VOZ, no .env."""
from __future__ import annotations
import argparse, os, time, wave
from pathlib import Path

FRASE = ("João, o servidor voltou às dez e quarenta. Os testes passaram, quatrocentos e vinte e nove. "
         "O Codex está compilando; eu te aviso quando entregar.")

VARIANTES: dict[str, tuple[str, str]] = {
    "1-mordomo-onyx": ("onyx",
        "Voz masculina grave e calma, dicção precisa, sotaque brasileiro neutro, tom seco e educado, "
        "leve textura de assistente de inteligência artificial — um mordomo britânico falando português."),
    "2-jarvis-ash": ("ash",
        "Assistente de inteligência artificial, voz masculina, registro médio-grave. Dicção impecável e "
        "levemente mecânica: cada consoante no lugar, sem arrastar vogal. Ritmo constante e ligeiramente "
        "acelerado, como quem já sabe a resposta. Entonação contida — informa, não entretém. "
        "Português do Brasil neutro. Nenhum entusiasmo, nenhuma hesitação, nenhum sorriso na voz."),
    "3-jarvis-onyx": ("onyx",
        "Assistente de inteligência artificial, voz masculina grave. Dicção impecável e levemente mecânica, "
        "consoantes marcadas, vogais curtas. Ritmo constante e eficiente. Entonação quase plana, com uma "
        "única inflexão discreta no fim da frase. Português do Brasil neutro, sem regionalismo. "
        "Calmo e preciso como um instrumento, não como uma pessoa animada."),
    "4-jarvis-sage": ("sage",
        "Assistente de inteligência artificial, voz masculina serena e articulada. Fala rápido e claro, sem "
        "pressa aparente. Precisão de máquina com timbre humano. Entonação mínima, respiração imperceptível. "
        "Português do Brasil neutro. Educado e direto; nunca caloroso, nunca frio."),
    "5-jarvis-echo": ("echo",
        "Assistente de inteligência artificial, voz masculina clara e metálica no timbre, humana no ritmo. "
        "Dicção cirúrgica, ritmo ágil, entonação contida. Português do Brasil neutro. "
        "Soa sintetizado sem soar robô de desenho animado."),
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Amostras da voz do J.A.I.M.E, para escolher de ouvido.")
    ap.add_argument("--frase", default=FRASE)
    ap.add_argument("--pasta", default=str(Path.home() / "Jaime/amostras-voz"))
    ap.add_argument("--velocidade", type=float, default=1.0)
    a = ap.parse_args(argv)

    from openai import OpenAI
    from ..config import settings
    if not settings.openai_key:
        print("✗ sem OPENAI_API_KEY no .env"); return 2
    c = OpenAI(api_key=settings.openai_key)
    pasta = Path(a.pasta).expanduser(); pasta.mkdir(parents=True, exist_ok=True)

    print(f"frase: «{a.frase[:60]}…»\n")
    for nome, (voz, instr) in VARIANTES.items():
        t = time.time()
        try:
            with c.audio.speech.with_streaming_response.create(
                    model=os.environ.get("JAIME_OPENAI_TTS_MODELO", "gpt-4o-mini-tts"),
                    voice=voz, input=a.frase, instructions=instr,
                    response_format="pcm", speed=a.velocidade) as r:
                pcm = b"".join(r.iter_bytes())
        except Exception as e:
            print(f"  {nome:<16} falhou: {type(e).__name__}: {e}"); continue
        destino = pasta / f"{nome}.wav"
        with wave.open(str(destino), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
        print(f"  {nome:<16} voz={voz:<5} {len(pcm)/2/24000:5.1f}s de fala  (gerou em {time.time()-t:.1f}s)")
    print(f"\nOuça em {pasta} — `open {pasta}`.")
    print("A mais curta é a mais rápida de ouvir; a mais longa arrasta.")
    print("Escolheu? No .env: JAIME_OPENAI_VOZ=<voz> e JAIME_VOZ_ESTILO_BASE=<a instrução daquela variante>.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
