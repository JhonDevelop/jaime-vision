"""A especificação e o crítico dela — nada é produzido sem spec validada.

Por que existe: o modelo escreve código depressa e escreve spec depressa também, e uma spec ruim produz
código que passa no teste errado. A etapa que salva é a do meio — alguém procurar buraco ANTES de existir
código, quando corrigir custa um parágrafo em vez de uma tarde.

Esta é a única trava do ciclo do agente, e é de QUALIDADE, não de permissão: não existe para impedir o
Jaime de fazer, existe para ele não fazer a coisa errada com capricho.

O crítico tem duas metades, e a ordem importa:

    MECÂNICA    o que dá para conferir por código: faltou seção, critério que não dá para verificar,
                nenhum caso de erro, entrada sem saída, número sem unidade. Isso é barato, é determinístico
                e pega a maioria dos buracos — então roda primeiro e nunca gasta modelo.
    DE JUÍZO    o que só um leitor pega: requisito ambíguo, suposição escondida, escopo que cresceu.
                Fica para o hemisfério direito, e só depois que a mecânica passou.

Uma spec com buraco volta com a lista do que falta, não com um "melhore". Crítica sem endereço é ruído."""
from __future__ import annotations
import re
from dataclasses import dataclass, field

SECOES = ("problema", "entrada", "saída", "erros", "aceite")
CABECALHOS = {
    "problema": re.compile(r"^#+\s*(problema|contexto|por ?qu[êe])", re.I | re.M),
    "entrada": re.compile(r"^#+\s*(entrada|entradas|input)", re.I | re.M),
    "saída": re.compile(r"^#+\s*(sa[íi]da|sa[íi]das|output|resultado)", re.I | re.M),
    "erros": re.compile(r"^#+\s*(erros?|casos? de erro|falhas?|o que pode dar errado)", re.I | re.M),
    "aceite": re.compile(r"^#+\s*(aceite|crit[ée]rios? de aceite|pronto quando|defini[çc][ãa]o de pronto)", re.I | re.M),
}
# Um critério de aceite serve quando dá para CONFERIR sem opinião. Estas palavras são conferíveis.
VERIFICAVEL = re.compile(
    r"\b(test[ea]|pytest|passa|retorna|devolve|responde|status|\d+\s*(ms|s|kb|mb|%|reais|r\$)|"
    r"existe|cont[ée]m|igual|menor|maior|abre|grava|salva|falha|erro|exce[çc][ãa]o|"
    r"arquivo|rota|endpoint|linha|campo)\b", re.I)
# E estas denunciam critério de opinião, que nunca fecha porque ninguém consegue discordar nem concordar.
OPINIAO = re.compile(r"\b(bom|boa|bonito|bonita|melhor|r[áa]pido o suficiente|adequad|satisfat[óo]ri|"
                     r"amig[áa]vel|intuitiv|limpo|elegante|robusto|escal[áa]vel)\b", re.I)
VAGO = re.compile(r"\b(etc|entre outros|e assim por diante|algo assim|mais ou menos|talvez|"
                  r"se poss[íi]vel|idealmente|deveria)\b", re.I)

MODELO = """# {titulo}

## Problema
{problema}

## Entrada
- (o que chega, de onde, em que formato)

## Saída
- (o que sai, para onde, em que formato)

## Erros
- (o que pode dar errado e o que acontece quando dá)

## Critérios de aceite
- (como CONFERIR que ficou pronto — teste que passa, arquivo que existe, rota que responde, número com unidade)
"""


@dataclass
class Falha:
    onde: str
    o_que: str
    como_arrumar: str

    def linha(self) -> str:
        return f"- [{self.onde}] {self.o_que} → {self.como_arrumar}"


@dataclass
class Parecer:
    falhas: list[Falha] = field(default_factory=list)

    @property
    def passou(self) -> bool:
        return not self.falhas

    def texto(self) -> str:
        if self.passou:
            return "PRONTO: a spec tem problema, entrada, saída, erros e critérios conferíveis."
        return ("A spec ainda tem buraco. Arrume isto antes de produzir:\n"
                + "\n".join(f.linha() for f in self.falhas))


def esqueleto(titulo: str, problema: str = "") -> str:
    """O papel em branco com as seções certas — mais rápido que lembrar quais são."""
    return MODELO.format(titulo=titulo.strip()[:100] or "Sem título",
                         problema=(problema.strip() or "(o que está errado hoje, e para quem isso dói)"))


def _itens(texto: str, cabecalho: re.Pattern) -> list[str]:
    """As linhas de lista que vêm logo depois de um cabeçalho, até o próximo cabeçalho."""
    m = cabecalho.search(texto)
    if not m:
        return []
    resto = texto[m.end():]
    fim = re.search(r"^#+\s", resto, re.M)
    bloco = resto[:fim.start()] if fim else resto
    return [l.strip(" -*\t") for l in bloco.splitlines() if l.strip().startswith(("-", "*"))
            and len(l.strip(" -*\t")) > 3]


def criticar(spec: str) -> Parecer:
    """A metade mecânica: o que dá para conferir por código, sem gastar modelo e sem depender de humor."""
    t = spec or ""
    p = Parecer()

    for nome in SECOES:
        if not CABECALHOS[nome].search(t):
            p.falhas.append(Falha(nome, "a seção não existe",
                                  f"escreva «## {nome.capitalize()}» e o conteúdo dela"))

    for nome in ("entrada", "saída", "erros", "aceite"):
        if CABECALHOS[nome].search(t) and not _itens(t, CABECALHOS[nome]):
            p.falhas.append(Falha(nome, "a seção está vazia",
                                  "liste pelo menos um item; seção com título e sem conteúdo engana"))

    aceites = _itens(t, CABECALHOS["aceite"])
    for a in aceites:
        if OPINIAO.search(a):
            p.falhas.append(Falha("aceite", f"«{a[:60]}» é opinião",
                                  "troque por algo que se confere: teste que passa, número com unidade, "
                                  "arquivo que existe"))
        elif not VERIFICAVEL.search(a):
            p.falhas.append(Falha("aceite", f"«{a[:60]}» não diz como conferir",
                                  "diga o que observar para saber que fechou"))

    if aceites and not any(re.search(r"\b(test[ea]|pytest)\b", a, re.I) for a in aceites):
        p.falhas.append(Falha("aceite", "nenhum critério é um teste",
                              "pelo menos um aceite tem que ser um teste que falharia hoje e passa depois"))

    for vago in set(m.group(0).lower() for m in VAGO.finditer(t)):
        p.falhas.append(Falha("texto", f"«{vago}» deixa o escopo aberto",
                              "diga exatamente o que entra e o que fica de fora"))

    entradas, saidas = _itens(t, CABECALHOS["entrada"]), _itens(t, CABECALHOS["saída"])
    if entradas and not saidas:
        p.falhas.append(Falha("saída", "tem entrada e não tem saída",
                              "o que essa coisa devolve? se não devolve nada, diga que efeito ela causa"))

    if len(t.strip()) < 220:
        p.falhas.append(Falha("texto", "a spec é curta demais para ser conferível",
                              "descreva o suficiente para outra pessoa implementar sem perguntar"))
    return p


def pedido_de_critica(spec: str) -> str:
    """O que mandar ao hemisfério direito DEPOIS que a mecânica passou — o que só um leitor pega."""
    return ("[spec] Leia esta especificação como quem vai ter que implementar e não pode perguntar nada. "
            "Aponte só o que um leitor pega e um verificador não: requisito ambíguo (duas leituras possíveis), "
            "suposição escondida, escopo que cresceu, caso de uso real que ficou de fora. "
            "Uma linha por buraco, com o endereço na spec. Sem buraco, responda só PRONTO.\n\n" + (spec or ""))
