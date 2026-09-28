"""Fase 2 — "isso" = o objeto selecionado; TTL, plural, lado, ambiguidade e as armadilhas do português."""
import asyncio
from types import SimpleNamespace
from jaime.spatial.core import SpatialCore, SpatialObject, Vec3
from jaime.spatial.referencias import ContextoVoz, Resolvedor


class Relogio:
    def __init__(self): self.t = 100.0
    def __call__(self): return self.t


def _cena():
    rel = Relogio()
    c = SpatialCore(relogio=rel)
    c.add(SpatialObject("projeto:bub", "projeto", Vec3(0.2, 0.35, 0), label="BUB", resource_ref="~/projetos/bub"))
    c.add(SpatialObject("projeto:seventyone", "projeto", Vec3(0.4, 0.35, 0), label="SeventyOne"))
    c.add(SpatialObject("projeto:gearhead", "projeto", Vec3(0.6, 0.35, 0), label="GearHead"))
    return c, rel, Resolvedor(c, ttl_s=20, relogio=rel)


def test_isso_e_o_objeto_selecionado_por_gesto():
    c, rel, r = _cena()
    c.select("joao", "projeto:bub", 0.97)
    rel.t += 3
    res = r.resolver("Jaime, abre isso")
    assert res.status == "ok" and [o.id for o in res.objetos] == ["projeto:bub"]
    assert "projeto:bub" in res.contexto() and "~/projetos/bub" in res.contexto() and "3 s" in res.contexto()


def test_selecao_vencida_nao_vale_mais():
    c, rel, r = _cena()
    c.select("joao", "projeto:bub", 0.97)
    rel.t += 25
    assert r.resolver("abre isso").status == "nenhum"


def test_isso_da_conversa_e_frases_comuns_nao_viram_referencia_espacial():
    c, rel, r = _cena()
    c.select("joao", "projeto:bub", 0.97)
    for frase in ("Jaime, está aí?", "isso", "isso mesmo", "Isso aí", "fala da BUB pra mim", "vira à esquerda na próxima"):
        assert r.resolver(frase).status == "sem_referencia", frase


def test_compara_esses_pega_as_duas_ultimas_selecoes():
    c, rel, r = _cena()
    c.select("joao", "projeto:bub", 0.97); rel.t += 4
    c.select("joao", "projeto:gearhead", 0.97); rel.t += 1
    res = r.resolver("compara esses dois")
    assert res.status == "ok" and {o.id for o in res.objetos} == {"projeto:bub", "projeto:gearhead"}
    assert "'esses'" in res.contexto()


def test_plural_com_uma_so_selecao_pergunta():
    c, rel, r = _cena()
    c.select("joao", "projeto:bub", 0.97)
    res = r.resolver("compara esses")
    assert res.status == "ambiguo" and "BUB" in res.pergunta and "outro" in res.pergunta


def test_duas_selecoes_quase_juntas_perguntam_em_uma_frase_e_a_resposta_desambigua():
    c, rel, r = _cena()
    c.select("joao", "projeto:bub", 0.97); rel.t += 0.5
    c.select("joao", "projeto:seventyone", 0.97); rel.t += 1
    res = r.resolver("abre isso")
    assert res.status == "ambiguo" and res.pergunta == "Qual deles: SeventyOne ou BUB?"
    rel.t += 3
    res2 = r.resolver("o BUB")
    assert res2.status == "ok" and res2.objetos[0].id == "projeto:bub" and "abre isso" in res2.motivo
    assert c.selected["joao"] == "projeto:bub"


def test_desambiguacao_por_ordinal_e_por_lado():
    c, rel, r = _cena()
    c.select("joao", "projeto:gearhead", 0.97); rel.t += 0.3
    c.select("joao", "projeto:bub", 0.97)
    assert r.resolver("move isso").status == "ambiguo"
    assert r.resolver("a da esquerda").objetos[0].id == "projeto:bub"
    c.select("joao", "projeto:gearhead", 0.97); rel.t += 0.3
    c.select("joao", "projeto:seventyone", 0.97)
    assert r.resolver("fecha isso").status == "ambiguo"
    assert r.resolver("a primeira").objetos[0].id == "projeto:seventyone"


def test_a_da_direita_entre_as_selecoes_recentes():
    c, rel, r = _cena()
    c.select("joao", "projeto:bub", 0.97); rel.t += 5
    c.select("joao", "projeto:gearhead", 0.97); rel.t += 5
    res = r.resolver("abre a da direita")
    assert res.status == "ok" and res.objetos[0].id == "projeto:gearhead"


def test_selecao_fraca_confirma_antes():
    c, rel, r = _cena()
    c.select("joao", "projeto:bub", 0.7)
    res = r.resolver("abre isso")
    assert res.status == "ambiguo" and res.pergunta == "Você quer dizer BUB?"
    assert r.resolver("sim").objetos[0].id == "projeto:bub"


def test_so_perguntar_quando_ha_verbo_de_acao():
    c, rel, r = _cena()
    c.select("joao", "projeto:bub", 0.97); rel.t += 0.2
    c.select("joao", "projeto:seventyone", 0.97)
    assert r.resolver("o que você acha disso aqui, esse projeto é bom?").status == "ok"   # conversa, não comando


def test_contexto_voz_desliga_rastreamento_por_voz():
    c, rel, r = _cena()
    chamados = []
    serv = SimpleNamespace(desligar_rastreamento=lambda motivo: ("coro", motivo), emitir=lambda *a, **k: None)
    v = ContextoVoz(serv, r, agendar=lambda coro: chamados.append(coro))
    curta, ctx = v.antes_do_turno("Jaime, desliga o rastreamento das mãos", "app=Finder")
    assert curta == "Rastreamento de mãos desligado." and ctx == "app=Finder" and chamados == [("coro", "João pediu por voz")]
    curta, _ = v.antes_do_turno("para de rastrear", "")
    assert curta and len(chamados) == 2


def test_contexto_voz_acrescenta_ao_contexto_existente():
    c, rel, r = _cena()
    emitidos = []
    serv = SimpleNamespace(emitir=lambda tipo, **d: emitidos.append(d))
    v = ContextoVoz(serv, r)
    c.select("joao", "projeto:bub", 0.97)
    curta, ctx = v.antes_do_turno("resume isso", "app=Code, janela=bub")
    assert curta is None and ctx.startswith("app=Code, janela=bub; espacial") and "projeto:bub" in ctx
    assert emitidos[-1]["evento"] == "voice.reference" and emitidos[-1]["objetos"] == ["projeto:bub"]
    curta, ctx = v.antes_do_turno("que horas são?", "app=Code")
    assert curta is None and ctx == "app=Code"


# ── no orquestrador de verdade ───────────────────────────────────────────────
def _jaime(voz, lote=None):
    from jaime.orchestrator.jaime import Jaime
    from jaime.vigia.acesso import Acesso, hash_senha
    j = Jaime.__new__(Jaime)
    j.acesso = Acesso(hash_senha("1234 5678")); j.acesso.tentar("1234 5678")
    j.falante_atual = ""; j._senha_incerta = 0; j.proposta_renomear = None; j.aguardando_nome = False
    j.vault = SimpleNamespace(diario=lambda *a: None)
    j.vigia = SimpleNamespace(lote=lote, convidado=""); j.confianca = SimpleNamespace(pendente=None)
    j.estado = SimpleNamespace(resumo_curto=lambda: "ok"); j.gravador = SimpleNamespace(gravando=False)
    j._client = object(); j.espacial_voz = voz; j.porteiro = None
    async def _mundo(texto): return None
    j._mundo = _mundo
    return j


def _turno(j, texto):
    async def go():
        return [t async for t in j._ask_stream(texto, canal="voice")]
    return asyncio.run(go())


def test_orquestrador_pergunta_sem_chamar_modelo_quando_e_ambiguo():
    c, rel, r = _cena()
    c.select("joao", "projeto:bub", 0.97); rel.t += 0.3
    c.select("joao", "projeto:seventyone", 0.97)
    j = _jaime(ContextoVoz(SimpleNamespace(emitir=lambda *a, **k: None), r))
    assert _turno(j, "abre isso") == ["Qual deles: SeventyOne ou BUB?"]


def test_com_lote_do_vigia_pendente_isso_e_aprovacao_e_nao_passa_pelo_espacial():
    c, rel, r = _cena()
    chamadas = []
    class Espiao(ContextoVoz):
        def antes_do_turno(self, texto, contexto=""):
            chamadas.append(texto); return super().antes_do_turno(texto, contexto)
    j = _jaime(Espiao(SimpleNamespace(emitir=lambda *a, **k: None), r), lote=[object()])
    try:
        _turno(j, "faz isso")
    except Exception:
        pass                                   # segue para o lote real (sem cliente de verdade aqui)
    assert chamadas == []
