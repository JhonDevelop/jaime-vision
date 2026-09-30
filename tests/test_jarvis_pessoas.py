"""Rostos de várias pessoas: cadastro com nome e relação, "quem é esse?", lista, esquecer um só, grafo de relações."""
import asyncio, json
import pytest
from jaime.jarvis.integracao import Jarvis, tipo_relacao
from jaime.jarvis.monitor import Monitor
from jaime.jarvis.rosto import Rostos
from jaime.jarvis.voz import cena
from jaime.relacoes.grafo import Relacoes

A, B, C = [0.1] * 128, [0.5] * 128, [0.9] * 128


class _B:
    ultimo_dia = ""; ultimo = []


def _j(tmp_path, **kw):
    r = Rostos(tmp_path / "rosto.json")
    g = Relacoes(tmp_path / "rel.db")
    kw.setdefault("relacoes", g)
    ev = []
    j = Jarvis(_B(), Monitor(r, carregar=lambda: None, emitir=lambda t, **d: None, espera_rosto=.3), r,
               emitir=lambda t, **d: ev.append((t, d)), env={}, espera_rosto=.5, **kw)
    return j, r, g, ev


async def _todas(gen):
    return [f.strip() async for f in gen]


def test_rostos_varias_pessoas(tmp_path):
    r = Rostos(tmp_path / "rosto.json")
    r.cadastrar([A])
    r.cadastrar([B], pessoa="Ana", nome="Ana", relacao="irmã")
    assert r.verificar(A)["status"] == "confirmado"
    v = r.verificar(B)
    assert v["status"] == "conhecido" and v["nome"] == "Ana" and v["relacao"] == "irmã" and v["pessoa"] == "ana"
    assert r.verificar(C)["status"] == "desconhecido"
    assert r.dono_cadastrado and len(r.pessoas()) == 2
    assert r.esquecer("Ana") and not r.esquecer("Ana")
    assert r.verificar(B)["status"] == "desconhecido" and r.dono_cadastrado


def test_formato_antigo_vira_joao(tmp_path):
    arq = tmp_path / "rosto.json"
    arq.write_text(json.dumps({"amostras": [A]}))
    r = Rostos(arq)
    assert r.verificar(A)["status"] == "confirmado" and r.pessoas()[0]["id"] == "joao"


def test_visita_nao_ve_saude(tmp_path):
    r = Rostos(tmp_path / "rosto.json")
    r.cadastrar([A]); r.cadastrar([B], pessoa="ana", nome="Ana")
    m = Monitor(r, carregar=lambda: pytest.fail("não pode ler saúde"), emitir=lambda t, **d: None, espera_rosto=1)

    async def rodar():
        falas = []
        async for f in m.rodar():
            falas.append(f)
            if len(falas) == 1:
                m.receber_rosto(r.verificar(B))
        return falas
    falas = asyncio.run(rodar())
    assert "Olá, Ana" in falas[1]


@pytest.mark.parametrize("frase,esperado", [
    ("aprende o rosto da Ana, minha irmã", ("aprende_rosto", {"nome": "Ana", "relacao": "irmã"})),
    ("quem é esse?", ("quem_e", {})),
    ("quais rostos você conhece?", ("rostos", {})),
])
def test_frases(frase, esperado):
    assert cena(frase) == esperado


def test_tipo_relacao():
    assert tipo_relacao("irmã") == "parentesco" and tipo_relacao("sócio") == "sociedade"
    assert tipo_relacao("amiga") == "amizade" and tipo_relacao("dentista") == "" and tipo_relacao("") == ""


def test_cadastro_de_outra_pessoa_liga_no_grafo(tmp_path):
    j, r, g, ev = _j(tmp_path)
    fala = asyncio.run(_todas(j.gerador("aprende o rosto da Ana, minha irmã")))[0]
    assert "consentimento" in fala and j.cadastrando["pessoa"] == "ana" and not j.cadastrando["dono"]
    assert ev[-1] == ("rosto", {"acao": "cadastrar", "amostras": 5, "nome": "Ana"})
    n = r.cadastrar([B], **{k: j.cadastrando[k] for k in ("pessoa", "nome", "dono", "relacao")})
    assert j.cadastrado(n) == "Aprendi o rosto de Ana. Anotei que é sua irmã." and j.cadastrando is None
    d = g.sobre("Ana")
    assert d["relacoes"][0]["relacao"] == "parentesco" and d["relacoes"][0]["detalhe"] == "irmã"
    assert "Ana, sua irmã" in asyncio.run(_todas(j.gerador("quais rostos você conhece?")))[0]


def test_quem_e_e_presenca(tmp_path):
    j, r, g, ev = _j(tmp_path)
    r.cadastrar([A]); r.cadastrar([B], pessoa="gabriel", nome="Gabriel", relacao="sócio")
    g.fato("Gabriel", "cargo", "diretor comercial")

    async def rodar(desc):
        gen = j.gerador("quem é esse?")
        falas = []
        t = asyncio.create_task(_todas(gen))
        await asyncio.sleep(.05)
        j.receber_rosto(r.verificar(desc))
        falas = await t
        return falas
    falas = asyncio.run(rodar(B))
    assert falas[0] == "É Gabriel, seu sócio." and "cargo: diretor comercial" in falas[1]
    assert ("rosto", {"acao": "identificar"}) in ev
    ctx = j.contexto_presente()
    assert "Gabriel (sócio do João)" in ctx and "diretor comercial" in ctx and "visita" in ctx
    assert asyncio.run(rodar(A))[0] == "É o senhor, João." and j.contexto_presente() == ""
    assert "Não vi ninguém" in asyncio.run(_todas(j.gerador("quem é esse?")))[0]      # sem resposta da câmera


def test_esquecer_so_um(tmp_path):
    j, r, g, ev = _j(tmp_path)
    r.cadastrar([A]); r.cadastrar([B], pessoa="ana", nome="Ana")
    assert "esqueci o rosto de Ana" in asyncio.run(_todas(j.gerador("esquece o rosto da Ana")))[0]
    assert r.dono_cadastrado and len(r.pessoas()) == 1
    assert "Não tenho" in asyncio.run(_todas(j.gerador("esquece o rosto da Ana")))[0]
    asyncio.run(_todas(j.gerador("esquece meu rosto")))
    assert not r.cadastrado


def test_rota_cadastra_pessoa_nomeada(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from jaime.jarvis import rotas
    a = FastAPI(); a.include_router(rotas.router); c = TestClient(a)
    j, r, g, ev = _j(tmp_path, relacoes=lambda: Relacoes(tmp_path / "rel.db"))   # a rota roda em outra thread
    rotas.ESTADO.update(jarvis=j, jaime=None, falar=None)
    j._aprender("Ana", "prima")
    assert c.post("/jarvis/rosto/cadastrar", json={"descritores": [B]}).json() == {"amostras": 1}
    assert c.post("/jarvis/rosto/verificar", json={"descritor": B}).json() == {"status": "conhecido", "nome": "Ana"}
    assert j.presente_agora()["nome"] == "Ana" and g.sobre("Ana")["relacoes"][0]["detalhe"] == "prima"
    assert c.post("/jarvis/rosto/cadastrar", json={"descritores": [B]}).status_code == 409     # um "aprende" = um cadastro
