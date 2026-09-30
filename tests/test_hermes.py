"""Hermes Agent: cliente, aprovações pelo Vigia (só 'once', só com o sim do João), tarefa sensível segura antes de sair."""
import asyncio, json
import httpx
import pytest
import jaime.hermes.tools as mod
from jaime.hermes.cliente import HermesCliente, descrever_aprovacao
from jaime.hermes.tools import motivo_tarefa
from jaime.vigia.hooks import Vigia

CHAVE = "segredo-do-hermes-123"


class FakeHermes:
    """Imita /v1/runs do Hermes: 'PERIGO' para em waiting_for_approval; o resto completa."""
    def __init__(self):
        self.runs, self.respostas, self.criados = {}, [], []

    def __call__(self, req: httpx.Request):
        assert req.headers["authorization"] == f"Bearer {CHAVE}"
        p = req.url.path
        if p == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if p == "/v1/runs" and req.method == "POST":
            b = json.loads(req.content); rid = f"run_{len(self.runs)}"; self.criados.append(b)
            if "PERIGO" in b["input"]:
                self.runs[rid] = {"status": "waiting_for_approval", "approval": {"command": "rm -rf /tmp/x", "description": "delete", "request_id": "req1"}}
            else:
                self.runs[rid] = {"status": "completed", "output": f"feito: {b['input']}"}
            return httpx.Response(202, json={"run_id": rid, "status": "started"})
        rid = p.split("/")[3]
        if p.endswith("/approval"):
            b = json.loads(req.content); self.respostas.append(b)
            self.runs[rid] = {"status": "completed", "output": "apagado" if b["choice"] == "once" else "BLOCKED"}
            return httpx.Response(200, json={"resolved": 1})
        if p.endswith("/stop"):
            return httpx.Response(200, json={"status": "stopping"})
        return httpx.Response(200, json={"run_id": rid, **self.runs[rid]})


def cliente(fake=None):
    fake = fake or FakeHermes()
    return HermesCliente(url="http://127.0.0.1:8642", chave=CHAVE, ligado=True, transporte=httpx.MockTransport(fake)), fake


def ferramentas(c, v):
    mod.create_sdk_mcp_server = lambda name, version, tools: {t.name: t.handler for t in tools}
    return mod.build_hermes_server(c, v)


txt = lambda r: r["content"][0]["text"]


def test_validacao_do_endpoint():
    assert HermesCliente(ligado=False).motivo_indisponivel == "JAIME_HERMES=off"
    assert "HTTPS" in HermesCliente(url="http://192.168.0.9:8642", chave="k", ligado=True).motivo_indisponivel
    assert "HERMES_API_KEY" in HermesCliente(ligado=True).motivo_indisponivel
    assert HermesCliente(url="https://hermes.minha.rede", chave="k", ligado=True).disponivel
    c = HermesCliente.do_ambiente({"JAIME_HERMES": "on", "HERMES_API_KEY": "k", "HERMES_TIMEOUT_S": "abc"})
    assert c.disponivel and c.timeout == 30.0


def test_chave_nunca_aparece_em_erro():
    def quebra(req):
        raise httpx.ConnectError(f"falhou com {CHAVE}")
    c = HermesCliente(url="http://127.0.0.1:8642", chave=CHAVE, ligado=True, transporte=httpx.MockTransport(quebra))
    r = asyncio.run(c.executar("oi"))
    assert r.status == "erro" and CHAVE not in r.erro and "•••" in r.erro


def test_so_once_ou_deny():
    c, _ = cliente()
    with pytest.raises(ValueError):
        asyncio.run(c.responder_aprovacao("run_0", "req1", "always"))


def test_delegar_simples_completa():
    c, fake = cliente(); T = ferramentas(c, Vigia())
    r = txt(asyncio.run(T["hermes_delegar"]({"tarefa": "resume o README do projeto"})))
    assert "feito: resume o README" in r and fake.criados[0]["session_id"] == "jaime"


def test_comando_perigoso_so_com_sim_do_joao():
    c, fake = cliente(); v = Vigia(); T = ferramentas(c, v)
    r = txt(asyncio.run(T["hermes_delegar"]({"tarefa": "PERIGO limpa a pasta"})))
    assert "precisa do sim do João" in r and v.pedir_lote().startswith("Você deseja que eu deixe o Hermes rodar")
    args = {"run_id": "run_0", "request_id": "req1"}
    assert "precisa do sim" in txt(asyncio.run(T["hermes_aprovar"](args))) and fake.respostas == []   # sem sim: nada sai
    v.liberar_lote()
    r = txt(asyncio.run(T["hermes_aprovar"](args)))
    assert "apagado" in r and fake.respostas == [{"choice": "once", "request_id": "req1"}]
    assert "precisa do sim" in txt(asyncio.run(T["hermes_aprovar"](args)))      # o mesmo sim não vale duas vezes


def test_negar_e_livre():
    c, fake = cliente(); T = ferramentas(c, Vigia())
    asyncio.run(T["hermes_delegar"]({"tarefa": "PERIGO"}))
    r = txt(asyncio.run(T["hermes_negar"]({"run_id": "run_0", "request_id": "req1"})))
    assert fake.respostas[-1]["choice"] == "deny" and "BLOCKED" in r


def test_tarefa_sensivel_segura_antes_de_sair():
    c, fake = cliente(); v = Vigia(); T = ferramentas(c, v)
    r = txt(asyncio.run(T["hermes_delegar"]({"tarefa": "manda mensagem no WhatsApp pro Gabriel"})))
    assert "precisa do sim" in r and fake.criados == []
    v.liberar_lote()
    assert "feito" in txt(asyncio.run(T["hermes_delegar"]({"tarefa": "manda mensagem no WhatsApp pro Gabriel"})))


def test_convidado_nao_libera_nada():
    c, fake = cliente(); v = Vigia(); v.convidado = "Gabriel"; T = ferramentas(c, v)
    assert "visita" in txt(asyncio.run(T["hermes_delegar"]({"tarefa": "apaga os arquivos da pasta X"}))) and fake.criados == []


@pytest.mark.parametrize("frase,esperado", [
    ("resume o README", None), ("pesquisa preço de GPU", None), ("organiza as fotos por data", None),
    ("apaga os arquivos da pasta Downloads", "apagar"), ("publica o post no Instagram", "publicar"),
    ("faz git push na main", "mexer na main"), ("instala o docker", "instalar/mexer no sistema"),
    ("compra um mouse", "comprar/pagar"), ("envia o e-mail pro contador", "mandar mensagem"),
])
def test_motivo_tarefa(frase, esperado):
    assert motivo_tarefa(frase) == esperado


def test_descrever_aprovacao():
    assert descrever_aprovacao({"command": "rm -rf x", "description": "delete"}) == "deixe o Hermes rodar `rm -rf x` (delete)"
