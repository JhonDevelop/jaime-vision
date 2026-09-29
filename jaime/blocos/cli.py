"""`python -m jaime blocos <ação>`

  terminal [url]         cliente de texto (JBP perfil terminal)
  janela [url]           cliente de janelas nativas (Tk), sem navegador
  demo [porta]           servidor mínimo: cockpit + blocos (com exemplos), sem cérebro/voz — porta 8791
  parear <nome>          token de um dispositivo de fora (óculos, visor, tablet) — exige JAIME_SERVER_TOKEN trocado
  modelos                lista modelos, fontes e o resultado do contrato de cada modelo
  contrato               roda o contrato de renderização em todos os modelos (sai 1 se algum falhar)"""
from __future__ import annotations
import asyncio, json, sys
from pathlib import Path

URL = "ws://127.0.0.1:8787/blocos/ws"

EXEMPLOS = [
    {"modelo": "maquina", "ancoragem": {"x": 0.03, "y": 0.12}},
    {"modelo": "relogio", "ancoragem": {"x": 0.03, "y": 0.30}},
    {"id": "bub-semana", "tipo": "grafico", "titulo": "Leads da BUB na semana", "prioridade": 2, "ancoragem": {"x": 0.66, "y": 0.12},
     "conteudo": {"forma": "barras", "series": [{"nome": "leads", "pontos": [["seg", 12], ["ter", 18], ["qua", 9], ["qui", 22], ["sex", 17]]}]}},
    {"id": "hoje", "tipo": "lista", "titulo": "Hoje", "prioridade": 2, "ancoragem": {"x": 0.66, "y": 0.47},
     "conteudo": {"itens": [{"texto": "Revisar proposta da Oldsen", "detalhe": "10h"}, {"texto": "Gravar vídeo #71", "detalhe": "15h"},
                            {"texto": "Enviar orçamento de reforma", "feito": True}]}},
    {"id": "arquitetura", "tipo": "grafo", "titulo": "BUB · arquitetura", "prioridade": 1, "ancoragem": {"x": 0.35, "y": 0.62},
     "conteudo": {"nos": [{"id": "app"}, {"id": "api"}, {"id": "banco"}, {"id": "fila"}],
                  "arestas": [{"de": "app", "para": "api", "rotulo": "chama"}, {"de": "api", "para": "banco"}, {"de": "api", "para": "fila"}]}},
    {"id": "deploy", "tipo": "acoes", "titulo": "Deploy da BUB pronto", "prioridade": 3, "ancoragem": {"x": 0.35, "y": 0.12},
     "conteudo": {"texto": "Testes verdes na branch main.", "botoes": [{"rotulo": "Publicar", "intencao": "publica o deploy da BUB"},
                                                                     {"rotulo": "Ver o diff", "intencao": "mostra o diff do deploy da BUB"}]}},
]


def montar_app_demo(pasta: Path | None = None, exemplos: bool = True):
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from fastapi.responses import FileResponse, PlainTextResponse
    from . import integracao
    from .rotas import router
    estatico = Path(__file__).resolve().parent.parent / "hud" / "static"
    g = integracao.montar(None, pasta=pasta or Path("/tmp/jaime-blocos-demo"), emitir=lambda *a, **k: None, env={})
    m = integracao.ESTADO["modelos"]

    @asynccontextmanager
    async def vida(app):
        if exemplos:
            for d in EXEMPLOS:
                g.abrir({**m.instanciar(d["modelo"]), **{k: v for k, v in d.items() if k != "modelo"}} if "modelo" in d else d, origem="joao")
        t = asyncio.create_task(g.rodar())
        yield
        t.cancel()
    app = FastAPI(lifespan=vida)
    app.include_router(router)

    @app.get("/")
    async def raiz():
        return FileResponse(estatico / "cockpit.html", headers={"Cache-Control": "no-store"})

    @app.get("/hud/stream")
    async def stream():
        return PlainTextResponse(": demo sem bus\n\n", media_type="text/event-stream")

    @app.get("/hud/espacial.js")
    async def esp():
        return PlainTextResponse("", media_type="application/javascript")
    return app


def rodar(acao: str, args: list[str]) -> int:
    if acao == "terminal":
        from .clientes.terminal import rodar as r
        return r(args[0] if args else URL)
    if acao == "janela":
        from .clientes.janela import rodar as r
        return r(args[0] if args else URL)
    if acao == "demo":
        import uvicorn
        porta = int(args[0]) if args else 8791
        print(f"demo de blocos em http://127.0.0.1:{porta}/  ·  terminal: python -m jaime blocos terminal ws://127.0.0.1:{porta}/blocos/ws")
        uvicorn.run(montar_app_demo(), host="127.0.0.1", port=porta, log_level="warning")
        return 0
    if acao == "parear":
        from ..config import settings
        from .integracao import token_dispositivo
        if not args:
            print("uso: python -m jaime blocos parear <nome-do-dispositivo>"); return 2
        if settings.server_token in ("", "troque-isto"):
            print("Troque o JAIME_SERVER_TOKEN no .env antes: com o token padrão, nenhum dispositivo de fora entra."); return 1
        nome = args[0].strip().lower()
        print(f"dispositivo: {nome}\ntoken: {token_dispositivo(settings.server_token, nome)}\n"
              f"conecte em: ws://<ip-desta-máquina>:{settings.port}/blocos/ws?dispositivo={nome}&t=<token>\n"
              "(precisa de JAIME_BIND aberto; trocar o JAIME_SERVER_TOKEN revoga todos os dispositivos)")
        return 0
    if acao in ("modelos", "contrato"):
        from .fontes import padrao
        from .modelo import validar
        from .modelos import Modelos, contrato
        from .integracao import PASTA
        m = Modelos(PASTA, padrao(None))
        falhas = 0
        for nome in m.nomes():
            d = m.receita(nome)
            try:
                erros = contrato(validar({**d, "conteudo": d.get("conteudo") or {"texto": "exemplo", "itens": [{"rotulo": "x", "valor": "1"}]}}))
            except Exception as e:
                erros = [f"{type(e).__name__}: {e}"]
            falhas += bool(erros)
            print(f"{'✘' if erros else '✔'} {nome}" + (f": {'; '.join(erros)}" if erros else ""))
        if acao == "modelos":
            print("\nfontes:", ", ".join(f["nome"] for f in padrao(None).listar()), "(+ as do Jaime vivo)")
        return 1 if falhas else 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(rodar(sys.argv[1] if len(sys.argv) > 1 else "", sys.argv[2:]))
