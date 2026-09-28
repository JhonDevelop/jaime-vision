"""`python -m jaime espacial <ação>` — demo, medição e inventário sem subir o servidor.

  demo [cenário]            roda o simulador (sem câmera) e imprime os eventos + métricas
  bench [segundos]          simulação em TEMPO REAL a 30 fps: p50/p95 captura→evento do caminho quente
  gravar <cenário> <arq>    grava um cenário sintético em JSONL (só landmarks) para replay
  replay <arquivo.jsonl>    reproduz um JSONL e imprime os eventos
  inventario                SO/CPU/GPU/VRAM/câmeras/monitores/engines/frota (só leitura; sem segredos)
  hud [porta]               cockpit + camada espacial em modo sim, SEM cérebro/voz (porta 8788; não mexe no serviço da 8787)
  cenarios                  lista os cenários"""
from __future__ import annotations
import asyncio, json, sys
from pathlib import Path


def _rodar_servico(fonte, cenario_objs=True, tempo_real=False, espera_max=120.0):
    from .config import ConfigEspacial
    from .core import SpatialCore
    from .servico import ServicoEspacial
    from .simulador import objetos_demo
    core = SpatialCore()
    for o in objetos_demo():
        core.add(o)
    eventos = []
    cfg = ConfigEspacial(modo="sim", repetir=False, fila=2 if tempo_real else 100_000)
    s = ServicoEspacial(cfg, emitir=lambda tipo, _efemero=False, **d: eventos.append(d), core=core,
                        fonte=fonte(core) if callable(fonte) else fonte)

    async def go():
        await s.iniciar()
        t = 0.0
        while s.rodando and t < espera_max:
            await asyncio.sleep(0.02); t += 0.02
        await s.parar("fim")
    asyncio.run(go())
    return s, eventos


def _imprimir(eventos, metricas):
    for e in eventos:
        k = e.get("evento")
        if k in ("spatial.cursor", "gesture.drag", "gesture.hover"):
            continue
        extra = e.get("data") or {}
        print(f"  {k:24} obj={e.get('object_id') or '-':22} ator={e.get('actor', '-'):6} {json.dumps(extra, ensure_ascii=False) if extra else ''}")
    print(json.dumps(metricas, ensure_ascii=False, indent=1))


def rodar(acao: str, args: list[str]) -> int:
    from .fontes import FonteSequencia, FonteReplay
    from .simulador import cenario, poses, gravar, CENARIOS
    if acao in ("check", "cenarios"):
        print("cenários:", ", ".join(CENARIOS)); print(__doc__); return 0
    if acao == "demo":
        nome = args[0] if args else "demo"
        s, ev = _rodar_servico(lambda core: FonteSequencia(poses(cenario(nome, core), ruido=0.002), tempo_real=False))
        print(f"cenário '{nome}' — sem câmera, sem ação no SO:")
        _imprimir(ev, s.metricas.resumo()); return 0 if not s.erro else 1
    if acao == "bench":
        seg = float(args[0]) if args else 10.0
        def fonte(core):
            seq = poses(cenario("demo", core), ruido=0.002)
            dur = seq[-1][0] + 0.1
            voltas = max(1, int(seg / dur + 0.999))
            longa = [(t + i * dur, ps) for i in range(voltas) for t, ps in seq]
            return FonteSequencia(longa, tempo_real=True)
        s, _ = _rodar_servico(fonte, tempo_real=True, espera_max=seg + 30)
        m = s.metricas.resumo()
        print(json.dumps({"segundos": seg, "fps_alvo": 30, **m}, ensure_ascii=False, indent=1)); return 0
    if acao == "gravar":
        if len(args) < 2:
            print("uso: python -m jaime espacial gravar <cenário> <arquivo.jsonl>"); return 2
        from .core import SpatialCore
        from .simulador import objetos_demo
        core = SpatialCore()
        for o in objetos_demo():
            core.add(o)
        p = gravar(poses(cenario(args[0], core)), Path(args[1]))
        print(f"✔ {p}"); return 0
    if acao == "replay":
        if not args:
            print("uso: python -m jaime espacial replay <arquivo.jsonl>"); return 2
        s, ev = _rodar_servico(FonteReplay(args[0], tempo_real=False))
        _imprimir(ev, s.metricas.resumo()); return 0 if not s.erro else 1
    if acao == "inventario":
        from .inventario import coletar
        try:
            from ..config import settings
            vault = settings.vault
        except Exception:
            vault = None
        print(json.dumps(coletar(vault), ensure_ascii=False, indent=1)); return 0
    if acao == "hud":
        return _hud(int(args[0]) if args else 8788)
    print(__doc__); return 2


def montar_app_demo(modo: str = "sim", cenario_nome: str = "demo"):
    """Um FastAPI mínimo: cockpit + /hud/stream do bus + rotas espaciais. Sem Jaime, sem voz, sem vault."""
    import json as _json
    from fastapi import FastAPI
    from fastapi.responses import FileResponse, StreamingResponse
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from ..hud.events import bus
    from .config import ConfigEspacial
    from .integracao import montar
    from .rotas import router
    estatico = Path(__file__).resolve().parent.parent / "hud" / "static"
    falso = SimpleNamespace(s=SimpleNamespace(vault=None), acesso=SimpleNamespace(liberado=True), vigia=SimpleNamespace(convidado=""))
    cfg = ConfigEspacial(modo=modo, cenario=cenario_nome, repetir=True)

    @asynccontextmanager
    async def vida(app):
        s = montar(falso, cfg)
        await s.iniciar()
        yield
        await s.parar("demo encerrada")
    app = FastAPI(lifespan=vida)
    app.include_router(router)

    @app.get("/")
    async def raiz():
        return FileResponse(estatico / "cockpit.html", headers={"Cache-Control": "no-store"})

    @app.get("/hud/stream")
    async def stream():
        async def gen():
            q = bus.assinar()
            try:
                while True:
                    try:
                        evt = await asyncio.wait_for(q.get(), timeout=15)
                        yield f"data: {_json.dumps(evt, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"
            finally:
                bus.cancelar(q)
        return StreamingResponse(gen(), media_type="text/event-stream")
    return app


def _hud(porta: int) -> int:
    import uvicorn
    print(f"demo espacial em http://127.0.0.1:{porta}/ — sem câmera, sem cérebro, sem ação no SO. Ctrl+C encerra.")
    uvicorn.run(montar_app_demo(), host="127.0.0.1", port=porta, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(rodar(sys.argv[1] if len(sys.argv) > 1 else "check", sys.argv[2:]))
