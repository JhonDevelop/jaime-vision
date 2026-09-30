"""Bloco de interface — a unidade do que o J.A.I.M.E mostra, independente de ONDE vai aparecer.

Um bloco diz O QUE mostrar (tipo + conteúdo estruturado), nunca COMO desenhar: o cockpit web, uma janela nativa,
o terminal, óculos, um visor de realidade mista ou um fone de ouvido recebem o mesmo bloco e cada um o desenha (ou
fala) do seu jeito, pelas próprias capacidades (`superficies.py`). É isso que deixa a interface dele independente
da web: a web vira só mais um cliente.

Todo bloco que entra passa por `validar()` — inclusive (principalmente) os que o próprio modelo compõe: tipo
conhecido, conteúdo no formato do tipo, textos e listas com limite, nada de script. Bloco inválido não quebra a
tela: é consertado quando dá (truncar, converter) ou recusado com o motivo.
"""
from __future__ import annotations
import re, time
from dataclasses import dataclass, field, asdict
from typing import Any
from uuid import uuid4

VERSAO_ESQUEMA = 1
TIPOS = ("texto", "lista", "tabela", "metricas", "grafico", "grafo", "status", "acoes", "imagem", "html", "progresso")
MAX_TEXTO, MAX_ITENS, MAX_LINHAS, MAX_COLUNAS, MAX_PONTOS = 4000, 60, 200, 12, 400
ID_RX = re.compile(r"[^a-z0-9_.:-]+")


class BlocoInvalido(ValueError):
    pass


@dataclass
class Ancoragem:
    """Onde o bloco prefere morar. Cada superfície interpreta o que entende: o cockpit usa x,y (0..1 da tela);
    um visor usa posição 3D em metros relativa ao usuário; óculos ignoram e empilham por prioridade."""
    x: float | None = None
    y: float | None = None
    largura: float | None = None           # fração da tela (0..1)
    altura: float | None = None
    display_id: str | None = None          # monitor preferido (jaime/spatial/telas.py)
    pos3d: tuple[float, float, float] | None = None
    superficie: str | None = None          # "só no cockpit", "só nos óculos"… (None = todas)


@dataclass
class Bloco:
    tipo: str
    titulo: str
    conteudo: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex[:8])
    fonte: str | None = None               # dado vivo: "sistema.maquina", "financas.resumo"… (fontes.py)
    parametros: dict = field(default_factory=dict)
    intervalo_s: float = 0.0               # refresh da fonte (0 = estático)
    prioridade: int = 1                    # 0 baixa · 1 normal · 2 alta · 3 urgente (superfície pequena mostra os maiores)
    privado: bool = False                  # finanças, diário, pessoas: só em superfície do dono com o cérebro aberto
    ancoragem: Ancoragem = field(default_factory=Ancoragem)
    ttl_s: float = 0.0                     # fecha sozinho depois de N s (0 = até alguém fechar)
    falar: bool = False                    # ao abrir, a superfície de voz lê o resumo
    criado_por: str = "jaime"              # joao | jaime | modelo:<nome>
    modelo: str | None = None              # nome do modelo (template) de onde veio
    versao: int = 1
    criado: float = field(default_factory=time.time)
    atualizado: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["v"] = VERSAO_ESQUEMA
        return d


# ── validação/conserto por tipo ──────────────────────────────────────────────
def _txt(v: Any, n: int = MAX_TEXTO) -> str:
    s = "" if v is None else str(v)
    return s[:n]


def _num(v: Any) -> float | None:
    try:
        f = float(str(v).replace(",", ".")) if not isinstance(v, (int, float)) else float(v)
        return f if f == f and abs(f) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _conteudo(tipo: str, c: Any) -> dict:
    c = c if isinstance(c, dict) else ({"texto": c} if isinstance(c, str) else {"itens": c} if isinstance(c, list) else {})
    if tipo == "texto":
        return {"texto": _txt(c.get("texto") or c.get("markdown") or ""), "tom": _txt(c.get("tom") or "", 16)}
    if tipo == "lista":
        itens = []
        for it in list(c.get("itens") or [])[:MAX_ITENS]:
            if isinstance(it, dict):
                itens.append({"texto": _txt(it.get("texto") or it.get("titulo") or "", 300), "detalhe": _txt(it.get("detalhe") or "", 300),
                              "feito": bool(it.get("feito", False))})
            else:
                itens.append({"texto": _txt(it, 300), "detalhe": "", "feito": False})
        return {"itens": itens, "ordenada": bool(c.get("ordenada", False))}
    if tipo == "tabela":
        cols = [_txt(x, 60) for x in list(c.get("colunas") or [])[:MAX_COLUNAS]]
        linhas = []
        for ln in list(c.get("linhas") or [])[:MAX_LINHAS]:
            ln = list(ln.values()) if isinstance(ln, dict) else list(ln) if isinstance(ln, (list, tuple)) else [ln]
            linhas.append([_txt(x, 120) for x in ln[:MAX_COLUNAS]])
        if not cols and linhas:
            cols = [f"c{i + 1}" for i in range(len(linhas[0]))]
        return {"colunas": cols, "linhas": linhas}
    if tipo == "metricas":
        out = []
        for m in list(c.get("itens") or c.get("metricas") or [])[:12]:
            if not isinstance(m, dict):
                continue
            out.append({"rotulo": _txt(m.get("rotulo") or m.get("nome") or "", 40), "valor": _txt(m.get("valor"), 40),
                        "unidade": _txt(m.get("unidade") or "", 12), "variacao": _num(m.get("variacao")),
                        "estado": _txt(m.get("estado") or "", 8)})       # ok | atencao | ruim
        return {"itens": out}
    if tipo == "grafico":
        forma = c.get("forma") if c.get("forma") in ("barras", "linha") else "barras"
        series = []
        for s in list(c.get("series") or [])[:6]:
            if not isinstance(s, dict):
                continue
            pts = []
            for p in list(s.get("pontos") or [])[:MAX_PONTOS]:
                if isinstance(p, dict):
                    x, y = p.get("x"), _num(p.get("y"))
                elif isinstance(p, (list, tuple)) and len(p) >= 2:
                    x, y = p[0], _num(p[1])
                else:
                    x, y = len(pts), _num(p)
                if y is not None:
                    pts.append({"x": _txt(x, 30), "y": y})
            series.append({"nome": _txt(s.get("nome") or "", 40), "pontos": pts})
        return {"forma": forma, "series": series, "unidade": _txt(c.get("unidade") or "", 12)}
    if tipo == "grafo":
        nos = [{"id": _txt(n.get("id"), 60), "rotulo": _txt(n.get("rotulo") or n.get("id"), 60)}
               for n in list(c.get("nos") or [])[:80] if isinstance(n, dict) and n.get("id")]
        ids = {n["id"] for n in nos}
        arestas = [{"de": _txt(a.get("de"), 60), "para": _txt(a.get("para"), 60), "rotulo": _txt(a.get("rotulo") or "", 40)}
                   for a in list(c.get("arestas") or [])[:200] if isinstance(a, dict) and a.get("de") in ids and a.get("para") in ids]
        return {"nos": nos, "arestas": arestas}
    if tipo == "status":
        return {"estado": _txt(c.get("estado") or "ok", 12), "texto": _txt(c.get("texto") or "", 300)}
    if tipo == "progresso":
        v = _num(c.get("valor")) or 0.0
        return {"valor": max(0.0, min(1.0, v if v <= 1 else v / 100)), "texto": _txt(c.get("texto") or "", 200)}
    if tipo == "acoes":
        # botões disparam INTENÇÕES com nome (não código): quem executa é o Jaime, pelo caminho normal (Vigia incluso)
        from .protocolo import intencao_segura
        botoes = [{"rotulo": _txt(b.get("rotulo"), 40), "intencao": _txt(b.get("intencao"), 200)}
                  for b in list(c.get("botoes") or [])[:8] if isinstance(b, dict) and b.get("rotulo") and b.get("intencao")
                  and intencao_segura(str(b.get("intencao")))]
        return {"texto": _txt(c.get("texto") or "", 300), "botoes": botoes}
    if tipo == "imagem":
        src = _txt(c.get("src") or "", 500)
        if src and not (src.startswith("/hud/") or src.startswith("data:image/")):
            raise BlocoInvalido("imagem só de rota local do HUD ou data:image (nada de URL externa)")
        return {"src": src, "legenda": _txt(c.get("legenda") or "", 200)}
    if tipo == "html":
        # só superfícies web desenham, e sempre em iframe sandbox (como o `mostrar` que já existe); as outras usam o `alternativo`
        html = _txt(c.get("html") or "", 20000)
        if re.search(r"<\s*script|javascript:|on\w+\s*=", html, re.I):
            raise BlocoInvalido("html de bloco não pode ter script nem handler de evento")
        return {"html": html, "alternativo": _txt(c.get("alternativo") or c.get("texto") or "", 600)}
    raise BlocoInvalido(f"tipo desconhecido: {tipo}")


def validar(d: dict | Bloco) -> Bloco:
    """dict (do modelo, do HUD, de um cliente) → Bloco válido, consertando o que dá e recusando o resto."""
    if isinstance(d, Bloco):
        d = d.to_dict()
    if not isinstance(d, dict):
        raise BlocoInvalido("bloco precisa ser um objeto")
    tipo = str(d.get("tipo") or "").strip().lower()
    if tipo not in TIPOS:
        raise BlocoInvalido(f"tipo '{tipo}' não existe (use: {', '.join(TIPOS)})")
    titulo = _txt(d.get("titulo") or "", 80).strip()
    if not titulo:
        raise BlocoInvalido("bloco sem título")
    anc = d.get("ancoragem") or {}
    anc = anc if isinstance(anc, dict) else {}
    lim = lambda v: None if _num(v) is None else max(0.0, min(1.0, _num(v)))
    p3 = anc.get("pos3d")
    p3 = tuple(float(x) for x in p3[:3]) if isinstance(p3, (list, tuple)) and len(p3) >= 3 and all(_num(x) is not None for x in p3[:3]) else None
    b = Bloco(tipo=tipo, titulo=titulo, conteudo=_conteudo(tipo, d.get("conteudo")),
              id=ID_RX.sub("-", str(d.get("id") or uuid4().hex[:8]).lower())[:48] or uuid4().hex[:8],
              fonte=_txt(d.get("fonte"), 60) or None, parametros=d.get("parametros") if isinstance(d.get("parametros"), dict) else {},
              intervalo_s=max(0.0, min(3600.0, _num(d.get("intervalo_s")) or 0.0)),
              prioridade=int(max(0, min(3, _num(d.get("prioridade")) if _num(d.get("prioridade")) is not None else 1))),
              privado=bool(d.get("privado", False)),
              ancoragem=Ancoragem(lim(anc.get("x")), lim(anc.get("y")), lim(anc.get("largura")), lim(anc.get("altura")),
                                  _txt(anc.get("display_id"), 40) or None, p3, _txt(anc.get("superficie"), 20) or None),
              ttl_s=max(0.0, min(86400.0, _num(d.get("ttl_s")) or 0.0)), falar=bool(d.get("falar", False)),
              criado_por=_txt(d.get("criado_por") or "jaime", 40), modelo=_txt(d.get("modelo"), 60) or None,
              versao=int(_num(d.get("versao")) or 1))
    if _num(d.get("criado")):
        b.criado = float(_num(d.get("criado")))
    if b.intervalo_s and b.intervalo_s < 2:
        b.intervalo_s = 2.0                               # fonte viva mais rápida que 2 s é desperdício (e trava HUD pequeno)
    return b


def de_dict(d: dict) -> Bloco:
    """Reconstrói um bloco já validado (persistência) — passa pela validação do mesmo jeito."""
    return validar(d)
