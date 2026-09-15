import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from jaime.cortex.roteador import Escolha
from jaime.cortex.provedores.base import Resposta

def test_anthropic_session_limit_faz_failover_para_openai():
    async def run():
        from jaime.orchestrator.jaime import Jaime

        from jaime.config import settings

        with patch("jaime.orchestrator.jaime.ClaudeSDKClient"), \
             patch("jaime.orchestrator.jaime.Vault") as mock_vault, \
             patch("jaime.orchestrator.jaime.Indice"):
            
            mock_vault.return_value.read.return_value = ""
            j = Jaime(settings)
            j.openai = SimpleNamespace(
                disponivel=True,
                modelo="gpt-5.5",
                responder=AsyncMock(return_value=Resposta(
                    texto="Resposta via OpenAI em fallback com sucesso.",
                    provedor="openai",
                    modelo="gpt-5.5",
                    latencia=0.5,
                    custo=0.001
                ))
            )
            j.placar = SimpleNamespace(registrar=lambda *args, **kwargs: None)
            j.vault = SimpleNamespace(diario=lambda *args, **kwargs: None)
            j._usar_modelo = AsyncMock()
            j._memoria = lambda texto: ""
            j._contexto_texto = lambda ctx="": "contexto"

            async def stream_erro(texto):
                raise RuntimeError("anthropic_session_limit: You've hit your session limit · resets 5:10pm")
                yield "" # pragma: no cover

            j._stream = stream_erro

            escolha = Escolha(tipo="conversa", modelo="claude-sonnet-5", motivo="teste", confianca=1.0)
            partes = []
            async for t in j._turno_anthropic(escolha, "Olá Jaime", canal="voice", contexto="", inicio=0.0):
                partes.append(t)

            resposta_final = "".join(partes)
            assert "Resposta via OpenAI em fallback com sucesso." in resposta_final
            assert "session limit" not in resposta_final
            assert j.openai.responder.called

    asyncio.run(run())
