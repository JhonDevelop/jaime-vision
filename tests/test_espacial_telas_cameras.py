"""Fases 4 e 5 — monitores (geometria lógica, hotplug, alvo por monitor, calibração) e multicâmera (DLT)."""
import numpy as np
import pytest
from jaime.spatial.core import Vec3
from jaime.spatial.geometry import CameraObservation
from jaime.spatial.multicamera import Triangulador, camera_sintetica, carregar, parear, salvar, triangular
from jaime.spatial.telas import (Display, VigiaTelas, carregar_calibracao, destino_janela, display_em, escolher,
                                 espelhados, impressao, salvar_calibracao)

# Mac com Retina embutido (escala 2) à esquerda, 4K externo em escala 1,5 no meio e 1080p girado à direita
EMB = Display("emb", "embutido", -1440, 180, 1440, 900, 2.0, 0, False, True)
MEIO = Display("4k", "externo 1", 0, 0, 2560, 1440, 1.5, 0, True, False)
DIR = Display("vert", "externo 2", 2560, -240, 1080, 1920, 1.0, 90, False, False)
TRES = [EMB, MEIO, DIR]


def test_display_em_com_coordenadas_negativas_e_escala_mista():
    assert display_em(TRES, -10, 500) is EMB and display_em(TRES, 100, 100) is MEIO and display_em(TRES, 3000, -100) is DIR
    assert display_em(TRES, -2000, 0) is None


def test_impressao_muda_com_escala_rotacao_e_conjunto():
    h = impressao(TRES)
    assert impressao(list(reversed(TRES))) == h                            # ordem não importa
    assert impressao([EMB, MEIO, Display(**{**DIR.__dict__, "rotacao": 0})]) != h
    assert impressao([EMB, Display(**{**MEIO.__dict__, "escala": 2.0}), DIR]) != h
    assert impressao([EMB, MEIO]) != h


def test_espelhamento_detectado():
    assert espelhados([MEIO, Display("x", "clone", 0, 0, 2560, 1440)]) and not espelhados(TRES)


def test_escolher_monitor_relativo():
    assert escolher(TRES, "direita", MEIO) is DIR and escolher(TRES, "esquerda", MEIO) is EMB
    assert escolher(TRES, "direita", DIR) is None and escolher(TRES, "principal") is MEIO
    assert escolher(TRES, "embutido") is EMB and escolher(TRES, "vert") is DIR


def test_destino_mantem_posicao_relativa_e_cabe_na_tela():
    x, y = destino_janela((1280, 720, 800, 600), MEIO, DIR)       # meio do 4K → meio (relativo) do vertical
    assert DIR.contem(x, y) and DIR.contem(x + 799, y + 599)
    x, y = destino_janela((2400, 1300, 800, 600), MEIO, EMB)     # canto inferior direito: não pode sair da tela
    assert EMB.contem(x, y) and x + 800 <= EMB.x + EMB.largura + 1 and y + 600 <= EMB.y + EMB.altura + 1


def test_hotplug_girar_e_desplugar_suspendem_ate_validar():
    layout = [list(TRES)]
    avisos = []
    vt = VigiaTelas(backend=lambda: layout[0], ao_mudar=avisos.append)
    assert vt.checar() is None and not vt.suspenso
    layout[0] = [EMB, MEIO]                                        # desplugou o vertical no meio do uso
    ev = vt.checar()
    assert ev["saiu"] == ["vert"] and vt.suspenso and avisos
    vt.validar(); assert not vt.suspenso
    layout[0] = [EMB, Display(**{**MEIO.__dict__, "escala": 2.0})]   # mudou a escala
    assert vt.checar() and vt.suspenso


def test_sem_backend_de_monitores_fica_suspenso():
    assert VigiaTelas(backend=lambda: []).suspenso


def test_calibracao_vale_so_para_o_mesmo_layout(tmp_path):
    arq = tmp_path / "calib.json"
    salvar_calibracao(arq, TRES, {"4k": {"origem": [0, 0, 0], "direita": [0.6, 0, 0], "baixo": [0, 0.34, 0]}})
    planos, motivo = carregar_calibracao(arq, TRES)
    assert not motivo and planos["4k"].pixel_from_room(Vec3(0.3, 0.17, 0.0)) == (1280, 720)
    planos, motivo = carregar_calibracao(arq, [EMB, MEIO])
    assert planos == {} and "outro layout" in motivo


# ── multicâmera ──────────────────────────────────────────────────────────────
def _par():
    a = camera_sintetica("a", (-0.4, -0.2, -1.0), (0, 0, 0.3))
    b = camera_sintetica("b", (0.4, -0.2, -1.0), (0, 0, 0.3))
    return a, b


def test_dlt_recupera_ponto_com_ruido_de_1px_em_menos_de_1cm():
    a, b = _par()
    rng = np.random.default_rng(3)
    erros = []
    for _ in range(200):
        X = rng.uniform([-0.3, -0.3, 0.1], [0.3, 0.3, 0.6])
        obs = [(c.P, tuple(np.array(c.projetar(X)) + rng.normal(0, 1.0, 2))) for c in (a, b)]
        erros.append(np.linalg.norm(triangular(obs) - X))
    assert np.percentile(erros, 95) < 0.01


def test_triangulador_3d_sincronizado_e_fallback_2d():
    a, b = _par()
    X = np.array([0.1, 0.05, 0.3])
    oa = CameraObservation("a", 1.000, 10, a.projetar(X), 0.9)
    ob = CameraObservation("b", 1.010, 17, b.projetar(X), 0.9)
    t = Triangulador([a, b])
    r = t.ponto([oa, ob])
    assert r.modo == "3d" and r.pos.distance(Vec3(*X)) < 1e-6 and r.erro_px < 0.01
    atrasada = CameraObservation("b", 1.080, 19, b.projetar(X), 0.9)
    r = t.ponto([oa, atrasada])
    assert r.modo == "2d" and "sincronia" in r.motivo and r.pos.z == 0.0      # sem profundidade inventada
    r = t.ponto([oa])
    assert r.modo == "2d" and "uma câmera" in r.motivo
    r = t.ponto([oa, CameraObservation("b", 1.01, 17, b.projetar(X), 0.3)])   # oclusão: confiança baixa
    assert r.modo == "2d"


def test_calibracao_errada_rejeitada_pela_reprojecao():
    a, b = _par()
    X = np.array([0.1, 0.05, 0.3])
    oa = CameraObservation("a", 1.0, 10, a.projetar(X), 0.9)
    ob = CameraObservation("b", 1.0, 10, b.projetar(X), 0.9)
    # calibração da câmera b "velha": alguém esbarrou e ela girou 2 graus para o lado (pan)
    ang = np.radians(2); Ry = np.array([[np.cos(ang), 0, np.sin(ang)], [0, 1, 0], [-np.sin(ang), 0, np.cos(ang)]])
    b_velha = camera_sintetica("b", (0.4, -0.2, -1.0), (0, 0, 0.3)); b_velha.R = Ry @ b_velha.R
    b_velha.t = -b_velha.R @ np.array([0.4, -0.2, -1.0])
    tri = Triangulador([a, b_velha]); tri.cams["c"] = camera_sintetica("c", (0, -0.6, -1.0), (0, 0, 0.3))
    c = tri.cams["c"]
    r = tri.ponto([oa, ob, CameraObservation("c", 1.0, 10, c.projetar(X), 0.9)])
    assert r.modo == "2d" and "reprojeção" in r.motivo


def test_versao_de_calibracao_diferente_nao_triangula(tmp_path):
    a, b = _par()
    X = np.array([0.0, 0.0, 0.3])
    obs = [CameraObservation("a", 1.0, 1, a.projetar(X), 0.9), CameraObservation("b", 1.0, 1, b.projetar(X), 0.9)]
    assert Triangulador([a, b]).ponto(obs, {"a": 1, "b": 2}).modo == "2d"
    p = salvar([a, b], tmp_path / "cams.json")
    a2, b2 = carregar(p)
    assert np.allclose(a2.P, a.P) and Triangulador([a2, b2]).ponto(obs).modo == "3d"


def test_parear_cameras_com_fps_desigual():
    a = [CameraObservation("a", i / 30, i, (0, 0), 0.9) for i in range(30)]       # 30 fps
    b = [CameraObservation("b", i / 60 + 0.004, i, (0, 0), 0.9) for i in range(60)]   # 60 fps, defasada 4 ms
    grupos = parear({"a": a, "b": b}, 0.01)
    assert len(grupos) == 30 and all(abs(g[0].timestamp - g[1].timestamp) <= 0.01 for g in grupos)
    assert len({id(g[1]) for g in grupos}) == 30
