# Frota — as máquinas que eu alcanço

Uma linha por máquina. O **host** é o que a máquina diz de si (`hostname`) e é por ele que eu descubro de
quem ela é — não pelo que o agente se declara. Apagar a linha tira a máquina da frota na hora.

Níveis: `leitor` lista e lê; `operador` lê, escreve e roda comando **na pasta**; `dono` o mesmo, na **casa
inteira** daquele usuário (só para as máquinas do próprio João). `leitor` e `operador` exigem pasta.

Protegido em qualquer nível, inclusive `dono`: `.ssh`, `.gnupg`, `.aws`, `.env`, `.netrc`, chaveiro,
`.kube/config`, `.docker/config.json`. Chave de acesso não é "arquivo na casa" — é a casa dos outros.

Esta máquina (`MacBookPro`) **não entra na frota**: é onde eu rodo. Frota é o que está do outro lado.

| apelido | host | dono | nível | pasta | como mexer |
|---|---|---|---|---|---|

## Como põe uma máquina aqui

1. Na máquina nova, o dono roda `hostname` e passa o resultado.
2. Aqui: «Jaime, cadastra a máquina do Gabriel: apelido gabriel, host `X`, dono Gabriel Mello, nível
   operador, pasta `/Users/gabriel/Projetos`.»
3. «Jaime, convida a máquina do Gabriel» → sai um código de 8 caracteres, válido por 10 minutos e uma vez
   só. O código pode ser ditado; o token permanente **nunca** — ele vai pela rede, direto para a máquina.
4. Na máquina nova: `curl -fsSL 'http://192.168.200.23:8787/frota/instalar?c=CODIGO' | sh`

O passo a passo completo, com o desenho e os cuidados, está em `docs/FROTA-GABRIEL.md`. O prompt pronto
para o dono da outra máquina colar no Claude Code dele está em `docs/PROMPT-GABRIEL.md`.

## O retrato de cada máquina

Na primeira vez que eu mexo numa máquina eu tiro o retrato dela (`conhecer_maquina`): sistema, shell, o que
está instalado, onde ficam os projetos. Fica em `01-Estado/Maquina-<apelido>.md`. É o que me faz saber se
ali é `brew` ou `apt`, se o python é `python3`, e onde o trabalho mora — em vez de chutar.
