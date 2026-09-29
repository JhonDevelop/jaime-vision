"""Comandos de voz dos blocos, resolvidos SEM modelo (milissegundos): abrir/fechar/ler/listar blocos, salvar e
abrir layouts, desfazer. Só frases com a palavra "bloco(s)" ou "layout" entram aqui — "abre finanças" continua
indo ao cérebro como sempre. O que não for comando direto (ex.: "cria um bloco comparando a BUB e a Oldsen") vai
ao modelo com a lista de blocos abertos no contexto, e ele usa as ferramentas `mcp__blocos__*`."""
from __future__ import annotations
import re, unicodedata


def _n(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")).strip(" .!?")


ABRIR = re.compile(r"\b(abre|abra|abrir|mostra|mostre|mostrar|coloca|coloque|poe|ponha)\b (?:o |um |uns |os )?blocos? (?:de |da |do |das |dos |com )?(?P<nome>.+)$")
FECHAR_TODOS = re.compile(r"\b(fecha|feche|fechar|tira|tire|limpa|limpe)\b (?:todos )?(?:os )?blocos\b|\b(fecha|feche|limpa) tudo\b")
FECHAR = re.compile(r"\b(fecha|feche|fechar|tira|tire)\b (?:o |esse |este |aquele )?bloco(?: de| da| do| das| dos)? ?(?P<nome>.*)$")
LER = re.compile(r"\b(le|leia|ler|fala|diz)\b (?:o |pra mim o )?bloco (?:de |da |do )?(?P<nome>.+)$")
LISTAR = re.compile(r"\b(quais|que) blocos\b|\blista (?:os )?blocos\b")
SALVAR = re.compile(r"\b(salva|salve|guarda|guarde)\b (?:esse |este |o |os )?(?:layout|blocos) (?:como|de|com o nome) (?P<nome>[\w -]{2,30})$")
ABRIR_LAYOUT = re.compile(r"\b(abre|abra|carrega|volta)\b (?:o |pro |para o )?layout (?:de |da |do )?(?P<nome>[\w -]{2,30})$")
DESFAZER = re.compile(r"\bdesfa(z|ca|zer)\b.*\bbloco")


def _achar(g, nome: str):
    """Bloco aberto pelo nome falado: id, título ou modelo."""
    n = _n(nome)
    if not n:
        return None
    for b in g.listar():
        if n in (_n(b.id), _n(b.titulo), _n(b.modelo or "")) or n in _n(b.titulo) or (b.modelo and _n(b.modelo) in n):
            return b
    return None


def comando(texto: str, g, modelos) -> str | None:
    """Frase → resposta curta (já executada) ou None (segue para o cérebro)."""
    t = _n(texto)
    t = re.sub(r"^(jaime|jarvis)[, ]+", "", t)
    if "bloco" not in t and "layout" not in t:
        return None
    if LISTAR.search(t):
        abertos = g.listar()
        return ("Abertos: " + ", ".join(b.titulo for b in abertos) + ".") if abertos else "Nenhum bloco aberto."
    if FECHAR_TODOS.search(t):
        n = len(g.fechar("todos", motivo="voz"))
        return f"Fechei {n} bloco{'s' if n != 1 else ''}." if n else "Não havia bloco aberto."
    if DESFAZER.search(t):
        return g.desfazer().capitalize() + "."
    if (m := SALVAR.search(t)):
        n = g.salvar_layout(m.group("nome"))
        return f"Layout {m.group('nome').strip()} salvo com {n} bloco{'s' if n != 1 else ''}."
    if (m := ABRIR_LAYOUT.search(t)):
        try:
            ids = g.abrir_layout(m.group("nome"))
            return f"Layout {m.group('nome').strip()} aberto: {len(ids)} bloco{'s' if len(ids) != 1 else ''}."
        except KeyError as e:
            return str(e).strip("'\"")
    if (m := LER.search(t)):
        b = _achar(g, m.group("nome"))
        return g.ler(b.id) if b else None
    if (m := FECHAR.search(t)):
        nome = m.group("nome")
        b = _achar(g, nome) if nome else (g.listar()[-1] if len(g.listar()) == 1 else None)
        if b:
            g.fechar(b.id, motivo="voz")
            return f"Fechei {b.titulo}."
        return None if nome else "Qual bloco?"
    if (m := ABRIR.search(t)):
        nome = modelos.resolver_nome(m.group("nome"))
        if not nome:
            return None                                   # pedido de bloco novo: o cérebro compõe com mcp__blocos__abrir
        b = g.abrir(modelos.instanciar(nome), origem="joao")
        return f"{b.titulo} aberto."
    return None


def contexto(g) -> str:
    abertos = g.listar()
    if not abertos:
        return "blocos: nenhum aberto"
    return "blocos abertos: " + "; ".join(f"{b.titulo} (id {b.id}, {b.tipo})" for b in abertos[:12])
