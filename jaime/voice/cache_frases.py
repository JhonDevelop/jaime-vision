"""Cache persistente de PCM para frases curtas e repetidas do TTS."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path


MAX_CARACTERES = 80
MAX_ARQUIVOS = 300


class CacheFrases:
    """Arquivos PCM nomeados pela configuração sonora que os produziu."""
    def __init__(self, pasta: str | Path | None = None, *, motor: str = "auto", voz: str = "", velocidade: float = 1.0,
                 instrucoes: str = "", max_arquivos: int = MAX_ARQUIVOS):
        configurada = os.environ.get("JAIME_CACHE_FRASES", "")
        self.habilitado = configurada.lower() != "off"
        self.pasta = Path(pasta or configurada or "~/Jaime/vozes/frases").expanduser()
        self.max_arquivos = max_arquivos
        self.configurar(motor=motor, voz=voz, velocidade=velocidade, instrucoes=instrucoes)

    def configurar(self, *, motor: str, voz: str, velocidade: float, instrucoes: str) -> None:
        self.motor, self.voz = motor, voz
        self.velocidade, self.instrucoes = velocidade, instrucoes

    def _caminho(self, texto: str) -> Path | None:
        if not self.habilitado or not texto or len(texto) > MAX_CARACTERES:
            return None
        material = "|".join((texto, self.motor, self.voz, str(self.velocidade), self.instrucoes))
        return self.pasta / (hashlib.sha256(material.encode("utf-8")).hexdigest() + ".pcm")

    def get(self, texto: str) -> bytes | None:
        caminho = self._caminho(texto)
        if caminho is None:
            return None
        try:
            pcm = caminho.read_bytes()
            if not pcm:
                return None
            os.utime(caminho, None)       # acesso também atualiza o LRU
            return pcm
        except OSError:
            return None

    def put(self, texto: str, pcm: bytes | bytearray | None) -> None:
        caminho = self._caminho(texto)
        if caminho is None or not pcm:
            return
        try:
            self.pasta.mkdir(parents=True, exist_ok=True)
            temporario = caminho.with_suffix(".tmp")
            temporario.write_bytes(bytes(pcm))
            temporario.replace(caminho)
            self._podar()
        except OSError:
            pass                         # cache nunca pode impedir a fala

    def _podar(self) -> None:
        try:
            arquivos = sorted(self.pasta.glob("*.pcm"), key=lambda p: p.stat().st_mtime)
            for antigo in arquivos[:-self.max_arquivos]:
                antigo.unlink(missing_ok=True)
        except OSError:
            pass
