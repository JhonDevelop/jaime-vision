# Engenharia de Proteção, Harness Operacional e Poupança de Recursos

> Documento mestre de governança, blindagem de runtime, poupança de tokens e divisão estratégica de tarefas no ecossistema J.A.I.M.E.

---

## 1. Princípio Fundamental: O Assistente como Sócio e Alavanca

O J.A.I.M.E foi desenhado para ser o braço direito operacional do João, não uma fonte de ansiedade, desperdício financeiro ou travamentos. Para que ele atue como uma extensão de alta produtividade sem gerar frustrações:

1. **Eficiência de Custo Primeiro**: Nenhuma chamada a modelo de fronteira (Opus/Sonnet/GPT-5.5) deve ocorrer se uma regra de código, um modelo local, uma busca indexada ou um modelo leve (Haiku/Luna/Codex) puder resolver.
2. **Silêncio e Proteção na Falha**: Erros de infraestrutura, quotas de API e limites de sessão nunca devem ser vocalizados em inglês ao usuário como se fossem respostas. Falhas de um provedor devem ser contornadas por failover automático e transparente.
3. **Escuta Humana e Respeitosa**: O assistente nunca interrompe o fluxo de fala do João sem critério semântico comprovado; se o João abre a boca, o áudio do Jaime cessa instantaneamente (< 100 ms).
4. **Divisão Racional de Tarefas**: O trabalho pesado de código deve ser absorvido por ferramentas de custo fixo (plano Plus no Codex via Maestri), poupando tokens de API das chaves pagas por uso.

---

## 2. Divisão de Tarefas: Cérebros, Orquestrantes, Maestros e Filhos

Para equilibrar o uso de tokens e garantir especialização, o trabalho no J.A.I.M.E é distribuído em camadas hierárquicas claras:

```
                                  JOÃO (Voz / HUD / Telegram)
                                              │
                                              ▼
                                 ┌─────────────────────────┐
                                 │   1º CÉREBRO CENTRAL    │  (claude-agent-sdk / Claude Code)
                                 │       (O MAESTRO)       │  • Diálogo humano (1–3 frases)
                                 │    Atendimento Direto   │  • Decisões táticas imediatas
                                 └────────────┬────────────┘
                                              │
                     ┌────────────────────────┼────────────────────────┐
                     ▼                        ▼                        ▼
        ┌─────────────────────────┐ ┌────────────────────┐ ┌─────────────────────────┐
        │  FILHOS DE CÓDIGO BRUTO │ │2º CÉREBRO REFLEXIVO│ │  3º CÉREBRO OPERACIONAL │
        │     (CODEX / PLUS)      │ │    (A MENTE)       │ │   (ANTIGRAVITY / CLI)   │
        ├─────────────────────────┤ ├────────────────────┤ ├─────────────────────────┤
        │ • Refatorações pesadas  │ │ • Telemetria       │ │ • Arquitetura & Harness │
        │ • Escrita de testes     │ │ • Análise de logs  │ │ • Circuit Breakers      │
        │ • Migrações e scripts   │ │ • Problemas abertos│ │ • Resolução de bugs core│
        │ • CUSTO API: US$ 0.00   │ │ • Autoestudo       │ │ • Merges de worktrees   │
        │   (plano fixo Plus)     │ │ • Orçamento 25%    │ │ • Blindagem de runtime  │
        └─────────────────────────┘ └────────────────────┘ └─────────────────────────┘
```

### Matriz de Alocação de Trabalho por Custo

| Domínio da Tarefa | Executor Recomendado | Provedor / Mecanismo | Custo Variável por Token |
|---|---|---|---|
| **Hora, clima, lembretes, tranca, status** | Código nativo (`_mundo`, `_porta`) | Python local (sem LLM) | **Zero** |
| **Pesquisa factual rápida e redação curta** | Córtex Rápido | Claude Haiku 4.5 ou OpenAI GPT-5.6 Luna | Mínimo (~US$ 0,25/M) |
| **Mão de obra pesada de código (features/testes)** | **Codex CLI** (worktrees Maestri) | ChatGPT Plus (`codex exec`) | **Zero na API** |
| **Estudo noturno e reflexão de melhorias** | Cérebro de Estudo / Mente | Haiku / Sonnet confinado | Controlado (Teto 25% do dia) |
| **Criação artística / Poesia / Vitrine** | Mente Criativa | Janela Noturna (21h–06h) | Controlado (Teto 15% do dia) |
| **Decisão estratégica e síntese final** | Juiz / Cérebro Central | Anthropic Sonnet/Opus ou GPT-5.5 | Apenas sob demanda do João |

---

## 3. Sistema de Poupança Extrema de Tokens e Dados

### 3.1 Filtro Zero-Token (Pré-Processamento Local)
1. **Comandos de Mundo no `_porta`**: Perguntas sobre relógio, data, clima (`clima.py` com cache de 10 min) e criação de lembretes locais nunca chegam aos modelos de linguagem. O retorno é imediato em milissegundos e consome zero tokens.
2. **VAD Silero Estrito**: O áudio ambiente do microfone só aciona transcrição quando o VAD local acusa probabilidade de voz humana (`prob > 0.5`). Sons de ventilador, digitação e barulho da rua são descartados antes de gerar requisição de rede.
3. **Filtro de Destinatário ("É comigo?")**: Se a transcrição não contiver o nome ativador ("Jaime") e a janela ativa não for o próprio assistente, a fala é registrada como `ignorado=True` no HUD e **nenhuma chamada ao LLM é realizada**.

### 3.2 Cache Semântico e Memória FTS5
1. **Indexação Local (SQLite BM25)**: Em vez de injetar dezenas de arquivos do vault no System Prompt a cada turno (o que explodiria o consumo de tokens de entrada), o `jaime/brain/indice.py` executa busca vetorial/BM25 pontual e injeta apenas os 3 trechos mais relevantes (`[memória do vault: ...]`).
2. **Prevenção de Perguntas Repetidas**: A ferramenta `mcp__emocao__perguntar_ao_joao` consulta `10-Eu/Perguntas-Feitas.md`. Se o João já respondeu no passado, a resposta é reaproveitada sem gastar novos turnos de esclarecimento.

---

## 4. Poupança de Gastos com Voz e Tempo Real

### 4.1 Cache Permanente de Áudio PCM (`jaime/voice/cache_frases.py`)
* Respostas curtas recorrentes ("Estou aqui, senhor.", "Palavra-passe, por favor.", "Pode escrever.", "Certo, João. Estou aqui se precisar.", muletas como "Deixa eu ver...") são sintetizadas **uma única vez** e armazenadas em disco em formato PCM int16 (`~/Jaime/vozes/frases/<hash>.pcm`).
* Toda ocorrência subsequente toca direto do disco em **~150 ms** e consome **zero caracteres de TTS** (OpenAI ou ElevenLabs).

### 4.2 Fim de Turno Semântico Tolerante (M-11)
* O maior causador de gasto desnecessário em tempo real eram turnos truncados: o usuário hesitava ("Eu queria que você..."), o sistema cortava com 450 ms, chamava o modelo, gastava tokens e gerava uma resposta inútil, obrigando o usuário a repetir tudo.
* Com a heurística M-11:
  - Frases que terminam com conectivos, verbos incompletos ou preposições abertas ("preciso", "quero", "sobre o", "para", "e também") forçam espera de silêncio de até **1500 ms**.
  - O corte rápido (450 ms) só é acionado se houver pontuação explícita ou intenção clara já mapeada com rascunho local.

### 4.3 Barge-In com Cancelamento Imediato de Geração
* Ao detectar a voz do João durante a fala do Jaime:
  1. O player de áudio mata a reprodução instantaneamente (< 100 ms).
  2. O stream de geração do modelo é cancelado via `client.interrupt()`, evitando que a API continue gerando e cobrando tokens de saída de um texto que jamais será ouvido.

---

## 5. Engenharia de Proteção e Circuit Breakers (Harness)

### 5.1 Failover Transparente entre Provedores
Se o provedor primário (Anthropic) emitir erro de rate limit, quota ou sessão:
```
[Anthropic Claude SDK] ──► Erro: "session limit" / "rate limit" / 429
                                  │
                                  ▼ (Circuit Breaker intercepta)
                    ┌─────────────────────────────┐
                    │  FAILOVER TRANSPARENTE      │
                    │  Desvia turno para OpenAI   │
                    │  (GPT-5.5 / GPT-5.6 Luna)   │
                    └─────────────┬───────────────┘
                                  │
                                  ▼
                    Resposta entregue ao João em pt-BR
                    (Sem mensagens em inglês, sem travamento)
```

### 5.2 Vigia em Lote e Confiança Progressiva
* O Vigia não interrompe ações inofensivas de leitura e navegação.
* Para ações destrutivas ou externas (envio de e-mails, exclusão de arquivos, push forçado):
  - Todas as ações do turno são agrupadas em uma **única pergunta em lote**: *"Você deseja que eu envie o e-mail, crie o evento e mova os arquivos?"*.
  - A resposta "sim" libera o lote exato.
  - Na 5ª aprovação consecutiva sem correções, o sistema gera uma proposta formal de exceção de escopo em `01-Estado/Confianca.md`.

---

## 6. Passo a Passo de Produção: Protocolo de Entrega e Qualidade

Nenhuma modificação deve entrar em produção na branch `main` ou no serviço sem obedecer ao checklist do Harness:

1. **Isolamento em Piso/Worktree**:
   - Todo trabalho ocorre em worktree dedicado (`jaime-codex`, `jaime-hud`, `jaime-mente`). O chão (`main`) permanece íntegro.
2. **Harness de Testes Unitários**:
   - Execução local com `pytest -q`. Nenhum merge é autorizado com testes falhando.
3. **Medição de Impacto**:
   - Medir latência (`python -m jaime voz latencia`) e verificar se novas ferramentas não inflam o System Prompt desnecessariamente.
4. **Merge Supervisionado com Registro**:
   - Merge na branch `main`, atualização de `vault/01-Estado/Estado.md` e anotação datada em `vault/40-Diario/`.
5. **Reinicialização Segura do Serviço**:
   - Checagem de processo vivo via `bash jaime/ops/servico.sh status` e validação no stream do HUD (`http://127.0.0.1:8787`).
