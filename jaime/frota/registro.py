"""A matrícula da frota: qual máquina é de quem, e o que o J.A.I.M.E pode fazer em cada uma.

O pedido do João (17/09): «como fazer ele ter acesso a outros computadores da minha rede, que permitem ele
usar vários computadores se necessário, reconhecer os donos deles, e saber como mexer neles» — e, minutos
depois, o detalhe que resolve a parte difícil: «faça ele ler o nome do computador em que está conectado
para saber já de quem é o computador».

Esse detalhe é o coração daqui, e vale explicar por que:

A ponte antiga aceitava `--nome "Gabriel"` e acreditava. Isso não é reconhecer o dono, é repetir o que a
máquina disse. Se qualquer coisa que se conecta pode se chamar do que quiser, o nome do dono é enfeite — e
o pior tipo de enfeite, porque as permissões pendem dele.

Então inverte: **a máquina diz o hostname, e a matrícula diz o dono.** O hostname não é segredo e não é
prova por si só; a prova é o token, que só existe para aquele hostname (`token_da_maquina`, derivado do
segredo do servidor). Uma máquina não consegue se passar por outra porque não tem o token da outra. E o
dono, o nível e a pasta vêm da matrícula que o JOÃO escreveu — não de quem está pedindo.

Onde a matrícula mora: `01-Estado/Frota.md`, uma tabela Markdown no vault. É de propósito. O João edita à
mão, vê num relance quem está na frota e com qual nível, e tira uma máquina da frota apagando uma linha. Um
banco de dados aqui só esconderia a decisão mais importante da casa atrás de uma ferramenta.

Os três níveis, e a diferença entre eles é ALCANCE, não ação:

    leitor      lista e lê. Nada mais. Para uma máquina que ele só precisa consultar.
    operador    lê, escreve e roda comando — dentro da pasta aberta. O trabalho normal.
    dono        o mesmo, na casa inteira daquele usuário. Para as máquinas do próprio João.

O nível é conferido nos DOIS lados: aqui, para ele nem tentar e dizer ao João o porquê; e no agente da
outra máquina, que é quem manda de verdade — quem está na máquina decide o que sai dela."""
from __future__ import annotations
import hashlib, hmac, re
from dataclasses import dataclass

NOTA = "01-Estado/Frota.md"
NIVEIS = ("leitor", "operador", "dono")

# O que cada nível pode PEDIR. A diferença de alcance (pasta vs. casa inteira) é do agente, não daqui.
ACOES = {
    "leitor":   frozenset({"listar", "ler", "conhecer"}),
    "operador": frozenset({"listar", "ler", "escrever", "rodar", "conhecer"}),
    "dono":     frozenset({"listar", "ler", "escrever", "rodar", "conhecer"}),
}

_CABECALHO = ("| apelido | host | dono | nível | pasta | como mexer |\n"
              "|---|---|---|---|---|---|\n")
_SUFIXOS = (".local", ".lan", ".home", ".localdomain")


def normalizar_host(host: str) -> str:
    """«MacBook-Pro-de-Joao.local», «macbookprodejoao» e «MacBook Pro de Joao» viram a mesma coisa.

    Hostname de Mac na mão do usuário muda de cara sozinho: o Bonjour põe `.local`, o usuário troca
    maiúscula, o traço vira espaço na hora de digitar. Comparar a string crua faria a mesma máquina virar
    duas na matrícula, e aí o dono dela se perde."""
    h = (host or "").strip().lower()
    for s in _SUFIXOS:
        if h.endswith(s):
            h = h[: -len(s)]
    return re.sub(r"[^a-z0-9]", "", h)


def token_da_maquina(segredo: str, host: str) -> str:
    """O token daquela máquina, e só daquela.

    Derivado, não sorteado: não há lista de tokens para guardar, sincronizar ou vazar. Trocar o
    `JAIME_SERVER_TOKEN` invalida a frota inteira de uma vez — o botão de pânico é um só."""
    return hmac.new((segredo or "").encode(),
                    f"frota:{normalizar_host(host)}".encode(), hashlib.sha256).hexdigest()[:32]


def confere_token(segredo: str, host: str, oferecido: str) -> bool:
    """Comparação de tempo constante: token errado não deve demorar diferente de token quase certo."""
    return hmac.compare_digest(token_da_maquina(segredo, host), (oferecido or "").strip())


@dataclass
class NaFrota:
    """Uma linha da matrícula: uma máquina que o João já apresentou ao Jaime."""
    apelido: str
    host: str
    dono: str
    nivel: str = "operador"
    pasta: str = ""                  # vazio = a casa do usuário (só faz sentido no nível dono)
    notas: str = ""                  # nota do vault com o "como mexer nesta máquina"

    @property
    def chave(self) -> str:
        return normalizar_host(self.host)

    def pode(self, acao: str) -> bool:
        return acao in ACOES.get(self.nivel, ACOES["leitor"])

    def linha(self) -> str:
        return (f"| {self.apelido} | {self.host} | {self.dono} | {self.nivel} | "
                f"{self.pasta or '—'} | {self.notas or '—'} |")

    def __str__(self) -> str:
        onde = self.pasta or "a casa dele"
        return f"{self.apelido} ({self.host}) · do {self.dono} · {self.nivel} · {onde}"


class Registro:
    """Lê e escreve a matrícula da frota no vault."""

    def __init__(self, vault=None):
        self.vault = vault

    # ── ler ──────────────────────────────────────────────────────────────
    def todas(self) -> list[NaFrota]:
        txt = ""
        try:
            txt = (self.vault.read(NOTA) if self.vault else "") or ""
        except Exception:
            return []
        saida, vistos = [], set()
        for ln in txt.splitlines():
            ln = ln.strip()
            if not ln.startswith("|") or ln.startswith("|---") or "---" in ln.replace(" ", "")[:8]:
                continue
            c = [x.strip() for x in ln.strip("|").split("|")]
            if len(c) < 4 or c[0].lower() in ("apelido", ""):
                continue
            nivel = c[3].lower()
            m = NaFrota(apelido=c[0], host=c[1], dono=c[2],
                        nivel=nivel if nivel in NIVEIS else "leitor",
                        pasta="" if len(c) < 5 or c[4] in ("—", "-", "") else c[4],
                        notas="" if len(c) < 6 or c[5] in ("—", "-", "") else c[5])
            if m.chave and m.chave not in vistos:
                vistos.add(m.chave); saida.append(m)
        return saida

    def por_host(self, host: str) -> NaFrota | None:
        """DE QUEM É esta máquina — a pergunta que o João fez.

        Exato no hostname normalizado primeiro. Só depois o apelido, porque é o que ele digita ou fala
        ('roda isso no mini'), e um apelido pode colidir com outro de propósito."""
        k = normalizar_host(host)
        if not k:
            return None
        todas = self.todas()
        for m in todas:
            if m.chave == k:
                return m
        for m in todas:
            if normalizar_host(m.apelido) == k:
                return m
        return None

    def quem_e(self, host: str) -> str:
        """Uma frase para ele dizer em voz. Máquina de fora é dita como de fora, sem fingir familiaridade."""
        m = self.por_host(host)
        if m is None:
            return (f"«{host}» não está na minha frota — não sei de quem é essa máquina, e por isso não "
                    f"mexo nela. Se for sua, me diga e eu cadastro.")
        return f"{host} é {'sua' if m.dono.startswith('João') else f'do {m.dono}'} — {m}."

    # ── escrever ─────────────────────────────────────────────────────────
    def cadastrar(self, apelido: str, host: str, dono: str, nivel: str = "operador",
                  pasta: str = "", notas: str = "") -> str:
        if not (apelido or "").strip() or not (host or "").strip() or not (dono or "").strip():
            return "faltou apelido, host ou dono"
        if nivel not in NIVEIS:
            return f"nível tem que ser um de {', '.join(NIVEIS)}"
        if nivel != "dono" and not (pasta or "").strip():
            # Nível abaixo de dono sem pasta seria a casa inteira com nome de pasta — o oposto do que
            # o nível promete. A checagem vive aqui, e não só na ferramenta, porque a matrícula é o que
            # sobra depois: quem lê a tabela tem de poder confiar nela.
            return "leitor e operador precisam de uma pasta: só o nível dono alcança a casa inteira"
        if self.vault is None:
            return "sem vault para guardar a matrícula"
        nova = NaFrota(apelido.strip(), host.strip(), dono.strip(), nivel, pasta.strip(), notas.strip())
        restantes = [m for m in self.todas() if m.chave != nova.chave]
        corpo = ["# Frota — as máquinas que eu alcanço", "",
                 "Uma linha por máquina. O **host** é o que a máquina diz de si (`hostname`) e é por ele que",
                 "eu descubro de quem ela é — não pelo que o agente se declara. Apagar a linha tira a máquina",
                 "da frota na hora. Níveis: `leitor` lê; `operador` lê, escreve e roda na pasta; `dono` o mesmo",
                 "na casa inteira.", "", _CABECALHO.rstrip("\n")]
        corpo += [m.linha() for m in sorted(restantes + [nova], key=lambda m: m.apelido.lower())]
        try:
            self.vault.write(NOTA, "\n".join(corpo) + "\n")
        except Exception as e:
            return f"não consegui escrever a matrícula: {type(e).__name__}"
        return f"cadastrada: {nova}"

    def remover(self, host: str) -> str:
        m = self.por_host(host)
        if m is None:
            return f"«{host}» não estava na frota"
        restantes = [x for x in self.todas() if x.chave != m.chave]
        corpo = ["# Frota — as máquinas que eu alcanço", "", _CABECALHO.rstrip("\n")]
        corpo += [x.linha() for x in restantes]
        try:
            self.vault.write(NOTA, "\n".join(corpo) + "\n")
        except Exception as e:
            return f"não consegui escrever a matrícula: {type(e).__name__}"
        return f"fora da frota: {m.apelido} ({m.host}). O token dela para de valer no próximo registro."
