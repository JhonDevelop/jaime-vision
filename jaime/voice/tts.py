"""Fala: ElevenLabs em streaming. Sem chave → imprime no terminal (útil para testar o resto).

O player: `elevenlabs.stream()` exige o mpv instalado. Quando ele não existe — o caso do macOS
sem Homebrew — o áudio é juntado e tocado pelo player nativo (afplay no macOS), que basta para
frases curtas. Sem nenhum dos dois, o texto vai para o terminal em vez de o Jaime emudecer."""
from __future__ import annotations
import os, shutil, subprocess, tempfile
from ..config import Settings
from ..hud.events import bus

def _player_nativo() -> list[str] | None:
    for cmd in (["afplay"], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"], ["cvlc", "--play-and-exit"]):
        if shutil.which(cmd[0]):
            return cmd
    return None

class TTS:
    def __init__(self, s: Settings):
        self.s = s
        self._client = None
        if s.elevenlabs_key:
            from elevenlabs.client import ElevenLabs
            self._client = ElevenLabs(api_key=s.elevenlabs_key)

    def _tocar(self, audio) -> None:
        """mpv quando existir (streaming, menor latência); senão, arquivo + player nativo."""
        if shutil.which("mpv"):
            from elevenlabs import stream
            stream(audio)
            return
        player = _player_nativo()
        dados = b"".join(audio)
        if not player:
            print("🔈 (sem player de áudio: instale mpv, ou use afplay/ffplay)")
            return
        caminho = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(dados); caminho = f.name
            subprocess.run(player + [caminho], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        finally:
            if caminho:
                os.unlink(caminho)

    def _say_nativo(self, texto: str) -> bool:
        """Último recurso no macOS: voz local em pt-BR. Grátis, offline, sotaque pior."""
        if not shutil.which("say"):
            return False
        subprocess.run(["say", "-v", os.environ.get("JAIME_SAY_VOZ", "Luciana"), texto],
                       check=False, stderr=subprocess.DEVNULL)
        return True

    def falar(self, texto: str):
        texto = texto.strip()
        if not texto:
            return
        bus.emitir("voz", falando=True)
        try:
            if not self._client:
                if not self._say_nativo(texto):
                    print(f"🔈 {texto}")
                return
            # elevenlabs >= 2: convert_as_stream virou stream()
            audio = self._client.text_to_speech.stream(
                text=texto, voice_id=self.s.elevenlabs_voice or "JBFqnCBsd6RMkjVDRZzb",
                model_id="eleven_multilingual_v2", output_format="mp3_22050_32",
            )
            self._tocar(audio)
        except Exception as e:
            # plano sem a voz escolhida, cota estourada, rede fora: fala do mesmo jeito
            print(f"⚠ ElevenLabs falhou ({type(e).__name__}); usando a voz local")
            if not self._say_nativo(texto):
                print(f"🔈 {texto}")
        finally:
            bus.emitir("voz", falando=False)
