# O J.A.I.M.E na máquina do Gabriel — sem briga com o que já roda aqui

Este documento resolve um problema específico: o João e o Gabriel trabalham **na mesma sala**, e o J.A.I.M.E
já está ligado na máquina do João, com microfone e alto-falante. O Gabriel precisa que o Jaime alcance os
arquivos e as worktrees **do computador dele** — sem que apareça um segundo assistente competindo pelo som.

A regra que faz tudo funcionar, e a única que não pode ser quebrada:

> **Um Jaime, vários braços.**
> O Jaime roda **só** na máquina do João. A máquina do Gabriel roda **só** o agente da frota — que não
> fala, não escuta e não abre porta nenhuma.

---

## 1. O desenho, em uma figura

```
   ┌──────────────────────── MÁQUINA DO JOÃO (192.168.200.23) ────────────────────────┐
   │                                                                                  │
   │   🎤 microfone   ──►   J.A.I.M.E   ──►  🔊 alto-falante                           │
   │   (dos dois)            │  │  │         (dos dois)                               │
   │                         │  │  │                                                   │
   │            Maestri ◄────┘  │  └────► Codex · Claude · Gemini                      │
   │            (aqui)          │         (tudo processado AQUI)                       │
   │                            │                                                      │
   └────────────────────────────┼──────────────────────────────────────────────────────┘
                                │  a conexão SAI da máquina do Gabriel e vem para cá
                                ▼
   ┌────────────────── MÁQUINA DO GABRIEL ──────────────────┐
   │   agente da frota (~/.jaime-frota/)                    │
   │   · sem voz  · sem microfone  · sem porta aberta       │
   │   · alcança só a pasta que o Gabriel autorizar         │
   └────────────────────────────────────────────────────────┘
```

O cérebro, o custo dos tokens, o Maestri, o vault e a voz ficam **todos** na máquina do João. A máquina do
Gabriel entra como um braço: lê, escreve e roda comando nas worktrees dele, quando o Jaime pedir.

## 2. O que roda onde

| | Máquina do João | Máquina do Gabriel |
|---|---|---|
| J.A.I.M.E (`jaime serve`) | ✅ sim, como hoje | ❌ **nunca** |
| Microfone / escuta | ✅ o de sempre | ❌ nenhum |
| Voz / alto-falante | ✅ o de sempre | ❌ nenhuma |
| Porta 8787 | ✅ aberta na rede local | ❌ nada aberto |
| Maestri, Codex, Claude, Gemini | ✅ tudo aqui | ❌ nada |
| Vault / memória | ✅ o do João | ❌ nenhum |
| Agente da frota | — | ✅ **só isto** |

## 3. Por que não subir um segundo Jaime lá

Não é preciosismo — são três estragos concretos, e os dois primeiros acontecem no primeiro minuto:

1. **Os microfones se escutam.** Dois Jaimes na mesma sala: o A fala, o B transcreve o que o A disse e
   responde, o A transcreve a resposta do B e responde de volta. Vira um loop, em voz alta, e nenhum dos
   dois consegue ouvir uma pessoa. O sistema anti-eco do Jaime protege ele **da própria voz**, não da voz
   de outro Jaime.
2. **Duas vozes falando juntas.** Nenhum dos dois é audível.
3. **Dois donos, duas memórias, um custo dobrado.** Cada Jaime manteria vault e diário próprios,
   chamaria os modelos por conta e cobraria em dobro por respostas piores, porque cada metade só veria
   metade do contexto.

Se um dia o Gabriel quiser o **assistente dele**, com voz e memória próprias, isso existe e é outro
caminho: `jaime/donos.py` conduz a cópia separada, na máquina dele, com o vault dele. É deliberadamente
outra coisa — e não é para rodar na mesma sala ao mesmo tempo.

## 4. A parte do João — três passos, uma vez só

O Jaime faz tudo isso por voz. Em texto, se preferir:

**a) Cadastrar a máquina do Gabriel na frota.** Precisa do hostname dela — o Gabriel roda `hostname` e
manda. Depois, para o Jaime:

> «Jaime, cadastra a máquina do Gabriel na frota: apelido gabriel, host `MacBook-do-Gabriel.local`, dono
> Gabriel Mello, nível operador, pasta `/Users/gabriel/Projetos`.»

O **nível** é o que ele pode fazer lá:

| nível | pode | para quem |
|---|---|---|
| `leitor` | listar e ler | máquina que ele só consulta |
| `operador` | ler, escrever e **rodar comando** — dentro da pasta | **o caso do Gabriel** |
| `dono` | o mesmo, na casa inteira do usuário | só as máquinas do próprio João |

**b) Pedir o convite.**

> «Jaime, convida a máquina do Gabriel.»

Sai um código de 8 caracteres que **vale 10 minutos e uma vez só**. Esse código pode ser dito em voz alta
ou mandado no WhatsApp — ele não é a credencial. O token permanente da máquina nunca passa pela conversa:
vai pela rede, direto para o computador do Gabriel, no momento da instalação.

**c) Passar ao Gabriel a linha que o Jaime devolveu.** É uma linha só.

## 5. A parte do Gabriel — uma linha

No Terminal do Mac dele:

```sh
curl -fsSL 'http://192.168.200.23:8787/frota/instalar?c=CODIGO_QUE_O_JOAO_PASSOU' | sh
```

O instalador **mostra na tela** o que vai ser permitido — apelido, dono, o que o Jaime poderá fazer, em
qual pasta, e o que fica protegido — e só continua se o Gabriel digitar `sim`. Depois pergunta se deve
subir junto com o computador; para a máquina do Gabriel, a resposta recomendada é **não** (ele liga quando
quer emprestar).

Religar depois, quando quiser:

```sh
sh ~/.jaime-frota/ligar.sh
```

Encerrar: `Ctrl-C`. O acesso acaba junto, na hora.

Se o Gabriel preferir que o próprio Claude Code dele faça a instalação e confira tudo antes, use o
`docs/PROMPT-GABRIEL.md` — é um prompt pronto para colar.

## 6. Como os dois falam com ele, dividindo o mesmo microfone

O microfone e o alto-falante são os da máquina do João, para os dois. O Jaime já tem o conceito de **quem
está falando** (`falante_atual`: João, Gabriel, desconhecido). Na prática:

- O Gabriel se apresenta uma vez: **«Jaime, sou o Gabriel»**. Dali em diante o Jaime trata o turno como
  dele e usa a máquina dele quando o pedido for de arquivo ou worktree.
- Para não haver dúvida num pedido que mexe em arquivo, vale nomear a máquina: «roda os testes **na minha
  máquina**», «lê o `README` **no gabriel**».
- O Jaime **não mistura memória**: o que é do Gabriel não entra no diário do João como se fosse dele.
- Interromper funciona para os dois: falar por cima corta a fala dele, de quem quer que seja a voz.

Quando o Gabriel for embora, o agente dele desliga (ou o Ctrl-C, ou o computador saindo da rede) e o Jaime
volta a dizer que aquela máquina está fora do ar — sem quebrar nada.

## 7. O que o Jaime pode e o que ele nunca faz na máquina do Gabriel

**Pode**, dentro da pasta autorizada: listar, ler, escrever, rodar comando (git, teste, build), e tirar o
retrato da máquina para saber com o que se trabalha ali — se é `brew` ou `apt`, se o python é `python3`,
onde ficam os projetos. Esse retrato fica guardado, então na segunda vez ele já sabe.

**Nunca**, e isso não depende de configuração nem do nível:

- sai da pasta autorizada — caminho com `..`, caminho absoluto e **atalho que aponta para fora** são
  recusados na máquina do Gabriel, antes de qualquer leitura;
- toca em `.ssh`, `.gnupg`, `.aws`, `.env`, `.netrc`, chaveiro, `.kube/config`, `.docker/config.json` —
  nem no nível `dono`. Com a chave de ssh do Gabriel ele entraria em servidor que não é dele;
- abre porta, instala serviço sem perguntar, ou fica no boot sem o Gabriel dizer `sim`;
- faz `git push` sem confirmação — o Vigia barra, aqui como em qualquer lugar.

E o desenho protege o Gabriel de um jeito que não depende de boa vontade: **nada entra na máquina dele.**
É ela que liga para cá e pergunta se tem trabalho. Não há porta para bater.

## 8. Quando algo não funciona

| sintoma | o que é | o que fazer |
|---|---|---|
| «não está na frota» | o hostname não bate com a matrícula | `hostname` na máquina dele, e o João corrige a linha em `01-Estado/Frota.md` |
| «token não confere com esta máquina» | o hostname mudou depois da instalação | pedir novo convite e reinstalar |
| «Convite inválido ou expirado» | passou de 10 min, ou já foi usado | pedir outro: «Jaime, convida a máquina do Gabriel» |
| «fora do ar (sumiu há Ns)» | o agente caiu, ou o Mac dormiu | `sh ~/.jaime-frota/ligar.sh` |
| «eu sou leitor e leitor não roda comando» | o nível está baixo | o João sobe o nível na matrícula e o Gabriel religa |
| não alcança o servidor | Wi-Fi diferente, ou o Jaime não está com a porta aberta na rede | os dois na mesma rede; `JAIME_BIND` não pode estar em `127.0.0.1` |
| dois Jaimes falando | subiu `jaime serve` na máquina do Gabriel | matar o segundo. Só o agente roda lá |

## 9. Tirar da frota

> «Jaime, tira a máquina do Gabriel da frota.»

Some a linha da matrícula e o acesso acaba no próximo registro. Do lado do Gabriel, apagar de vez:

```sh
launchctl unload ~/Library/LaunchAgents/com.jaime.frota.plist 2>/dev/null
rm -rf ~/.jaime-frota ~/Library/LaunchAgents/com.jaime.frota.plist
```

---

**Onde isso vive no código:** `jaime/frota/` — `registro.py` (matrícula: hostname → dono, nível, pasta),
`frota.py` (as ligações e os convites), `servidor.py` (as ferramentas do Jaime), `agente.py` (o que roda na
outra máquina — quem manda), `instalador.py` (o `curl | sh`). Testes em `tests/test_frota.py`.
