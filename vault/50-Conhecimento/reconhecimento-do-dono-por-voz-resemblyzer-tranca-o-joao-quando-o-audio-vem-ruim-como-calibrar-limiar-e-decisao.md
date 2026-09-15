# Reconhecimento do dono por voz (resemblyzer) tranca o João quando o áudio vem ruim: como calibrar limiar e decisão

> Resolvido pelo cérebro de estudo em 15/09/2026 (problema P-0003, origem joao_pediu).

## Como reproduzir
cd /tmp/jaime-lab && source venv/bin/activate && python3 test_p0003_repro.py — mostra a distribuição de score sob ruído e compara limiar simples (trava 100% em ruído forte) vs fluxo proposto (trava definitivo só ~11%, FAR impostor 0%)

## O que resolveu
Troquei o corte único por decisão de 3 zonas: score = max(similaridade ao centroide, melhor similaridade a qualquer uma das 5 frases de cadastro); zona ambígua (0.55–0.76) pede pra repetir com EMA (alpha=0.6) entre tentativas (até 2), e só depois cai no fallback de senha digitada — que nunca abre pra estranho porque não relaxa o limiar de voz, troca de fator de autenticação.

## Onde se aplica
jaime/voice/falantes.py (novo módulo com Profile/VerificationSession/verify) — substitui a comparação simples de embedding único em jaime/voice/falantes.py original; usar T_ACCEPT=0.76, T_REJECT=0.55, EMA_ALPHA=0.6, MAX_RETRIES=2 como ponto de partida
