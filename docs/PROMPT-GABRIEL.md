# Prompt para o Gabriel colar no Claude Code dele

Este arquivo tem **um prompt pronto**. O Gabriel abre o Claude Code na máquina dele, cola o bloco abaixo,
troca as duas coisas marcadas com `<< >>` e manda. O Claude Code dele faz a instalação, confere o que está
sendo autorizado e liga a ponte.

Por que passar pelo Claude Code em vez de rodar o `curl | sh` direto: o Claude Code **lê o instalador antes
de executar** e explica ao Gabriel, com as palavras dele, o que aquilo permite. Quem instala tem o direito
de saber o que instalou — e um agente conferindo é melhor que uma promessa num README.

O que o Gabriel precisa ter em mão, e só isso:

1. o **código do convite** (8 caracteres) que o João passou — vale 10 minutos;
2. a **pasta** que ele quer abrir para o Jaime (as worktrees dele, por exemplo `~/Projetos`).

---

## ✂️ Cole daqui para baixo

````text
Você vai me conectar ao J.A.I.M.E — o assistente autônomo do João Vitor Leal, meu sócio. Ele roda na
máquina dele (192.168.200.23:8787) e eu quero que ele alcance os arquivos e worktrees DESTA máquina, que
é minha. Meu nome é Gabriel Mello.

MEUS DADOS
  Código do convite : << COLE O CÓDIGO DE 8 CARACTERES AQUI >>
  Pasta que eu abro : << COLE O CAMINHO, ex.: ~/Projetos >>
  Servidor do João  : http://192.168.200.23:8787

REGRA QUE NÃO PODE SER QUEBRADA
Nesta máquina roda SOMENTE o agente da frota. NÃO instale o J.A.I.M.E completo, NÃO suba servidor, NÃO
ligue voz nem microfone aqui. Eu e o João trabalhamos na mesma sala e usamos o microfone e o alto-falante
DELE; um segundo assistente com voz criaria um loop de áudio entre as duas máquinas. Se em algum ponto o
caminho parecer exigir subir um Jaime completo aqui, PARE e me diga — é sinal de que algo está errado.

FAÇA NESTA ORDEM, e me mostre o resultado de cada passo:

1. CONFIRA A REDE E A MÁQUINA
   - rode `hostname` e me mostre o resultado (o João precisa que ele bata com o cadastro dele);
   - rode `curl -sS -o /dev/null -w '%{http_code}\n' http://192.168.200.23:8787/hud/estado` para ver se eu
     alcanço a máquina dele. Se não alcançar, pare e me diga: provavelmente estamos em redes diferentes;
   - confirme que existe `python3` aqui.

2. BAIXE O INSTALADOR SEM EXECUTAR, E ME EXPLIQUE
   - `curl -fsSL 'http://192.168.200.23:8787/frota/instalar?c=CODIGO' -o /tmp/jaime-frota-instalar.sh`
     (troque CODIGO pelo meu código acima);
   - LEIA o arquivo e me diga, em português claro e em no máximo 8 linhas:
       · com que apelido e como dono de quem esta máquina entraria;
       · qual NÍVEL foi definido para mim (leitor / operador / dono) e o que esse nível permite;
       · qual pasta exatamente ficaria alcançável;
       · se ele abre alguma porta nesta máquina, ou instala algo que suba no boot;
       · qualquer coisa no script que você considere fora do combinado acima.
   - Se o download devolver "Convite inválido ou expirado", pare: eu peço outro código ao João.

3. ESPERE MEU "OK"
   Não execute nada antes de eu confirmar. Se o nível vier como `dono`, me avise em destaque — eu quero
   `operador` numa pasta, não a casa inteira.

4. INSTALE E LIGUE
   - rode `sh /tmp/jaime-frota-instalar.sh`;
   - ele vai perguntar se eu autorizo: responda `sim`;
   - quando perguntar se deve subir junto com o computador, responda `não` — eu prefiro ligar quando eu
     quiser emprestar a máquina;
   - confirme comigo que apareceu a linha de registro aceito e "Esperando trabalho…".

5. ME DEIXE O BÁSICO ANOTADO
   Escreva em `~/.jaime-frota/COMO-USAR.md` um resumo curto com: como religar
   (`sh ~/.jaime-frota/ligar.sh`), como encerrar (Ctrl-C), como apagar tudo
   (`rm -rf ~/.jaime-frota`), e a frase que eu falo para o Jaime me reconhecer no microfone do João
   ("Jaime, sou o Gabriel"). Não escreva o token neste arquivo.

LIMITES QUE EU QUERO QUE VOCÊ RESPEITE E CONFIRA
  - não me peça senha nenhuma, e não coloque senha, token ou chave em nenhum arquivo que você criar;
  - não toque em ~/.ssh, ~/.aws, ~/.gnupg, chaveiro, .env ou qualquer credencial minha;
  - não instale nada além do que o instalador do João traz (o agente e a configuração dele);
  - não rode `sudo`;
  - se qualquer passo falhar duas vezes, pare e me explique o que aconteceu em vez de tentar variações.

No fim, me diga em duas frases o que ficou ligado e o que o Jaime passa a poder fazer nesta máquina.
````

## ✂️ Cole até aqui

---

## Depois que ligar

- **Falar com ele:** pelo microfone do João, na sala. Diga uma vez «Jaime, sou o Gabriel».
- **Pedir coisa da sua máquina:** vale nomear, para não haver dúvida — «roda os testes na minha máquina»,
  «lê o `README` no gabriel».
- **Encerrar:** `Ctrl-C` no terminal do agente. O acesso acaba na hora.
- **Religar:** `sh ~/.jaime-frota/ligar.sh`.

O que ele **nunca** faz aqui, independente de configuração: sair da pasta que você abriu (atalho que aponta
para fora é recusado nesta máquina, antes de qualquer leitura), tocar em chave de ssh, `.env` ou chaveiro,
abrir porta, ou dar `git push` sem confirmação.

O documento completo do desenho — por que um Jaime só, o que roda onde, e a parte que cabe ao João — está em
`docs/FROTA-GABRIEL.md`.
