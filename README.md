# J.A.I.M.E

**Assistente pessoal autônomo que roda na sua máquina, fala com você por voz e trabalha sozinho.**

Não é um chat com ferramentas. É um processo que fica ligado, ouve, decide, age, se lembra do que aconteceu
e do que você é, e continua trabalhando quando você sai da frente. Feito para o João Vitor Leal
(Franca/SP) e para quem quiser rodar a própria cópia.

```
17.630 linhas de Python · 26 módulos · 498 testes · 25 servidores MCP · 115 ferramentas
709 agentes · 292 skills · 218 commits
```

---

## Índice

1. [O que ele faz](#1-o-que-ele-faz)
2. [Como ele funciona por dentro](#2-como-ele-funciona-por-dentro)
3. [A memória: o vault](#3-a-memória-o-vault)
4. [Os três cérebros](#4-os-três-cérebros)
5. [A voz](#5-a-voz)
6. [A interface](#6-a-interface)
7. [Autonomia: do "tive uma ideia" ao "entreguei"](#7-autonomia-do-tive-uma-ideia-ao-entreguei)
8. [Segurança: o Vigia e o que ele nunca faz](#8-segurança-o-vigia-e-o-que-ele-nunca-faz)
9. [Do que ele depende](#9-do-que-ele-depende)
10. [Permissões que você precisa dar](#10-permissões-que-você-precisa-dar)
11. [Quanto pesa](#11-quanto-pesa)
12. [Quanto custa](#12-quanto-custa)
13. [Instalação](#13-instalação)
14. [Operação do dia a dia](#14-operação-do-dia-a-dia)
15. [Dois donos na mesma máquina](#15-dois-donos-na-mesma-máquina)
16. [Testes e como contribuir](#16-testes-e-como-contribuir)
17. [O que ele ainda não faz](#17-o-que-ele-ainda-não-faz)

---

## 1. O que ele faz

**Conversa por voz, em português, full-duplex.** Você fala, ele ouve, responde e cala. Sabe quando você
terminou de falar ouvindo o *áudio*, não a transcrição — então não corta no meio da sua respiração. Se você
falar por cima, ele para em menos de 100 ms.

**Lembra da sua vida.** Pessoas, animais, lugares, projetos e as relações entre eles, num grafo com data e
evidência. Quem é o Rafael, de quem é o Thor, quem trocou de emprego. Fato que muda não vira contradição: o
antigo fica no histórico.

**Decide se te interrompe.** Alguém manda mensagem? Ele decide por juízo, não por regra fixa. Urgência de
verdade passa mesmo de desconhecido; conversa fiada não passa nem de gente próxima. E se alguém aparece
muito e ele não sabe quem é, ele fica curioso e pergunta — uma vez.

**Opera a máquina.** Terminal, arquivos, browser com perfil próprio, teclado e mouse de verdade
(`pyautogui`), captura e leitura de tela. Não precisa de API para usar um app: ele vê e clica.

**Trabalha sozinho.** Pensa quando está ocioso, estuda o que não entendeu, cria de madrugada, propõe
melhorias em si mesmo e persegue objetivos até conseguir — com verificação contra critério escrito antes.

**Cuida do que é seu.** Finanças, afazeres, agenda, rotinas, projetos, música. Tudo com painel visual.

---

## 2. Como ele funciona por dentro

```
    você (voz / teclado / Telegram / WhatsApp)
                    │
        ┌───────────▼───────────┐
        │  ouvido full-duplex   │  Silero VAD → STT em fluxo → Smart Turn (fim de turno pelo áudio)
        └───────────┬───────────┘
                    │
        ┌───────────▼───────────┐
        │     orquestrador      │  Claude Agent SDK · um cliente, fila com prioridade
        │  (o Central, Claude)  │  decide, delega, costura, responde
        └──┬────────┬────────┬──┘
           │        │        │
    25 servidores   │   hemisférios no Maestri
       MCP em       │   ├── Esquerdo (Codex): código, teste, execução
       processo     │   └── Direito (Gemini): pesquisa, alternativa, crítica
           │        │
    ┌──────▼────────▼──────┐
    │  vault (Markdown)    │  a memória, legível por humano, versionada
    └──────────────────────┘
           │
    ┌──────▼──────┐
    │  cockpit    │  SSE → canvas: cérebro, nós, mundos, painéis
    └─────────────┘
```

**Um processo, muitas trilhas.** O serviço sobe um servidor FastAPI e nele convivem: o ouvido, o
observador de tela, as notificações, a Mente que pensa, o estudo, o despertador dos hemisférios, a agenda
com cron, a telemetria e o Telegram. Cada um é uma task de `asyncio`; nenhum bloqueia o outro.

**As capacidades são servidores MCP em processo.** Não são subprocessos nem HTTP: são `create_sdk_mcp_server`
dentro do mesmo Python, um por domínio. São 25, com 115 ferramentas. Os principais:

| servidor | o que faz |
|---|---|
| `cerebro` | ler e escrever no vault, diário, tarefas, estado |
| `relacoes` · `curiosidade` | quem é quem; quem fala com você e se merece interromper |
| `cerebros` | escolher com qual hemisfério pensar, e aprender qual acerta mais |
| `harness` | perseguir um objetivo até conseguir, verificando contra critério |
| `agente` | a carteira de iniciativas e o ciclo de spec |
| `acervo` | achar qualquer um dos 709 agentes sem carregá-los todos |
| `interface` | mostrar coisas na tela, inclusive desenhando a tela na hora |
| `maos` · `web` | terminal, arquivos, browser, teclado, mouse, raspagem |
| `financas` · `agenda` · `musica` | dinheiro, compromissos, Spotify |
| `emocao` · `mente` · `vontade` | humor, pensamento próprio, impulsos |
| `equipe` · `ponte` | filhos no Maestri; acesso à máquina de outro dono |
| `espelho` | o que ele aprendeu do jeito do dono |

---

## 3. A memória: o vault

Uma pasta de Markdown. **Não é banco de dados de propósito**: você abre no Obsidian, lê, discorda e corrige
na mão, e ele obedece na próxima leitura.

```
vault/
  00-Jaime/      quem ele é, origem, regras       ← só o dono edita
  01-Estado/     fase, vontades, pensamentos, confiança, cérebros, iniciativas
  10-Eu/         quem o dono é, pessoas, datas, traços aprendidos
  20-Projetos/   uma nota por projeto
  30-Tarefas/    Inbox, lembretes, rotinas (cron)
  40-Diario/     um arquivo por dia — toda decisão vira linha
  50-Conhecimento/ o que ele aprendeu e as fontes
  60-Conversas/  o que foi dito, por dia
  70-Financas/   lançamentos
  90-Estudo/     problemas que ele abriu sozinho
```

Fora do vault: `~/Jaime/` guarda o que ele *produz* (imagens, vídeo, criações, capturas, worktrees dos
filhos, modelos, cache de voz, `relacoes.db`).

**A regra que sustenta a memória:** todo fato traz **evidência** — de onde saiu e quantas vezes apareceu.
Sem isso, memória vira chute, e chute sobre gente da sua vida é pior que silêncio.

---

## 4. Os três cérebros

Ele não pensa com um modelo, pensa com três, e cada um tem ofício.

| lado | motor | o que faz | agentes |
|---|---|---|---|
| **Central** | Claude | decide, fala com você, orquestra, escreve no vault. **O único que fala.** | 28 |
| **Esquerdo** | Codex | a técnica: código, execução, teste, refatoração | 472 |
| **Direito** | Gemini | o evolutivo: pesquisa longa, alternativas, crítica, criação | 209 |

Os dois lados são **terminais de verdade** no [Maestri](https://maestri.dev), criados sob demanda ou
adotados se já existirem. Um despertador mantém os dois acordados e dá a cada um pauta própria tirada de
coisa real: problemas abertos no estudo, TODO do próprio código, projetos sem nota.

**O roteamento aprende.** Depois de conferir uma entrega, o peso daquele lado naquele tipo de trabalho sobe
se acertou e cai o dobro se errou. A tabela fica em `01-Estado/Cerebros.md`, em Markdown, para o dono
corrigir na mão.

**Em voz, quase nunca se fala deles.** O que ele delega aparece no cockpit e fica lá. A boca só abre quando
acabou algo que *você pediu* — e aí sem nome de motor: "um dos meus agentes terminou o relatório".

---

## 5. A voz

O que faz a voz parecer boa não é uma peça, são cinco.

**Ouvir.** Silero VAD detecta a fala; o STT (Deepgram, OpenAI ou local) transcreve em fluxo com parciais.

**Saber quando você terminou.** Aqui está a parte que quase todo assistente erra. A pontuação da
transcrição não distingue uma pausa para respirar de um ponto final, porque essa diferença está na
prosódia. Então entra o [Smart Turn v3](https://github.com/pipecat-ai/smart-turn) (BSD-2, ONNX, local):
quando o silêncio passa de 260 ms, ele olha os últimos 8 s de *áudio* e diz se você terminou. **67 ms por
decisão**, em CPU. Incompleto, ele espera de verdade; rede de segurança fecha em 2,5 s.

**Falar rápido.** O timbre e o ritmo vêm de uma instrução de estilo, não de filtro de áudio. A instrução
pede falante nativo do Brasil, dicção precisa, entonação contida e **ritmo de conversa**. Lição aprendida
na marra: pedir "voz calma e serena" faz o modelo falar devagar — a mesma frase caiu de 15,1 s para 7,0 s
só trocando o texto da instrução.

**Não fazer esperar.** As 36 frases que ele mais repete ficam pré-sintetizadas no disco e saem em **0,3 ms**
em vez de 1,5 a 3,5 s. `python -m jaime.ops.aquecer_voz` refaz o cache — e **tem que ser refeito toda vez
que a voz muda**, senão fica um remendo de dois ritmos.

**Calar.** Barge-in em menos de 100 ms, e só quando **entendeu**: o critério acústico levanta uma suspeita,
o áudio vai para o STT e quem corta é a transcrição. Palavra de verdade corta; nada em 1,6 s e a suspeita
morre. Sem muleta "peraí" quando ele não está fazendo nada, e sem perguntar "continuo o que eu dizia?" —
cortar já foi a sua resposta.

Escolher a voz: `python -m jaime.ops.amostras_voz` gera variantes falando a mesma frase, para comparar de
ouvido. O padrão é `onyx` a 1.2.

---

## 6. A interface

Um arquivo HTML, sem build, sem dependência externa. Em `http://127.0.0.1:8787`.

**Sem abas.** Atalhos discretos no topo e as mesmas letras no teclado: `C` cérebro, `N` nós, `U` mundos,
`B` cérebros, `F` finanças, `A` afazeres, `G` agenda, `M` música, `T` teclado, `esc` fecha.

**Tudo ao mesmo tempo, em camadas:** poeira de estrelas ao fundo, a malha dos ~1.700 nós reais (cada nota
do vault, cada linha do diário, cada ferramenta, cada tripulante), os 14 mundos do universo em órbita, o
córtex com os dois lobos e suas tripulações, e o cérebro no centro que muda de cor pelo estado e de tamanho
pelo **volume real** do áudio.

**Ele desenha telas.** Quando você pede para ver algo que não tem painel pronto, ele compõe o HTML na hora
e abre num pop-up isolado (iframe com sandbox). Nunca responde "não tenho tela para isso".

**Duas agendas.** A sua (compromissos, lembretes, prazos) e a dele (rotinas, estudo, criação, melhorias),
em trilhos separados, porque o que ele decide fazer sozinho não é obrigação sua.

---

## 7. Autonomia: do "tive uma ideia" ao "entreguei"

A carteira de iniciativas (`01-Estado/Iniciativas.md`) é o fio que liga as peças soltas.

```
imaginada → projetada → validada → produzindo → testando → lançada → medida
```

- **Imaginar** — um assunto que volta **três vezes** no pensamento vira iniciativa. Uma vez é ideia solta.
- **Projetar** — uma spec com problema, entrada, saída, erros e **critério de aceite**.
- **Validar** — um crítico procura buraco *antes* de existir código. Confere por máquina o que dá
  (seção vazia, critério que é opinião, nenhum aceite que seja teste, palavra que abre o escopo) e manda o
  resto ao `spec-guardian`. **É a única trava do ciclo, e é de qualidade, não de permissão.**
- **Produzir** — o harness persegue a spec, delegando a mão de obra ao hemisfério esquerdo num worktree.
- **Testar** — o `pytest` roda **por fora** do agente: ele não pode declarar sucesso sozinho.
- **Lançar** — reversível por padrão. Projeto seu vira PR; melhoria dele entra por autoevolução.
- **Medir** — deu certo sobe Criação e Maestria; deu errado abre um problema de estudo.

**Três coisas impedem o autoengano:** critério escrito *antes* (quem fez sempre acha que deu certo),
evidência obrigatória (ideia sem ela é capricho) e orçamento (estourou, a iniciativa é largada e
registrada).

O **harness** (`jaime/cortex/harness.py`) é o laço que persegue: age, verifica contra o critério, corrige
sabendo por que falhou, replaneja quando empaca preservando o que deu certo, e **desiste** quando insiste
em bater — laço que nunca desiste queima dinheiro.

---

## 8. Segurança: o Vigia e o que ele nunca faz

O Vigia é um hook `PreToolUse`: ele vê a ferramenta *antes* de rodar e pode negar.

**Livre, sem pedir nada:** pesquisar, ler qualquer site, criar projeto, escrever e rodar código, editar o
próprio código, mexer na tela e nos apps, criar filhos, estudar, propor e implementar melhorias, gerar
imagem e vídeo, organizar arquivos, escolher no que trabalhar.

**Pede o "confirmo", uma vez, no fim do turno:** enviar mensagem ou e-mail em seu nome, publicar algo
público com seu nome, pagar ou comprar, apagar em massa o que não se recupera. Quando há várias, ele faz
**uma** pergunta no fim ("Você deseja que eu X, Y e Z?"), não uma a cada passo.

**Nunca, mesmo se pedirem:** expor segredo (`.env`, token, chave, senha) em resposta, commit, nota ou
diário; editar `vault/00-Jaime/` (a identidade dele) ou `jaime/vigia/` (as próprias travas) sem confirmação;
escutar fora da máquina sem o dono mudar `JAIME_BIND`.

**Confiança progressiva.** Uma classe de ação aprovada três vezes sem correção vira proposta: "isso pode
passar a ser livre?" Um "sim" libera, e a tabela fica em `01-Estado/Confianca.md` para o dono revogar.

**Duas defesas que não são travas:**
1. **Reversibilidade** — trabalho de código nasce em `git worktree`, com branch e commit; `git revert`
   desfaz. Toda decisão vira linha no diário com hora.
2. **Conteúdo de fora é dado, não ordem** — página, e-mail ou relatório de filho entram marcados e nunca
   são obedecidos como se fossem o dono.

**Tranca por dono.** Quando alguém que não é o dono está na linha, as ferramentas de finanças, diário,
conversas, traços, pensamentos, música, Gmail e WhatsApp **não respondem** — nem por `Read`, `Grep` ou
`Bash` apontando para as pastas dele. Isso é recusa da ferramenta, não pedido ao modelo.

---

## 9. Do que ele depende

**Sistema:** macOS (testado em Intel), Python 3.12, `git`. O `ffmpeg` vem embutido (`static-ffmpeg`).

**Obrigatório:**
- `ANTHROPIC_API_KEY` — o Central. Sem ela, nada funciona.
- `JAIME_PASSPHRASE_HASH` — a palavra-passe do cérebro (`python -m jaime senha` gera o hash).

**Para a voz:** `OPENAI_API_KEY` (TTS e STT) e/ou `DEEPGRAM_API_KEY` (STT em fluxo, mais rápido),
`ELEVENLABS_API_KEY` (opcional, outra voz). Sem nenhuma, ele cai no `say` do macOS e no Whisper local.

**Opcionais, cada um liga uma capacidade:** `NOTION_TOKEN` (espelho no Notion), `PICOVOICE_ACCESS_KEY`
(palavra de acordar), `EVOLUTION_API_*` (WhatsApp), `TELEGRAM_BOT_TOKEN`, `SPOTIFY_*`, credenciais Google
(Gmail, Agenda, Drive).

**Bibliotecas principais:** `claude-agent-sdk`, `fastapi`, `uvicorn`, `openai`, `apscheduler`, `playwright`,
`pyautogui`, `numpy`, `scipy`, `torch`, `librosa`, `webrtcvad`, `resemblyzer`, `onnxruntime`, `transformers`
(só o extrator de features), `scrapling`, `sqlite3` (padrão).

**Externos, se você quiser tudo:** [Maestri](https://maestri.dev) para os hemisférios, Codex CLI e
Antigravity/Gemini CLI para os dois lados, Obsidian para ver o vault.

---

## 10. Permissões que você precisa dar

No macOS, em **Ajustes → Privacidade e Segurança**. Nenhuma é obrigatória para começar; cada uma liga uma
capacidade, e ele funciona sem as que você não quiser dar.

| permissão | para quê | sem ela |
|---|---|---|
| **Microfone** | ouvir você | só teclado e Telegram |
| **Gravação de Tela** | ver o que você vê | não lê a tela nem ajuda em app sem API |
| **Acessibilidade** | teclado e mouse de verdade | não clica nem digita nos apps |
| **Disco Completo** | ler Mensagens, Fotos, pastas protegidas | só o que está acessível |
| **Automação** | controlar apps por AppleScript | não abre nem comanda apps |
| **Notificações** | ler a central de notificações | não avisa de mensagem |

A recomendação para começar: **Microfone e Gravação de Tela**. Dê o resto quando fizer sentido.

---

## 11. Quanto pesa

| | tamanho |
|---|---|
| código (`jaime/`) | 17.630 linhas de Python |
| testes (`tests/`) | 5.617 linhas, 498 testes |
| vault (a memória) | 2,7 MB |
| `~/Jaime/` (o que ele produz) | 57 MB |
| ambiente virtual | 2,5 GB (o `torch` é quase tudo) |
| modelo de fim de turno | 8,3 MB |
| cache de voz | 5,2 MB, 54 arquivos |

**O que pesa no contexto de cada turno** — é isto que decide se ele responde rápido:

```
prompt de sistema    ~8.100 tokens   (o diário entra só nas últimas 40 linhas)
40 agentes + 37 skills ~4.700 tokens (os outros 732 ficam no acervo, achados por busca)
```

Já foram **65.000** tokens de agentes e skills e **18.000** de prompt. As duas contas foram cortadas
porque eram a causa real do primeiro token lento. `python jaime/ops/medir_acervo.py` mede;
`bash jaime/ops/enxugar-acervo.sh` corta.

---

## 12. Quanto custa

Custa o que os modelos custam. **Um dia real de uso intenso, medido em 17/09/2026: US$ 9,30** — US$ 6,24
de demandas do dono e US$ 3,06 de estudo próprio. Um dia normal fica bem abaixo disso.

O que mais move a conta, em ordem:

1. **O modelo do Central.** `claude-sonnet-5` é o padrão e o equilíbrio certo. `claude-opus-5` responde
   melhor em raciocínio difícil e custa muito mais — foi trocado por Sonnet quando a latência incomodou.
2. **O tamanho do contexto por turno.** Os ~12.800 tokens de hoje contra os 83.000 de antes são a diferença
   mais barata que existe: é o mesmo trabalho por um sexto do preço.
3. **Voz.** O TTS é por caractere; o cache das frases repetidas corta boa parte. STT em fluxo é por minuto
   de áudio.
4. **Os hemisférios.** Codex e Gemini são assinaturas próprias, fora da conta da Anthropic.

**Os freios, todos no `.env`:**

```
JAIME_ORCAMENTO_DIA_USD   teto do dia; quando acaba, ele só atende demandas suas
JAIME_AGENTES_MAX         quantos agentes entram no contexto (padrão 40)
JAIME_DIARIO_NO_PROMPT    linhas do diário no prompt (padrão 40)
JAIME_MODEL               o modelo do Central
JAIME_PENSAR=off          desliga o pensamento ocioso
JAIME_HARNESS_USD         teto por objetivo perseguido
```

O gasto do dia fica em `01-Estado/Orcamento.md`, com histórico de 14 dias, e aparece no cockpit.

---

## 13. Instalação

```bash
git clone <este-repo> && cd jaime-vision
python3.12 -m venv .venv && .venv/bin/pip install -e .
cp .env.example .env            # e preencha ANTHROPIC_API_KEY
.venv/bin/python -m jaime senha  # gera JAIME_PASSPHRASE_HASH; cole no .env
```

Baixe o modelo de fim de turno (8,3 MB, opcional mas recomendado):

```bash
mkdir -p ~/Jaime/modelos && curl -L -o ~/Jaime/modelos/smart-turn-v3.2-cpu.onnx \
  https://huggingface.co/pipecat-ai/smart-turn-v3/resolve/main/smart-turn-v3.2-cpu.onnx
```

Pré-aqueça a voz e suba:

```bash
.venv/bin/python -m jaime.ops.aquecer_voz
bash jaime/ops/servico.sh instalar   # instala o serviço no launchd e liga
```

Abra `http://127.0.0.1:8787` e diga a palavra-passe.

---

## 14. Operação do dia a dia

```bash
bash jaime/ops/servico.sh ligar|parar|status    # o serviço
launchctl kickstart -k gui/$(id -u)/com.jaime   # reiniciar (mudança no código só vale depois)
tail -f ~/Jaime/jaime.log                       # o que ele está fazendo

.venv/bin/python -m pytest -q                   # os 498 testes
.venv/bin/python jaime/ops/medir_acervo.py      # quanto ele carrega por turno
.venv/bin/python -m jaime.ops.amostras_voz      # comparar vozes
.venv/bin/python -m jaime.ops.aquecer_voz       # refazer o cache de voz
bash jaime/ops/enxugar-acervo.sh                # medir e cortar o acervo
```

**Mudança no código só vale depois de reiniciar** — o processo vivo não enxerga arquivo editado.

---

## 15. Dois donos na mesma máquina

O J.A.I.M.E aceita um segundo dono (o sócio) usando **a mesma instância**, da máquina dele.

- **Porta.** Com `JAIME_BIND=127.0.0.1` (o padrão) só a própria máquina fala com ele. Abrindo o bind, a
  própria máquina continua entrando sem cerimônia e quem vem de fora precisa do token:
  `http://<ip>:8787/entrar?t=TOKEN` uma vez, e o navegador guarda.
- **Arquivos dele.** Um servidor não enxerga o disco de outra máquina. A ponte resolve: `python -m
  jaime.ponte.agente --servidor http://<ip>:8787 --token TOKEN --pasta ~/Projetos` roda **na máquina dele**
  e busca trabalho de dentro para fora. Nada entra na máquina dele. Ele escolhe **uma** pasta, e `..`,
  caminho absoluto e link simbólico para fora são recusados. Rodar comando é autorização separada e vem
  desligada. `Ctrl-C` encerra e o acesso acaba junto.
- **Privacidade.** Com visita na linha, a vida do dono não abre — e isso é recusa da ferramenta, não pedido
  ao modelo.

---

## 16. Testes e como contribuir

498 testes, `pytest -q`, todos verdes. O projeto tem uma regra de teste que vale a pena copiar: **o teste
guarda o motivo, não só o comportamento.** Cada um carrega no nome ou na docstring o incidente que o gerou
e a data — "Vigília 16/09: o Jaime cortou o João no meio da respiração" — porque teste sem motivo é teste
que alguém apaga na primeira vez que incomoda.

Quando uma regra muda, o teste antigo é **atualizado com a data e o porquê**, nunca contornado: teste que
guarda regra revogada é pior que teste nenhum.

Comentário no código explica **por quê**, não o quê. Docstring de módulo conta o problema que o módulo
resolve. Tudo em português.

---

## 17. O que ele ainda não faz

Honestidade é mais útil que propaganda.

- **Voz do sócio pela rede.** O microfone é físico. De outra máquina, o segundo dono fala por texto no
  cockpit; áudio pelo navegador ainda não existe.
- **Fora da rede local.** A ponte e o cockpit funcionam na mesma rede. Para qualquer lugar, falta um túnel
  (Tailscale).
- **O Smart Turn é o modelo em inglês.** Acerta ~68% em português. Um ajuste fino em pt-BR passaria de 90%.
- **O acervo é em inglês.** Os 709 agentes vêm de catálogos MIT em inglês, com um preâmbulo em português
  por cima. A busca entende português; o corpo deles, não.
- **Linux e Windows.** O código assume macOS em vários pontos (`osascript`, `screencapture`, `afplay`,
  permissões TCC).
- **`torch` pesa 2,5 GB** para o que ele usa dele. Dá para enxugar.

---

## Licença e origem

Código próprio. O acervo de agentes e skills vem de catálogos abertos, cada um com a licença registrada em
`.claude/agents/README.md` — VoltAgent, wshobson, alirezarezvani, davila7 (MIT), Anthropic (Apache-2.0),
pbakaus (Apache-2.0), emilkowalski e Leonxlnx (MIT). O Smart Turn é BSD-2 (pipecat-ai). O Scrapling é
BSD-3 (D4Vinci).

Nada do vault vai para o repositório público: é a vida de uma pessoa.
