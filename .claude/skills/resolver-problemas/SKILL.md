---
name: resolver-problemas
description: "Método para atacar qualquer problema difícil: reproduzir, formar hipótese, isolar, provar, consertar a causa. Use quando algo quebrou, está lento, ou 'às vezes funciona'."
---
# Resolver problemas — achar a causa, não calar o sintoma

**As seis etapas. Não pule nenhuma.**

1. **Enuncie o problema em uma frase**, com o que você esperava e o que aconteceu. Se não consegue escrever essa frase, você ainda não sabe qual é o problema.
2. **Reproduza.** Qual entrada, qual comando, com que frequência. Sem reprodução você tem palpite, não problema. "Às vezes" é um dado: anote quantas vezes em quantas.
3. **Leia o que a máquina já disse** antes de mexer: log, diário do dia, eventos, `git diff`, `git log`. A resposta costuma já estar escrita em algum lugar.
4. **Uma hipótese por vez, e ela tem que prever algo.** "Se for o cache, então limpar o cache resolve e o log mostra X." Teste só isso. Hipótese que explica tudo não explica nada.
5. **Isole por bissecção.** Metade do caminho, metade do tempo, metade do código. Comente, desligue, volte a versão. Estreite até sobrar uma coisa.
6. **Prove.** Só é causa o que você consegue ligar e desligar à vontade. Se você "consertou" e não sabe por quê, não consertou.

**Depois**: conserte a causa, não o sintoma; deixe um teste que falharia antes e passa depois; registre a linha no diário do dia.

**Sinais de que você está se enganando**
- Mudou três coisas de uma vez e funcionou. Você não sabe qual foi.
- Está ajustando limiar no chute.
- Reiniciou "para ver se melhora" sem ter lido o log.
- Está há trinta minutos na mesma hipótese. Troque de hipótese ou peça ajuda.
- Disse "deve ser" mais de duas vezes.

**Quando empacar**: escreva o problema para outra pessoa (isso resolve metade), ou delegue a um filho no Maestri com a reprodução pronta e volte a atender o João.
