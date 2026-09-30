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
    return {"modelo": "atomo", "arquivo": "", "titulo": objeto.strip(), "exato": False}


def fala(r: dict) -> str:
    if r["exato"]:
        return (f"Holograma de {r['titulo']} pronto. Mova a mão para girar, afaste as duas mãos para abrir as peças "
                "e feche a mão para remontar.")
    return (f"Ainda não tenho um modelo de {r['titulo']}. Se o senhor salvar um arquivo {_slug(r['titulo'])}.glb na pasta "
            "Jaime/hologramas, eu monto ele. Por enquanto deixei um holograma genérico.")


def arquivo_glb(slug: str) -> Path | None:
    s = _slug(slug)
    p = (PASTA / f"{s}.glb").resolve()
    return p if s and p.parent == PASTA.resolve() and p.is_file() else None
