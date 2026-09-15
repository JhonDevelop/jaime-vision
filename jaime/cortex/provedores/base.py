"""Interface comum dos provedores de modelo: `responder(prompt, contexto, ferramentas=None)`.

Um provedor produz TEXTO. As mãos (ferramentas do Agent SDK, MCPs, hooks do Vigia) continuam sendo
só da Anthropic, pelo cliente persistente do orquestrador — aqui é o cérebro alternativo e o juiz."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Protocol

@dataclass
class Resposta:
    texto: str
    provedor: str
    modelo: str
    latencia: float = 0.0
    custo: float = 0.0
    tokens: int = 0
    erro: str = ""
    extras: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.erro and bool(self.texto.strip())

class Provedor(Protocol):
    nome: str
    modelo: str
    async def responder(self, prompt: str, contexto: str = "", ferramentas: list[str] | None = None) -> Resposta: ...

class Cronometro:
    def __enter__(self):
        self.t0 = time.time(); return self
    def __exit__(self, *a):
        self.s = time.time() - self.t0
