# Interface em blocos

A interface do J.A.I.M.E deixou de ser "uma página web". Agora ela é feita de **blocos**: pedaços independentes de
informação (as métricas da máquina, a agenda, um gráfico, um diagrama, botões de decisão) que você abre, fecha, arrasta
e reorganiza. Você pode fazer isso com as mãos ou com a voz, ou deixar o Jaime abrir sozinho. O mesmo bloco aparece
em todas as **superfícies** conectadas ao mesmo tempo, cada uma mostrando do seu jeito:

| superfície | como abrir | o que mostra |
|---|---|---|
| cockpit (web) | o HUD de sempre, `http://127.0.0.1:8787` | tudo; lâminas arrastáveis; tecla **K** abre o seletor |
| janela nativa | `python -m jaime blocos janela` | cada bloco é uma janela do sistema, sem navegador (Mac/Windows/Linux) |
| terminal | `python -m jaime blocos terminal` | caixas de texto, gráfico vira sparkline |
| óculos / visor / celular | `/blocos/leve?perfil=oculos` ou um app próprio no protocolo | os 3 blocos mais importantes, curtos; fundo preto (transparente em óculos see-through) |
| falante | qualquer cliente com `perfil: falante` | só a fala: um resumo de uma frase por bloco |

## Pedindo por voz (sem gastar modelo)

"abre o bloco da máquina" · "fecha o bloco de tarefas" · "fecha todos os blocos" · "quais blocos estão abertos?" ·
"lê o bloco da agenda" · "salva esse layout como trabalho" · "abre o layout trabalho" · "desfaz o último bloco".
Com as mãos no ar ligadas (docs/ESPACIAL.md), cada bloco vira um objeto da cena: aponte e diga "fecha isso", arraste
para mudar de lugar em todas as telas, jogue na lixeira virtual para fechar.

Pedidos novos ("abre um bloco comparando o faturamento da BUB e da Oldsen") vão ao cérebro, que compõe o bloco com
`mcp__blocos__abrir`. Se você pedir a mesma coisa de novo, ele transforma esse bloco em **modelo**.

## Modelos e fontes vivas

Modelos prontos: `maquina`, `relogio`, `financas`, `financas-mensal`, `tarefas`, `agenda`, `estado`, `placar`,
`espacial`, `casa`, `presenca`. Os que têm **fonte** se atualizam sozinhos (máquina a cada 5 s, finanças a cada
1 min…). Fonte privada (finanças, tarefas, agenda, casa, presença) só aparece em superfície do dono com o cérebro
destrancado: se o cérebro tranca, os blocos privados somem de todas as telas em até 1 s.

`python -m jaime blocos modelos` lista tudo e roda o **contrato** em cada modelo.

## Como o Jaime melhora a interface sozinho, sem se quebrar

- **Contrato de renderização:** nenhum modelo novo é gravado sem passar em todas as superfícies (cockpit, janela,
  terminal, óculos, visor, falante). Tem de adaptar sem erro, ter texto e fala não vazios e nunca mandar HTML para quem
  não é web. Cada versão fica guardada, e `reverter` volta a anterior. Modelo embutido nunca é sobrescrito.
- **Uso vira sinal:** bloco que o Jaime abriu sozinho e você fechou em menos de 5 s conta como "não queria isso". Esses
  números entram nos sinais da autoevolução (`Evolucao.sinais`), e as propostas de melhoria nascem do que você usa e
  rejeita de verdade.
- **Gate de qualidade** (`jaime/qualidade.py`): toda proposta de autoevolução, além do pytest verde, é medida contra o
  código atual em processos separados. São medidos os gestos em replay, o contrato dos blocos e a voz em frases de
  referência. A proposta é reprovada se alguma métrica piorar, se o número de testes cair (apagar teste para passar
  não vale) ou se ela mexer em `jaime/vigia/`, `.env`, `vault/00-Jaime/` ou `CLAUDE.md`. O relatório vai para o PR.
  `JAIME_EVOLUCAO_GATE=off` desliga.

## Protocolo JBP v1 (para construir uma superfície nova: óculos, relógio, carro, ESP32)

Transporte: WebSocket `ws://<host>:8787/blocos/ws`, uma mensagem JSON por frame.

```text
cliente → {"op":"ola","perfil":"oculos","nome":"óculos do João","capacidades":{"largura":640,"linhas_max":4,"voz":true},"v":1}
servidor → {"op":"bem_vindo","sessao":"…","perfil":"oculos","capacidades":{…},"v":1}
servidor → {"op":"abrir","bloco":{"id":"maquina","tipo":"metricas","titulo":"Máquina","prioridade":1,
                                   "linhas":["CPU: 12 %","Memória: 61 %","Disco: 30 %"],"fala":"Máquina: CPU 12 %, …"}}
servidor → {"op":"atualizar","bloco":{…}}      servidor → {"op":"fechar","id":"maquina"}
cliente → {"op":"fechar","id":"…"} · {"op":"mover","id":"…","ancoragem":{"x":0.7,"y":0.2}} · {"op":"ler","id":"…"}
          {"op":"acao","id":"…","intencao":"<a do botão>"} · {"op":"desfazer"} · {"op":"ping"}
```

- **Capacidades** (todas opcionais): `visual`, `largura`, `altura`, `linhas_max`, `blocos_max`, `cores`, `graficos`,
  `tabelas`, `grafos`, `html`, `imagens`, `tres_d`, `voz`, `entrada`. O servidor adapta cada bloco antes de mandar.
  O cliente recebe `linhas` (texto pronto) sempre que é visual, `fala` sempre que tem voz, e `conteudo` estruturado só
  quando sabe desenhar aquele tipo. Com `tres_d`, a ancoragem traz `pos3d` em metros.
- **Botões** (`acao`): o cliente manda só a intenção que o próprio bloco oferece. Qualquer outra é recusada. A intenção
  vira um turno normal do Jaime, com Vigia e diário.
- **De fora da máquina** (óculos na rede): troque o `JAIME_SERVER_TOKEN`, abra o `JAIME_BIND`, gere o token do
  dispositivo com `python -m jaime blocos parear oculos-joao` e conecte em
  `ws://<ip>:8787/blocos/ws?dispositivo=oculos-joao&t=<token>`. Trocar o `JAIME_SERVER_TOKEN` revoga todos os
  dispositivos. Um site de terceiros não consegue virar superfície (Origin checado).

Um cliente mínimo em Python:

```python
import json
from websockets.sync.client import connect
with connect("ws://127.0.0.1:8787/blocos/ws") as ws:
    ws.send(json.dumps({"op": "ola", "perfil": "falante", "nome": "caixa da cozinha"}))
    for m in map(json.loads, ws):
        if m["op"] == "abrir":
            print("dizer:", m["bloco"]["fala"])      # aqui entra o TTS do dispositivo
```

Para óculos com navegador ou app com WebView (celular pareado com óculos de display, Quest, Vision Pro), a
superfície pronta é `/blocos/leve?perfil=oculos` (ou `visor`). Para um app nativo (Unity, visionOS, Android XR),
implemente o JBP acima: são 6 mensagens.

## O que está validado e o que falta

Validado aqui, com testes: protocolo ponta a ponta (WebSocket real), diff por superfície, privacidade ao trancar,
cliente lento desconectado, voz sem modelo, layouts, contrato, uso, gate. Também foi feita a captura do cockpit, das
janelas nativas (Tk em tela virtual), do terminal e da superfície de óculos. **Falta** testar num óculos, num visor e
no falante reais, e as janelas nativas no macOS e no Windows (o Tk é o mesmo, mas transparência e "sempre na frente"
variam por sistema).
