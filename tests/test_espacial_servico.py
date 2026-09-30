"""Fase 0/1 — serviço espacial com simulador e replay: sem câmera, sem SO, sem LLM."""
import asyncio, time
import pytest
from jaime.hud.events import Bus
from jaime.spatial.config import ConfigEspacial
from jaime.spatial.core import SpatialCore
from jaime.spatial.fontes import FonteSequencia, RastreadorIdentidade
from jaime.spatial.filtro import OneEuro
from jaime.spatial.landmarks import CameraFrame, razao_pinca
from jaime.spatial.servico import ServicoEspacial
from jaime.spatial.simulador import cenario, gravar, ler, mao_sintetica, objetos_demo, poses, Quadro


class Coletor:
    def __init__(self):
        self.eventos = []

    def __call__(self, tipo, _efemero=False, **d):
        self.eventos.append({"tipo": tipo, "_efemero": _efemero, **d})

    def kinds(self):
        return [e["evento"] for e in self.eventos if e["tipo"] == "espacial"]


def _rodar(nome, modo="sim", **kw):
    core = SpatialCore()
    for o in objetos_demo():
        core.add(o)
    seq = poses(cenario(nome, core), ruido=kw.pop("ruido", 0.0))
    col = Coletor()
    cfg = ConfigEspacial(modo=modo, repetir=False, hz_efemero=1000, fila=100_000)   # sem tempo real: fila grande, sem descarte
    s = ServicoEspacial(cfg, emitir=col, core=core, fonte=FonteSequencia(seq, tempo_real=False), **kw)

    async def go():
        await s.iniciar()
        for _ in range(400):
            if not s.rodando:
                break
            await asyncio.sleep(0.005)
        await s.parar("fim do teste")
    asyncio.run(go())
    return s, col


def test_mao_sintetica_tem_a_pinca_pedida():
    lm = mao_sintetica(0.3, 0.4, 0.12)
    assert len(lm) == 21 and abs(razao_pinca(lm) - 0.12) < 1e-6


def test_pinca_seleciona_arrasta_e_solta_so_no_hud():
    s, col = _rodar("pinca")
    k = col.kinds()
    assert "spatial.select" in k and "gesture.grab" in k and "gesture.drag" in k and "gesture.release" in k
    assert k.index("gesture.grab") < k.index("gesture.release")
    grab = next(e for e in col.eventos if e.get("evento") == "gesture.grab")
    assert grab["object_id"] == "projeto:bub" and grab["actor"] == "demo"
    # o objeto foi arrastado de (0.2, 0.35) para perto de (0.5, 0.65) — só no HUD
    o = s.core.objects["projeto:bub"]
    assert abs(o.position.x - 0.5) < 0.05 and abs(o.position.y - 0.65) < 0.05
    assert s.metricas.frames > 30 and not s.erro


def test_pinca_parcial_na_zona_morta_nao_dispara():
    _, col = _rodar("parcial")
    assert not {"gesture.grab", "gesture.click", "spatial.select"} & set(col.kinds())


def test_tremor_na_fronteira_nao_vira_clique():
    core = SpatialCore()
    for o in objetos_demo():
        core.add(o)
    a = core.objects["projeto:bub"].position
    qs = [Quadro(i / 30, a.x, a.y, 0.26 if i % 2 else 0.45) for i in range(60)]   # abre/fecha a cada frame
    col = Coletor()
    s = ServicoEspacial(ConfigEspacial(modo="sim", repetir=False, hz_efemero=1000), emitir=col, core=core,
                        fonte=FonteSequencia(poses(qs, fps=30), tempo_real=False))
    s.cfg.fila = 100_000
    async def go():
        await s.iniciar()
        while s.rodando:
            await asyncio.sleep(0.005)
    asyncio.run(go())
    assert "gesture.grab" not in col.kinds()


def test_clique_rapido_e_parado():
    _, col = _rodar("clique")
    k = col.kinds()
    assert "gesture.click" in k
    clique = next(e for e in col.eventos if e.get("evento") == "gesture.click")
    assert clique["object_id"] == "projeto:seventyone"


def test_perda_de_rastreamento_cancela_e_devolve_o_objeto():
    s, col = _rodar("perda")
    k = col.kinds()
    assert "spatial.tracking_lost" in k and "gesture.cancel" in k and "gesture.release" not in k
    o = s.core.objects["projeto:bub"]
    assert abs(o.position.x - 0.2) < 1e-6 and abs(o.position.y - 0.35) < 1e-6   # cancelar = desfazer o arrasto


def test_duas_maos_escalam_com_limite():
    s, col = _rodar("duas_maos")
    escalas = [e["data"]["scale"] for e in col.eventos if e.get("evento") == "gesture.scale"]
    assert escalas and max(escalas) > 1.5 and max(escalas) <= 4.0


def test_eventos_de_cursor_e_arrasto_nao_poluem_o_historico_do_bus():
    bus = Bus()
    core = SpatialCore()
    for o in objetos_demo():
        core.add(o)
    s = ServicoEspacial(ConfigEspacial(modo="sim", repetir=False, fila=100_000), emitir=bus.emitir, core=core,
                        fonte=FonteSequencia(poses(cenario("pinca", core)), tempo_real=False))
    q = bus.assinar()
    async def go():
        await s.iniciar()
        while s.rodando:
            await asyncio.sleep(0.005)
    asyncio.run(go())
    hist = [e.get("evento") for e in bus.historico]
    assert "spatial.cursor" not in hist and "gesture.drag" not in hist
    assert "gesture.grab" in hist and "gesture.release" in hist
    assert q.qsize() > len(bus.historico)          # os assinantes receberam também os efêmeros


def test_fila_bounded_descarta_o_frame_mais_velho():
    """Rastreador lento (20 ms) e câmera a 200 fps: a fila nunca passa de 2 e a latência não cresce sem fim."""
    class Lento(RastreadorIdentidade):
        def detect(self, frame):
            time.sleep(0.02); return list(frame.poses or [])
    core = SpatialCore()
    for o in objetos_demo():
        core.add(o)
    seq = poses(cenario("pinca", core), fps=200)
    col = Coletor()
    s = ServicoEspacial(ConfigEspacial(modo="camera", fila=2, repetir=False), emitir=col, core=core,
                        fonte=FonteSequencia(seq, tempo_real=True), rastreador=Lento())
    async def go():
        await s.iniciar()
        while s.rodando:
            assert s._fila is None or s._fila.qsize() <= 2
            await asyncio.sleep(0.002)
    asyncio.run(go())
    m = s.metricas.resumo()
    assert m["descartados"] > 0
    assert m["fila_ms"]["p95"] < 150           # sem fila bounded seriam segundos de atraso


def test_camera_real_sem_dono_suspende_sem_rodar_o_rastreador():
    chamadas = []
    class Espiao(RastreadorIdentidade):
        def detect(self, frame):
            chamadas.append(frame.frame_id); return []
    core = SpatialCore()
    col = Coletor()
    seq = poses([Quadro(0, .5, .5, .6), Quadro(0.3, .5, .5, .6)])
    s = ServicoEspacial(ConfigEspacial(modo="camera", repetir=False), emitir=col, core=core,
                        fonte=FonteSequencia(seq, tempo_real=False), rastreador=Espiao(), dono_ok=lambda: False)
    async def go():
        await s.iniciar()
        while s.rodando:
            await asyncio.sleep(0.005)
    asyncio.run(go())
    assert chamadas == []
    assert any(e.get("evento") == "spatial.estado" and e.get("suspenso") for e in col.eventos)


def test_kill_switch_solta_a_fonte_e_cancela_as_tasks():
    core = SpatialCore()
    for o in objetos_demo():
        core.add(o)
    fonte = FonteSequencia(poses(cenario("demo", core)), tempo_real=True, repetir=True)
    s = ServicoEspacial(ConfigEspacial(modo="sim"), emitir=Coletor(), core=core, fonte=fonte)
    async def go():
        await s.iniciar()
        await asyncio.sleep(0.2)
        tasks = list(s._tasks)
        st = await s.desligar_rastreamento("João disse para parar")
        assert all(t.done() for t in tasks)
        return st
    st = asyncio.run(go())
    assert fonte._fechada and not st["rodando"] and st["parada"] == "João disse para parar"


def test_fonte_que_cai_emite_tracking_lost_e_erro():
    class Quebra:
        camera_id = "0"
        async def frames(self):
            for i, (t, ps) in enumerate(poses(cenario("pinca", core))[:30]):
                yield CameraFrame("0", i, time.monotonic(), poses=ps, media_ts=t)
            raise RuntimeError("USB desconectado")
        def fechar(self):
            pass
    core = SpatialCore()
    for o in objetos_demo():
        core.add(o)
    col = Coletor()
    s = ServicoEspacial(ConfigEspacial(modo="sim", fila=100_000), emitir=col, core=core, fonte=Quebra())
    async def go():
        await s.iniciar()
        while s.rodando:
            await asyncio.sleep(0.005)
    asyncio.run(go())
    assert "USB desconectado" in s.erro
    assert "spatial.tracking_lost" in col.kinds()


def test_replay_jsonl_so_landmarks(tmp_path):
    seq = poses(cenario("clique"))
    p = gravar(seq, tmp_path / "sessao.jsonl")
    texto = p.read_text()
    assert "pixels" not in texto and "png" not in texto
    lido = ler(p)
    assert len(lido) == len(seq) and lido[10][1][0].landmarks[8] == pytest.approx(seq[10][1][0].landmarks[8], abs=1e-4)


def test_one_euro_tira_tremor_sem_atrasar_muito():
    import random
    rng = random.Random(1)
    f = OneEuro()
    bruto = [0.5 + rng.gauss(0, 0.004) for i in range(90)]
    parado = [f(v, i / 30) for i, v in enumerate(bruto)]
    amp_bruta = max(bruto[30:]) - min(bruto[30:])
    amp_filtrada = max(parado[30:]) - min(parado[30:])
    assert amp_filtrada < 0.5 * amp_bruta
    # degrau de 0,3: em 5 frames (167 ms) o filtro já percorreu mais de 85% do caminho
    g = OneEuro()
    for i in range(30):
        g(0.2, i / 30)
    ys = [g(0.5, 1 + i / 30) for i in range(1, 6)]
    assert ys[-1] > 0.2 + 0.85 * 0.3
