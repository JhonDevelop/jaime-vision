"""Fase 8 — IA local: desligada por padrão, host do dono, estrita sem nuvem escondida, rota só explícita."""
import asyncio, json, random
from types import SimpleNamespace
import httpx
import pytest
from jaime.cortex.bench_local import CASOS, rodar
from jaime.cortex.placar import Placar
from jaime.cortex.provedores.local import ProvedorLocal
from jaime.cortex.roteador import Roteador

MODELOS = {"decisao": "claude-fable", "codigo": "claude-opus", "padrao": "claude-sonnet", "rotina": "claude-haiku"}


def servidor(resposta="ok", status=200, modelos=("qwen3:8b",), chamadas=None):
    def handler(req: httpx.Request):
        if chamadas is not None:
            chamadas.append((req.method, str(req.url), req.headers.get("authorization", "")))
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": m} for m in modelos]})
        if status != 200:
            return httpx.Response(status, text="erro do servidor")
        corpo = json.loads(req.content)
        texto = resposta(corpo) if callable(resposta) else resposta
        return httpx.Response(200, json={"choices": [{"message": {"content": texto}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
    return httpx.MockTransport(handler)


def test_desligado_por_padrao_e_exige_modelo():
    assert not ProvedorLocal.do_ambiente({}).disponivel
    assert "MODEL" in ProvedorLocal.do_ambiente({"JAIME_LOCAL_AI": "on"}).motivo_indisponivel
    assert ProvedorLocal.do_ambiente({"JAIME_LOCAL_AI": "on", "JAIME_LOCAL_AI_MODEL": "qwen3:8b"}).disponivel


@pytest.mark.parametrize("url,hosts,token,ok", [
    ("http://127.0.0.1:11434/v1", "", "", True),
    ("https://api.vendor.com/v1", "", "", False),                      # nuvem disfarçada de local
    ("http://192.168.0.50:11434/v1", "", "", False),                   # LAN sem estar na lista
    ("http://192.168.0.50:11434/v1", "192.168.0.50", "", False),       # LAN sem TLS nem token
    ("http://192.168.0.50:11434/v1", "192.168.0.50", "segredo", True),
    ("https://rtx.local:8443/v1", "rtx.local", "", True),
    ("http://inference.local/v1", "", "", True),                       # OpenShell
])
def test_hosts_do_dono_e_lan_com_tls_ou_token(url, hosts, token, ok):
    p = ProvedorLocal.do_ambiente({"JAIME_LOCAL_AI": "on", "JAIME_LOCAL_AI_MODEL": "m", "JAIME_LOCAL_AI_BASE_URL": url,
                                   "JAIME_LOCAL_AI_HOSTS": hosts, "JAIME_LOCAL_AI_TOKEN": token})
    assert p.disponivel is ok, p.motivo_indisponivel


def test_responde_sem_custo_por_token_e_manda_token_na_lan():
    ch = []
    p = ProvedorLocal("http://192.168.0.50:11434/v1", "qwen3:8b", True, hosts_extra={"192.168.0.50"}, token="segredo",
                      transporte=servidor("Olá, João.", chamadas=ch))
    r = asyncio.run(p.responder("oi", "contexto"))
    assert r.ok and r.texto == "Olá, João." and r.custo == 0.0 and r.modelo == "local:qwen3:8b" and r.tokens == 15
    assert ch[0][2] == "Bearer segredo"
    assert asyncio.run(p.saude()) == (True, "ok")


def test_saude_detecta_modelo_nao_carregado():
    p = ProvedorLocal("http://127.0.0.1:11434/v1", "llama-70b", True, transporte=servidor(modelos=("qwen3:8b",)))
    ok, msg = asyncio.run(p.saude())
    assert not ok and "não carregado" in msg


def test_disjuntor_abre_depois_de_falhas_seguidas():
    t = [0.0]
    ch = []
    p = ProvedorLocal("http://127.0.0.1:11434/v1", "m", True, transporte=servidor(status=500, chamadas=ch), relogio=lambda: t[0])
    for _ in range(3):
        assert not asyncio.run(p.responder("x")).ok
    r = asyncio.run(p.responder("x"))
    assert "circuito aberto" in r.erro and len(ch) == 3              # a 4ª nem foi à rede
    t[0] = 61.0
    asyncio.run(p.responder("x")); assert len(ch) == 4


def test_roteador_local_so_por_rota_explicita_nunca_por_exploracao(tmp_path):
    r = Roteador(MODELOS, Placar(tmp_path), exploracao=1.0, rng=random.Random(1), local="qwen3:8b")
    for _ in range(300):                                               # exploração 100%: mesmo assim nunca o local
        assert not r.decidir("que horas são hoje na agenda").modelo.startswith("local:")
    e = r.decidir("resume isso pelo modelo local")
    assert e.modelo == "local:qwen3:8b" and "pediu" in e.motivo
    r2 = Roteador(MODELOS, Placar(tmp_path), exploracao=0.0, local="qwen3:8b", local_tipos=("rotina",))
    assert r2.decidir("anota na agenda o dentista amanhã").modelo == "local:qwen3:8b"
    assert r2.decidir("refatora a função de deploy do repositório").modelo == "claude-opus"   # Central segue
    r3 = Roteador(MODELOS, Placar(tmp_path), exploracao=0.0)          # sem IA local configurada: frase não muda nada
    assert r3.decidir("resume isso pelo modelo local").modelo.startswith("claude")


def test_bench_local_registra_no_placar_com_custo_zero(tmp_path):
    def resp(corpo):
        q = corpo["messages"][-1]["content"]
        if "17 vezes 3" in q: return "51"
        if "tarefa" in q: return "- [ ] revisar o orçamento do cliente da reforma @bub"
        if "build" in q: return "A build terminou sem erros."
        if "Abre isso" in q: return "Qual deles: proposta ou contrato?"
        if "JSON" in q: return '{"nome": "Carlos", "cidade": "Ribeirão Preto"}'
        return "quinta"                                                # erra de propósito
    p = ProvedorLocal("http://127.0.0.1:11434/v1", "qwen3:8b", True, transporte=servidor(resp))
    pl = Placar(tmp_path)
    res = asyncio.run(rodar(p, pl))
    assert res["acertos"] == len(CASOS) - 1 and res["custo_api_usd"] == 0.0
    assert pl.amostras("local:qwen3:8b", "rotina") == 3 and "local:qwen3:8b" in (tmp_path / "01-Estado" / "Placar.md").read_text()


# ── no orquestrador: estrito não chama a nuvem ────────────────────────────────
class _Nada:
    def __getattr__(self, k):
        return lambda *a, **kw: None


def _jaime(provedor):
    from jaime.orchestrator.jaime import Jaime
    from jaime.vigia.acesso import Acesso, hash_senha
    j = Jaime.__new__(Jaime)
    j.acesso = Acesso(hash_senha("1234 5678")); j.acesso.tentar("1234 5678")
    j.falante_atual = ""; j._senha_incerta = 0; j.proposta_renomear = None; j.aguardando_nome = False; j.porteiro = None
    j.vault = _Nada(); j.estado = SimpleNamespace(resumo_curto=lambda: "ok"); j.gravador = SimpleNamespace(gravando=False)
    j.vigia = SimpleNamespace(lote=None, convidado="", lote_executado=False, descartar_lote=lambda: 0, pedir_lote=lambda: None,
                              ultimo_lote_classes=[])
    j.confianca = SimpleNamespace(pendente=None, responder=lambda t: None, aprovar=lambda c: None)
    j.humor = SimpleNamespace(registrar_tom=lambda *a: None, registrar_hora=lambda *a: None, registrar_resultado=lambda *a, **k: None, dados=lambda: {})
    j._client = object(); j._lock = asyncio.Lock()
    j.placar = SimpleNamespace(registrar=lambda *a, **k: j.registros.append(a))
    j.registros = []
    j.openai = SimpleNamespace(disponivel=False)
    j.s = SimpleNamespace(openai_uso="minimo", model_padrao="claude-sonnet")
    j.local = provedor
    j.roteador = Roteador(MODELOS, SimpleNamespace(taxa=lambda *a: 0.5, amostras=lambda *a: 0), 0.0, local=provedor.modelo)
    j.estudo = _Nada(); j._contexto_texto = lambda c="": ""
    j.nuvem = []
    async def _anthropic(*a):
        j.nuvem.append(a); yield "resposta da nuvem"
    j._turno_anthropic = _anthropic
    async def _mundo(t): return None
    async def _pos(*a): return None
    j._mundo = _mundo; j._pos_turno = _pos
    return j


def _turno(j, texto):
    async def go():
        return "".join([t async for t in j._ask_stream(texto, canal="hud")])
    return asyncio.run(go())


def test_estrito_quando_o_local_cai_avisa_e_nao_usa_a_nuvem():
    j = _jaime(ProvedorLocal("http://127.0.0.1:11434/v1", "qwen3:8b", True, estrito=True, transporte=servidor(status=503)))
    out = _turno(j, "resume o dia pelo modelo local")
    assert "modo estrito" in out and j.nuvem == []
    assert j.registros[-1][0] == "local:qwen3:8b" and j.registros[-1][2] == "erro"


def test_nao_estrito_cai_na_nuvem_e_diz_que_caiu():
    j = _jaime(ProvedorLocal("http://127.0.0.1:11434/v1", "qwen3:8b", True, estrito=False, transporte=servidor(status=503)))
    assert _turno(j, "resume o dia pelo modelo local") == "resposta da nuvem" and len(j.nuvem) == 1


def test_local_saudavel_responde_sem_nuvem():
    j = _jaime(ProvedorLocal("http://127.0.0.1:11434/v1", "qwen3:8b", True, transporte=servidor("Feito localmente.")))
    assert _turno(j, "resume o dia pelo modelo local") == "Feito localmente." and j.nuvem == []
