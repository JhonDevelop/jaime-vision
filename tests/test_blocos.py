"""Blocos de interface: modelo, adaptação por superfície, gerenciador, protocolo, voz e modelos (templates)."""
import asyncio, json
from types import SimpleNamespace
import pytest
from jaime.blocos.fontes import Fontes, padrao
from jaime.blocos.gerenciador import Gerenciador
from jaime.blocos.modelo import BlocoInvalido, TIPOS, validar
from jaime.blocos.modelos import EMBUTIDOS, Modelos, Uso, contrato
from jaime.blocos.protocolo import Sessao, sessao_de_ola, tratar_mensagem
from jaime.blocos.superficies import PERFIS, adaptar, capacidades_de, linhas_texto, resumo_falado, selecionar, sparkline
from jaime.blocos.voz import comando

EXEMPLOS = {
    "texto": {"texto": "A build terminou. Nenhum erro."},
    "lista": {"itens": ["revisar orçamento", {"texto": "ligar pro Rafael", "detalhe": "14h"}]},
    "tabela": {"colunas": ["modelo", "acertos"], "linhas": [["opus", "9/10"], {"a": "sonnet", "b": "7/10"}]},
    "metricas": {"itens": [{"rotulo": "CPU", "valor": "37", "unidade": "%", "variacao": -4}]},
    "grafico": {"forma": "linha", "unidade": "R$", "series": [{"nome": "saldo", "pontos": [[1, 10], [2, 14], [3, "12,5"]]}]},
    "grafo": {"nos": [{"id": "app"}, {"id": "api"}], "arestas": [{"de": "app", "para": "api", "rotulo": "chama"}, {"de": "app", "para": "x"}]},
    "status": {"estado": "atencao", "texto": "Notion fora do ar"},
    "acoes": {"texto": "Deploy pronto.", "botoes": [{"rotulo": "Publicar", "intencao": "publica o deploy da BUB"}]},
    "imagem": {"src": "/hud/tela", "legenda": "tela agora"},
    "html": {"html": "<b>oi</b>", "alternativo": "um oi em negrito"},
    "progresso": {"valor": 45, "texto": "indexando o vault"},
}


# ── modelo ───────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("tipo", TIPOS)
def test_todo_tipo_valida_e_passa_no_contrato_de_todas_as_superficies(tipo):
    b = validar({"tipo": tipo, "titulo": f"exemplo {tipo}", "conteudo": EXEMPLOS[tipo]})
    assert contrato(b) == []


def test_validacao_conserta_e_recusa():
    b = validar({"tipo": "grafo", "titulo": "x", "conteudo": EXEMPLOS["grafo"]})
    assert len(b.conteudo["arestas"]) == 1                             # aresta para nó inexistente cai
    b = validar({"tipo": "progresso", "titulo": "x", "conteudo": {"valor": 45}})
    assert b.conteudo["valor"] == 0.45
    b = validar({"tipo": "texto", "titulo": "t" * 300, "conteudo": "x" * 9000, "prioridade": 9, "intervalo_s": 0.5, "fonte": "relogio"})
    assert len(b.titulo) == 80 and len(b.conteudo["texto"]) == 4000 and b.prioridade == 3 and b.intervalo_s == 2.0
    for ruim in ({"tipo": "video", "titulo": "x"}, {"tipo": "texto", "titulo": ""},
                 {"tipo": "html", "titulo": "x", "conteudo": {"html": "<img src=x onerror=alert(1)>"}},
                 {"tipo": "html", "titulo": "x", "conteudo": {"html": "<script>fetch('/')</script>"}},
                 {"tipo": "imagem", "titulo": "x", "conteudo": {"src": "https://rastreador.com/pixel.png"}}):
        with pytest.raises(BlocoInvalido):
            validar(ruim)
    assert validar({"tipo": "texto", "titulo": "x", "id": "Painel BUB/../../x"}).id == "painel-bub-..-..-x"


# ── superfícies ──────────────────────────────────────────────────────────────
def test_adaptacao_por_superficie():
    tab = validar({"tipo": "tabela", "titulo": "Placar", "conteudo": {"colunas": ["a", "b"], "linhas": [[str(i), "x"] for i in range(30)]}})
    cockpit = adaptar(tab, PERFIS["cockpit"], "cockpit")
    oculos = adaptar(tab, PERFIS["oculos"], "oculos")
    falante = adaptar(tab, PERFIS["falante"], "falante")
    assert "conteudo" in cockpit and "conteudo" not in oculos and len(oculos["linhas"]) <= 4
    assert "linhas" not in falante and "conteudo" not in falante and falante["fala"].startswith("Placar: tabela com 30")
    html = validar({"tipo": "html", "titulo": "H", "conteudo": EXEMPLOS["html"]})
    assert "conteudo" in adaptar(html, PERFIS["cockpit"]) and all("conteudo" not in adaptar(html, PERFIS[p]) for p in ("janela", "visor", "terminal"))
    assert adaptar(html, PERFIS["janela"])["linhas"] == ["um oi em negrito"]
    g = validar({"tipo": "grafico", "titulo": "G", "conteudo": EXEMPLOS["grafico"]})
    assert "▁" in adaptar(g, PERFIS["terminal"], "terminal")["linhas"][0] and resumo_falado(g) == "G: subindo, último valor 12,5 R$."
    v = validar({"tipo": "texto", "titulo": "V", "ancoragem": {"pos3d": [0.1, 1.2, -0.8]}})
    assert adaptar(v, PERFIS["visor"])["ancoragem"]["pos3d"] == [0.1, 1.2, -0.8] and "pos3d" not in adaptar(v, PERFIS["cockpit"])["ancoragem"]


def test_privado_e_limite_por_superficie():
    blocos = [validar({"tipo": "texto", "titulo": f"b{i}", "prioridade": i % 4}) for i in range(8)]
    blocos.append(validar({"tipo": "texto", "titulo": "finanças", "privado": True, "prioridade": 3}))
    assert len(selecionar(blocos, PERFIS["oculos"], "oculos", True)) == 3
    assert selecionar(blocos, PERFIS["oculos"], "oculos", True)[0].titulo == "finanças"
    assert all(b.titulo != "finanças" for b in selecionar(blocos, PERFIS["cockpit"], "cockpit", dono_ok=False))
    visita = capacidades_de("cockpit", {"confiavel": False})
    assert all(b.titulo != "finanças" for b in selecionar(blocos, visita, "cockpit", True))


def test_cliente_nao_se_promove_a_confiavel_e_numeros_ruins_sao_ignorados():
    c = capacidades_de("oculos", {"confiavel": True, "largura": "abc", "blocos_max": 5, "html": 1, "entrada": ["voz"] * 20})
    assert c.confiavel is True and c.largura == 640 and c.blocos_max == 5 and c.html is True and len(c.entrada) == 6
    assert capacidades_de("oculos", {"confiavel": False}).confiavel is False


def test_sparkline_e_texto():
    assert sparkline([1, 2, 3, 4]) == "▁▃▅█" and sparkline([5, 5]) == "▄▄"
    b = validar({"tipo": "lista", "titulo": "L", "conteudo": {"itens": [f"item {i}" for i in range(20)]}})
    ls = linhas_texto(b, 40, 5)
    assert len(ls) == 5 and ls[-1].startswith("… +16")


# ── gerenciador ──────────────────────────────────────────────────────────────
class Relogio:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t


def _g(tmp_path=None, **kw):
    f = Fontes()
    estado = {"n": 1}
    f.registrar("contador", "teste", "metricas", lambda p: {"itens": [{"rotulo": "n", "valor": str(estado["n"])}]}, intervalo_padrao=5)
    f.registrar("segredo", "teste privado", "texto", lambda p: {"texto": "saldo 10"}, privada=True)
    f.registrar("quebrada", "falha", "texto", lambda p: 1 / 0)
    rel = Relogio()
    falas = []
    g = Gerenciador(f, tmp_path, relogio=rel, falar=falas.append, uso=Uso(tmp_path), **kw)
    return g, rel, estado, falas


def test_abrir_atualizar_fechar_desfazer(tmp_path):
    g, rel, _, falas = _g(tmp_path)
    b = g.abrir({"tipo": "texto", "titulo": "Nota", "id": "nota", "conteudo": "oi", "falar": True})
    assert b.versao == 1 and falas == ["Nota: oi."]
    b2 = g.atualizar("nota", {"conteudo": {"texto": "tchau"}, "prioridade": 3})
    assert b2.versao == 2 and b2.conteudo["texto"] == "tchau" and b2.criado == b.criado
    g.fechar("nota")
    assert "nota" not in g.blocos
    assert "fechar" in g.desfazer() and g.blocos["nota"].conteudo["texto"] == "tchau"
    g.desfazer(); assert g.blocos["nota"].conteudo["texto"] == "oi"
    g.desfazer(); assert "nota" not in g.blocos


def test_fonte_viva_privada_ttl_e_refresh(tmp_path):
    g, rel, estado, _ = _g(tmp_path)
    b = g.abrir({"tipo": "texto", "titulo": "Contador", "fonte": "contador", "id": "c", "ttl_s": 60})
    assert b.tipo == "metricas" and b.conteudo["itens"][0]["valor"] == "1" and b.intervalo_s == 5
    assert g.abrir({"tipo": "texto", "titulo": "S", "fonte": "segredo"}).privado
    with pytest.raises(BlocoInvalido):
        g.abrir({"tipo": "texto", "titulo": "X", "fonte": "inventada"})
    q = g.abrir({"tipo": "texto", "titulo": "Q", "fonte": "quebrada", "id": "q"})
    assert q.tipo == "status" and "ZeroDivisionError" in q.conteudo["texto"] and "q" in g.erros_fonte
    rel.t += 3; asyncio.run(g.tique()); assert g.blocos["c"].versao == 1          # ainda não deu 5 s
    estado["n"] = 2; rel.t += 3; asyncio.run(g.tique())
    assert g.blocos["c"].versao == 2 and g.blocos["c"].conteudo["itens"][0]["valor"] == "2"
    rel.t += 5; asyncio.run(g.tique()); assert g.blocos["c"].versao == 2           # mesmo dado: não difunde à toa
    rel.t += 60; asyncio.run(g.tique()); assert "c" not in g.blocos                # TTL


def test_limite_de_abertos_fecha_o_menos_importante(tmp_path):
    g, rel, _, _ = _g(tmp_path, max_abertos=3)
    for i, p in enumerate((2, 0, 3)):
        rel.t += 1; g.abrir({"tipo": "texto", "titulo": f"b{i}", "id": f"b{i}", "prioridade": p})
    rel.t += 1; g.abrir({"tipo": "texto", "titulo": "novo", "id": "novo", "prioridade": 1})
    assert set(g.blocos) == {"b0", "b2", "novo"}


def test_layouts_guardam_receita_e_nao_gravam_privado_estatico(tmp_path):
    g, rel, _, _ = _g(tmp_path)
    g.abrir({"tipo": "texto", "titulo": "Contador", "fonte": "contador", "id": "c"})
    g.abrir({"tipo": "texto", "titulo": "Nota", "id": "n", "conteudo": "fixa"})
    g.abrir({"tipo": "texto", "titulo": "Diário", "id": "d", "conteudo": "coisa íntima", "privado": True})
    assert g.salvar_layout("Trabalho") == 2
    texto = (tmp_path / "layouts.json").read_text()
    assert "íntima" not in texto and '"conteudo": {}' in texto
    g.fechar("todos"); assert not g.blocos
    assert sorted(g.abrir_layout("trabalho")) == ["c", "n"] and g.blocos["c"].conteudo["itens"]
    with pytest.raises(KeyError):
        g.abrir_layout("nao-existe")


# ── protocolo ────────────────────────────────────────────────────────────────
def test_sessao_recebe_so_o_diff_e_privado_some_ao_trancar(tmp_path):
    dono = {"ok": True}
    g, rel, _, _ = _g(tmp_path)
    g.dono_ok = lambda: dono["ok"]
    msgs = []
    s = sessao_de_ola({"op": "ola", "perfil": "oculos"}, msgs.append, confiavel=True)
    g.conectar(s)
    g.abrir({"tipo": "texto", "titulo": "A", "id": "a"})
    g.abrir({"tipo": "texto", "titulo": "Saldo", "id": "s", "fonte": "segredo"})
    assert [m["op"] for m in msgs] == ["abrir", "abrir"] and msgs[1]["bloco"]["privado"]
    g.atualizar("a", {"titulo": "A2"})
    assert msgs[-1]["op"] == "atualizar" and msgs[-1]["bloco"]["titulo"] == "A2" and len(msgs) == 3
    dono["ok"] = False; asyncio.run(g.tique())
    assert msgs[-1] == {"op": "fechar", "id": "s"}
    g.fechar("a"); assert msgs[-1] == {"op": "fechar", "id": "a"}


def test_cliente_lento_e_desconectado_sem_travar_os_outros(tmp_path):
    g, *_ = _g(tmp_path)
    def cheio(msg): raise RuntimeError("fila cheia")
    ok = []
    g.conectar(Sessao("oculos", PERFIS["oculos"], cheio))
    g.conectar(Sessao("cockpit", PERFIS["cockpit"], ok.append))
    g.abrir({"tipo": "texto", "titulo": "A"})
    assert len(g.sessoes) == 1 and ok and ok[0]["op"] == "abrir"


def test_acoes_de_bloco_so_com_intencao_do_proprio_bloco_e_superficie_do_dono(tmp_path):
    g, *_ = _g(tmp_path)
    g.abrir({"tipo": "acoes", "titulo": "Deploy", "id": "d", "conteudo": EXEMPLOS["acoes"]})
    feitas = []
    async def executar(i): feitas.append(i)
    dono = Sessao("cockpit", PERFIS["cockpit"], lambda m: None)
    visita = Sessao("cockpit", capacidades_de("cockpit", {"confiavel": False}), lambda m: None)
    async def go():
        r1 = await tratar_mensagem(g, dono, {"op": "acao", "id": "d", "intencao": "apaga o repositório"}, executar)
        r2 = await tratar_mensagem(g, visita, {"op": "acao", "id": "d", "intencao": "publica o deploy da BUB"}, executar)
        r3 = await tratar_mensagem(g, dono, {"op": "acao", "id": "d", "intencao": "publica o deploy da BUB"}, executar)
        await asyncio.sleep(0)
        return r1, r2, r3
    r1, r2, r3 = asyncio.run(go())
    assert r1["op"] == "erro" and r2["op"] == "erro" and r3["op"] == "falar" and feitas == ["publica o deploy da BUB"]


# ── voz ──────────────────────────────────────────────────────────────────────
def test_comandos_de_voz_sem_modelo(tmp_path):
    g = Gerenciador(padrao(None), tmp_path)
    m = Modelos(tmp_path, g.fontes)
    assert comando("Jaime, abre o bloco da máquina", g, m) == "Máquina aberto." and "maquina" in g.blocos
    assert comando("abre um bloco de hora", g, m) == "Agora aberto."
    assert comando("quais blocos estão abertos?", g, m) == "Abertos: Máquina, Agora."
    assert comando("salva esse layout como trabalho", g, m) == "Layout trabalho salvo com 2 blocos."
    assert comando("fecha o bloco da máquina", g, m) == "Fechei Máquina." and "maquina" not in g.blocos
    assert comando("fecha todos os blocos", g, m) == "Fechei 1 bloco."
    assert comando("abre o layout trabalho", g, m) == "Layout trabalho aberto: 2 blocos."
    assert comando("abre finanças", g, m) is None                       # sem "bloco": segue ao cérebro como antes
    assert comando("abre um bloco comparando a BUB com a Oldsen", g, m) is None   # novo: o cérebro compõe
    assert comando("que horas são?", g, m) is None


# ── modelos e uso ────────────────────────────────────────────────────────────
def test_modelos_embutidos_passam_no_contrato():
    fontes = padrao(None)
    for nome, d in EMBUTIDOS.items():
        b = validar({**d, "conteudo": EXEMPLOS.get(d["tipo"], {})})
        assert contrato(b) == [], nome


def test_modelo_novo_passa_pelo_contrato_tem_versoes_e_reverte(tmp_path):
    m = Modelos(tmp_path, padrao(None))
    ok, msg = m.salvar("painel-bub", {"tipo": "metricas", "titulo": "BUB hoje", "conteudo": {"itens": [{"rotulo": "leads", "valor": "12"}]}})
    assert ok and "v1" in msg
    ok, msg = m.salvar("painel-bub", {"tipo": "metricas", "titulo": "BUB agora", "conteudo": {"itens": [{"rotulo": "leads", "valor": "14"}]}})
    assert ok and m.instanciar("painel-bub")["titulo"] == "BUB agora"
    assert m.reverter("painel-bub")[0] and m.instanciar("painel-bub")["titulo"] == "BUB hoje"
    assert not m.salvar("financas", {"tipo": "texto", "titulo": "x"})[0]                          # embutido
    assert not m.salvar("x", {"tipo": "texto", "titulo": "x", "fonte": "inventada"})[0]
    assert not m.salvar("x", {"tipo": "texto", "titulo": "segredo", "conteudo": "123", "privado": True})[0]
    assert not m.salvar("x", {"tipo": "metricas", "titulo": "vazio", "conteudo": {}})[0]             # nada p/ mostrar/falar
    assert Modelos(tmp_path).instanciar("painel-bub")["titulo"] == "BUB hoje"                         # persistiu


def test_uso_vira_sinal_de_evolucao(tmp_path):
    g, rel, _, _ = _g(tmp_path)
    for _ in range(4):
        g.abrir({"tipo": "texto", "titulo": "Clima", "id": "clima", "conteudo": "sol"}, origem="jaime")
        rel.t += 2; g.fechar("clima", motivo="fechado em cockpit"); rel.t += 10
    for _ in range(3):
        g.abrir({"tipo": "texto", "titulo": "Tarefas", "id": "t", "conteudo": "x"}, origem="joao"); rel.t += 60; g.fechar("t")
    s = g.uso.sinais()
    assert "fechou em <5 s 4 de 4" in s and "tipo:texto" in s
    assert Uso(tmp_path).dados                                                                         # persistiu


# ── integração com o orquestrador e a evolução ──────────────────────────────
def test_orquestrador_resolve_comando_de_bloco_sem_modelo(tmp_path, monkeypatch):
    from jaime.blocos import integracao
    from jaime.orchestrator.jaime import Jaime
    from jaime.vigia.acesso import Acesso, hash_senha
    j = Jaime.__new__(Jaime)
    j.acesso = Acesso(hash_senha("1234 5678")); j.acesso.tentar("1234 5678")
    j.falante_atual = ""; j._senha_incerta = 0; j.proposta_renomear = None; j.aguardando_nome = False; j.porteiro = None
    j.vault = SimpleNamespace(diario=lambda *a: None); j.estado = SimpleNamespace(resumo_curto=lambda: "ok")
    j.gravador = SimpleNamespace(gravando=False); j.vigia = SimpleNamespace(lote=None, convidado="")
    j.confianca = SimpleNamespace(pendente=None); j._client = object()
    async def _mundo(t): return None
    j._mundo = _mundo
    integracao.montar(j, pasta=tmp_path, emitir=lambda *a, **k: None, env={})
    assert j._servidor_blocos() and set(j._servidor_blocos()) == {"blocos"}
    async def turno(t):
        return [x async for x in j._ask_stream(t, canal="voice")]
    assert asyncio.run(turno("abre o bloco da máquina")) == ["Máquina aberto."]
    assert asyncio.run(turno("fecha todos os blocos")) == ["Fechei 1 bloco."]
    integracao.montar(j, env={"JAIME_BLOCOS": "off"})
    assert integracao.ESTADO["g"] is None


def test_evolucao_recebe_sinais_extras(tmp_path):
    from jaime import evolucao as ev
    from jaime.brain.vault import Vault
    from jaime.brain.estado import Estado
    for d in ("00-Jaime", "01-Estado", "40-Diario", "90-Estudo"):
        (tmp_path / "v" / d).mkdir(parents=True)
    v = Vault(tmp_path / "v")
    e = ev.Evolucao(SimpleNamespace(vault=v, estado=Estado(v)), tmp_path)
    e.sinais_extras = [lambda: "Interface (blocos):\n- bloco 'clima': rejeitado", lambda: 1 / 0]
    assert "bloco 'clima'" in e.sinais()


# ── WebSocket JBP ponta a ponta ─────────────────────────────────────────────
def _app(tmp_path):
    from fastapi import FastAPI
    from jaime.blocos import integracao
    from jaime.blocos.rotas import router
    integracao.montar(None, pasta=tmp_path, emitir=lambda *a, **k: None, env={})
    app = FastAPI(); app.include_router(router)
    return app, integracao.ESTADO["g"]


def test_websocket_oculos_recebem_blocos_adaptados_e_fecham(tmp_path):
    from fastapi.testclient import TestClient
    app, g = _app(tmp_path)
    with TestClient(app) as c:
        with c.websocket_connect("/blocos/ws") as ws:
            ws.send_json({"op": "ola", "perfil": "oculos", "nome": "óculos"})
            assert ws.receive_json()["op"] == "bem_vindo"
            assert c.post("/blocos", json={"modelo": "maquina"}).json()["ok"]
            m = ws.receive_json()
            assert m["op"] == "abrir" and m["bloco"]["titulo"] == "Máquina" and "fala" in m["bloco"] and len(m["bloco"]["linhas"]) <= 4
            c.post("/blocos", json={"tipo": "tabela", "titulo": "T", "id": "t", "conteudo": {"colunas": ["a"], "linhas": [["1"]]}})
            m = ws.receive_json()
            assert m["bloco"]["id"] == "t" and "conteudo" not in m["bloco"]           # óculos não desenham tabela
            ws.send_json({"op": "fechar", "id": "t"})
            assert ws.receive_json() == {"op": "fechar", "id": "t"} and "t" not in g.blocos
            ws.send_json({"op": "ping"}); assert ws.receive_json() == {"op": "pong"}
            ws.send_json({"op": "ler", "id": "maquina"}); assert ws.receive_json()["texto"].startswith("Máquina: CPU")
        assert g.sessoes == {}                                              # desconectou e saiu


def test_websocket_recusa_handshake_ruim_e_site_de_fora(tmp_path):
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    app, g = _app(tmp_path)
    with TestClient(app) as c:
        with c.websocket_connect("/blocos/ws") as ws:
            ws.send_json({"op": "abrir"})
            assert ws.receive_json()["op"] == "erro"
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect("/blocos/ws", headers={"origin": "https://site-malicioso.com"}) as ws:
                ws.receive_json()
        assert c.post("/blocos", json={"modelo": "relogio"}, headers={"origin": "https://site-malicioso.com"}).status_code == 403


def test_dispositivo_de_fora_so_com_token_proprio():
    from jaime.blocos.integracao import token_dispositivo
    from jaime.blocos.rotas import dispositivo_autorizado
    t = token_dispositivo("segredo-forte", "oculos-joao")
    assert dispositivo_autorizado("oculos-joao", t, "segredo-forte")
    assert not dispositivo_autorizado("outro", t, "segredo-forte")
    assert not dispositivo_autorizado("oculos-joao", t, "troque-isto")                 # segredo padrão: ninguém de fora
    assert not dispositivo_autorizado("oculos-joao", "", "segredo-forte")
