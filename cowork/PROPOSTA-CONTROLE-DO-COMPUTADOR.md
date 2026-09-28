# Proposta — controle do computador por gestos, voz e visão espacial

> **Status: proposta do João, 28/09/2026. Não aprovada. A mensagem original foi interrompida** — trate como
> rascunho até ele confirmar. O Cowork registra e analisa; não implementa.

## A proposta, nas palavras do João

O J.A.I.M.E continua com acesso ao computador inteiro, **exatamente como hoje**. Gestos, voz, visão espacial,
contexto e autonomia entram **por cima** desse acesso, como interfaces adicionais — não o substituem. Exemplos:
pegar uma pasta com a mão e arrastar para outro monitor; "abre isso no editor"; amassar um projeto e jogar na
lixeira. O gesto vira uma ação real do sistema.

O acesso fica **em níveis**:
- **Simples e reversível** — abrir pasta, mover janela, navegar, selecionar, copiar: praticamente instantâneo.
- **Perigoso** — apagar definitivamente, instalar software, alterar arquivos de sistema, publicar código,
  executar comandos privilegiados: passa por permissão, confirmação ou política configurável.

```
J.A.I.M.E
   ↓
Intent Engine
   ↓
Computer Control Layer
   ├── Mouse · Keyboard · Windows · Filesystem · Applications
   ├── Terminal · IDE · Browsers · Multi-monitor · System APIs
   ↓
Permission / Safety Layer
   ↓
Windows / macOS / Linux
```

A parte espacial **só gera intenções** ("pegou pasta X", "moveu para monitor 3", "deu zoom", "abriu", "jogou na
lixeira"); o J.A.I.M.E as traduz em ações reais.

## O que já existe, camada por camada

| Camada | Já existe | Não consta |
|---|---|---|
| Intent Engine | `cortex/roteador.py` classifica pedidos em texto; `voice/antecipador.py` tira intenção da fala parcial | qualquer intenção vinda de gesto ou do espaço |
| Mouse / teclado | `maos/computador.py`: `capturar`, `clicar`, `digitar`, `tecla` | arrastar, soltar, rolar |
| Janelas / apps | AppleScript (permissão Automação); observador da janela ativa | mover janela entre telas |
| Arquivos | `maos/arquivos.py`, `maos/projetos.py` | mandar para a Lixeira (hoje só existe apagar) |
| Terminal | `Bash` do Agent SDK | — |
| Browsers | `maos/browser.py` (Playwright), `maos/raspar.py` | — |
| IDE | — | integração direta com editor |
| Multi-monitor | — | **não consta**: `computador.tamanho()` devolve uma tela só |
| Visão | `maos/visao.py` (visão contínua), `casa/camera.py` (webcam) | rastreamento de mão |
| Permissões | `vigia/hooks.py`, `vigia/confianca.py`, tranca por dono | — |
| Sistema operacional | macOS | **Windows e Linux** — o código assume `osascript`, `screencapture`, `afplay` |

A regra central da proposta — **gesto só gera intenção** — já casa com a arquitetura: o Vigia é um hook
`PreToolUse` e enxerga qualquer ferramenta antes de ela rodar. Se toda intenção virar uma chamada às mesmas
ferramentas de hoje, nenhuma interface nova ganha um caminho que passe por fora da trava.

## A decisão que precisa vir antes do código

**Os níveis propostos são mais rígidos que o Vigia de hoje.** Em 16/09, a pedido explícito e reafirmado do
João, o Vigia foi reduzido ao mínimo (`jaime/vigia/hooks.py`, comentário no topo):

| Ação | Proposta de 28/09 | Vigia hoje |
|---|---|---|
| comandos privilegiados (`sudo`) | confirmação | **livre** |
| instalar software (`curl … \| sh`) | confirmação | **livre** |
| alterar arquivos de sistema (`chmod`) | confirmação | **livre** |
| publicar código | confirmação | push em `feat/*` livre; push em `main` pede "sim" |
| apagar definitivamente | confirmação | só `rm -rf` de raiz/home e apagar em massa pedem "sim" |

As duas frases da proposta — "exatamente como hoje" e "ações perigosas passam por confirmação" — não valem ao
mesmo tempo. **O João escolhe:** (a) manter o Vigia de 16/09 e os gestos herdam essa permissividade, ou
(b) apertar o Vigia para os níveis desta proposta, para todas as interfaces.

> A decisão de 16/09 está só no comentário do código; **não consta** em `vault/20-Projetos/Jaime.md` → Decisões.

## Três regras específicas de gesto

Independentemente da escolha acima, gesto tem um problema que voz e texto não têm: **reconhecimento de mão erra
por natureza**, e um falso positivo vira ação real.

1. **Gesto sozinho só alcança o nível reversível.** "Amassar e jogar na lixeira" move para a Lixeira — nunca
   esvazia a Lixeira, nunca apaga. Ação irreversível pedida por gesto exige confirmação por voz ou texto.
2. **Confiança progressiva separada por canal.** Uma classe de ação que ficou livre por aprovações em voz não fica
   livre por gesto automaticamente.
3. **Kill switch físico.** Um gesto e uma palavra ("para") que cancelam qualquer sequência em curso — como já
   existe para a visão contínua.

## Etapas sugeridas (se aprovada)

| # | Etapa | Critério de pronto |
|---|---|---|
| 1 | Decisão dos níveis (a ou b acima) registrada em Decisões | linha datada em `Jaime.md`; Vigia e `SEGURANCA.md` coerentes com ela |
| 2 | Primitivas que faltam: arrastar, mandar para a Lixeira, mover janela entre telas, listar monitores | testes; mover uma janela para o monitor 2 por voz |
| 3 | Intent Engine para entradas não textuais: intenção estruturada → mesma ferramenta de hoje | nenhuma intenção executa por um caminho que o Vigia não veja (teste) |
| 4 | Rastreamento de mão como fonte de intenção, atrás de flag | pegar, soltar, abrir, lixeira reconhecidos; falso positivo nunca irreversível (teste) |
| 5 | Windows e Linux | só se o João pedir — é a etapa mais cara e hoje nada usa |

Ordem proposta: 1 → 2 → 3 → 4. A etapa 5 é independente e pode nunca ser necessária.
