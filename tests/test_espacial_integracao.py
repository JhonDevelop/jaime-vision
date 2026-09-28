"""Fase 0 — integração com o bus/HUD existentes: flag off não cria nada; flag sim mostra eventos no HUD."""
import asyncio, time
from pathlib import Path
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jaime.hud.events import Bus
from jaime.spatial import integracao
from jaime.spatial.config import ConfigEspacial
from jaime.spatial.rotas import router

RAIZ = Path(__file__).resolve().parent.parent


def _jaime(tmp_path, liberado=True, convidado=""):
    (tmp_path / "20-Projetos").mkdir(parents=True, exist_ok=True)
    for n in ("BUB", "SeventyOne", "INDEX"):
        (tmp_path / "20-Projetos" / f"{n}.md").write_text("conteúdo privado que não pode vazar", encoding="utf-8")
    return SimpleNamespace(s=SimpleNamespace(vault=tmp_path), acesso=SimpleNamespace(liberado=liberado),
                           vigia=SimpleNamespace(convidado=convidado))


def test_config_padrao_e_desligada():
    c = ConfigEspacial.do_ambiente({})
    assert c.modo == "off" and not c.ativo and c.dry_run and c.fila == 2
    assert ConfigEspacial.do_ambiente({"JAIME_SPATIAL": "qualquer-coisa"}).modo == "off"
    assert ConfigEspacial.do_ambiente({"JAIME_SPATIAL": "sim", "JAIME_SPATIAL_FRAME_QUEUE": "99"}).fila == 8


def test_flag_off_nao_cria_servico_nem_rotas_ativas(tmp_path):
    j = _jaime(tmp_path)
    assert integracao.montar(j, ConfigEspacial()) is None
    app = FastAPI(); app.include_router(router)
    with TestClient(app) as c:
        assert c.get("/espacial/estado").json()["ativo"] is False
        assert c.post("/espacial/ligar").status_code == 409     # clique não liga o que a configuração desligou
        assert c.get("/hud/espacial.js").status_code == 200


def test_flag_sim_demo_chega_ao_bus_sem_camera_e_sem_vazar_o_vault(tmp_path):
    bus = Bus()
    j = _jaime(tmp_path)
    s = integracao.montar(j, ConfigEspacial(modo="sim", repetir=False, fila=100_000), emitir=bus.emitir)
    ids = set(s.core.objects)
    assert {"projeto:bub", "projeto:seventyone"} <= ids and "projeto:index" not in ids
    s.fonte = None
    from jaime.spatial.fontes import FonteSequencia
    from jaime.spatial.simulador import cenario, poses
    s.fonte = FonteSequencia(poses(cenario("pinca", s.core)), tempo_real=False)
    async def go():
        await s.iniciar()
        while s.rodando:
            await asyncio.sleep(0.005)
    asyncio.run(go())
    tipos = {e["tipo"] for e in bus.historico}
    kinds = [e.get("evento") for e in bus.historico]
    assert tipos == {"espacial"} and "gesture.grab" in kinds and "spatial.scene" in kinds
    assert all("privado" not in str(e) for e in bus.historico)     # só o NOME da nota vira objeto
    assert j.espacial is s


def test_rotas_estado_kill_switch_selecao_e_latencia(tmp_path):
    bus = Bus()
    j = _jaime(tmp_path)
    s = integracao.montar(j, ConfigEspacial(modo="sim"), emitir=bus.emitir)
    app = FastAPI(); app.include_router(router)
    with TestClient(app) as c:
        r = c.post("/espacial/ligar").json()
        assert r["ativo"] and r["rodando"] and r["modo"] == "sim"
        time.sleep(0.3)
        r = c.post("/espacial/selecionar", json={"id": "projeto:bub"}).json()
        assert r["ok"] and r["ator"] == "joao"
        assert c.post("/espacial/selecionar", json={"id": "nao-existe"}).status_code == 404
        c.post("/espacial/latencia", json={"amostras": [12.5, 20, "lixo", -3, 99999]})
        est = c.get("/espacial/estado").json()
        assert est["metricas"]["evento_render_ms"]["n"] == 2
        r = c.post("/espacial/desligar").json()
        assert r["rodando"] is False and r["parada"] == "desligado no HUD"
    assert s.fonte is None


def test_selecao_pelo_hud_com_cerebro_trancado_nao_vira_do_dono(tmp_path):
    j = _jaime(tmp_path, liberado=False)
    integracao.montar(j, ConfigEspacial(modo="sim"), emitir=Bus().emitir)
    app = FastAPI(); app.include_router(router)
    with TestClient(app) as c:
        assert c.post("/espacial/selecionar", json={"id": "projeto:bub"}).json()["ator"] == "desconhecido"


def test_servidor_e_cockpit_estao_ligados_a_camada_espacial():
    server = (RAIZ / "jaime" / "server.py").read_text(encoding="utf-8")
    assert "montar_espacial(jaime)" in server and "espacial_router" in server and 'espacial.parar(' in server
    cockpit = (RAIZ / "jaime" / "hud" / "static" / "cockpit.html").read_text(encoding="utf-8")
    assert "/hud/espacial.js" in cockpit and "case 'espacial'" in cockpit
    js = (RAIZ / "jaime" / "hud" / "static" / "espacial.js").read_text(encoding="utf-8")
    assert "if (!e.ativo) return" in js           # com a flag off o JS não instala nada


def test_mcp_espacial_so_entra_nas_opcoes_com_a_flag_ligada(tmp_path):
    from jaime.orchestrator.jaime import Jaime
    j = Jaime.__new__(Jaime)
    assert j._servidor_espacial() == {}                       # flag off: nada de MCP novo
    jj = _jaime(tmp_path)
    s = integracao.montar(jj, ConfigEspacial(modo="sim"), emitir=Bus().emitir)
    j.espacial, j.espacial_acoes, j.espacial_voz = s, jj.espacial_acoes, jj.espacial_voz
    assert set(j._servidor_espacial()) == {"espacial"}
    integracao.montar(jj, ConfigEspacial())                    # desligar limpa o estado global das rotas
    assert integracao.ESTADO["acoes"] is None and integracao.ESTADO["servico"] is None
