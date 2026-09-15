"""Anthropic como provedor de TEXTO (para o juiz e para a segunda opinião): `claude_agent_sdk.query()`
de um turno só, sem ferramentas, pela mesma assinatura/chave do orquestrador.

Não confundir com o cliente persistente do Jaime (jaime/orchestrator/jaime.py), que tem as mãos.
Custo: abre um processo do CLI por chamada (~5 s de partida) — por isso o juiz só roda quando vale."""
from __future__ import annotations
from .base import Resposta, Cronometro

class ProvedorAnthropic:
    nome = "anthropic"

    def __init__(self, modelo: str = "claude-sonnet-5", cwd: str | None = None):
        self.modelo = modelo
        self.cwd = cwd

    async def responder(self, prompt: str, contexto: str = "", ferramentas: list[str] | None = None) -> Resposta:
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage, TextBlock
        opts = ClaudeAgentOptions(model=self.modelo, cwd=self.cwd, max_turns=1, allowed_tools=[],
                                  system_prompt=contexto or "Responda em português do Brasil, direto.",
                                  permission_mode="default")
        partes, custo = [], 0.0
        try:
            with Cronometro() as c:
                async for msg in query(prompt=prompt, options=opts):
                    if isinstance(msg, AssistantMessage):
                        partes += [b.text for b in msg.content if isinstance(b, TextBlock)]
                    elif isinstance(msg, ResultMessage):
                        custo = float(msg.total_cost_usd or 0)
            return Resposta("".join(partes).strip(), self.nome, self.modelo, c.s, custo)
        except Exception as e:
            return Resposta("", self.nome, self.modelo, erro=f"{type(e).__name__}: {str(e)[:160]}")
