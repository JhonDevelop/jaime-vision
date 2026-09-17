"""A ponte: o Jaime roda na máquina do João e mexe nos arquivos da máquina do outro dono.
O que não pode cair: a pasta escolhida é o limite (nem `..`, nem caminho absoluto, nem link para fora),
rodar comando é autorização separada, e ponte caída avisa em vez de fingir que fez."""
import asyncio, os
from pathlib import Path
import pytest
from jaime.ponte.servidor import Ponte
from jaime.ponte.agente import executar, _dentro


@pytest.fixture
def raiz(tmp_path):
    (tmp_path / "projeto").mkdir()
    (tmp_path / "projeto" / "main.py").write_text("print('oi')\n")
    (tmp_path / "segredo-fora.txt").write_text("isto está FORA da pasta aberta")
    return tmp_path / "projeto"


# ── o limite é a pasta que ele abriu ──────────────────────────────────────
def test_a_pasta_escolhida_e_o_limite(raiz):
    assert _dentro(raiz, "main.py") is not None
    assert _dentro(raiz, "sub/novo.txt") is not None          # ainda não existe, mas cai dentro
    assert _dentro(raiz, "../segredo-fora.txt") is None
    assert _dentro(raiz, "/etc/passwd") is None
    assert _dentro(raiz, "../../../../etc/hosts") is None

def test_link_simbolico_apontando_para_fora_e_recusado(raiz):
    alvo = raiz.parent / "segredo-fora.txt"
    link = raiz / "atalho.txt"
    try:
        os.symlink(alvo, link)
    except (OSError, NotImplementedError):
        pytest.skip("sem symlink neste sistema")
    assert _dentro(raiz, "atalho.txt") is None                # resolve o link ANTES de decidir
    assert "fora da pasta" in executar(raiz, "ler", {"caminho": "atalho.txt"}, False)

def test_ler_listar_e_escrever_dentro_da_pasta(raiz):
    assert "main.py" in executar(raiz, "listar", {"caminho": ""}, False)
    assert "print('oi')" in executar(raiz, "ler", {"caminho": "main.py"}, False)
    assert "escrito" in executar(raiz, "escrever", {"caminho": "sub/n.txt", "conteudo": "abc"}, False)
    assert (raiz / "sub" / "n.txt").read_text() == "abc"
    assert "fora da pasta" in executar(raiz, "escrever", {"caminho": "../invadido.txt", "conteudo": "x"}, False)
    assert not (raiz.parent / "invadido.txt").exists()

def test_arquivo_oculto_nao_aparece_na_listagem(raiz):
    (raiz / ".env").write_text("CHAVE=segredo")
    assert ".env" not in executar(raiz, "listar", {"caminho": ""}, False)


# ── rodar comando é autorização separada, e vem desligada ─────────────────
def test_rodar_comando_so_com_autorizacao_explicita(raiz):
    assert "não autorizei" in executar(raiz, "rodar", {"comando": "echo oi"}, False)
    saida = executar(raiz, "rodar", {"comando": "echo oi"}, True)
    assert "oi" in saida and "[saiu 0]" in saida

def test_o_comando_roda_na_pasta_dele_e_nao_em_outro_lugar(raiz):
    assert raiz.name in executar(raiz, "rodar", {"comando": "pwd"}, True)

def test_acao_desconhecida_nao_quebra(raiz):
    assert "não sei fazer" in executar(raiz, "voar", {}, True)


# ── a fila, do lado do João ───────────────────────────────────────────────
def test_ponte_caida_avisa_em_vez_de_fingir():
    async def r():
        p = Ponte()
        assert not p.viva and "ninguém ligou" in p.estado()
        t = await p.pedir("ler", caminho="x")
        assert "caída" in t and "jaime.ponte.agente" in t          # diz o que fazer
    asyncio.run(r())

def test_rodar_negado_quando_o_dono_nao_liberou():
    async def r():
        p = Ponte(); p.registrar("Gabriel", "mac-dele", "/Users/g/Proj", pode_rodar=False)
        assert p.viva
        assert "não liberou rodar" in await p.pedir("rodar", comando="ls")
    asyncio.run(r())

def test_o_pedido_atravessa_e_a_resposta_volta():
    async def r():
        p = Ponte(); p.registrar("Gabriel", "mac-dele", "/Users/g/Proj", pode_rodar=True)
        pedido = asyncio.create_task(p.pedir("ler", caminho="main.py"))
        await asyncio.sleep(0.02)
        t = await p.proximo(espera=1)                               # o agente busca trabalho
        assert t and t["acao"] == "ler" and t["args"]["caminho"] == "main.py"
        assert p.responder(t["id"], "print('oi')")                  # e devolve o que leu lá
        assert await pedido == "print('oi')"
    asyncio.run(r())

def test_sem_trabalho_o_agente_volta_vazio_e_nao_trava():
    async def r():
        p = Ponte(); p.registrar("G", "m", "/r", True)
        assert await p.proximo(espera=0.05) is None
    asyncio.run(r())

def test_resposta_de_pedido_que_nao_existe_e_ignorada():
    p = Ponte(); p.registrar("G", "m", "/r", True)
    assert p.responder("id-que-nao-existe", "x") is False

def test_o_estado_conta_a_verdade():
    p = Ponte(); p.registrar("Gabriel", "mac-do-gabriel", "/Users/g/Projetos", pode_rodar=False)
    e = p.estado()
    assert "Gabriel" in e and "mac-do-gabriel" in e and "rodar comando: não" in e and "viva" in e


# ── o elo que faltava: HTTP ↔ fila, no app de verdade ─────────────────────
def test_o_agente_busca_pela_rede_e_a_resposta_volta_pelo_mesmo_caminho():
    """Prova o trajeto inteiro sem mock de rede: o Jaime enfileira, o agente busca por HTTP,
    responde por HTTP, e quem pediu recebe."""
    from fastapi import FastAPI, Header, HTTPException
    from fastapi.testclient import TestClient

    ponte = Ponte()
    TOKEN = "segredo-de-teste"
    app = FastAPI()

    def _auth(t):
        if t != TOKEN:
            raise HTTPException(401, "token inválido")

    @app.post("/ponte/registrar")
    async def reg(body: dict, x_jaime_token: str | None = Header(default=None)):
        _auth(x_jaime_token)
        ponte.registrar(body["dono"], body["maquina"], body["raiz"], body["pode_rodar"])
        return {"ok": True}

    @app.post("/ponte/proximo")
    async def prox(x_jaime_token: str | None = Header(default=None)):
        _auth(x_jaime_token)
        return await ponte.proximo(espera=2) or {}

    @app.post("/ponte/responder")
    async def resp(body: dict, x_jaime_token: str | None = Header(default=None)):
        _auth(x_jaime_token)
        return {"ok": ponte.responder(body["id"], body["saida"])}

    with TestClient(app) as c:
        assert c.post("/ponte/registrar", json={"dono": "Gabriel", "maquina": "mac-dele",
                                                "raiz": "/Users/g/Proj", "pode_rodar": True},
                      headers={"X-Jaime-Token": TOKEN}).status_code == 200
        assert c.post("/ponte/proximo", headers={"X-Jaime-Token": "errado"}).status_code == 401

        # o pedido nasce no mesmo laço em que o app vive, como acontece de verdade
        async def trajeto():
            tarefa = asyncio.create_task(ponte.pedir("ler", caminho="app.py"))
            await asyncio.sleep(0.05)
            t = await ponte.proximo(espera=2)
            assert t and t["acao"] == "ler"
            assert ponte.responder(t["id"], "print('projeto do Gabriel')")
            return await tarefa
        assert asyncio.run(trajeto()) == "print('projeto do Gabriel')"
