"""Fase 7 — ensinar gesto: positivos, negativos, validação separada, falsos/hora, ambiguidade, remoção."""
import json, math, random
import pytest
from jaime.spatial.gestos_pessoais import Treinador

rng = random.Random(11)


def traj(forma, n=20, ruido=0.015, escala=None, desloc=None):
    esc = escala if escala is not None else rng.uniform(0.7, 1.3)
    dx, dy = desloc if desloc is not None else (rng.uniform(0, 0.5), rng.uniform(0, 0.5))
    pts = []
    for i in range(n):
        u = i / (n - 1)
        if forma == "z":            # Z: direita, diagonal para baixo-esquerda, direita
            x, y = (3 * u, 0) if u < 1 / 3 else ((1 - (u - 1 / 3) * 3) * 1, (u - 1 / 3) * 3) if u < 2 / 3 else ((u - 2 / 3) * 3, 1)
        elif forma == "v":          # V: desce e sobe
            x, y = u, (2 * u if u < 0.5 else 2 - 2 * u)
        elif forma == "circulo":
            x, y = 0.5 + 0.5 * math.cos(2 * math.pi * u), 0.5 + 0.5 * math.sin(2 * math.pi * u)
        elif forma == "reta":       # o movimento mais comum: arrastar para a direita
            x, y = u, 0.02 * math.sin(6 * u)
        else:                       # rabisco aleatório (movimento do dia a dia)
            x, y = rng.random(), rng.random()
        pts.append((dx + esc * x + rng.gauss(0, ruido), dy + esc * y + rng.gauss(0, ruido)))
    return pts


def fluxo_comum(n=240):
    """Uma "hora" de movimentos comuns: retas, rabiscos, circulares lentos — janelas de 20 pontos."""
    return [traj(rng.choice(["reta", "rabisco", "reta", "rabisco"])) for _ in range(n)]


def _ensinar(t, nome, forma, acao="hud:arquivar", pos=8, neg="reta"):
    t.iniciar(nome, acao, ["hud"], consentimento=True)
    for _ in range(pos):
        t.exemplo(nome, traj(forma))
    for _ in range(3):
        t.exemplo(nome, traj(neg), negativo=True)


def test_ensina_valida_ativa_reconhece_e_rejeita_negativo(tmp_path):
    t = Treinador(tmp_path / "gestos.json")
    _ensinar(t, "arquivar", "z")
    m = t.avaliar("arquivar", fluxo_comum(), horas_fluxo=1.0)
    assert m["pronto"] and m["recall"] >= 0.8 and m["precisao"] >= 0.95 and m["fp_hora"] is not None
    ok, msg = t.ativar("arquivar")
    assert ok and "Aprendi 'arquivar'" in msg
    assert t.reconhecer(traj("z"))[0] == "arquivar"
    assert t.reconhecer(traj("reta"))[0] is None
    assert t.reconhecer(traj("z"), contexto="terminal")[0] is None     # fora do contexto escolhido


def test_gesto_parecido_com_um_ativo_e_recusado(tmp_path):
    t = Treinador(tmp_path / "g.json")
    _ensinar(t, "arquivar", "z"); t.avaliar("arquivar", fluxo_comum(), 1.0); assert t.ativar("arquivar")[0]
    _ensinar(t, "arquivar2", "z")
    t.avaliar("arquivar2", fluxo_comum(), 1.0)
    ok, msg = t.ativar("arquivar2")
    assert not ok and ("ambíguo" in msg or "precisão" in msg or "reconheci" in msg)


def test_dois_gestos_distintos_convivem(tmp_path):
    t = Treinador(tmp_path / "g.json")
    _ensinar(t, "arquivar", "z"); t.avaliar("arquivar", fluxo_comum(), 1.0); assert t.ativar("arquivar")[0]
    _ensinar(t, "marcar", "v", acao="select"); t.avaliar("marcar", fluxo_comum(), 1.0)
    ok, msg = t.ativar("marcar")
    assert ok, msg
    assert t.reconhecer(traj("v"))[0] == "marcar" and t.reconhecer(traj("z"))[0] == "arquivar"


@pytest.mark.parametrize("acao", ["move_to_trash", "delete_forever", "run_command", "send", "publish", "install", "edit_file", "qualquer"])
def test_gesto_nunca_concede_privilegio(tmp_path, acao):
    with pytest.raises(PermissionError):
        Treinador(tmp_path / "g.json").iniciar("perigo", acao, consentimento=True)


def test_sem_consentimento_nao_grava_e_poucos_exemplos_nao_ativam(tmp_path):
    t = Treinador(tmp_path / "g.json")
    with pytest.raises(PermissionError):
        t.iniciar("x", "select")
    assert not (tmp_path / "g.json").exists()
    t.iniciar("x", "select", consentimento=True)
    for _ in range(3):
        t.exemplo("x", traj("v"))
    assert not t.avaliar("x")["pronto"] and not t.ativar("x")[0]


def test_sem_medir_falsos_por_hora_nao_ativa(tmp_path):
    t = Treinador(tmp_path / "g.json")
    _ensinar(t, "arquivar", "z")
    t.avaliar("arquivar")                               # sem fluxo comum
    ok, msg = t.ativar("arquivar")
    assert not ok and "falsas ativações" in msg


def test_remover_apaga_os_exemplos_do_disco_e_so_guarda_landmarks(tmp_path):
    arq = tmp_path / "g.json"
    t = Treinador(arq)
    _ensinar(t, "arquivar", "z")
    d = json.loads(arq.read_text())
    assert d["formato"] == "jaime.spatial.gestos" and set(d["gestos"][0]) >= {"positivos", "negativos"}
    assert "pixels" not in arq.read_text() and "png" not in arq.read_text()
    assert t.remover("arquivar")
    assert json.loads(arq.read_text())["gestos"] == [] and Treinador(arq).gestos == {}


def test_novo_exemplo_desativa_ate_reavaliar(tmp_path):
    t = Treinador(tmp_path / "g.json")
    _ensinar(t, "arquivar", "z"); t.avaliar("arquivar", fluxo_comum(), 1.0); t.ativar("arquivar")
    t.exemplo("arquivar", traj("z"))
    assert not t.gestos["arquivar"].ativo and t.reconhecer(traj("z"))[0] is None
