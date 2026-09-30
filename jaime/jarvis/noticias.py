"""Radar de notícias por RSS (sem chave): um destaque por tema, com imagem e fonte — o que o briefing mostra e fala.

Temas padrão: tecnologia (g1), inteligência artificial (Google Notícias) e política (g1). O João troca por
`JAIME_NOTICIAS="tecnologia|https://…;esportes|https://…"`. Cache de 20 min por feed. Sem imagem no feed, tenta
o `og:image` da matéria (timeout curto); sem nada, o card fica sem foto.
"""
from __future__ import annotations
import asyncio, html, os, re, time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict

import httpx

PADRAO = [
    ("tecnologia", "https://g1.globo.com/rss/g1/tecnologia/"),
    ("novos modelos de IA", "https://news.google.com/rss/search?q=intelig%C3%AAncia+artificial+modelo&hl=pt-BR&gl=BR&ceid=BR:pt-419"),
    ("política", "https://g1.globo.com/rss/g1/politica/"),
]
MEDIA = "{http://search.yahoo.com/mrss/}"
_cache: dict[str, tuple[float, list]] = {}


@dataclass
class Noticia:
    tema: str
    titulo: str
    fonte: str = ""
    link: str = ""
    imagem: str = ""
    resumo: str = ""

    def dados(self) -> dict:
        return asdict(self)


def temas_do_ambiente(env=None) -> list[tuple[str, str]]:
    e = os.environ if env is None else env
    bruto = (e.get("JAIME_NOTICIAS", "") or "").strip()
    if not bruto:
        return list(PADRAO)
    out = []
    for parte in bruto.split(";"):
        tema, _, url = parte.partition("|")
        if tema.strip() and url.strip().startswith("https://"):
            out.append((tema.strip(), url.strip()))
    return out or list(PADRAO)


def _limpo(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()


def ler_rss(xml: str, tema: str, fonte_padrao: str = "") -> list[Noticia]:
    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError:
        return []
    canal = raiz.find("channel")
    fonte_canal = _limpo(canal.findtext("title", "") if canal is not None else "") or fonte_padrao
    fonte_canal = re.split(r"\s[>|–-]\s", fonte_canal)[0].strip()
    out = []
    for it in raiz.iter("item"):
        titulo = _limpo(it.findtext("title", ""))
        if not titulo:
            continue
        fonte = _limpo(it.findtext("source", "")) or fonte_canal
        if fonte and titulo.endswith(f" - {fonte}"):
            titulo = titulo[: -len(fonte) - 3].strip()
        img = ""
        for tag in (f"{MEDIA}content", f"{MEDIA}thumbnail", "enclosure"):
            el = it.find(tag)
            if el is not None and (el.get("url") or "").startswith("http") and "image" in (el.get("type") or "image"):
                img = el.get("url"); break
        desc = it.findtext("description", "") or ""
        if not img and (m := re.search(r"<img[^>]+src=[\"']([^\"']+)", html.unescape(desc))):
            img = m.group(1)
        out.append(Noticia(tema, titulo, fonte, (it.findtext("link", "") or "").strip(), img, _limpo(desc)[:280]))
    return out


async def _og_image(c: httpx.AsyncClient, url: str) -> str:
    if not url or "news.google.com" in url:
        return ""
    try:
        r = await c.get(url, timeout=4, follow_redirects=True)
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', r.text[:200_000])
        return m.group(1) if m else ""
    except Exception:
        return ""


async def destaques(temas: list[tuple[str, str]] | None = None, http: httpx.AsyncClient | None = None,
                    ttl: float = 1200.0) -> list[Noticia]:
    """Um destaque por tema (o primeiro item do feed), em paralelo; tema que falhar some sem derrubar os outros."""
    temas = temas or temas_do_ambiente()
    dono = http is None
    c = http or httpx.AsyncClient(timeout=8, headers={"User-Agent": "Mozilla/5.0 (J.A.I.M.E radar)"}, follow_redirects=True)

    async def um(tema: str, url: str) -> Noticia | None:
        agora = time.time()
        if url in _cache and agora - _cache[url][0] < ttl:
            itens = _cache[url][1]
        else:
            try:
                r = await c.get(url); r.raise_for_status()
                itens = ler_rss(r.text, tema)
                _cache[url] = (agora, itens)
            except Exception:
                return None
        if not itens:
            return None
        n = itens[0]
        if not n.imagem:
            n.imagem = await _og_image(c, n.link)
        return n

    try:
        res = await asyncio.gather(*(um(t, u) for t, u in temas))
    finally:
        if dono:
            await c.aclose()
    return [n for n in res if n]
