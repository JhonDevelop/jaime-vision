"""Imagens com a OpenAI (gpt-image-2.5): gerar e editar. Salva em `~/Jaime/imagens/` e registra no diário.
`cliente` é injetável para teste."""
from __future__ import annotations
import base64, os, time
from pathlib import Path
from ..identidade import slug

PASTA = Path(os.environ.get("JAIME_IMAGENS", "~/Jaime/imagens")).expanduser()
MODELOS = [os.environ.get("JAIME_OPENAI_IMAGEM", "gpt-image-2.5-flare"), "gpt-image-2", "gpt-image-1"]
TAMANHOS = {"quadrada": "1024x1024", "paisagem": "1536x1024", "retrato": "1024x1536", "thumbnail": "1536x1024"}

class Imagens:
    def __init__(self, api_key: str, vault=None, cliente=None):
        self.vault = vault
        self._c = cliente
        if not cliente and api_key:
            from openai import OpenAI
            self._c = OpenAI(api_key=api_key)

    @property
    def disponivel(self) -> bool:
        return self._c is not None

    def _salvar(self, b64: str, nome: str, sufixo: str = "") -> Path:
        PASTA.mkdir(parents=True, exist_ok=True)
        caminho = PASTA / f"{slug(nome)[:40] or 'imagem'}{sufixo}-{time.strftime('%Y%m%d-%H%M%S')}.png"
        caminho.write_bytes(base64.b64decode(b64))
        if self.vault:
            self.vault.diario(f"Imagem {'editada' if sufixo else 'gerada'}: {caminho.name} — {nome[:80]}", "Feito")
        return caminho

    def gerar(self, prompt: str, formato: str = "quadrada", qualidade: str = "medium") -> Path:
        if not self._c:
            raise RuntimeError("OPENAI_API_KEY ausente")
        erro = None
        for modelo in MODELOS:
            try:
                r = self._c.images.generate(model=modelo, prompt=prompt, size=TAMANHOS.get(formato, formato), quality=qualidade, n=1)
                return self._salvar(r.data[0].b64_json, prompt)
            except Exception as e:
                erro = e
                if "model" not in str(e).lower() and "not found" not in str(e).lower():
                    break
        raise RuntimeError(f"geração falhou: {type(erro).__name__}: {str(erro)[:160]}")

    def editar(self, caminho: Path, prompt: str, formato: str = "quadrada") -> Path:
        if not self._c:
            raise RuntimeError("OPENAI_API_KEY ausente")
        caminho = Path(caminho).expanduser()
        with open(caminho, "rb") as f:
            r = self._c.images.edit(model=MODELOS[0], image=f, prompt=prompt, size=TAMANHOS.get(formato, formato))
        return self._salvar(r.data[0].b64_json, prompt, "-edit")
