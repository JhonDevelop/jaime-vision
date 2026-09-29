# A casa: Home Assistant, Alexa e Bluetooth

O J.A.I.M.E manda; a Alexa executa. Ele entende o pedido, decide, confere e lembra. Os Echos viram alto-falantes
espalhados pela casa, e tudo o que a Alexa sabe fazer por voz ele manda por texto: tocar música, rodar rotinas,
ligar aparelhos que só existem no app Alexa, ajustar volume e timers. Você fala com o Jaime. Ele fala com a casa.

```
João ──voz/HUD/óculos──► J.A.I.M.E (cérebro, Vigia, memória)
                               │
                               ├─► Home Assistant ──► luzes, tomadas, sensores, câmeras, BLE (proxies ESPHome)
                               │         └──► Alexa (integração) ──► Echos: falar, anunciar, tocar, comandos
                               └─► Bluetooth desta máquina ──► presença (celular/relógio do João por perto)
```

## Ligar em 4 passos

1. **Home Assistant** rodando na rede, com um token de longa duração: `HA_URL` e `HA_TOKEN` no `.env`
   (já existia, está em `docs/CONEXOES.md`).
2. **Alexa no Home Assistant**. Escolha **uma** integração:
   - **Alexa Devices** (oficial, dentro do HA): Configurações › Dispositivos e serviços › Adicionar › *Alexa Devices*.
     A conta Amazon precisa ter 2FA com **app autenticador** (não SMS).
   - **Alexa Media Player** (HACS, não oficial): alternativa se a oficial não pegar a sua conta.

   Nas duas, a conta tem de ser a brasileira (amazon.com.br) para os seus Echos aparecerem. As duas usam a API não
   oficial da Amazon e podem parar de funcionar quando a Amazon muda algo. O Jaime descobre sozinho qual das duas está
   instalada; `alexa_echos` lista o que ele encontrou.
3. Opcional: `JAIME_ALEXA_PADRAO=sala` é o Echo usado quando o pedido não diz onde.
4. Reinicie o serviço. Depois é só pedir: "toca Legião Urbana na sala", "avisa a casa toda que o jantar está pronto",
   "liga o ventilador do quarto".

## O que ele faz com a Alexa

| ferramenta | o que faz |
|---|---|
| `alexa_falar` | a Alexa fala um texto num Echo; `announce` toca o sininho e fala em todos |
| `alexa_comando` | qualquer coisa que se diria à Alexa, mandada como texto |
| `alexa_tocar` / `alexa_parar` / `alexa_volume` | música, rádio, podcast; parar; volume de 0 a 100 |
| `alexa_echos` | quais Echos existem e qual integração está ligada |
| `saida_audio` | a **voz do Jaime** sai por um Echo pareado por Bluetooth, como caixa de som |

**Duas vozes, dois usos.** `alexa_falar` usa a voz da Alexa, para avisos na casa. Para ouvir o próprio Jaime pelo
Echo, pareie o computador com o Echo ("Alexa, emparelhar") e deixe o Echo como saída de som. No Mac, o
`SwitchAudioSource` (`brew install switchaudio-osx`) deixa o Jaime trocar a saída sozinho.

## Segurança

Estas ações ficam presas no **lote do Vigia** até você dizer "sim" (ou "confirmo"): comprar ou pedir pela Alexa,
ligar para alguém ou fazer drop in, mandar mensagem, destrancar ou abrir porta, portão ou garagem, desarmar alarme e
desligar câmera. Isso vale tanto pela Alexa quanto pelo Home Assistant (`casa_servico` com `lock.unlock`,
`alarm_control_panel.alarm_disarm`, portão/garagem em `cover`). Cada "sim" libera uma ação. Com visita na linha,
nenhuma delas roda.

## Bluetooth

- **Aparelhos BLE da casa** (sensores, tomadas, fechaduras, SwitchBot, Xiaomi…) entram pelo Home Assistant, pela
  integração Bluetooth dele, com o adaptador do servidor ou proxies ESPHome pelos cômodos. Para o Jaime eles viram
  entidades comuns.
- **Presença:** `JAIME_BT=on` e `JAIME_BT_CONHECIDOS="celular do João=iPhone de João"` fazem esta máquina escanear
  anúncios BLE (pacote `bleak`, `pip install bleak`, que funciona no Mac, no Windows e no Linux). O Jaime passa a saber
  quando você chega e sai, com histerese de sinal. `JAIME_BT_SAUDAR=on` faz ele cumprimentar na chegada. **Presença
  nunca destranca nada**, porque um anúncio Bluetooth é fácil de imitar.

## Blocos

Os modelos `casa` (luzes acesas, portas abertas, temperatura) e `presenca` (quem está em casa) podem ser abertos em
qualquer superfície: "abre o bloco da casa".

## Validação

Toda a lógica foi testada com um Home Assistant simulado (`tests/test_casa_alexa.py`). Ainda **falta testar** com o
HA real e os seus Echos, com a sua conta Amazon, e o scan Bluetooth no Mac e no Windows.
