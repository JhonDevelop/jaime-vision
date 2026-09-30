"""Demonstração da tela Jarvis sem o Jaime inteiro: `python -m jaime jarvis demo [porta]` (padrão 8792).

Abre http://127.0.0.1:8792/hud/jarvis e chama /demo/briefing, /demo/monitor ou /demo/holograma (ou use os botões
da própria tela). Os dados são os do vídeo (fictícios) e a voz é simulada — cada frase gera o evento `voz` com o
texto, no ritmo de uma fala real — então dá para ver a sincronia card ↔ voz exatamente como no serviço.
"""
from __future__ import annotations
import asyncio, json, re
from pathlib import Path

from ..hud.events import bus
from .briefing import Briefing
from .monitor import Monitor
from .rosto import Rostos
from . import holograma as holo
from .saude import Resumo, observacoes

CLIMA = {"current": {"temperature_2m": 26.7, "weather_code": 1}, "daily": {"temperature_2m_max": [27.5], "temperature_2m_min": [23.3], "precipitation_probability_max": [62]}}
EMAILS = [{"de": "Stripe <no-reply@stripe.com>", "assunto": "Ação necessária: atualize seus dados comerciais", "resumo": "envie o documento solicitado até 22/10/2026"},
          {"de": "Santander <aviso@santander.com.br>", "assunto": "Sua fatura está próxima do vencimento", "resumo": ""}] + \
         [{"de": f"Contato {i} <c{i}@exemplo.com>", "assunto": f"Assunto {i}", "resumo": ""} for i in range(18)]


def _imagem(cor1: str, cor2: str, texto: str) -> str:
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' width='640' height='320'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
           f"<stop offset='0' stop-color='{cor1}'/><stop offset='1' stop-color='{cor2}'/></linearGradient></defs>"
           f"<rect width='640' height='320' fill='url(#g)'/><text x='32' y='290' font-family='Arial' font-size='26' fill='white' opacity='.8'>{texto}</text></svg>")
    from urllib.parse import quote
    return "data:image/svg+xml," + quote(svg)


NOTICIAS = [
    {"tema": "tecnologia", "titulo": "Uma frase atribuída a Mahatma Gandhi, líder indiano, destaca que a felicidade surge quando o que o senhor pensa, diz e faz está em harmonia",
     "fonte": "Correio Braziliense", "imagem": _imagem("#6b5a3a", "#2b2418", "tecnologia"), "link": ""},
    {"tema": "novos modelos de IA", "titulo": "A OpenAI freou o lançamento de um novo modelo diante de riscos de segurança",
     "fonte": "", "imagem": _imagem("#3a4a5a", "#11161c", "novos modelos de IA"), "link": ""},
    {"tema": "política", "titulo": "A Veja destaca a nova pesquisa Atlas Intel sobre a disputa entre Lula e Flávio Bolsonaro a cinco dias da eleição",
     "fonte": "", "imagem": _imagem("#c9d4e6", "#7c8aa6", "política"), "link": ""},
]


async def _resumir(prompt: str, texto: str) -> str:
    if "UMA frase" in prompt:            # notícias contadas com as palavras do Jaime
        return json.dumps(["Nas notícias de tecnologia, uma frase atribuída a Mahatma Gandhi, líder indiano, destaca que a felicidade surge quando o que o senhor pensa, diz e faz está em harmonia",
                           "Nas notícias sobre novos modelos de inteligência artificial, a OpenAI freou o lançamento de um novo modelo diante de riscos de segurança",
                           "Na política, a Veja destaca a nova pesquisa Atlas Intel sobre a disputa entre Lula e Flávio Bolsonaro a cinco dias da eleição"], ensure_ascii=False)
    return json.dumps([{"de": "Stripe", "acao": "Atualize os dados comerciais e envie o documento solicitado à Stripe antes de 22/10/2026 para evitar impacto nos pagamentos."},
                       {"de": "Santander", "acao": "A fatura do Santander está próxima do vencimento."},
                       {"de": "PCPT1", "acao": "Há duas convocações para a Assembleia Geral extraordinária de PCPT1."},
                       {"de": "Contabilidade", "acao": "Responder ao contador sobre o fechamento de setembro."},
                       {"de": "Oldsen", "acao": "Aprovar a arte da nova coleção."}], ensure_ascii=False)


def briefing_demo() -> Briefing:
    saude = Resumo(distancia_km=.1, duracao_min=63, habitual_km=.5, fc_pico=192, estresse=13.6, recuperacao=34)
    saude.observacoes = observacoes(saude) + [f"observação {i}" for i in range(15)]
    return Briefing(clima=lambda: CLIMA, agenda=lambda: [], emails=lambda: EMAILS, noticias=lambda: NOTICIAS,
                    saude=lambda: saude, desvios=lambda: [], resumir=_resumir, cidade="Maragogi", timeout=5)


async def falar_simulado(gen, cps: float = 15.0):
    """Faz o papel do TTS: cada frase sai como evento `voz` com o texto, no tempo que levaria para ser dita."""
    async for trecho in gen:
        for frase in [f.strip() for f in re.split(r"(?<=[.!?])\s+", trecho) if f.strip()]:
            bus.emitir("voz", falando=True, estado="falando", texto=frase)
            passos = max(4, int(len(frase) / cps / .12))
            for i in range(passos):
                bus.emitir("voz", falando=True, estado="falando", nivel=round(.35 + .45 * abs(((i * 7) % 10) - 5) / 5, 2), _efemero=True)
                await asyncio.sleep(.12)
    bus.emitir("voz", falando=False, estado="ouvindo")


async def _holo_demo(prompt: str, ctx: str) -> str:
    """Faz o papel do modelo: uma estação espacial de peças (o serviço de verdade pergunta ao Claude/OpenAI);
    na edição, abre as portas dianteiras como dobradiça; no desenho, dá volume com um vaso."""
    if "Pedido do João" in prompt:
        idx = [int(m.group(1)) for m in re.finditer(r"^(\d+): porta dianteira", prompt, re.M)]
        return json.dumps({"ops": [{"op": "girar", "alvo": idx or [0], "valor": [0, 1.1, 0], "pivo": "frente"}], "fala": "Portas dianteiras abertas."})
    if "DESENHOU" in prompt:
        return json.dumps({"titulo": "vaso", "pecas": [
            {"nome": "base", "forma": "cilindro", "pos": [0, -1, 0], "tam": [.8, .2, 0]}, {"nome": "corpo", "forma": "esfera", "pos": [0, 0, 0], "tam": [1.1, 0, 0]},
            {"nome": "gargalo", "forma": "cilindro", "pos": [0, 1.3, 0], "tam": [.35, .9, 0]}, {"nome": "boca", "forma": "toro", "pos": [0, 1.8, 0], "tam": [.4, .08, 0], "rot": [1.5708, 0, 0]}]})
    pecas = [{"nome": "módulo central", "forma": "cilindro", "pos": [0, 0, 0], "tam": [0.5, 3, 0], "rot": [0, 0, 1.5708], "explode": [0, 0, 0]},
             {"nome": "anel habitável", "forma": "toro", "pos": [0, 0, 0], "tam": [1.8, 0.18, 0], "rot": [0, 1.5708, 0], "explode": [0, 1.6, 0]}]
    for i, x in enumerate((-2.2, 2.2)):
        pecas.append({"nome": f"painel {i}", "forma": "caixa", "pos": [x, 0, 0], "tam": [1.4, 0.05, 2.6], "explode": [x, 0, 0]})
        pecas.append({"nome": f"doca {i}", "forma": "esfera", "pos": [x * .7, 0, 0], "tam": [0.35, 0, 0], "explode": [x * .6, -1.2, 0]})
    for i in range(4):
        pecas.append({"nome": f"antena {i}", "forma": "cone", "pos": [0, 0.6 + i * 0.1, (i - 1.5) * 0.6], "tam": [0.08, 0.7, 0], "explode": [0, 2.2, (i - 1.5)]})
    return json.dumps({"pecas": pecas}, ensure_ascii=False)


def app(porta: int = 8792):
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse, FileResponse
    from .rotas import router, ESTADO, ESTATICO
    from .integracao import Jarvis
    a = FastAPI(title="Jarvis demo"); a.include_router(router)
    rostos = Rostos(Path("/tmp/jarvis-demo-rosto.json"))
    saude = Resumo(distancia_km=.1, duracao_min=63, habitual_km=.5, fc_pico=192, estresse=13.6, recuperacao=34, calorias=412, fc_repouso=58)
    from .sentinela import Sentinela, Alvo
    from .integracao import CAPACIDADES_PADRAO
    sent = Sentinela([Alvo("HUD local", f"http://127.0.0.1:{porta}/hud/jarvis"), Alvo("API parada (teste)", "http://127.0.0.1:9/")], intervalo=20)
    j = Jarvis(briefing_demo(), Monitor(rostos, carregar=lambda: saude, espera_rosto=12), rostos, env={"JAIME_JARVIS_ABRIR_TELA": "off"},
               modelo_holo=_holo_demo, sentinela=sent, capacidades=lambda: CAPACIDADES_PADRAO)
    ESTADO.update(jarvis=j, jaime=None)

    @a.on_event("startup")
    async def _sentinela():
        asyncio.create_task(sent.rodar())

    @a.get("/hud/stream")
    async def stream():
        async def gen():
            q = bus.assinar()
            try:
                while True:
                    try:
                        yield f"data: {json.dumps(await asyncio.wait_for(q.get(), 15), ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"
            finally:
                bus.cancelar(q)
        return StreamingResponse(gen(), media_type="text/event-stream")

    @a.get("/hud/vendor/{arquivo}")
    async def vendor(arquivo: str):
        return FileResponse(ESTATICO / "vendor" / Path(arquivo).name)

    @a.get("/hud/sistemas")
    async def sistemas():
        return {"fila": {"itens": []}, "equipe": [{"nome": n, "estado": "vivo"} for n in ("mente", "vigília", "hud", "gemini")],
                "estudo": {"abertos": 1}, "orcamento": {"ativo": False, "total": 0.42, "teto": 0},
                "vontades": {"niveis": {"utilidade": .3, "curiosidade": .59, "maestria": .2, "criação": 1.0, "ordem": .15, "vínculo": .97}, "escolha": {"atividade": "criar"}},
                "humor": {"rotulo": "caloroso"}, "vigia": {"lote": [], "armado": False}, "cerebro": {"trancado": False},
                "ouvido": {"modo": "duplex", "erro": "", "latencia_mediana_ms": 208}, "hermes": "no ar", "sentinela": sent.estado(),
                "proximos": "1. Revisar proposta da BUB\n2. Gravar vídeo da Oldsen\n3. Treino às 18h"}

    async def cena(texto: str):
        g = j.gerador(texto)
        if g is not None:
            await falar_simulado(g)

    @a.post("/hud/falar")
    async def falar(body: dict):
        asyncio.create_task(cena(str(body.get("texto", ""))))
        return {"ok": True}

    @a.post("/hud/voz")
    async def voz(body: dict):
        return {"ok": True}

    @a.get("/demo/{qual}")
    async def demo(qual: str, objeto: str = "Tesla Model X"):
        texto = {"briefing": "me dá o briefing", "monitor": "ativar monitor", "holograma": f"cria um holograma do {objeto}",
                 "estacao": "cria um holograma de uma estação espacial", "capacidades": "qual sua capacidade máxima?",
                 "sistemas": "como estão os sistemas?",
                 "particulas": "modo partículas", "fios": "modo fios", "fecha": "fecha o holograma",
                 "desenho": "quero desenhar", "volume": "dá volume ao desenho", "portas": "abre as portas dianteiras",
                 "desfaz": "desfaz", "stl": "exporta em stl", "imprimir": "manda para impressão com 12 cm"}.get(qual, qual)
        j.briefing.ultimo_dia = ""
        asyncio.create_task(cena(texto))
        return {"ok": True, "texto": texto}

    return a


def main(argv: list[str]) -> None:
    import uvicorn
    porta = int(argv[0]) if argv else 8792
    print(f"Jarvis demo em http://127.0.0.1:{porta}/hud/jarvis  ·  /demo/briefing · /demo/monitor · /demo/holograma")
    uvicorn.run(app(porta), host="127.0.0.1", port=porta, log_level="warning")
