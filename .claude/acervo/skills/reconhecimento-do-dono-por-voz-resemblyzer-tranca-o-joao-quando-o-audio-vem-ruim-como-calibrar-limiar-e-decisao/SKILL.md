---
name: reconhecimento-do-dono-por-voz-resemblyzer-tranca-o-joao-quando-o-audio-vem-ruim-como-calibrar-limiar-e-decisao
description: jaime/voice/falantes.py (novo módulo com Profile/VerificationSession/verify) — substitui a comparação simples de embedding único em jaime/voice/falant
---

Pra qualquer decisão baseada em similaridade de cosseno contra um perfil biométrico ruidoso (voz, e no futuro possivelmente rosto): 1) nunca usar corte único — definir T_ACCEPT e T_REJECT com zona ambígua no meio; 2) na zona ambígua, pedir nova amostra com EMA entre tentativas, nunca decidir com 1 amostra só; 3) esgotadas as tentativas, cair num fallback de OUTRO fator (senha/PIN), nunca afrouxar o limiar biométrico; 4) cadastro deve guardar as amostras individuais além da média, e o score final ser o melhor entre similaridade ao centroide e à melhor amostra individual; 5) pra calibrar sem a lib pesada instalada, simular embeddings sintéticos L2-normalizados em alta dimensão com ruído aditivo NORMALIZADO (cuidado: gaussiano cru em alta dimensão tem norma ~sqrt(dim) e domina o sinal mesmo com peso de ruído pequeno).
