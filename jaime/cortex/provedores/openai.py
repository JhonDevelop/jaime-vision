"""OpenAI via Responses API — cérebro alternativo para texto, pesquisa (web_search) e decisões.

Modelos (lista real vista pela chave em 15/09/2026): gpt-5.5 (padrão), gpt-5.6-luna (rápido), gpt-5.6-sol,
gpt-5.5-pro; voz: gpt-realtime-2, gpt-realtime-whisper, gpt-4o-mini-tts; imagem: gpt-image-2.5-flare/sunburst.
Confira `client.models.list()` antes de fixar outro. Sem `OPENAI_API_KEY` ou sem crédito, `responder()`
devolve uma Resposta com `erro` — o roteador cai para a Anthropic, nunca trava."""
from __future__ import annotations
import os
from .base import Resposta, Cronometro

# custo por milhão de tokens (entrada, saída) — aproximação para o placar; ajuste em JAIME_OPENAI_PRECO
PRECOS = {"gpt-5.5": (1.25, 10.0), "gpt-5.6-luna": (0.25, 2.0), "gpt-5.6-sol": (2.5, 15.0)}

class ProvedorOpenAI:
    nome = "openai"

    def __init__(self, api_key: str, modelo: str = "gpt-5.5"):
        self.modelo = modelo
        self._client = None
        if api_key:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=api_key)

    @property
    def disponivel(self) -> bool:
        return self._client is not None

    async def responder(self, prompt: str, contexto: str = "", ferramentas: list[str] | None = None) -> Resposta:
        if not self._client:
            return Resposta("", self.nome, self.modelo, erro="OPENAI_API_KEY ausente")
        entrada = ([{"role": "system", "content": contexto}] if contexto else []) + [{"role": "user", "content": prompt}]
        tools = [{"type": "web_search"}] if ferramentas and "web_search" in ferramentas else None
        try:
            with Cronometro() as c:
                r = await self._client.responses.create(model=self.modelo, input=entrada, **({"tools": tools} if tools else {}))
            texto = (getattr(r, "output_text", "") or "").strip()
            uso = getattr(r, "usage", None)
            tokens_in = int(getattr(uso, "input_tokens", 0) or 0); tokens_out = int(getattr(uso, "output_tokens", 0) or 0)
            pi, po = PRECOS.get(self.modelo, (1.0, 8.0))
            custo = (tokens_in * pi + tokens_out * po) / 1_000_000
            return Resposta(texto, self.nome, getattr(r, "model", self.modelo), c.s, custo, tokens_in + tokens_out)
        except Exception as e:
            return Resposta("", self.nome, self.modelo, erro=f"{type(e).__name__}: {str(e)[:160]}")
