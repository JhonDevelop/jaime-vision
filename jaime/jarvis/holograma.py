"""Holograma 3D controlado pela mão (vídeo do carro verde).

O modelo é montado na tela (three.js) a partir de PEÇAS — cada peça explode para fora e volta — então "explodir"
mostra o objeto por dentro, como no vídeo. Catálogo procedural: carro (SUV), moto, casa, drone, foguete, átomo,
planeta. Objeto que não está no catálogo: se existir `~/Jaime/hologramas/<nome>.glb` (modelo baixado pelo João),
ele carrega o arquivo; senão ele diz que não tem e mostra o mais próximo que tiver.
"""
from __future__ import annotations
import os, re, unicodedata
from pathlib import Path

PASTA = Path(os.environ.get("JAIME_HOLOGRAMAS", "~/Jaime/hologramas")).expanduser()
CATALOGO = {
    "carro": ["carro", "suv", "tesla", "model x", "model s", "model y", "carro eletrico", "caminhonete", "picape", "automovel", "veiculo", "polo", "amarok"],
    "moto": ["moto", "motocicleta", "scooter"],
    "casa": ["casa", "predio", "prédio", "construcao", "construção", "obra", "imovel", "imóvel"],
    "drone": ["drone", "quadricoptero"],
    "foguete": ["foguete", "nave", "rocket", "espaconave"],
    "atomo": ["atomo", "átomo", "molecula", "molécula"],
    "planeta": ["planeta", "terra", "globo", "mundo", "lua"],
}


def _n(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")).strip()


def _slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _n(t)).strip("-")[:60]


def resolver(objeto: str) -> dict:
    """{'modelo': chave do catálogo | 'glb', 'arquivo': slug, 'titulo': o que o João pediu, 'exato': bool}"""
    alvo = _n(objeto)
    slug = _slug(objeto)
    if slug and (PASTA / f"{slug}.glb").is_file():
        return {"modelo": "glb", "arquivo": slug, "titulo": objeto.strip(), "exato": True}
    for chave, apelidos in CATALOGO.items():
        if any(re.search(rf"\b{re.escape(_n(a))}\b", alvo) for a in apelidos):
            return {"modelo": chave, "arquivo": "", "titulo": objeto.strip(), "exato": True}
    if (pecas := carregar_gerado(objeto)):
        return {"modelo": "gerado", "arquivo": slug, "titulo": objeto.strip(), "exato": True, "pecas": pecas}
    return {"modelo": "atomo", "arquivo": "", "titulo": objeto.strip(), "exato": False}


def fala(r: dict) -> str:
    if r["exato"]:
        return (f"Holograma de {r['titulo']} pronto. Mova a mão para girar, afaste as duas mãos para abrir as peças "
                "e feche a mão para remontar.")
    return (f"Não consegui montar {r['titulo']} agora. Se o senhor salvar um arquivo {_slug(r['titulo'])}.glb na pasta "
            "Jaime/hologramas, eu uso ele. Por enquanto deixei um holograma genérico.")


def arquivo_glb(slug: str) -> Path | None:
    s = _slug(slug)
    p = (PASTA / f"{s}.glb").resolve()
    return p if s and p.parent == PASTA.resolve() and p.is_file() else None


# ── holograma de QUALQUER objeto: o modelo descreve as peças, a tela monta ────────────────────────────
FORMAS = {"caixa", "cilindro", "esfera", "toro", "cone", "tubo"}   # tubo = traço desenhado (pontos + raio)
MAX_PECAS = 48
PROMPT = """Você é o módulo de hologramas do J.A.I.M.E. Descreva o objeto "{obj}" como um modelo 3D feito de PEÇAS
primitivas para um holograma em wireframe que pode "explodir" (cada peça se afasta do centro e volta).
Responda SÓ um JSON: {{"pecas": [{{"nome": "...", "forma": "caixa|cilindro|esfera|toro|cone",
"pos": [x, y, z], "tam": [a, b, c], "rot": [rx, ry, rz], "explode": [dx, dy, dz]}}]}}
Regras: unidades em metros de maquete, o objeto inteiro cabe em ~5 x 3 x 3, centrado na origem, y para cima;
tam: caixa=[largura, altura, profundidade], cilindro=[raio, altura, 0], esfera=[raio, 0, 0], toro=[raio, espessura, 0],
cone=[raio, altura, 0]; rot em radianos; explode = direção para fora (≈1 a 2.5 de comprimento), peças internas
explodem para cima ou para baixo; entre 12 e {n} peças, as mais reconhecíveis do objeto (proporções reais), incluindo
partes internas quando fizer sentido. Sem texto fora do JSON."""


def _num3(v, lim: float) -> list[float]:
    try:
        xs = [float(x) for x in (list(v) + [0, 0, 0])[:3]]
    except (TypeError, ValueError):
        return [0.0, 0.0, 0.0]
    return [max(-lim, min(lim, x)) for x in xs]


def validar_pecas(dados) -> list[dict]:
    """Só o que a tela sabe desenhar, dentro de limites (o texto do modelo nunca vira código na página)."""
    pecas = (dados or {}).get("pecas") if isinstance(dados, dict) else None
    out = []
    for p in (pecas or [])[:MAX_PECAS]:
        if not isinstance(p, dict) or p.get("forma") not in FORMAS:
            continue
        tam = [abs(x) for x in _num3(p.get("tam", [1, 1, 1]), 6)]
        if max(tam) < 0.02:
            continue
        item = {"nome": re.sub(r"[^\w\s\-çãõáéíóúâêô]", "", str(p.get("nome", "")))[:40], "forma": p["forma"],
                "pos": _num3(p.get("pos", [0, 0, 0]), 6), "tam": tam, "rot": _num3(p.get("rot", [0, 0, 0]), 6.3),
                "explode": _num3(p.get("explode", [0, 1, 0]), 4)}
        if p["forma"] == "tubo":
            pts = [_num3(q, 6) for q in (p.get("pontos") or [])[:400] if isinstance(q, (list, tuple))]
            if len(pts) < 2:
                continue
            item["pontos"], item["tam"] = pts, [min(max(tam[0], .01), .3), 0.0, 0.0]
        out.append(item)
    return out


def carregar_gerado(objeto: str) -> list[dict] | None:
    import json
    p = PASTA / f"{_slug(objeto)}.json"
    try:
        return validar_pecas(json.loads(p.read_text(encoding="utf-8"))) or None
    except Exception:
        return None


async def gerar(objeto: str, modelo_fn) -> dict:
    """Pede as peças ao modelo, valida, guarda em ~/Jaime/hologramas/<nome>.json (a segunda vez é instantânea)."""
    import json
    if (pecas := carregar_gerado(objeto)):
        return {"modelo": "gerado", "arquivo": _slug(objeto), "titulo": objeto.strip(), "exato": True, "pecas": pecas}
    bruto = await modelo_fn(PROMPT.format(obj=objeto.strip()[:80], n=MAX_PECAS), "")
    m = re.search(r"\{.*\}", bruto or "", re.S)
    try:
        pecas = validar_pecas(json.loads(m.group(0))) if m else []
    except json.JSONDecodeError:
        pecas = []
    if len(pecas) < 4:
        return {**resolver(objeto), "falhou": True}
    PASTA.mkdir(parents=True, exist_ok=True)
    (PASTA / f"{_slug(objeto)}.json").write_text(json.dumps({"objeto": objeto, "pecas": pecas}, ensure_ascii=False), encoding="utf-8")
    return {"modelo": "gerado", "arquivo": _slug(objeto), "titulo": objeto.strip(), "exato": True, "pecas": pecas}
