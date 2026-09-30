"""Estúdio de hologramas: edição por voz (operações validadas), desenho → volume, OBJ/STL/GLB, impressão 3D."""
import asyncio, json, struct
import pytest
from jaime.jarvis import holograma as holo, malha3d as m3
from jaime.jarvis.estudio import Estudio, validar_ops, simplificar
from jaime.jarvis.integracao import Jarvis
from jaime.jarvis.monitor import Monitor
from jaime.jarvis.rosto import Rostos
from jaime.jarvis.voz import cena, edicao


class _B:
    ultimo_dia = ""; ultimo = []


async def _todas(gen):
    return [f.strip() async for f in gen]


def _spec():
    return holo.validar_pecas({"pecas": [
        {"nome": "base", "forma": "caixa", "pos": [0, 0, 0], "tam": [2, .2, 1]},
        {"nome": "coluna", "forma": "cilindro", "pos": [0, 1, 0], "tam": [.2, 2, 0]},
        {"nome": "topo", "forma": "esfera", "pos": [0, 2.2, 0], "tam": [.3, 0, 0]},
        {"nome": "anel", "forma": "toro", "pos": [0, 1, 0], "tam": [.6, .05, 0], "rot": [1.57, 0, 0]},
        {"nome": "ponta", "forma": "cone", "pos": [0, 2.7, 0], "tam": [.2, .5, 0]},
        {"nome": "traço", "forma": "tubo", "tam": [.05, 0, 0], "pontos": [[0, 0, 0], [1, 1, 0], [2, 1, 1]]}]})


def test_primitivas_viram_malhas_fechadas():
    for p in _spec():
        mm = m3.malha_da_peca(p)
        n = len(mm["v"]) // 3
        assert mm["f"] and max(mm["f"]) < n and len(mm["f"]) % 3 == 0, p["forma"]


def test_arquivos_obj_stl_glb(tmp_path):
    malhas = [m3.malha_da_peca(p) for p in _spec()]
    arqs = m3.exportar("Luminária de mesa", malhas, pasta=tmp_path)
    assert set(arqs) == {"stl", "obj", "glb"}
    b = open(arqs["stl"], "rb").read()
    n = struct.unpack("<I", b[80:84])[0]
    assert n == sum(len(x["f"]) // 3 for x in malhas) and len(b) == 84 + 50 * n
    g = open(arqs["glb"], "rb").read()
    magic, ver, total = struct.unpack("<III", g[:12])
    assert magic == 0x46546C67 and ver == 2 and total == len(g)
    jl = struct.unpack("<I", g[12:16])[0]
    doc = json.loads(g[20:20 + jl])
    assert [n["name"] for n in doc["nodes"]][:2] == ["base", "coluna"]
    assert open(arqs["obj"]).read().count("\no ") == len(malhas)
    assert m3.exportar("Luminária de mesa", malhas, ["stl"], pasta=tmp_path)["stl"] != arqs["stl"]   # não sobrescreve


def test_impressao_mm_z_para_cima():
    malhas = [m3.malha_da_peca(p) for p in _spec()[:3]]
    mesa = m3.para_impressao(malhas, 120)
    xs = [v for p in mesa for v in p["v"][0::3]]; ys = [v for p in mesa for v in p["v"][1::3]]; zs = [v for p in mesa for v in p["v"][2::3]]
    assert min(zs) == pytest.approx(0, abs=1e-3)
    assert max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) == pytest.approx(120, abs=.01)
    assert max(zs) - min(zs) > max(ys) - min(ys)       # a coluna (y do holograma) virou a altura (Z) na mesa


def test_malhas_da_tela_sao_validadas():
    ok = {"nome": "porta<script>", "v": [0, 0, 0, 1, 0, 0, 0, 1, 0], "f": [0, 1, 2]}
    ruim = [{"v": [0, 0, 0, 1, 0, 0, 0, 1, 0], "f": [0, 1, 9]}, {"v": [float("nan")] * 9, "f": [0, 1, 2]}, {"v": [1, 2], "f": [0]}, "x"]
    out = m3.validar_malhas([ok] + ruim)
    assert len(out) == 1 and out[0]["nome"] == "portascript"


def test_validar_ops():
    ops = validar_ops({"ops": [
        {"op": "girar", "alvo": [2, 3, 99], "valor": [0, 1.2, 0]},
        {"op": "escalar", "alvo": "selecionada", "valor": 2},
        {"op": "apagar_disco", "alvo": [0]},
        {"op": "mover", "alvo": [99]},
        {"op": "adicionar", "peca": {"nome": "antena", "forma": "cone", "pos": [0, 3, 0], "tam": [.1, .8, 0]}},
        {"op": "explodir", "valor": 9}]}, n_pecas=5)
    assert [o["op"] for o in ops] == ["girar", "escalar", "adicionar", "explodir"]
    assert ops[0]["alvo"] == [2, 3] and ops[1]["valor"] == [2.0, 2.0, 2.0] and ops[3]["valor"] == 1.6


def test_simplificar_traco():
    pts = [[i * .001, 0, 0] for i in range(2000)]
    s = simplificar(pts)
    assert 2 <= len(s) <= 41 and s[0] == [0, 0, 0]


def _jarvis(tmp_path, monkeypatch, modelo=None):
    monkeypatch.setattr(holo, "PASTA", tmp_path / "holo")
    monkeypatch.setattr(m3, "EXPORTADOS", tmp_path / "holo" / "exportados")
    ev = []
    r = Rostos(tmp_path / "r.json")
    j = Jarvis(_B(), Monitor(r), r, emitir=lambda t, **d: ev.append((t, d)), env={}, modelo_holo=modelo)
    j.estudio.emitir = j.emitir; j.estudio.espera_tela = .3
    return j, ev


def test_edicao_por_voz_com_holograma_aberto(tmp_path, monkeypatch):
    pedidos = []

    async def modelo(prompt, ctx):
        pedidos.append(prompt)
        return json.dumps({"ops": [{"op": "girar", "alvo": [1, 2], "valor": [0, 1.2, 0]}], "fala": "Abri as portas."})
    j, ev = _jarvis(tmp_path, monkeypatch, modelo)
    assert j.gerador("abre as portas") is None                      # sem holograma aberto, segue para o cérebro
    j.estudio.receber_cena({"titulo": "carro", "pecas": [{"nome": "lataria"}, {"nome": "porta dianteira esquerda"}, {"nome": "porta dianteira direita"}]})
    assert asyncio.run(_todas(j.gerador("abre as portas"))) == ["Portas abertas."]          # comum: sem modelo
    assert not pedidos and ev[-1][1]["ops"] == [{"op": "girar", "alvo": [1, 2], "valor": [0.0, 1.1, 0.0], "pivo": "frente"}]
    assert asyncio.run(_todas(j.gerador("deixa as portas como asas de gaivota"))) == ["Abri as portas."]   # incomum: modelo
    assert "porta dianteira esquerda" in pedidos[0] and ev[-1][1]["ops"][0]["alvo"] == [1, 2]
    assert asyncio.run(_todas(j.gerador("desfaz"))) == ["Desfeito."] and ev[-1][1]["acao"] == "desfazer"


def test_exporta_com_malhas_da_tela_e_sem_tela(tmp_path, monkeypatch):
    j, ev = _jarvis(tmp_path, monkeypatch)
    j.estudio.abrir("suporte", _spec())

    async def com_tela():
        t = asyncio.create_task(_todas(j.gerador("exporta em stl")))
        await asyncio.sleep(.05)
        j.estudio.receber_malhas({"pecas": [{"nome": "peça", "v": [0, 0, 0, 1, 0, 0, 0, 1, 0], "f": [0, 1, 2]}]})
        return await t
    falas = asyncio.run(com_tela())
    assert "suporte.stl" in falas[0] and ("holograma", {"acao": "exportar"}) in ev
    assert (tmp_path / "holo" / "exportados" / "suporte.stl").stat().st_size == 84 + 50
    falas = asyncio.run(_todas(j.gerador("gera o arquivo 3d")))           # sem tela: monta das peças descritas
    assert all(x in falas[0] for x in (".stl", ".obj", ".glb"))


def test_blender_e_impressao(tmp_path, monkeypatch):
    j, ev = _jarvis(tmp_path, monkeypatch)
    j.estudio.abrir("vaso", _spec())
    chamados = []
    j.abrir_blender = lambda p: chamados.append(("blender", p)) or {"ok": True}
    j.abrir_fatiador = lambda p: chamados.append(("fatiador", p)) or {"ok": True, "fatiador": "Bambu Studio"}
    falas = asyncio.run(_todas(j.gerador("abre no blender")))
    assert falas[-1] == "Abrindo no Blender." and chamados[0][1].endswith(".glb")
    falas = asyncio.run(_todas(j.gerador("manda para impressão com 12 cm")))
    assert "12 centímetros" in falas[0] and "Bambu Studio" in falas[1] and chamados[1][1].endswith("vaso-120mm.stl")
    assert "Não tem holograma" in asyncio.run(_todas(Jarvis(_B(), Monitor(Rostos(tmp_path / "x.json")), Rostos(tmp_path / "x.json"), env={}).gerador("imprime isso")))[0]


def test_desenho_vira_volume(tmp_path, monkeypatch):
    async def modelo(prompt, ctx):
        assert "cadeira" in prompt and "[0.0, 0.0, 0.0]" in prompt.replace("[0, 0, 0]", "[0.0, 0.0, 0.0]")
        return json.dumps({"titulo": "cadeira", "pecas": _spec()[:4]})
    j, ev = _jarvis(tmp_path, monkeypatch, modelo)
    assert "Prancheta aberta" in asyncio.run(_todas(j.gerador("quero desenhar")))[0]
    assert "Ainda não vi" in asyncio.run(_todas(j.gerador("dá volume ao desenho")))[0]
    assert j.estudio.receber_tracos([[[0, 0, 0], [1, 0, 0], [1, 1, 0]], [[0, 0, 0]]]) == 1
    falas = asyncio.run(_todas(j.gerador("transforma o desenho em 3d, é uma cadeira")))
    assert "cadeira em três dimensões" in falas[-1] and ev[-1][1]["modelo"] == "gerado"
    assert (tmp_path / "holo" / "cadeira.json").exists()


@pytest.mark.parametrize("frase,esperado", [
    ("liga o controle pelo olhar", ("olhar", {"ligar": True})), ("desliga o controle por mão", ("computador", {"ligar": False})),
    ("imprime isso com 80 mm", ("imprimir", {"maior_mm": 80.0})), ("exporta em obj", ("exportar", {"formatos": ["obj"]})),
])
def test_frases_estudio(frase, esperado):
    assert cena(frase) == esperado
    assert edicao("aumenta a roda da frente") == ("editar", {"pedido": "aumenta a roda da frente"}) and edicao("que horas são?") is None


def test_sentidos_por_voz(tmp_path, monkeypatch):
    j, ev = _jarvis(tmp_path, monkeypatch)
    assert "calibrar" in asyncio.run(_todas(j.gerador("liga o controle pelo olhar")))[0] and ev[-1] == ("sentidos", {"olhar": True})
    assert "desligado" in asyncio.run(_todas(j.gerador("desliga o controle por mão")))[0]
    assert ("sentidos", {"computador": False}) in ev


def test_rotas_do_estudio(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from jaime.jarvis import rotas
    a = FastAPI(); a.include_router(rotas.router); c = TestClient(a)
    j, ev = _jarvis(tmp_path, monkeypatch)
    rotas.ESTADO.update(jarvis=j, jaime=None, falar=None)
    assert c.post("/jarvis/holograma/cena", json={"titulo": "carro", "pecas": [{"nome": "porta", "centro": [1, 2, 3]}], "selecionada": 0}).json() == {"ok": True}
    assert j.estudio.aberto and j.estudio.pecas[0]["nome"] == "porta" and j.estudio.selecionada == 0
    assert c.post("/jarvis/holograma/tracos", json={"tracos": [[[0, 0, 0], [1, 1, 1]]]}).json() == {"tracos": 1}
    assert c.post("/jarvis/holograma/fechado").json() == {"ok": True} and not j.estudio.aberto
    assert c.post("/jarvis/holograma/cena", json={}, headers={"Origin": "https://mal.com"}).status_code == 403
    assert c.get("/hud/jarvis/sentidos.js").status_code == 200


def test_caixa_e_mensagens(tmp_path, monkeypatch):
    j, ev = _jarvis(tmp_path, monkeypatch)

    class _Br(_B):
        async def _uma(self, nome):
            return nome, [{"de": "Stripe <a@b.com>", "assunto": "Atualize seus dados", "resumo": ""}]
        async def seg_emails(self, lista):
            from jaime.jarvis.briefing import Segmento
            return Segmento("emails", "Há 1 e-mail na caixa.", {"tipo": "emails", "rotulo": "X", "total": 1, "agir": 1, "itens": []})
    j.briefing = _Br()
    falas = asyncio.run(_todas(j.gerador("abre minha caixa de entrada")))
    assert falas == ["Abrindo a caixa de entrada.", "Há 1 e-mail na caixa."] and ev[-1][0] == "cartao" and "GMAIL" in ev[-1][1]["card"]["rotulo"]
    assert "Nenhuma mensagem" in asyncio.run(_todas(j.gerador("mostra as mensagens do whatsapp")))[0]
    j.mensagens = lambda: [{"app": "WhatsApp", "de": "Ana", "texto": "chego às 8", "hora": "10:00"}, {"app": "WhatsApp", "de": "Gabriel", "texto": "contrato ok", "hora": "10:05"}]
    f = asyncio.run(_todas(j.gerador("quem me mandou mensagem?")))[0]
    assert f.startswith("2 mensagens de Gabriel e Ana") and "contrato ok" in f
    j.convidado = lambda: "Gabriel"                                   # visita na linha: nada privado em voz alta
    assert "só nós" in asyncio.run(_todas(j.gerador("abre minha caixa de entrada")))[0]


def test_apps_premiere_e_abrir(tmp_path):
    import xml.etree.ElementTree as ET
    from jaime.maos import apps
    v = tmp_path / "bruto.mp4"; v.write_bytes(b"x")
    xml = apps.premiere_xml("Corte Oldsen", [{"caminho": str(v), "inicio": 1, "fim": 3}, {"caminho": str(v), "inicio": 10, "fim": 12.5}], 30, pasta=tmp_path)
    raiz = ET.parse(xml).getroot()
    itens = raiz.findall(".//video/track/clipitem")
    assert [(i.find("start").text, i.find("end").text, i.find("in").text, i.find("out").text) for i in itens] == [("0", "60", "30", "90"), ("60", "135", "300", "375")]
    assert raiz.find(".//sequence/duration").text == "135" and len(raiz.findall(".//file/pathurl")) == 1
    with pytest.raises(ValueError):
        apps.premiere_xml("x", [{"caminho": str(v), "inicio": 5, "fim": 2}], pasta=tmp_path)
    cmds = []
    r = apps.abrir("ps", str(v), rodar=cmds.append, sistema="Darwin", localizar_fn=lambda n, s: "/Applications/Adobe Photoshop 2025/Adobe Photoshop 2025.app")
    assert r["ok"] and cmds[-1] == ["open", "-a", "/Applications/Adobe Photoshop 2025/Adobe Photoshop 2025.app", str(v)]
    r = apps.abrir("canva", rodar=cmds.append, sistema="Darwin", localizar_fn=lambda n, s: None)
    assert r == {"ok": True, "app": "canva", "como": "web"} and cmds[-1] == ["open", "https://www.canva.com/"]
    assert not apps.abrir("premiere", rodar=cmds.append, sistema="Darwin", localizar_fn=lambda n, s: None)["ok"]
    assert apps.PERIGOSO_JSX.search("app.activeDocument.saveAs(f)") and not apps.PERIGOSO_JSX.search("app.documents.add(800, 600)")


def test_pedidos_comuns_sem_modelo():
    from jaime.jarvis.estudio import rapido
    nomes = ["lataria", "porta dianteira esquerda", "porta dianteira direita", "motor dianteiro", "motor traseiro",
             "roda dianteira esquerda", "roda dianteira direita", "roda traseira esquerda", "volante"]
    pecas = [{"i": i, "nome": n} for i, n in enumerate(nomes)]
    casos = {
        "separa a roda da frente": [{"op": "separar", "alvo": [5], "valor": 1.6}],
        "mostra só os motores": [{"op": "isolar", "alvo": [3, 4]}],
        "mostra o volante inteiro": [{"op": "isolar", "alvo": [8]}],
        "mostra tudo": [{"op": "mostrar_tudo"}],
        "esconde as portas": [{"op": "esconder", "alvo": [1, 2]}],
        "aumenta essa peça": [{"op": "escalar", "alvo": "selecionada", "valor": [1.3, 1.3, 1.3]}],
        "pinta a lataria de vermelho": [{"op": "cor", "alvo": [0], "valor": "#ff3b3b"}],
        "deixa o volante azul": [{"op": "cor", "alvo": [8], "valor": "#3b8bff"}],
        "foca no motor traseiro": [{"op": "focar", "alvo": [4]}],
        "volta a roda dianteira esquerda": [{"op": "resetar", "alvo": [5]}],
        "sobe o volante": [{"op": "mover", "alvo": [8], "valor": [0.0, 0.6, 0.0]}],
    }
    for frase, ops in casos.items():
        r = rapido(frase, pecas, 2)
        assert r is not None and r[0] == ops, frase
    assert rapido("separa o escapamento", pecas, None) is None           # peça que não existe: vai ao modelo
    assert rapido("faz ele parecer mais esportivo", pecas, None) is None


def test_ops_novas_validadas():
    ops = validar_ops({"ops": [{"op": "separar", "alvo": [0], "valor": 99}, {"op": "cor", "alvo": [0], "valor": "vermelho"},
                               {"op": "cor", "alvo": [0], "valor": "#AABBCC"}, {"op": "mostrar_tudo"}, {"op": "isolar", "alvo": [7]},
                               {"op": "resetar"}]}, n_pecas=3)
    assert ops == [{"op": "separar", "alvo": [0], "valor": 5.0}, {"op": "cor", "alvo": [0], "valor": "#aabbcc"}, {"op": "mostrar_tudo"}, {"op": "resetar"}]
