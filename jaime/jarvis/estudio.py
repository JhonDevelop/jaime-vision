"""Estúdio de hologramas: o que está aberto na tela, edição por voz, desenho, arquivos 3D.

A tela é quem manipula (peças, mãos, olhar); o servidor sabe o que está aberto porque a tela conta
(`POST /jarvis/holograma/cena`: título, peças com nome/centro/tamanho, peça selecionada; `…/tracos`: o desenho).

Edição por voz ("abre as portas", "aumenta essa peça", "coloca uma antena em cima"): o modelo recebe a lista de
peças e devolve OPERAÇÕES — nunca código. As operações são validadas aqui e aplicadas pela tela, com desfazer:
  mover [dx,dy,dz] · girar [rx,ry,rz] rad · escalar [sx,sy,sz] · esconder · mostrar · remover · duplicar [dx,dy,dz]
  · adicionar {peça} · explodir 0–1.6 · resetar [alvo opcional] · separar (a peça sai para fora e fica em destaque)
  · isolar (só ela aparece, enquadrada) · focar (enquadra sem esconder) · mostrar_tudo · cor "#rrggbb"
Os pedidos comuns ("separa a roda", "mostra só o motor", "mostra tudo", "aumenta essa peça", "pinta a porta de
vermelho", "gira a hélice", "esconde as portas") são resolvidos AQUI, sem modelo (`rapido`), em milissegundos;
o modelo só entra no que foge disso.
Alvo: lista de índices, "selecionada" (o que o João apontou/pinçou) ou "todas".
"""
from __future__ import annotations
import asyncio, json, re, time

from . import holograma as holo

OPS = {"mover", "girar", "escalar", "esconder", "mostrar", "remover", "duplicar", "adicionar", "explodir", "resetar",
       "separar", "isolar", "focar", "mostrar_tudo", "cor"}
SEM_ALVO = {"adicionar", "explodir", "mostrar_tudo"}
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
"caixa|cilindro|esfera|toro|cone", "pos", "tam", "rot"}} nas mesmas unidades do objeto) · explodir (valor 0 a 1.6) ·
resetar (alvo opcional: volta a peça ao lugar) · separar (valor = distância, a peça sai para fora) · isolar (só a peça
aparece, enquadrada) · focar (enquadra) · mostrar_tudo (sem alvo) · cor (valor "#rrggbb").
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
        if op == "resetar" and o.get("alvo") in (None, "", []):
            out.append(item); continue
        if op not in SEM_ALVO:
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
        elif op == "separar":
            try:
                item["valor"] = min(5.0, max(0.2, float(o.get("valor", 1.5))))
            except (TypeError, ValueError):
                item["valor"] = 1.5
        elif op == "cor":
            cor = str(o.get("valor", "")).lower()
            if not re.fullmatch(r"#[0-9a-f]{6}", cor):
                continue
            item["valor"] = cor
        out.append(item)
    return out


# ── pedidos comuns, sem modelo ──────────────────────────────────────────────────────────────────────────
CORES = {"vermelho": "#ff3b3b", "vermelha": "#ff3b3b", "azul": "#3b8bff", "verde": "#3dffa0", "amarelo": "#ffd23b",
         "amarela": "#ffd23b", "laranja": "#ff8a3b", "roxo": "#a45bff", "roxa": "#a45bff", "rosa": "#ff5bc8", "branco": "#f4fbff",
         "branca": "#f4fbff", "preto": "#2a2f36", "preta": "#2a2f36", "cinza": "#9aa6b2", "dourado": "#e8b64a", "dourada": "#e8b64a",
         "prata": "#c8d2dc", "ciano": "#3be8ff", "original": "#3dffa0"}
SINONIMOS = {"frente": "dianteir", "frontal": "dianteir", "dianteira": "dianteir", "dianteiro": "dianteir", "tras": "traseir",
             "traseira": "traseir", "traseiro": "traseir", "atras": "traseir", "esquerda": "esquerd", "esquerdo": "esquerd",
             "direita": "direit", "direito": "direit", "rodas": "roda", "portas": "porta", "pneus": "pneu", "bancos": "assento",
             "banco": "assento", "helices": "helice", "helice": "helice", "farois": "farol", "motores": "motor", "janelas": "janela",
             "asas": "asa", "aletas": "aleta", "paredes": "parede", "bracos": "braco", "pecas": "peca"}
VAZIAS = {"a", "o", "as", "os", "da", "do", "das", "dos", "de", "na", "no", "em", "um", "uma", "e", "pra", "para", "ela", "ele",
          "so", "somente", "apenas", "inteira", "inteiro", "inteiramente", "toda", "todo", "todas", "todos", "parte", "pouco",
          "mais", "bem", "ai", "aqui", "agora", "por", "favor", "jarvis", "jaime", "me", "lado", "cor", "tamanho", "vez"}
ESTA = {"essa", "esse", "isso", "esta", "este", "isto", "selecionada", "selecionado"}
ACOES = [  # (regex do verbo no começo, op, valor)
    (r"(separa|separe|destaca|destaque|solta|puxa|puxe|tira\s+pra\s+fora|isola\s+e\s+separa)", "separar", 1.6),
    (r"(mostra|mostre|deixa)\s+(so|somente|apenas)|isola|isole", "isolar", None),
    (r"(foca|foque|enquadra|aproxima|chega\s+perto)(\s+n[ao])?", "focar", None),
    (r"(esconde|esconda|oculta|some\s+com|tira|remove|apaga)", "esconder", None),
    (r"(aumenta|aumente|amplia|cresce)", "escalar", 1.3),
    (r"(diminui|diminua|reduz|encolhe)", "escalar", 0.77),
    (r"(dobra)", "escalar", 2.0),
    (r"(duplica|duplique|copia|clona)", "duplicar", [0.7, 0, 0]),
    (r"(volta|junta|remonta|recoloca|reseta)", "resetar", None),
    (r"(pinta|pinte|colore|muda\s+a\s+cor)", "cor", None),
]
DIRECOES = {"cima": (1, 0.6), "baixo": (1, -0.6), "frente": (0, 0.6), "tras": (0, -0.6), "esquerda": (2, -0.6), "direita": (2, 0.6)}


def _n(t: str) -> str:
    return holo._n(t)


def _tokens(texto: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z0-9]+", _n(texto)):
        if w in VAZIAS or len(w) < 2:
            continue
        w = SINONIMOS.get(w, w)
        if w.endswith("s") and len(w) > 4 and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


def _casa(token: str, nome_tokens: list[str]) -> bool:
    raiz = token[:max(4, len(token) - 1)] if len(token) > 4 else token
    return any(n.startswith(raiz) or raiz.startswith(n[:max(4, len(n) - 1)]) for n in nome_tokens if len(n) >= 2)


def achar_pecas(texto: str, pecas: list[dict], selecionada: int | None) -> tuple[list[int] | str | None, bool]:
    """('selecionada' | [índices] | None, plural?). "essa peça" → selecionada; "as rodas" → todas as rodas."""
    palavras = re.findall(r"[a-z0-9]+", _n(texto))
    if any(w in ESTA for w in palavras) and selecionada is not None:
        return "selecionada", False
    plural = any(w in ("as", "os", "todas", "todos") for w in palavras) or any(
        re.fullmatch(r"\w{3,}s", w) and SINONIMOS.get(w, w) != w for w in palavras)
    toks = [t for t in _tokens(texto) if t not in ESTA and t not in CORES and t not in DIRECOES and t != "peca"]
    if not toks:
        return ("selecionada" if selecionada is not None else None), False
    achados = [p["i"] for p in pecas if all(_casa(t, _tokens(p["nome"])) for t in toks)]
    if not achados:
        return None, plural
    if plural or len(achados) == 1:
        return achados, plural
    return ([selecionada] if selecionada in achados else achados[:1]), False


def rapido(pedido: str, pecas: list[dict], selecionada: int | None) -> tuple[list[dict], str] | None:
    """Pedido comum → (ops, fala) sem modelo; None quando não reconhece (vai para o modelo)."""
    t = re.sub(r"^\s*(jarvis|jaime)[,\s]*", "", _n(pedido)).strip(" .!?")
    if re.fullmatch(r"(mostra|mostre|volta|traz)\s+(tudo|todas?( as pecas)?|o objeto inteiro|inteiro)|mostrar tudo", t):
        return [{"op": "mostrar_tudo"}], "Tudo de volta."
    if re.fullmatch(r"(explode|abre as pecas|abre tudo|separa tudo|separa as pecas|desmonta( tudo)?)", t):
        return [{"op": "explodir", "valor": 1.2}], "Peças abertas."
    if re.fullmatch(r"(junta tudo|remonta tudo|monta de novo|fecha as pecas|junta as pecas|remonta)", t):
        return [{"op": "explodir", "valor": 0}], "Remontado."
    if re.fullmatch(r"(reseta|volta tudo ao normal|volta como era|desfaz tudo)", t):
        return [{"op": "resetar"}], "Voltei tudo ao original."
    if (m := re.match(r"(mostra|mostre|quero ver)\s+(?P<resto>.+?)\s+(inteir[ao]s?|inteiramente|completa|completo|sozinh[ao]s?)$", t)):
        alvo, _ = achar_pecas(m.group("resto"), pecas, selecionada)
        if alvo is not None:
            nome = "essa peça" if alvo == "selecionada" else pecas[alvo[0]]["nome"] if len(alvo) == 1 else f"{len(alvo)} peças"
            return [{"op": "isolar", "alvo": alvo}], f"Só {nome} na tela."
    cor = next((CORES[w] for w in re.findall(r"[a-z]+", t) if w in CORES), None)
    if cor and (m := re.match(r"(deixa|deixe|pinta|pinte|colore|muda|faz|faca)\b(?P<resto>.*)$", t)):
        alvo, _ = achar_pecas(m.group("resto"), pecas, selecionada)
        if alvo is None:
            return None
        return [{"op": "cor", "alvo": alvo, "valor": cor}], "Pintei."
    for rx, op, valor in ACOES:
        m = re.match("(?:" + rx + r")\b(?P<resto>.*)$", t)
        if not m:
            continue
        resto = m.group("resto")
        alvo, _ = achar_pecas(resto, pecas, selecionada)
        if alvo is None:
            return None
        nomes = "essa peça" if alvo == "selecionada" else (pecas[alvo[0]]["nome"] if len(alvo) == 1 else f"{len(alvo)} peças")
        o: dict = {"op": op, "alvo": alvo}
        if op == "cor":
            cor = next((CORES[w] for w in re.findall(r"[a-z]+", resto) if w in CORES), None)
            if not cor:
                return None
            o["valor"] = cor
            return [o], f"Pintei {nomes}."
        if op == "escalar":
            o["valor"] = [valor] * 3
            return [o], ("Aumentei " if valor > 1 else "Diminuí ") + nomes + "."
        if valor is not None:
            o["valor"] = valor
        falas = {"separar": f"Separei {nomes}.", "isolar": f"Só {nomes} na tela.", "focar": f"Enquadrei {nomes}.",
                 "esconder": f"Escondi {nomes}.", "duplicar": f"Dupliquei {nomes}.", "resetar": f"{nomes[0].upper() + nomes[1:]} de volta ao lugar."}
        return [o], falas.get(op, "Feito.")
    m = re.match(r"(gira|gire|roda|rode|vira|vire)\b(?P<resto>.*)$", t)
    if m:
        resto = m.group("resto")
        alvo, _ = achar_pecas(re.sub(r"\b(para|pra)?\s*(a|o)?\s*(esquerda|direita|cima|baixo)\b|de cabeca pra baixo|de cabeca para baixo", "", resto),
                              pecas, selecionada)
        if alvo is None:
            return None
        v = [0.0, 1.5708, 0.0]
        if "esquerda" in resto:
            v = [0.0, -1.5708, 0.0]
        elif "cima" in resto:
            v = [-1.5708, 0.0, 0.0]
        elif "baixo" in resto:
            v = [1.5708, 0.0, 0.0]
        if "cabeca" in resto:
            v = [3.1416, 0.0, 0.0]
        return [{"op": "girar", "alvo": alvo, "valor": v}], "Girei."
    m = re.match(r"(move|mova|leva|leve|empurra|empurre|sobe|suba|desce|desca|levanta|abaixa)\b(?P<resto>.*)$", t)
    if m:
        verbo, resto = m.group(1), m.group("resto")
        d = "cima" if verbo in ("sobe", "suba", "levanta") else "baixo" if verbo in ("desce", "desca", "abaixa") else \
            next((k for k in DIRECOES if re.search(rf"\b{k}\b", resto)), None)
        if d is None:
            return None
        alvo, _ = achar_pecas(re.sub(rf"\b(para|pra)?\s*(a|o)?\s*{d}\b", "", resto), pecas, selecionada)
        if alvo is None:
            return None
        eixo, q = DIRECOES[d]
        v = [0.0, 0.0, 0.0]; v[eixo] = q
        return [{"op": "mover", "alvo": alvo, "valor": v}], "Movi."
    m = re.match(r"abre\b(?P<resto>.*)$", t)
    if m and re.search(r"\bporta", m.group("resto")):
        alvo, _ = achar_pecas(m.group("resto"), pecas, selecionada)
        if alvo is None:
            return None
        return [{"op": "girar", "alvo": alvo, "valor": [0, 1.1, 0], "pivo": "frente"}], "Portas abertas." if len(alvo) > 1 else "Porta aberta."
    return None


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
        r = rapido(pedido, self.pecas, self.selecionada)
        if r is not None:
            ops = validar_ops({"ops": r[0]}, len(self.pecas))
            if ops:
                self.edicoes += 1
                self.emitir("holograma", acao="editar", ops=ops)
                return r[1]
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
