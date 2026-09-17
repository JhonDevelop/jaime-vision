"""O harness: o laço que persegue um objetivo, verifica contra critério, corrige, replaneja e desiste.
O que não pode cair: passo só fecha com PRONTO de verdade; falha volta com o PORQUÊ na tentativa
seguinte; replanejar preserva o que já deu certo; e o laço sempre para — por conclusão, teto ou ordem."""
import asyncio
from types import SimpleNamespace
import pytest
from jaime.cortex.harness import Harness, Passo, Perseguicao, ler_passos


class _Jaime:
    def __init__(self):
        self.linhas = []
        self.vault = SimpleNamespace(diario=lambda t, s="Log": self.linhas.append(t))


def _h(**kw):
    return Harness(_Jaime(), **kw)


# ── leitura do plano ──────────────────────────────────────────────────────
def test_passo_sem_criterio_nao_vira_passo():
    ps = ler_passos("1. subir o servidor | responde 200\n- só o título, sem critério\n* outro | com critério\nlixo")
    assert [p.titulo for p in ps] == ["subir o servidor", "outro"]
    assert ps[0].criterio == "responde 200"

def test_o_plano_tem_teto():
    assert len(ler_passos("\n".join(f"p{i} | c{i}" for i in range(20)), 5)) == 5


# ── o caminho feliz ───────────────────────────────────────────────────────
def test_persegue_ate_o_fim_e_conclui():
    h = _h(planejar=lambda o: _ok([Passo("a", "ca"), Passo("b", "cb")]),
           agir=lambda p, s: _ok(f"fiz {s.titulo}"),
           verificar=lambda p, s: _ok("PRONTO"))
    r = asyncio.run(h.perseguir("fazer as duas coisas"))
    assert r.estado == "concluida" and r.ciclos == 2
    assert [x.estado for x in r.passos] == ["ok", "ok"]
    assert "2/2 passos" in r.resumo()

def test_nao_fecha_passo_sem_pronto_de_verdade():
    """O modelo adora dizer que deu certo. Só a palavra PRONTO fecha."""
    vistos = []
    h = _h(max_tentativas=2, max_replanos=0,
           planejar=lambda o: _ok([Passo("a", "ca")]),
           agir=lambda p, s: _ok("acho que consegui"),
           verificar=lambda p, s: (vistos.append(1), _ok("ficou muito bom, parabéns"))[1])
    r = asyncio.run(h.perseguir("x"))
    assert r.estado == "desistiu" and len(vistos) == 2
    assert r.passos[0].estado == "desistido"


# ── corrigir: a falha volta com o porquê ──────────────────────────────────
def test_a_segunda_tentativa_sabe_por_que_a_primeira_falhou():
    recebido = []
    async def agir(p, s):
        recebido.append(s.porque_falhou)
        return "tentei"
    async def verificar(p, s):
        return "PRONTO" if s.tentativas >= 2 else "FALTA: o arquivo não existe"
    h = _h(planejar=lambda o: _ok([Passo("a", "ca")]), agir=agir, verificar=verificar)
    r = asyncio.run(h.perseguir("x"))
    assert r.estado == "concluida"
    assert recebido == ["", "FALTA: o arquivo não existe"]      # a 2ª tentativa recebeu o motivo


# ── replanejar: o que deu certo fica ──────────────────────────────────────
def test_replaneja_preservando_o_que_ja_deu_certo():
    async def verificar(p, s):
        return "PRONTO" if s.titulo in ("a", "novo1", "novo2") else "FALTA: esse caminho não existe"
    async def replanejar(p, travado):
        return [Passo("novo1", "c1"), Passo("novo2", "c2")]
    h = _h(max_tentativas=2,
           planejar=lambda o: _ok([Passo("a", "ca"), Passo("b", "cb")]),
           agir=lambda p, s: _ok("fiz"), verificar=verificar, replanejar=replanejar)
    r = asyncio.run(h.perseguir("x"))
    assert r.estado == "concluida" and r.replanos == 1
    assert [x.titulo for x in r.passos] == ["a", "novo1", "novo2"]     # 'b' saiu, 'a' ficou
    assert all(x.estado == "ok" for x in r.passos)

def test_sem_saida_no_replanejamento_e_desistencia_honesta():
    h = _h(max_tentativas=1,
           planejar=lambda o: _ok([Passo("a", "ca")]),
           agir=lambda p, s: _ok("fiz"), verificar=lambda p, s: _ok("FALTA tudo"),
           replanejar=lambda p, t: _ok([]))
    r = asyncio.run(h.perseguir("x"))
    assert r.estado == "desistiu" and "sem outro caminho" in r.motivo

def test_desiste_depois_de_replanejar_o_maximo():
    h = _h(max_tentativas=1, max_replanos=2,
           planejar=lambda o: _ok([Passo("a", "ca")]),
           agir=lambda p, s: _ok("fiz"), verificar=lambda p, s: _ok("FALTA"),
           replanejar=lambda p, t: _ok([Passo("outro", "c")]))
    r = asyncio.run(h.perseguir("x"))
    assert r.estado == "desistiu" and r.replanos == 2 and "continuo batendo" in r.motivo


# ── o laço sempre para ────────────────────────────────────────────────────
def test_teto_de_ciclos_segura_laco_infinito():
    h = _h(max_ciclos=5, max_tentativas=99, max_replanos=99,
           planejar=lambda o: _ok([Passo("a", "ca")]),
           agir=lambda p, s: _ok("fiz"), verificar=lambda p, s: _ok("FALTA"))
    r = asyncio.run(h.perseguir("x"))
    assert r.estado == "desistiu" and r.ciclos == 5 and "teto de 5 ciclos" in r.motivo

def test_o_joao_manda_parar_e_ele_para():
    h = _h(planejar=lambda o: _ok([Passo("a", "ca"), Passo("b", "cb")]),
           verificar=lambda p, s: _ok("PRONTO"))
    async def agir(p, s):
        h.interromper()                       # o João interrompe no meio do primeiro passo
        return "fiz"
    h.agir = agir
    r = asyncio.run(h.perseguir("x"))
    assert r.estado == "interrompida" and "mandou parar" in r.motivo

def test_plano_vazio_nao_vira_perseguicao():
    r = asyncio.run(_h(planejar=lambda o: _ok([])).perseguir("coisa impossível de quebrar"))
    assert r.estado == "desistiu" and "passos" in r.motivo

def test_erro_ao_agir_nao_derruba_o_laco():
    async def agir(p, s):
        raise RuntimeError("a ferramenta explodiu")
    h = _h(max_tentativas=1, max_replanos=0, planejar=lambda o: _ok([Passo("a", "ca")]),
           agir=agir, verificar=lambda p, s: _ok("FALTA"))
    r = asyncio.run(h.perseguir("x"))
    assert r.estado == "desistiu" and "explodiu" in r.passos[0].resultado

def test_nao_persegue_dois_objetivos_ao_mesmo_tempo():
    h = _h(planejar=lambda o: _ok([Passo("a", "ca")]), agir=lambda p, s: _ok("fiz"),
           verificar=lambda p, s: _ok("PRONTO"))
    asyncio.run(h.perseguir("primeiro"))
    h.atual.estado = "rodando"
    with pytest.raises(RuntimeError, match="já estou perseguindo"):
        asyncio.run(h.perseguir("segundo"))

def test_como_vai_conta_o_estado_em_portugues():
    h = _h()
    assert "não estou perseguindo" in h.como_vai()
    h.atual = Perseguicao("arrumar o cockpit", [Passo("a", "c", estado="ok"), Passo("b", "c")])
    t = h.como_vai()
    assert "arrumar o cockpit" in t and "✓ a" in t and "◻ b" in t


async def _coro(v):
    return v

def _ok(v):
    return _coro(v)
