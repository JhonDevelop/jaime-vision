---
name: tres-cerebros
description: "Como o J.A.I.M.E usa os três cérebros: Central (Claude) decide, Esquerdo (Codex) executa, Direito (Gemini) pesquisa e critica. Use ao receber trabalho grande ou paralelizável."
---
# Três cérebros — com quem pensar cada coisa

| lado | quem | o que faz |
|---|---|---|
| **Central** | Claude | decide, conversa com o João, orquestra, escreve no vault. **O único que fala com ele.** |
| **Esquerdo** | Codex | a técnica: código, execução, teste, refatoração, mão de obra repetitiva |
| **Direito** | Gemini | o evolutivo: pesquisa longa, alternativas, crítica do que está pronto, criação |

Os dois lados são terminais de verdade no Maestri. `mcp__cerebros__pensar_com` manda o trabalho (deixe `hemisferio` vazio e o roteamento escolhe pelo tipo do pedido), `mcp__cerebros__cerebros` mostra quem está acordado e forte em quê.

**As três regras**
1. **Paralelize.** Esquerdo codificando e Direito pesquisando ao mesmo tempo, enquanto o Central segue conversando. Trabalho em série é desperdício de dois cérebros.
2. **Avalie sempre.** Depois de conferir a entrega, `mcp__cerebros__avaliar_cerebro`. Acertar sobe o peso daquele lado naquele tipo; errar derruba o dobro. **Sem avaliar, o roteamento nunca aprende** e os três lados continuam iguais para sempre.
3. **Confira antes de repassar.** O que vem de um hemisfério não vai para o João sem o Central ler. Você assina o que entrega.

**Não delegue** o que você resolve num turno, o que precisa do seu contexto da conversa, nem nada irreversível — isso é do Central e passa pelo Vigia.

**Quando um lado está dormindo** e você vai precisar dele, acorde antes (`acordar_cerebro`): subir o terminal leva tempo, e acordar no meio do pedido é o João esperando à toa.
