"""Mãos controlando o computador: direita = mouse, esquerda = rolagem, calibração, ensaio, segurança."""
import pytest
from jaime.jarvis.controle_maos import ControleMaos, razao, fechada, aberta, FECHA, ABRE
from jaime.jarvis.mouse_so import MouseNulo

OFF = [-0.16, -0.04, 0.0, 0.04, 0.08]


def mao(x, y, pose="aberta"):
    """21 pontos em coordenadas da imagem crua. poses: aberta, pinca, medio, punho."""
    L = [None] * 21
    L[0] = (x, y + 0.2)
    for f in range(5):
        for k in range(1, 5):
            dobrado = pose == "punho" or (pose == "pinca" and f in (0, 1)) or (pose == "medio" and f in (0, 2))
            if dobrado and pose == "punho":
                yy = {1: 0.14, 2: 0.10, 3: 0.13, 4: 0.16}[k]
                L[f * 4 + k] = (x + OFF[f], y + yy)
            else:
                L[f * 4 + k] = (x + OFF[f], y + 0.2 - 0.06 * k)
    if pose == "pinca":
        L[8], L[4], L[7], L[6], L[3] = (x - .02, y + .02), (x - .025, y + .025), (x - .03, y + .05), (x - .035, y + .09), (x - .08, y + .08)
    if pose == "medio":
        L[12], L[4], L[3] = (x - .06, y + .03), (x - .065, y + .035), (x - .1, y + .08)
    return [list(p) for p in L]


def test_geometria_das_poses():
    assert razao(mao(.5, .5, "pinca")) < FECHA < ABRE < razao(mao(.5, .5, "aberta"))
    assert razao(mao(.5, .5, "medio"), 12) < FECHA and razao(mao(.5, .5, "medio")) > ABRE
    assert fechada(mao(.5, .5, "punho")) and not fechada(mao(.5, .5, "pinca")) and aberta(mao(.5, .5, "aberta"))


class Relogio:
    def __init__(self): self.t = 100.0
    def __call__(self): return self.t


def _c(tmp_path, calib=True, **kw):
    m = MouseNulo(area=(0, 0, 2000, 1000))
    ev = []
    r = Relogio()
    c = ControleMaos(mouse=m, emitir=lambda t, **d: ev.append((t, d)), arquivo=tmp_path / "maos.json", relogio=r, env={}, **kw)
    if calib:
        c.calib = {"u0": .2, "v0": .2, "u1": .8, "v1": .8}
    return c, m, ev, r


def _passos(c, r, seq, dt=1 / 30):
    for maos in seq:
        r.t += dt
        c.receber(maos, r.t)


def D(x, y, pose="aberta"):
    return {"lado": "direita", "p": mao(x, y, pose)}


def E(x, y, pose="aberta"):
    return {"lado": "esquerda", "p": mao(x, y, pose)}


def test_move_e_clica(tmp_path):
    c, m, ev, r = _c(tmp_path)
    assert "ligado" in c.ligar() and not c.ensaio
    _passos(c, r, [[D(.5, .5)]] * 20)
    x, y = m.pos
    assert 1080 < x < 1190 and 680 < y < 790             # base do indicador (u=.54, v=.64) na área .2–.8
    _passos(c, r, [[D(.5, .5, "pinca")]] * 3 + [[D(.5, .5)]] * 2)
    assert ("apertar", "esquerdo", 1) in m.log and ("soltar", "esquerdo", 1) in m.log and c.contagem["cliques"] == 1
    _passos(c, r, [[D(.5, .5, "pinca")]] * 3 + [[D(.5, .5)]] * 2)
    assert ("apertar", "esquerdo", 2) in m.log            # segunda pinça logo em seguida = clique duplo


def test_espelho_mao_para_direita_cursor_para_direita(tmp_path):
    c, m, ev, r = _c(tmp_path)
    c.ligar()
    _passos(c, r, [[D(.6, .5)]] * 30)
    x1 = m.pos[0]
    _passos(c, r, [[D(.4, .5)]] * 30)                      # x menor na imagem crua = mais à direita no espelho
    assert m.pos[0] > x1 + 300


def test_arrasta_e_solta(tmp_path):
    c, m, ev, r = _c(tmp_path)
    c.ligar()
    _passos(c, r, [[D(.5, .5)]] * 10)
    _passos(c, r, [[D(.5, .5, "pinca")]] * 12)             # segura > 0,3 s → aperta
    assert ("apertar", "esquerdo", 1) in m.log and c.maos["direita"].arrastando
    _passos(c, r, [[D(.4 - i * .005, .5, "pinca")] for i in range(10)])
    assert any(a[0] == "mover" and a[3] for a in m.log)    # moveu arrastando
    _passos(c, r, [[D(.35, .5)]] * 2)
    assert m.log[-1][0] == "mover" and ("soltar", "esquerdo", 1) in m.log and c.contagem["arrastos"] == 1


def test_botao_direito_e_punho_levanta_o_mouse(tmp_path):
    c, m, ev, r = _c(tmp_path)
    c.ligar()
    _passos(c, r, [[D(.5, .5)]] * 5 + [[D(.5, .5, "medio")]] * 3 + [[D(.5, .5)]] * 2)
    assert ("apertar", "direito", 1) in m.log and c.contagem["direitos"] == 1
    _passos(c, r, [[D(.5, .5)]] * 20)
    parado = m.pos
    _passos(c, r, [[D(.3, .3, "punho")]] * 20)             # punho: a mão anda, o cursor não
    assert m.pos == parado and not any(a[0] == "apertar" for a in m.log[-20:])


def test_esquerda_rola(tmp_path):
    c, m, ev, r = _c(tmp_path)
    c.ligar()
    _passos(c, r, [[E(.7, .5, "pinca")]] + [[E(.7, .38, "pinca")]] * 20)   # pinça e sobe a mão
    rol = [a for a in m.log if a[0] == "rolar"]
    assert rol and all(a[1] > 0 for a in rol) and not any(a[0] == "apertar" for a in m.log)
    _passos(c, r, [[E(.7, .38)]] * 2)
    n = len(m.log)
    _passos(c, r, [[E(.7, .6)]] * 10)                      # sem pinça não rola
    assert len(m.log) == n


def test_mao_some_solta_o_botao(tmp_path):
    c, m, ev, r = _c(tmp_path)
    c.ligar()
    _passos(c, r, [[D(.5, .5, "pinca")]] * 12)
    assert c.maos["direita"].arrastando
    r.t += 0.5
    c.vigiar(r.t)
    assert ("soltar", "esquerdo") in [a[:2] for a in m.log] and not c.maos["direita"].arrastando


def test_calibracao_e_ensaio(tmp_path):
    c, m, ev, r = _c(tmp_path, calib=False)
    assert "calibrar" in c.ligar() and c.ensaio and c.etapa == 1
    _passos(c, r, [[D(.75, .3)]] * 3 + [[D(.75, .3, "pinca")]] * 3 + [[D(.75, .3)]] * 2)
    assert c.etapa == 2 and not any(a[0] in ("apertar", "soltar") for a in m.log)     # calibrando não clica
    _passos(c, r, [[D(.3, .7)]] * 3 + [[D(.3, .7, "pinca")]] * 3 + [[D(.3, .7)]] * 2)
    assert c.etapa == 0 and c.calib and not c.ensaio
    assert ControleMaos(mouse=m, arquivo=tmp_path / "maos.json", env={}).calib == c.calib   # guardado
    c2, m2, _, r2 = _c(tmp_path / "b", calib=False)
    c2.ligar()
    _passos(c2, r2, [[D(.5, .5, "pinca")]] * 3 + [[D(.5, .5)]] * 2 + [[D(.48, .49, "pinca")]] * 3 + [[D(.48, .49)]] * 2)
    assert c2.etapa == 1 and not c2.calib                  # pontos perto demais: recomeça


def test_ensaio_forcado_nao_clica(tmp_path):
    c, m, ev, r = _c(tmp_path)
    c.ensaio_forcado = True
    c.ligar()
    _passos(c, r, [[D(.5, .5)]] * 5 + [[D(.5, .5, "pinca")]] * 3 + [[D(.5, .5)]] * 2)
    assert not m.log and c.contagem["cliques"] == 1 and ("maos_so", {"acao": "clique", "ensaio": True}) in ev


def test_seguranca_trancado_e_duas_palmas(tmp_path):
    estado = {"ok": True}
    c, m, ev, r = _c(tmp_path, pode=lambda: (estado["ok"], "cérebro trancado"))
    c.ligar()
    _passos(c, r, [[D(.5, .5, "pinca")]] * 12)
    estado["ok"] = False
    _passos(c, r, [[D(.5, .5, "pinca")]])
    assert not c.ligado and ("soltar", "esquerdo") in [a[:2] for a in m.log]
    assert "trancado" in c.ligar()
    estado["ok"] = True
    c.ligar()
    _passos(c, r, [[D(.4, .5), E(.7, .5)]] * 70)           # 2,3 s com as duas palmas abertas paradas
    assert not c.ligado


def test_troca_as_maos_e_lados_confusos(tmp_path):
    c, m, ev, r = _c(tmp_path)
    c.ligar()
    assert "esquerda agora é o mouse" in c.trocar_maos()
    _passos(c, r, [[E(.5, .5)]] * 10)
    assert m.log and m.log[-1][0] == "mover"
    c.trocar_maos()
    lados = c._lados([D(.7, .5), D(.3, .5)])              # rastreador disse "direita" nas duas
    assert lados["direita"][0][0] == pytest.approx(.3) and lados["esquerda"][0][0] == pytest.approx(.7)
    assert c._lados([{"lado": "direita", "p": [[0, 0]] * 5}, {"lado": "x", "p": "lixo"}]) == {}


def test_desativado_por_configuracao(tmp_path):
    c = ControleMaos(mouse=MouseNulo(), arquivo=tmp_path / "m.json", env={"JAIME_MAOS_SO": "off"})
    assert "desligado na configuração" in c.ligar() and not c.ligado


def test_websocket_leva_as_maos_ao_mouse(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from jaime.jarvis import rotas
    from jaime.jarvis.integracao import Jarvis
    from jaime.jarvis.monitor import Monitor
    from jaime.jarvis.rosto import Rostos

    class _B:
        ultimo_dia = ""; ultimo = []
    c, m, ev, r = _c(tmp_path)
    c.relogio = __import__("time").monotonic
    rs = Rostos(tmp_path / "r.json")
    j = Jarvis(_B(), Monitor(rs), rs, env={}, controle=c)
    rotas.ESTADO.update(jarvis=j, jaime=None, falar=None)
    a = FastAPI(); a.include_router(rotas.router); cli = TestClient(a)
    assert "ligado" in asyncio_run(j.gerador("liga o controle do computador"))
    with cli.websocket_connect("/jarvis/maos/ws") as ws:
        for _ in range(8):
            ws.send_text(__import__("json").dumps({"maos": [D(.5, .5)]}))
        ws.send_text("lixo")
        ws.send_text(__import__("json").dumps({"maos": [D(.5, .5)]}))
    assert any(a[0] == "mover" for a in m.log)
    assert cli.get("/jarvis/maos/estado").json()["ligado"] is True
    c.nativo = True                                      # rastreador nativo manda: o navegador só observa
    n = len(m.log)
    with cli.websocket_connect("/jarvis/maos/ws") as ws:
        ws.send_text(__import__("json").dumps({"maos": [D(.3, .5)]}))
    assert len(m.log) == n
    import pytest as _p
    from starlette.websockets import WebSocketDisconnect
    with _p.raises(WebSocketDisconnect):
        with cli.websocket_connect("/jarvis/maos/ws", headers={"Origin": "https://mal.com"}) as ws:
            ws.receive_text()


def asyncio_run(gen):
    import asyncio

    async def todas():
        return " ".join([f async for f in gen])
    return asyncio.run(todas())


def test_nativo_converte_poses(tmp_path):
    import asyncio
    from jaime.jarvis import maos_nativo
    from jaime.spatial.landmarks import HandPose
    pose = HandPose([(x, y, 0.0) for x, y in mao(.5, .5)], "right")
    assert maos_nativo.poses_para_maos([pose])[0]["lado"] == "direita"
    c, m, ev, r = _c(tmp_path)
    c.ligar()

    class Fonte:
        def __init__(self): self.fechada = False
        async def frames(self):
            for i in range(10):
                yield i
                await asyncio.sleep(0)
            c.desligar()
        def fechar(self): self.fechada = True

    class Rastreador:
        def detect(self, frame): return [pose]
        def fechar(self): pass

    async def rodar():
        t = asyncio.create_task(maos_nativo.rodar(c, fonte_fn=Fonte, rastreador_fn=Rastreador, espera=.01))
        await asyncio.sleep(.3)
        t.cancel()
    asyncio.run(rodar())
    assert any(a[0] == "mover" for a in m.log) and not c.nativo
