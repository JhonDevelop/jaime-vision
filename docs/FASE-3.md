# Fase 3 — Jarvis de verdade: tempo real, autonomia supervisionada, mundo

> A fase 2 deu cérebros, mãos e conexões. A fase 3 é sobre **latência, confiança e alcance**. Ordem importa.

## Etapas

| # | Etapa | Critério de pronto |
|---|---|---|
| 1 | **Conversa em tempo real** — GPT-Realtime-2 fala-para-fala com as ferramentas do Jaime (`JAIME_VOZ_MODO=conversa`) | "Jaime, que horas são?" respondido em < 1 s; "abre o Finder" vira chamada à ferramenta `jaime` (Agent SDK) e a resposta volta falada; palavra-passe e "teclado" continuam funcionando; sem se ouvir |
| 2 | **Objetivo autônomo real supervisionado** — um objetivo de 1–2 h no dia a dia do João, com o HUD mostrando cada etapa | relatório no diário; ao menos uma pausa do Vigia retomada com "confirmo"; placar e estudo alimentados |
| 3 | **Conexões ativadas** — Google, Telegram e Meta com credenciais reais | briefing 07:00 com e-mails e agenda de verdade; DM comercial respondida com confirmo |
| 4 | **Casa e mundo** — Home Assistant / HomeKit (luzes, tomadas), câmera como olho (descrever o que vê) | "apaga a luz do escritório" funciona; "o que tem na câmera da entrada?" descreve |
| 5 | **Jogos e apps por visão** — computer use contínuo: ver a tela em loop e agir com reflexo, com limites e kill switch | joga um jogo simples de turno; para no "para" |
| 6 | **Memória semântica** — FTS5/embeddings no vault quando passar de 500 notas; recall proativo ("você falou disso em março") | busca por significado, não por palavra |
| 7 | **Autoevolução** — o Jaime propõe melhorias em si mesmo como PRs (branch + testes), o João aprova | um PR por semana aberto por ele, mergeado com "confirmo" |

## Etapa 1 — como funciona o modo conversa (`jaime/voice/tempo_real.py`)
```
microfone (PCM 24 kHz) ─► WebSocket Realtime ─► VAD do servidor ─► transcrição ─► "é comigo?" (nome / janela ativa)
                                                                         │
                                            response.create ◄────────────┘ (só quando é com ele)
                                                  │
        alto-falante ◄── áudio ──────────────────┤
        HUD (fala/legenda) ◄── transcrição ──────┤
        Agent SDK (mãos) ◄── tool `jaime(texto)` ─┘ → resultado volta como function_call_output → fala
```
- **Sem wake word por modelo**: a transcrição do próprio Realtime decide se a fala é com ele (mesma regra da fase 2).
- **Palavra-passe / teclado / renomear** continuam no `_porta`: quando trancado, a transcrição vai ao Jaime e a resposta
  curta é dita pelo Realtime ("diga exatamente: …").
- **Ferramentas do Realtime**: `jaime(texto)` (tudo que exige memória, mãos, conexões), `hora`, `clima`, `lembrete`.
  O modelo em tempo real cuida do papo; o Agent SDK das ações. Custo: Realtime é caro (~US$ 0,3/min de conversa) — o
  modo `pipeline` (Deepgram + Opus + TTS) continua sendo o padrão econômico; troque com `JAIME_VOZ_MODO=conversa`.
- **Não se ouve**: microfone mudo enquanto o áudio dele toca (+300 ms de cauda).
