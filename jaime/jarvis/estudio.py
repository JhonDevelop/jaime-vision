"""Estúdio de hologramas: o que está aberto na tela, edição por voz, desenho, arquivos 3D.

A tela é quem manipula (peças, mãos, olhar); o servidor sabe o que está aberto porque a tela conta
(`POST /jarvis/holograma/cena`: título, peças com nome/centro/tamanho, peça selecionada; `…/tracos`: o desenho).

Edição por voz ("abre as portas", "aumenta essa peça", "coloca uma antena em cima"): o modelo recebe a lista de
peças e devolve OPERAÇÕES — nunca código. As operações são validadas aqui e aplicadas pela tela, com desfazer:
  mover [dx,dy,dz] · girar [rx,ry,rz] rad · escalar [sx,sy,sz] · esconder · mostrar · remover · duplicar [dx,dy,dz]
  · adicionar {peça} · explodir 0–1.6 · resetar
Alvo: lista de índices, "selecionada" (o que o João apontou/pinçou) ou "todas".
"""
from __future__ import annotations
import asyncio, json, re, time

from . import holograma as holo

OPS = {"mover", "girar", "escalar", "esconder", "mostrar", "remover", "duplicar", "adicionar", "explodir", "resetar"}
MAX_OPS = 24
PIVOS = {"frente", "tras", "cima", "baixo", "esquerda", "direita"}
PROMPT_EDITAR = """Você edita um holograma 3D do J.A.I.M.E. Objeto: "{titulo}". Peças (índice: nome · centro · tamanho):
{pecas}
Peça selecionada pelo João: {sel}.
Pedido do João: "{pedido}"
Responda SÓ um JSON: {{"ops": [{{"op": "...", "alvo": [índices] | "selecionada" | "todas", "valor": ...}}], "fala": "frase curta do que fez"}}
op: mover (valor [dx,dy,dz], metros de maquete, relativo) · girar (valor [rx,ry,rz] em radianos, relativo; opcional
"pivo": "frente|tras|cima|baixo|esquerda|direita" = gira em torno daquela face, como dobradiça — "abre a porta dianteira"
= girar ~1.1 no eixo y com pivo "frente"; o capô abre com pivo "frente" no eixo z) · escalar (valor [sx,sy,sz] multiplicativo) · esconder · mostrar · remover ·
duplicar (valor [dx,dy,dz] de deslocamento da cópia) · adicionar (sem alvo; "peca": {{"nome", "forma":
"caixa|cilindro|esfera|toro|cone", "pos", "tam", "rot"}} nas mesmas unidades do objeto) · explodir (valor 0 a 1.6) · resetar.
Use os índices da lista (vários quando o pedido fala de um grupo: "as rodas", "as portas"). y é para cima,
x para a frente. No máximo {n} operações. Sem texto fora do JSON."""
PROMPT_VOLUME = """Você é o módulo de hologramas do J.A.I.M.E. O João DESENHOU no ar os traços abaixo (linhas 3D, y para cima).
{nome}Traços (cada um: lista de pontos [x,y,z], simplificados):
{tracos}
Transforme o desenho num objeto 3D sólido que respeite as formas e proporções dos traços (o contorno vira volume).
Responda SÓ um JSON: {{"titulo": "nome curto do objeto", "pecas": [{{"nome": "...", "forma": "caixa|cilindro|esfera|toro|cone",
"pos": [x, y, z], "tam": [a, b, c], "rot": [rx, ry, rz], "explode": [dx, dy, dz]}}]}}
tam: caixa=[largura, altura, profundidade], cilindro=[raio, altura, 0], esfera=[raio, 0, 0], toro=[raio, espessura, 0],
cone=[raio, altura, 0]; entre 6 e {n} peças. Sem texto fora do JSON."""


def _json(bruto: str) -> dict:
    m = re.search(r"\{.*\}", bruto or "", re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


def validar_ops(dados, n_pecas: int) -> list[dict]:
    """Só operações conhecidas, alvos que existem, números finitos e dentro de limites."""
    ops = (dados or {}).get("ops") if isinstance(dados, dict) else None
    out = []
    for o in (ops or [])[:MAX_OPS]:
        if not isinstance(o, dict) or o.get("op") not in OPS:
            continue
        op = o["op"]
        item: dict = {"op": op}
        if op not in ("adicionar", "resetar", "explodir"):
            alvo = o.get("alvo", "selecionada")
            if alvo in ("selecionada", "todas"):
                item["alvo"] = alvo
            else:
                idx = [int(i) for i in (alvo if isinstance(alvo, list) else [alvo]) if isinstance(i, (int, float)) and 0 <= int(i) < n_pecas]
                if not idx:
                    continue
                item["alvo"] = sorted(set(idx))[:64]
        if op in ("mover", "duplicar"):
            item["valor"] = holo._num3(o.get("valor", [0, 0, 0]), 8)
        elif op == "girar":
            item["valor"] = holo._num3(o.get("valor", [0, 0, 0]), 6.3)
            if o.get("pivo") in PIVOS:
                item["pivo"] = o["pivo"]
        elif op == "escalar":
            v = o.get("valor", 1)
            v = [v, v, v] if isinstance(v, (int, float)) else v
            item["valor"] = [min(20.0, max(.05, abs(x) or 1.0)) for x in holo._num3(v, 20)]
        elif op == "explodir":
            try:
                item["valor"] = min(1.6, max(0.0, float(o.get("valor", 1))))
            except (TypeError, ValueError):
                continue
        elif op == "adicionar":
            pecas = holo.validar_pecas({"pecas": [o.get("peca") or {}]})
            if not pecas:
                continue
            item["peca"] = pecas[0]
        out.append(item)
    return out


def simplificar(pontos: list, passo: float = .08, maximo: int = 40) -> list:
    """Traço de centenas de pontos → poucos (distância mínima entre eles), para caber no prompt."""
    out = []
    for p in pontos:
        if not out or sum((a - b) ** 2 for a, b in zip(p, out[-1])) >= passo * passo:
            out.append([round(float(x), 2) for x in p[:3]])
    if len(out) > maximo:
        k = len(out) / maximo
        out = [out[int(i * k)] for i in range(maximo)] + [out[-1]]
    return out


class Estudio:
    def __init__(self, emitir, espera_tela: float = 15.0):
        self.emitir, self.espera_tela = emitir, espera_tela
        self.aberto = False
        self.titulo = ""
        self.pecas: list[dict] = []          # o que a tela contou: [{i, nome, centro, tam, visivel}]
        self.selecionada: int | None = None
        self.spec: list[dict] = []           # peças descritas (gerado/desenho) — base para exportar sem tela
        self.tracos: list[list] = []
        self.edicoes = 0
        self._malhas: asyncio.Future | None = None
        self.visto = 0.0

    # ── o que a tela conta ──
    def abrir(self, titulo: str, spec: list[dict] | None = None) -> None:
        self.aberto, self.titulo, self.spec, self.tracos, self.selecionada, self.edicoes = True, titulo, list(spec or []), [], None, 0
        self.visto = time.time()

    def fechar(self) -> None:
        self.aberto = False

    def receber_cena(self, d: dict) -> None:
        self.aberto, self.visto = True, time.time()
        self.titulo = str(d.get("titulo") or self.titulo)[:80]
        pecas = []
        for i, p in enumerate((d.get("pecas") or [])[:400]):
            if isinstance(p, dict):
                pecas.append({"i": i, "nome": str(p.get("nome") or f"peça {i}")[:40],
                              "centro": holo._num3(p.get("centro", [0, 0, 0]), 50), "tam": holo._num3(p.get("tam", [0, 0, 0]), 50),
                              "visivel": bool(p.get("visivel", True))})
        self.pecas = pecas
        s = d.get("selecionada")
        self.selecionada = int(s) if isinstance(s, (int, float)) and 0 <= int(s) < len(pecas) else None

    def receber_tracos(self, tracos) -> int:
        limpos = []
        for t in (tracos or [])[:120]:
            pts = [holo._num3(p, 8) for p in (t or [])[:600] if isinstance(p, (list, tuple))]
            if len(pts) >= 2:
                limpos.append(pts)
        self.tracos = limpos
        self.spec = [{"nome": f"traço {k + 1}", "forma": "tubo", "pos": [0, 0, 0], "tam": [.04, 0, 0], "rot": [0, 0, 0],
                      "explode": [0, 0, 0], "pontos": t} for k, t in enumerate(limpos)]
        return len(limpos)

    def receber_malhas(self, d: dict) -> None:
        if self._malhas is not None and not self._malhas.done():
            self._malhas.set_result(d)

    # ── voz → tela ──
    async def editar(self, pedido: str, modelo_fn) -> str:
        if not self.pecas:
            return "Ainda não tenho as peças desse holograma; olhe para a tela e peça de novo."
        if modelo_fn is None:
            return "Estou sem modelo para editar agora."
        lista = "\n".join(f"{p['i']}: {p['nome']} · {p['centro']} · {p['tam']}" + ("" if p["visivel"] else " (escondida)") for p in self.pecas[:160])
        sel = f"{self.selecionada} ({self.pecas[self.selecionada]['nome']})" if self.selecionada is not None else "nenhuma"
        bruto = await modelo_fn(PROMPT_EDITAR.format(titulo=self.titulo, pecas=lista, sel=sel, pedido=pedido[:300], n=MAX_OPS), "")
        d = _json(bruto)
        ops = validar_ops(d, len(self.pecas))
        if not ops:
            return "Não consegui transformar isso em uma alteração do holograma. Tente dizer qual peça e o que fazer."
        if any(o.get("alvo") == "selecionada" for o in ops) and self.selecionada is None:
            return "Qual peça? Aponte para ela ou faça a pinça em cima, e peça de novo."
        self.edicoes += 1
        self.emitir("holograma", acao="editar", ops=ops)
        fala = str(d.get("fala") or "").strip()[:160]
        return fala or "Feito."

    def desfazer(self) -> str:
        if not self.edicoes:
            self.emitir("holograma", acao="desfazer")
            return "Desfeito."
        self.edicoes -= 1
        self.emitir("holograma", acao="desfazer")
        return "Desfeito."

    async def volume(self, modelo_fn, nome: str = "") -> dict | None:
        """Desenho → objeto sólido em peças (o modelo interpreta os traços)."""
        if not self.tracos or modelo_fn is None:
            return None
        txt = "\n".join(json.dumps(simplificar(t)) for t in self.tracos[:40])
        bruto = await modelo_fn(PROMPT_VOLUME.format(nome=f'O João disse que é: "{nome}".\n' if nome else "", tracos=txt, n=holo.MAX_PECAS), "")
        d = _json(bruto)
        pecas = holo.validar_pecas(d)
        if len(pecas) < 3:
            return None
        titulo = (nome or str(d.get("titulo") or "desenho")).strip()[:60]
        slug = holo._slug(titulo) or "desenho"
        holo.PASTA.mkdir(parents=True, exist_ok=True)
        (holo.PASTA / f"{slug}.json").write_text(json.dumps({"objeto": titulo, "pecas": pecas, "tracos": self.tracos}, ensure_ascii=False), encoding="utf-8")
        return {"modelo": "gerado", "arquivo": slug, "titulo": titulo, "exato": True, "pecas": pecas}

    async def malhas(self) -> list[dict]:
        """Pede à tela as malhas como estão agora (com as mãos do João); sem tela, monta da descrição."""
        from .malha3d import malha_da_peca, validar_malhas
        self._malhas = asyncio.get_event_loop().create_future()
        self.emitir("holograma", acao="exportar")
        try:
            d = await asyncio.wait_for(asyncio.shield(self._malhas), self.espera_tela)
            m = validar_malhas(d.get("pecas"))
            if m:
                return m
        except asyncio.TimeoutError:
            pass
        finally:
            self._malhas = None
        return [x for x in (malha_da_peca(p) for p in self.spec) if x["f"]]
