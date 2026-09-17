"""Curiosidade sobre quem fala com o João — e a decisão de avisar ou não.

O pedido dele (17/09): «se aquela pessoa me manda mensagens constantemente, então ele deve querer saber
quem é e desenvolver curiosidade, para me alertar sobre, criar memórias sobre aquela pessoa e o que ela
significa para mim».

O problema que isso resolve: hoje o filtro de notificação é uma regra fixa — contato salvo passa, número
desconhecido não. Regra fixa erra dos dois lados. O contato salvo que manda meme às onze da noite vira
alerta; o número novo do cliente que está fechando contrato não vira. O que falta não é uma regra melhor,
é o Jaime SABER quem é a pessoa.

Então ele aprende observando, como uma pessoa aprenderia:

    CONTA       quem fala, quantas vezes, em que horários, com que assunto. Frequência é o primeiro sinal
                de importância, e é grátis de medir.
    ESTRANHA    alguém que aparece muito e sobre quem ele não sabe nada é uma LACUNA — não um intruso.
                Isso vira curiosidade, e curiosidade vira UMA pergunta ao João. Uma, não um interrogatório.
    GUARDA      a resposta vira nó e relação no grafo, com evidência e data. Depois disso ele sabe quem é.
    DECIDE      com o grafo na mão, avisar deixa de ser regra e vira juízo: quem é essa pessoa para o João,
                o que costuma tratar, e se o que chegou agora foge do padrão dela.

O limite, que é o mesmo do resto da casa: ele nunca inventa fato sobre gente da vida do João, nunca guarda
segredo, e pergunta UMA coisa de cada vez — porque o João odeia responder duas vezes e odeia ser
interrogado por um programa."""
from __future__ import annotations
import re, time
from dataclasses import dataclass, field
from datetime import datetime

# Quantas mensagens até ele começar a se perguntar quem é. Uma mensagem é ruído; cinco é alguém presente
# na vida do João, e não saber quem é vira um buraco que atrapalha a decisão de avisar.
CURIOSO_A_PARTIR_DE = 5
# Quantas vezes ele pode perguntar sobre a MESMA pessoa antes de desistir e conviver com a dúvida.
PERGUNTAS_POR_PESSOA = 2
# Assunto que sempre merece o João saber, mesmo de quem ele não conhece.
# Sem \b no fim: são RADICAIS. "intima" tem que casar com "intimação", e o \b barrava, porque o ç conta
# como letra — o teste pegou exatamente isso.
URGENTE_RX = re.compile(
    r"\b(urgente|emerg[êe]nc|hospital|acidente|pol[íi]cia|vazou|invad|fraude|golpe|"
    r"contrato|assinatur|prazo|vence|pagamento|boleto|processo|intima|not[ií]fica)", re.I)
# E o que quase nunca merece interromper.
RUIDO_RX = re.compile(r"\b(bom dia|boa noite|kkk+|rs+|haha|meme|figurinha|corrente|promo[çc][ãa]o|"
                      r"desconto|cupom|sorteio|voc[êe] ganhou|clique aqui)\b", re.I)


@dataclass
class Remetente:
    """O que ele foi observando sobre quem fala com o João."""
    nome: str
    mensagens: int = 0
    primeira: float = field(default_factory=time.time)
    ultima: float = field(default_factory=time.time)
    horas: list[int] = field(default_factory=list)
    assuntos: list[str] = field(default_factory=list)
    perguntas_feitas: int = 0

    @property
    def frequente(self) -> bool:
        return self.mensagens >= CURIOSO_A_PARTIR_DE

    @property
    def hora_tipica(self) -> str:
        if not self.horas:
            return ""
        h = max(set(self.horas), key=self.horas.count)
        return "de madrugada" if h < 6 else "de manhã" if h < 12 else "de tarde" if h < 18 else "de noite"

    def resumo(self) -> str:
        dias = max(1, int((self.ultima - self.primeira) / 86400))
        return (f"{self.nome}: {self.mensagens} mensagens em {dias} dia(s)"
                + (f", quase sempre {self.hora_tipica}" if self.hora_tipica else ""))


class Curiosidade:
    """Observa quem fala com o João, estranha o que não conhece, e decide o que merece interromper."""

    def __init__(self, relacoes=None):
        self.relacoes = relacoes
        self.remetentes: dict[str, Remetente] = {}

    # ── contar ───────────────────────────────────────────────────────────
    def ouviu(self, de: str, texto: str = "", quando: float | None = None) -> Remetente:
        nome = (de or "").strip() or "desconhecido"
        r = self.remetentes.get(nome)
        t = quando or time.time()
        if r is None:
            r = self.remetentes[nome] = Remetente(nome, primeira=t)
        r.mensagens += 1
        r.ultima = t
        r.horas.append(datetime.fromtimestamp(t).hour)
        if texto:
            r.assuntos.append(texto[:80])
            r.assuntos[:] = r.assuntos[-10:]
        return r

    # ── estranhar: o que ele não sabe vira UMA pergunta ──────────────────
    def conhece(self, nome: str) -> bool:
        if self.relacoes is None:
            return False
        try:
            return self.relacoes.quem_e(nome) is not None
        except Exception:
            return False

    def curiosidade(self, nome: str) -> str:
        """A pergunta que ele faria ao João sobre essa pessoa. Vazio quando não há o que perguntar."""
        r = self.remetentes.get((nome or "").strip())
        if r is None or not r.frequente or self.conhece(r.nome):
            return ""
        if r.perguntas_feitas >= PERGUNTAS_POR_PESSOA:
            return ""                       # já perguntei duas vezes; conviver com a dúvida é melhor que insistir
        r.perguntas_feitas += 1
        quando = f", quase sempre {r.hora_tipica}" if r.hora_tipica else ""
        return (f"{r.nome} te mandou {r.mensagens} mensagens{quando} e eu não sei quem é. "
                f"Quem é essa pessoa para você?")

    def aprendi(self, nome: str, quem_e: str, relacao: str = "conhece") -> str:
        """A resposta do João vira memória de verdade: nó, relação, evidência e data."""
        nome = (nome or "").strip()
        if not nome or not (quem_e or "").strip():
            return "faltou dizer quem é"
        if self.relacoes is None:
            return "sem grafo para guardar"
        r = self.remetentes.get(nome)
        evidencia = (f"o João contou; {r.mensagens} mensagens observadas" if r else "o João contou")
        try:
            self.relacoes.lembrar_pessoa(nome, evidencia=evidencia)
            self.relacoes.fato(nome, "quem_e", quem_e.strip()[:160], evidencia=evidencia)
            if relacao and relacao != "conhece":
                self.relacoes.ligar("João", nome, relacao, evidencia=evidencia)
        except Exception as e:
            return f"não consegui guardar: {type(e).__name__}"
        return f"Anotei: {nome} — {quem_e.strip()[:80]}."

    # ── decidir: avisar é juízo, não regra fixa ──────────────────────────
    def vale_avisar(self, de: str, texto: str = "") -> tuple[bool, str]:
        """Interromper o João por causa disto? Devolve (sim/não, o porquê em uma frase).

        A ordem importa: urgência de conteúdo ganha de tudo, inclusive de desconhecido; ruído perde de
        tudo, inclusive de gente próxima. No meio, quem decide é o que ele SABE da pessoa."""
        t = (texto or "").strip()
        nome = (de or "").strip() or "desconhecido"
        if URGENTE_RX.search(t):
            return True, "o assunto não espera"
        if RUIDO_RX.search(t) and not URGENTE_RX.search(t):
            return False, "é conversa fiada"
        if self.conhece(nome):
            return True, f"é {nome}, e eu sei quem é"
        r = self.remetentes.get(nome)
        if r and r.frequente:
            return True, f"{nome} fala com você toda hora e eu ainda não sei quem é"
        return False, f"não conheço {nome} e não parece urgente"

    # ── o que ele sabe, para o prompt e para o cockpit ───────────────────
    def contexto(self, limite: int = 6) -> str:
        if not self.remetentes:
            return ""
        vivos = sorted(self.remetentes.values(), key=lambda r: -r.mensagens)[:limite]
        linhas = []
        for r in vivos:
            sei = "conheço" if self.conhece(r.nome) else "NÃO sei quem é"
            linhas.append(f"- {r.resumo()} — {sei}")
        return "\n".join(linhas)
