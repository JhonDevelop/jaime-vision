"""Fase 6 — modo matemática do Air Canvas: expressão CONFIRMADA → AST simbólica própria → SymPy → verificação.

Regra de segurança do pacote: texto reconhecido (OCR/escrita no ar) nunca é avaliado como código Python.
`sympy.sympify`/`parse_expr` usam `eval` por baixo — por isso este módulo tem o PRÓPRIO tokenizador e parser
descendente (números, variáveis de uma letra, + − × ÷ ^, parênteses, =, sqrt/sin/cos/tan/log/exp, pi) e monta a
expressão SymPy nó a nó. O `solve` roda num PROCESSO separado com prazo: equação patológica não trava o Jaime.

Aceita LaTeX simples (\\frac{a}{b}, \\sqrt{x}, x^{2}, \\cdot, \\times, \\div, \\left( \\right)) — o que um reconhecedor de
escrita devolve e o João confirma visualmente antes."""
from __future__ import annotations
import multiprocessing as mp
import re
from dataclasses import dataclass, field

MAX_CHARS = 160
FUNCOES = {"sqrt", "sin", "cos", "tan", "log", "ln", "exp"}


class ErroMatematica(ValueError):
    pass


def de_latex(s: str) -> str:
    t = s.strip().strip("$")
    t = re.sub(r"\\left|\\right", "", t)
    for _ in range(6):                                            # frações/raízes aninhadas
        t2 = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"((\1)/(\2))", t)
        t2 = re.sub(r"\\sqrt\{([^{}]*)\}", r"sqrt(\1)", t2)
        if t2 == t:
            break
        t = t2
    t = re.sub(r"\^\{([^{}]*)\}", r"^(\1)", t)
    t = t.replace("\\cdot", "*").replace("\\times", "*").replace("\\div", "/").replace("\\pi", "pi")
    t = re.sub(r"\\(sin|cos|tan|log|ln|exp)", r"\1", t)
    t = t.replace("{", "(").replace("}", ")")
    resto = re.search(r"\\[a-zA-Z]+", t)
    if resto or "\\" in t:
        raise ErroMatematica(f"comando LaTeX não suportado: {resto.group(0) if resto else t}")
    return t


TOKEN = re.compile(r"\s*(?:(\d+(?:[.,]\d+)?)|([a-zA-Z]+)|(\*\*|[-+*/^()=×÷·]))")


def tokens(s: str) -> list[tuple[str, str]]:
    if len(s) > MAX_CHARS:
        raise ErroMatematica("expressão longa demais para o modo matemática")
    out, i = [], 0
    s = s.strip()
    while i < len(s):
        m = TOKEN.match(s, i)
        if not m or m.end() == i:
            raise ErroMatematica(f"caractere inesperado: {s[i]!r}")
        num, nome, op = m.groups()
        if num:
            out.append(("num", num.replace(",", ".")))
        elif nome:
            if nome in FUNCOES or nome == "pi":
                out.append(("nome", nome))
            else:
                out += [("var", c) for c in nome]                 # "xy" = x·y (variáveis de uma letra)
        else:
            out.append(("op", {"**": "^", "×": "*", "·": "*", "÷": "/"}.get(op, op)))
        i = m.end()
    # multiplicação implícita: 2x, x(…), )(, )x, 2sqrt(…)
    res = []
    for k, tok in enumerate(out):
        if res:
            a, b = res[-1], tok
            if (a[0] in ("num", "var") or a == ("op", ")") or (a[0] == "nome" and a[1] == "pi")) and \
               (b[0] in ("num", "var", "nome") or b == ("op", "(")):
                res.append(("op", "*"))
        res.append(tok)
    return res


class _Parser:
    """expr := termo (('+'|'-') termo)* ; termo := fator (('*'|'/') fator)* ; fator := ('-'|'+') fator | pot ;
    pot := atomo ('^' fator)? ; atomo := num | var | pi | func '(' expr ')' | '(' expr ')'"""
    def __init__(self, toks):
        import sympy as sp
        self.sp, self.t, self.i = sp, toks, 0
        self.potencias = 0

    def ver(self):
        return self.t[self.i] if self.i < len(self.t) else ("fim", "")

    def comer(self, esperado=None):
        tok = self.ver()
        if esperado and tok != esperado:
            raise ErroMatematica(f"esperava {esperado[1]!r}, veio {tok[1]!r}")
        self.i += 1
        return tok

    def expr(self):
        v = self.termo()
        while self.ver() in (("op", "+"), ("op", "-")):
            op = self.comer()[1]; d = self.termo()
            v = v + d if op == "+" else v - d
        return v

    def termo(self):
        v = self.fator()
        while self.ver() in (("op", "*"), ("op", "/")):
            op = self.comer()[1]; d = self.fator()
            v = v * d if op == "*" else v / d
        return v

    def fator(self):
        if self.ver() == ("op", "-"):
            self.comer(); return -self.fator()
        if self.ver() == ("op", "+"):
            self.comer(); return self.fator()
        return self.pot()

    def pot(self):
        base = self.atomo()
        if self.ver() == ("op", "^"):
            self.comer(); exp = self.fator()
            self.potencias += 1
            if self.potencias > 3:
                raise ErroMatematica("potências demais numa expressão só")
            if exp.is_number and abs(float(exp)) > 50:
                raise ErroMatematica("expoente grande demais")
            # sem avaliar: ((9^50)^50)^50 como número tem 10^5 dígitos — quem calcula é o processo com prazo
            return self.sp.Pow(base, exp, evaluate=False)
        return base

    def atomo(self):
        sp = self.sp
        tipo, v = self.ver()
        if tipo == "num":
            self.comer(); return sp.Rational(v)
        if tipo == "var":
            self.comer(); return sp.Symbol(v)
        if tipo == "nome":
            self.comer()
            if v == "pi":
                return sp.pi
            self.comer(("op", "(")); arg = self.expr(); self.comer(("op", ")"))
            return {"sqrt": sp.sqrt, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "log": sp.log, "ln": sp.log, "exp": sp.exp}[v](arg)
        if (tipo, v) == ("op", "("):
            self.comer(); e = self.expr(); self.comer(("op", ")")); return e
        raise ErroMatematica(f"não entendi a partir de {v!r}")


def analisar(texto: str):
    """Texto (ou LaTeX) → (lado_esq, lado_dir|None) em SymPy, sem eval."""
    t = de_latex(texto) if "\\" in texto or "{" in texto else texto
    lados = t.split("=")
    if len(lados) > 2:
        raise ErroMatematica("mais de um '='")
    exprs = []
    for lado in lados:
        p = _Parser(tokens(lado))
        e = p.expr()
        if p.ver()[0] != "fim":
            raise ErroMatematica(f"sobrou {p.ver()[1]!r}")
        exprs.append(e)
    return exprs[0], (exprs[1] if len(exprs) == 2 else None)


@dataclass
class Solucao:
    entrada: str
    latex: str
    tipo: str                           # equacao | expressao
    resultado: list[str] = field(default_factory=list)
    verificado: bool = False
    passos: list[str] = field(default_factory=list)
    erro: str = ""


def _trabalho(texto: str, fila) -> None:
    import sympy as sp
    try:
        esq, dir_ = analisar(texto)
        if dir_ is None:
            v = sp.simplify(esq)
            fila.put(Solucao(texto, sp.latex(esq), "expressao", [str(v)], True,
                             [f"simplifica: {sp.latex(esq)} = {sp.latex(v)}"] + ([f"≈ {sp.N(v, 8)}"] if v.is_number else [])))
            return
        eq = sp.Eq(esq, dir_)
        simbolos = sorted((esq - dir_).free_symbols, key=str)
        if not simbolos:
            ok = bool(sp.simplify(esq - dir_) == 0)
            fila.put(Solucao(texto, sp.latex(eq), "equacao", ["verdadeira" if ok else "falsa"], True, ["sem incógnita: só conferi"]))
            return
        alvo = sp.Symbol("x") if sp.Symbol("x") in simbolos else simbolos[0]
        sols = sp.solve(eq, alvo)
        passos = [f"equação: {sp.latex(eq)}", f"isolando {alvo}: forma {sp.latex(sp.expand(esq - dir_))} = 0"]
        verif = True
        for s in sols:
            resto = sp.simplify((esq - dir_).subs(alvo, s))
            ok = resto == 0
            verif &= ok
            passos.append(f"confere {alvo} = {sp.latex(s)}: substituindo dá {sp.latex(resto)} {'✓' if ok else '✗'}")
        fila.put(Solucao(texto, sp.latex(eq), "equacao", [f"{alvo} = {s}" for s in sols], verif and bool(sols), passos,
                         "" if sols else "sem solução encontrada"))
    except ErroMatematica as e:
        fila.put(Solucao(texto, "", "?", erro=str(e)))
    except Exception as e:
        fila.put(Solucao(texto, "", "?", erro=f"{type(e).__name__}: {str(e)[:120]}"))


def resolver(texto: str, prazo_s: float = 5.0) -> Solucao:
    """Resolve num processo separado com prazo. A análise sintática também roda antes, aqui, para recusar lixo
    sem nem abrir o processo."""
    analisar(texto)                                  # levanta ErroMatematica para entrada inválida (barato: potências não avaliadas)
    ctx = mp.get_context("spawn")
    fila = ctx.Queue()
    p = ctx.Process(target=_trabalho, args=(texto, fila), daemon=True)
    p.start(); p.join(prazo_s)
    if p.is_alive():
        p.kill(); p.join(1)
        return Solucao(texto, "", "?", erro=f"passou de {prazo_s:.0f} s — desisti (equação pesada demais para o modo rápido)")
    try:
        return fila.get(timeout=1)
    except Exception:
        return Solucao(texto, "", "?", erro="o processo de cálculo terminou sem resposta")
