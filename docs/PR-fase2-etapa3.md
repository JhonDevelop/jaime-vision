# PR — Fase 2, etapa 3: OpenAI como segundo provedor + juiz

**Branch:** `feat/fase2-openai-juiz` → `main`

## O que muda
- `jaime/cortex/provedores/`: interface única `responder(prompt, contexto, ferramentas=None) → Resposta`.
  - `openai.py` — Responses API (`JAIME_OPENAI_MODEL`, padrão `gpt-5.5`; `web_search` em pesquisa). Sem chave ou
    sem crédito devolve `Resposta.erro` — nunca trava.
  - `anthropic.py` — `claude_agent_sdk.query()` de um turno, sem ferramentas: árbitro e segunda opinião.
- `jaime/cortex/juiz.py`: para *decisão* ou "pensa bem"/"compara", duas respostas em paralelo e o Fable 5.1
  escolhe A/B/mescla com uma frase de justificativa → diário (Decisões) + painel Raciocínio do HUD.
- Roteador: `openai:<modelo>` vira candidato só para *pesquisa* e *redação*, só com chave.
- Orquestrador: caminho OpenAI (texto) com fallback para a Anthropic no mesmo turno; caminho do juiz; regra
  "as mãos são só da Anthropic" mantida.
- `docs/ARQUITETURA.md` (seção "Dois provedores"), `.env.example`, `pyproject` (`openai`).

## Estado real da conta OpenAI (15/09/2026)
Chave válida, 124 modelos visíveis, **sem crédito** (`insufficient_quota`). Modelos que existem: gpt-5.5,
gpt-5.5-pro, gpt-5.6-luna, gpt-5.6-sol, gpt-realtime-2, gpt-realtime-whisper, gpt-4o-mini-tts,
gpt-image-2.5-flare/sunburst. Não existem "GPT-6 Astra" nem "GPT-5.6 Terra".

## Como testar
```
pytest -q                                   # 46 testes; juiz e provedores com dublês
python -m jaime cortex explicar "pesquisa o preço do ESP32"
# com crédito na OpenAI: "pensa bem: X ou Y?" → painel Raciocínio mostra juiz · escolha · justificativa
```

## Critério §3 linha 3
Mesma pergunta respondida pelos dois provedores; juiz escolhe e registra — validado com dublês; ao vivo assim que
houver crédito (sem crédito, o juiz devolve a resposta da Anthropic e registra o motivo).
