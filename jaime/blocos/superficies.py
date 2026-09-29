"""Superfícies: onde um bloco aparece, e como ele se adapta a cada uma.

Uma superfície declara CAPACIDADES (tela? de que tamanho? cores? gráfico? 3D? voz? toque? HTML?) e o servidor
adapta cada bloco a elas antes de mandar — o cliente nunca recebe o que não sabe mostrar. Os perfis prontos:

| perfil    | exemplo                                   | o que recebe                                        |
|-----------|-------------------------------------------|-----------------------------------------------------|
| cockpit   | HUD web no Mac/Windows                    | tudo (html em iframe sandbox)                       |
| janela    | janela nativa (tkinter), sem navegador    | tudo menos html (usa o alternativo)                 |
| terminal  | cliente de texto                          | texto; gráfico vira sparkline; tabela recortada     |
| oculos    | óculos com display pequeno (HUD monocular)| 3 blocos por prioridade, 4 linhas cada, sem tabela  |
| visor     | headset de realidade mista (AR/VR)        | tudo + posição 3D; html → alternativo               |
| falante   | caixa de som / fone / carro               | só a FALA: um resumo curto de cada bloco            |

Um óculos novo, um relógio, um painel no carro: basta declarar capacidades no handshake (protocolo.py).
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict, replace
from .modelo import Bloco

SPARK = "▁▂▃▄▅▆▇█"


@dataclass(frozen=True)
class Capacidades:
    visual: bool = True
    largura: int = 1280            # pontos lógicos da área útil
    altura: int = 800
    linhas_max: int = 40           # linhas de texto por bloco que cabem
    blocos_max: int = 24           # quantos blocos ao mesmo tempo
    cores: bool = True
    graficos: bool = True          # desenha gráfico de verdade (senão: sparkline/resumo)
    tabelas: bool = True
    grafos: bool = True
    html: bool = False
    imagens: bool = True
    tres_d: bool = False
    voz: bool = False              # fala resumos (tem alto-falante/TTS)
    entrada: tuple[str, ...] = ("clique",)   # clique | toque | voz | gesto | teclado
    confiavel: bool = True         # superfície do dono (pode receber bloco privado com o cérebro aberto)

    def to_dict(self) -> dict:
        d = asdict(self); d["entrada"] = list(self.entrada); return d


PERFIS: dict[str, Capacidades] = {
    "cockpit": Capacidades(html=True, entrada=("clique", "teclado", "voz", "gesto")),
    "janela": Capacidades(largura=900, altura=700, entrada=("clique", "teclado")),
    "terminal": Capacidades(largura=100, altura=40, linhas_max=14, graficos=False, grafos=False, imagens=False, cores=True,
                            entrada=("teclado",)),
    "oculos": Capacidades(largura=640, altura=400, linhas_max=4, blocos_max=3, graficos=False, tabelas=False, grafos=False,
                          imagens=False, voz=True, entrada=("voz", "toque")),
    "visor": Capacidades(largura=1920, altura=1080, tres_d=True, voz=True, entrada=("gesto", "voz", "olhar")),
    "falante": Capacidades(visual=False, linhas_max=0, blocos_max=24, graficos=False, tabelas=False, grafos=False,
                           imagens=False, voz=True, entrada=("voz",)),
}


def capacidades_de(perfil: str, extra: dict | None = None) -> Capacidades:
    """Perfil pronto + o que o cliente declarou (o cliente só pode RESTRINGIR segurança, nunca se promover a confiável)."""
    base = PERFIS.get(perfil, PERFIS["janela"])
    if not extra:
        return base
    ok = {k: v for k, v in extra.items() if k in Capacidades.__dataclass_fields__ and k != "confiavel"}
    if "entrada" in ok:
        ok["entrada"] = tuple(str(x) for x in ok["entrada"])[:6]
    for k in ("largura", "altura", "linhas_max", "blocos_max"):
        if k in ok:
            try:
                ok[k] = max(0, min(8192, int(ok[k])))
            except (TypeError, ValueError):
                ok.pop(k)
    for k in ("visual", "cores", "graficos", "tabelas", "grafos", "html", "imagens", "tres_d", "voz"):
        if k in ok:
            ok[k] = bool(ok[k])
    caps = replace(base, **ok)
    if extra.get("confiavel") is False:
        caps = replace(caps, confiavel=False)
    return caps


# ── texto: a base de toda degradação ─────────────────────────────────────────
def _fmt(v: float) -> str:
    if abs(v) >= 1000:
        return f"{v:,.0f}".replace(",", ".")
    return f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def sparkline(ys: list[float]) -> str:
    if not ys:
        return ""
    lo, hi = min(ys), max(ys)
    if hi == lo:
        return SPARK[3] * len(ys)
    return "".join(SPARK[int((y - lo) / (hi - lo) * (len(SPARK) - 1))] for y in ys)


def linhas_texto(b: Bloco, largura: int = 80, maximo: int = 40) -> list[str]:
    """O bloco como linhas de texto puro — é o que o terminal mostra e o que óculos pequenos recebem."""
    c, t = b.conteudo, b.tipo
    out: list[str] = []
    if t == "texto":
        for par in c.get("texto", "").splitlines() or [""]:
            while len(par) > largura:
                corte = par.rfind(" ", 0, largura)
                corte = corte if corte > largura // 2 else largura
                out.append(par[:corte]); par = par[corte:].lstrip()
            out.append(par)
    elif t == "lista":
        for i, it in enumerate(c.get("itens", []), 1):
            marca = f"{i}." if c.get("ordenada") else ("✓" if it.get("feito") else "•")
            out.append(f"{marca} {it['texto']}" + (f" — {it['detalhe']}" if it.get("detalhe") else ""))
    elif t == "tabela":
        cols, linhas = c.get("colunas", []), c.get("linhas", [])
        larg = [min(18, max([len(str(x)) for x in [col] + [ln[i] if i < len(ln) else "" for ln in linhas]] or [1]))
                for i, col in enumerate(cols)]
        cel = lambda ln: " │ ".join(str(ln[i] if i < len(ln) else "")[:larg[i]].ljust(larg[i]) for i in range(len(cols)))
        out.append(cel(cols)); out.append("─┼─".join("─" * w for w in larg))
        out += [cel(ln) for ln in linhas]
    elif t == "metricas":
        for m in c.get("itens", []):
            var = m.get("variacao")
            seta = "" if var is None else (f" ↑{_fmt(var)}%" if var > 0 else f" ↓{_fmt(abs(var))}%" if var < 0 else " =")
            out.append(f"{m['rotulo']}: {m['valor']}{(' ' + m['unidade']) if m.get('unidade') else ''}{seta}")
    elif t == "grafico":
        for s in c.get("series", []):
            ys = [p["y"] for p in s["pontos"]]
            if ys:
                out.append(f"{s['nome'] or 'série'} {sparkline(ys[-min(len(ys), max(8, largura - 30)):])} "
                           f"{_fmt(ys[-1])}{(' ' + c['unidade']) if c.get('unidade') else ''} (mín {_fmt(min(ys))}, máx {_fmt(max(ys))})")
    elif t == "grafo":
        rot = {n["id"]: n["rotulo"] for n in c.get("nos", [])}
        out += [f"{rot.get(a['de'], a['de'])} → {rot.get(a['para'], a['para'])}" + (f" ({a['rotulo']})" if a.get("rotulo") else "")
                for a in c.get("arestas", [])] or [", ".join(rot.values())]
    elif t == "status":
        icone = {"ok": "●", "atencao": "▲", "ruim": "■"}.get(c.get("estado"), "●")
        out.append(f"{icone} {c.get('estado', '')}: {c.get('texto', '')}")
    elif t == "progresso":
        n = 20; v = c.get("valor", 0.0)
        out.append("█" * int(v * n) + "░" * (n - int(v * n)) + f" {int(v * 100)}% {c.get('texto', '')}".rstrip())
    elif t == "acoes":
        if c.get("texto"):
            out.append(c["texto"])
        out += [f"[{i}] {bt['rotulo']}" for i, bt in enumerate(c.get("botoes", []), 1)]
    elif t == "imagem":
        out.append(f"(imagem) {c.get('legenda') or ''}".strip())
    elif t == "html":
        out.append(c.get("alternativo") or "(conteúdo visual — abra no cockpit)")
    if len(out) > maximo:
        resto = len(out) - (maximo - 1)
        out = out[:maximo - 1] + [f"… +{resto} linha(s)"]
    return [ln[:largura] for ln in out]


def resumo_falado(b: Bloco) -> str:
    """O bloco em UMA ou duas frases faladas (sem ler tabela linha a linha, sem símbolos)."""
    c, t = b.conteudo, b.tipo
    tit = b.titulo
    if t == "texto":
        frases = [f for f in c.get("texto", "").replace("\n", " ").split(". ") if f.strip()]
        return f"{tit}: " + ". ".join(frases[:2]).strip().rstrip(".") + "."
    if t == "lista":
        itens = [i["texto"] for i in c.get("itens", []) if not i.get("feito")]
        if not itens:
            return f"{tit}: nada pendente."
        return f"{tit}: {len(itens)} {'item' if len(itens) == 1 else 'itens'}. " + (f"Primeiro: {itens[0]}." if itens else "")
    if t == "tabela":
        return f"{tit}: tabela com {len(c.get('linhas', []))} linhas. Está na tela."
    if t == "metricas":
        partes = [f"{m['rotulo']} {m['valor']}{(' ' + m['unidade']) if m.get('unidade') else ''}" for m in c.get("itens", [])[:3]]
        return f"{tit}: " + ", ".join(partes) + "."
    if t == "grafico":
        s = next((s for s in c.get("series", []) if s["pontos"]), None)
        if not s:
            return f"{tit}: sem dados."
        ys = [p["y"] for p in s["pontos"]]
        tend = "subindo" if ys[-1] > ys[0] else "caindo" if ys[-1] < ys[0] else "estável"
        return f"{tit}: {tend}, último valor {_fmt(ys[-1])}{(' ' + c['unidade']) if c.get('unidade') else ''}."
    if t == "status":
        return f"{tit}: {c.get('texto') or c.get('estado')}."
    if t == "progresso":
        return f"{tit}: {int(c.get('valor', 0) * 100)} por cento."
    if t == "acoes":
        return f"{tit}: " + (c.get("texto") or "") + " Opções: " + ", ".join(bt["rotulo"] for bt in c.get("botoes", [])) + "."
    if t == "grafo":
        return f"{tit}: {len(c.get('nos', []))} peças e {len(c.get('arestas', []))} ligações."
    if t == "html":
        return f"{tit}: {c.get('alternativo') or 'está na tela'}."
    return f"{tit}."


# ── adaptação ────────────────────────────────────────────────────────────────
def pode_ver(b: Bloco, caps: Capacidades, dono_ok: bool) -> bool:
    if b.privado and not (caps.confiavel and dono_ok):
        return False
    return True


def adaptar(b: Bloco, caps: Capacidades, perfil: str = "") -> dict:
    """O que ESTA superfície recebe deste bloco. Sempre traz `linhas` (texto) e `fala`; traz `conteudo` completo só
    se a superfície desenha aquele tipo. Nunca devolve html para quem não é web."""
    d = {"id": b.id, "tipo": b.tipo, "titulo": b.titulo, "prioridade": b.prioridade, "versao": b.versao,
         "privado": b.privado, "atualizado": round(b.atualizado, 3), "fonte": b.fonte}
    if caps.voz:
        d["fala"] = resumo_falado(b)
    if not caps.visual:
        return d
    larg_txt = max(20, min(120, caps.largura // (8 if caps.largura > 200 else 1)))
    d["linhas"] = linhas_texto(b, larg_txt, max(1, caps.linhas_max))
    desenha = {"grafico": caps.graficos, "tabela": caps.tabelas, "grafo": caps.grafos, "imagem": caps.imagens,
               "html": caps.html}.get(b.tipo, True)
    if desenha and caps.linhas_max >= 6:
        d["conteudo"] = b.conteudo
    a = b.ancoragem
    anc = {"x": a.x, "y": a.y, "largura": a.largura, "altura": a.altura, "display_id": a.display_id}
    if caps.tres_d and a.pos3d:
        anc["pos3d"] = list(a.pos3d)
    d["ancoragem"] = {k: v for k, v in anc.items() if v is not None}
    return d


def selecionar(blocos: list[Bloco], caps: Capacidades, perfil: str, dono_ok: bool) -> list[Bloco]:
    """Quais blocos esta superfície mostra: filtra privacidade e ancoragem por superfície, e corta pelos
    `blocos_max` de maior prioridade (os mais recentes desempatam)."""
    vis = [b for b in blocos if pode_ver(b, caps, dono_ok) and (not b.ancoragem.superficie or b.ancoragem.superficie == perfil)]
    vis.sort(key=lambda b: (-b.prioridade, -b.atualizado))
    return vis[:caps.blocos_max]
