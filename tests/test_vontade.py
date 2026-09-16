"""Vontades (fase 3, §6): dinâmica dos impulsos, Mente (impulso × janela × orçamento), Vitrine e votos."""
import asyncio, types
from datetime import datetime
from pathlib import Path
import pytest
from jaime.brain.vault import Vault
from jaime.hud.events import bus
from jaime.cortex.placar import Placar
from jaime.vontade import ligar
from jaime.vontade.impulsos import Impulsos, REPOUSO, CRIACAO_POR_DIA, NOMES, observar_placar
from jaime.vontade.mente import Mente, janela
from jaime.vontade.criacoes import Criacoes

@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    for d in ("00-Jaime", "01-Estado", "10-Eu", "20-Projetos", "30-Tarefas", "40-Diario", "50-Conhecimento", "60-Conversas"):
        (tmp_path / d).mkdir()
    return Vault(tmp_path)

class Relogio:
    def __init__(self, t: float): self.t = t
    def __call__(self) -> float: return self.t

async def _com_escuta(imp: Impulsos, corpo):
    t = asyncio.create_task(imp.escutar())
    await asyncio.sleep(0)
    try:
        return await corpo()
    finally:
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass

async def _espera():
    for _ in range(6):
        await asyncio.sleep(0.005)

async def criador_falso(tipo, tema, pasta):
    return {"titulo": f"Haicai da madrugada ({tipo})", "conteudo": "# Haicai\n\nsilêncio no vale\n— Jaime\n", "descricao": "três linhas sobre a noite"}

# ── impulsos ──────────────────────────────────────────
def test_sobe_desce_limites_e_persistencia(vault):
    imp = Impulsos(vault)
    assert set(imp.niveis) == set(NOMES) and all(0 <= v <= 1 for v in imp.niveis.values())
    assert imp.subir("curiosidade", 0.9, "problema aberto") == 1.0          # teto
    assert imp.descer("ordem", 5) == 0.0                                    # piso
    txt = vault.read("01-Estado/Vontades.md")
    assert "| Curiosidade | 1.00 |" in txt and "problema aberto" in txt and "Últimos movimentos" in txt
    imp2 = Impulsos(vault)                                                  # recarrega do vault
    assert imp2.nivel("curiosidade") == 1.0 and imp2.nivel("ordem") == 0.0 and imp2.motivo("curiosidade") == "problema aberto"
    assert imp2.ranking()[0][0] == "curiosidade"

def test_decaimento_para_o_repouso_e_criacao_sobe_com_os_dias(vault):
    r = Relogio(1_800_000_000.0)
    imp = Impulsos(vault, relogio=r)
    imp.subir("utilidade", 0.6); imp.subir("curiosidade", 0.6); imp.descer("ordem", 0.15)
    c0 = imp.nivel("criacao")
    imp.tique()                                                             # sem tempo passado: nada muda
    assert imp.nivel("curiosidade") == pytest.approx(0.85)
    r.t += 24 * 3600; imp.tique()
    assert imp.nivel("utilidade") == pytest.approx(REPOUSO["utilidade"])    # decai rápido: em 1 dia está no repouso
    assert REPOUSO["curiosidade"] < imp.nivel("curiosidade") < 0.85          # decai devagar
    assert imp.nivel("ordem") > 0.0                                          # sobe de volta para o repouso
    assert imp.nivel("criacao") == pytest.approx(c0 + CRIACAO_POR_DIA)       # dias sem criar
    r.t += 24 * 3600; imp.tique()
    assert imp.nivel("criacao") == pytest.approx(c0 + 2 * CRIACAO_POR_DIA)
    r.t += 365 * 24 * 3600; imp.tique()
    assert imp.nivel("criacao") == 1.0 and all(0 <= v <= 1 for v in imp.niveis.values())

def test_eventos_movem_os_impulsos(vault):
    imp = Impulsos(vault); base = dict(imp.niveis)
    # Utilidade: demanda pendente sobe; fechada sem correção desce; João em aperto sobe; fila do Prompt B
    imp.evento("conversa", canal="voz", texto="jaime, me ajuda")
    assert imp.demanda_pendente and imp.nivel("utilidade") > base["utilidade"]
    u = imp.nivel("utilidade"); imp.evento("fala_fim")
    assert not imp.demanda_pendente and imp.nivel("utilidade") < u
    imp.evento("conversa", canal="hud", texto="x"); imp.evento("resultado", texto="falhou", erro=True); u = imp.nivel("utilidade"); imp.evento("fala_fim")
    assert imp.nivel("utilidade") == u                                       # fechada com erro: não desce
    imp.evento("humor", joao_em_problema=True); assert imp.nivel("utilidade") > u
    imp.evento("fila", pendentes=2); assert imp.demanda_pendente
    imp.evento("fila", pendentes=0); assert not imp.demanda_pendente
    # formato real de jaime/voice/fila.py (B): itens com estado; concluida/descartada não contam
    u = imp.nivel("utilidade")
    imp.evento("fila", itens=[{"id": 1, "estado": "concluida"}, {"id": 2, "estado": "em_andamento"}, {"id": 3, "estado": "interrompida"}], atual=2, aguardando=None)
    assert imp.demanda_pendente and imp._fila_pendentes == 2 and imp.nivel("utilidade") > u and "2 demanda(s) na fila" in imp.motivo("utilidade")
    imp.evento("fala_fim"); assert imp.demanda_pendente                     # a fila ainda tem itens abertos
    imp.evento("fila", itens=[{"id": 1, "estado": "concluida"}, {"id": 2, "estado": "concluida"}, {"id": 3, "estado": "descartada"}], atual=None, aguardando=None)
    assert not imp.demanda_pendente and imp._fila_pendentes == 0
    imp.evento("conversa", canal="rotina", texto="rotina"); assert not imp.demanda_pendente   # rotina não é demanda do João
    # Curiosidade: problema aberto sobe, resolvido desce
    imp.evento("estudo", msg="aberto P-0001: pod install", abertos=1); assert imp.nivel("curiosidade") > base["curiosidade"]
    c = imp.nivel("curiosidade"); imp.evento("estudo", msg="resolvido P-0001 → 50-Conhecimento/pod.md", abertos=0); assert imp.nivel("curiosidade") < c
    # Maestria: erro por tipo sobe, acerto desce; erro repetido também mexe na Curiosidade
    imp.evento("placar", modelo="m", tarefa="código", resultado="erro"); assert imp.nivel("maestria") > base["maestria"]
    m = imp.nivel("maestria"); imp.evento("placar", modelo="m", tarefa="código", resultado="acerto"); assert imp.nivel("maestria") < m
    c = imp.nivel("curiosidade")
    imp.evento("placar", msg="correção: m errou em 'código'"); imp.evento("placar", msg="correção: m errou em 'código'")
    assert imp.nivel("curiosidade") > c and "código" in imp.motivo("maestria")
    # Ordem: órfãs/links quebrados e Inbox grande sobem; saúde verde desce
    imp.evento("saude", problemas=["! 20-Projetos/X.md: nota órfã — nada aponta para ela", "! a.md: link quebrado [[b]]"], erros=0)
    assert imp.nivel("ordem") > base["ordem"]
    o = imp.nivel("ordem"); imp.evento("inbox", abertas=15); assert imp.nivel("ordem") > o
    o = imp.nivel("ordem"); imp.evento("saude", problemas=[], erros=0); assert imp.nivel("ordem") < o
    # Vínculo: perguntas sem resposta e datas próximas sobem; resposta/data lembrada descem
    imp.evento("perfil", perguntas_sem_resposta=2, datas_proximas=1); assert imp.nivel("vinculo") > base["vinculo"]
    v = imp.nivel("vinculo"); imp.evento("perfil", respondida="qual seu time"); assert imp.nivel("vinculo") < v
    v = imp.nivel("vinculo"); imp.evento("perfil", data_lembrada="aniversário da Ana"); assert imp.nivel("vinculo") < v
    assert bus.historico[-1]["tipo"] == "vontade" and "niveis" in bus.historico[-1]

def test_vitrine_entregue_e_votos_movem_criacao_e_maestria(vault):
    r = Relogio(1_800_000_000.0); imp = Impulsos(vault, relogio=r)
    imp.subir("criacao", 0.5); c = imp.nivel("criacao"); r.t += 3600
    imp.evento("vitrine", acao="entregue", id="C-0001", titulo="Haicai")
    assert imp.nivel("criacao") < c and imp.ultima_criacao == r.t
    c, m = imp.nivel("criacao"), imp.nivel("maestria")
    imp.evento("vitrine", acao="voto", id="C-0001", titulo="Haicai", gostou=True)
    assert imp.nivel("criacao") > c and imp.nivel("maestria") > m
    c, m = imp.nivel("criacao"), imp.nivel("maestria")
    imp.evento("vitrine", acao="voto", id="C-0001", titulo="Haicai", gostou=False)
    assert imp.nivel("criacao") < c and imp.nivel("maestria") == m

def test_escuta_o_bus_e_o_placar_observado(vault):
    placar = Placar(vault.root); observar_placar(placar)
    async def corpo():
        bus.emitir("estudo", msg="aberto P-0009: teste", abertos=1)
        placar.registrar("claude-x", "código", "erro", 1.0, 0.0, "teste")
        await _espera()
    imp = Impulsos(vault)
    asyncio.run(_com_escuta(imp, corpo))
    assert imp.nivel("curiosidade") > REPOUSO["curiosidade"] and imp.nivel("maestria") > REPOUSO["maestria"]
    assert placar.taxa("claude-x", "código") < 0.5                          # o Placar de verdade continua registrando

def test_sonda_le_perfil_e_inbox(vault):
    vault.write("10-Eu/Perguntas-Feitas.md", "| data | pergunta | resposta |\n|---|---|---|\n| 2026-09-10 | qual é o seu time | — |\n")
    vault.write("10-Eu/Datas.md", "- 18/09 — Aniversário da Ana\n")
    for i in range(13):
        vault.tarefa(f"tarefa {i}")
    from jaime.emocao.perguntas import Perguntas
    from jaime.emocao.perfil import Perfil
    imp = Impulsos(vault, relogio=Relogio(datetime(2026, 9, 15, 12, 0).timestamp()), perguntas=Perguntas(vault), perfil=Perfil(vault))
    imp.sondar()
    assert imp.nivel("vinculo") > REPOUSO["vinculo"] and imp.nivel("ordem") > REPOUSO["ordem"]
    assert "sem resposta" in imp.motivo("vinculo") or "próxima" in imp.motivo("vinculo")

# ── mente ─────────────────────────────────────────────
def test_janelas():
    assert janela(datetime(2026, 9, 15, 23, 0)) == "noite" and janela(datetime(2026, 9, 15, 3, 0)) == "noite"
    dia = datetime(2026, 9, 15, 10, 0)
    assert janela(dia, dia.timestamp() - 60) == "atento" and janela(dia, dia.timestamp() - 3600) == "ocioso"
    assert janela(datetime(2026, 9, 15, 19, 0), datetime(2026, 9, 15, 19, 0).timestamp()) == "ocioso"

def test_utilidade_vence_com_demanda_pendente(vault):
    imp = Impulsos(vault); imp.subir("criacao", 0.8, "dias sem criar"); imp.subir("curiosidade", 0.7)
    m = Mente(imp, vault, agora=lambda: datetime(2026, 9, 15, 23, 0))
    e = m.decidir()
    assert e.atividade == "criar" and e.janela == "noite" and e.pensamento.startswith("quero criar") and "porque" in e.pensamento
    imp.evento("conversa", canal="voz", texto="jaime, me ajuda")
    e = m.decidir()
    assert e.atividade == "atender" and e.impulso == "utilidade" and "quero atender" in e.pensamento and "porque" in e.pensamento
    assert "Vontade: quero atender" in vault.read(vault.daily_rel())
    imp.evento("fala_fim"); imp.niveis["utilidade"] = 1.0
    assert m.decidir().atividade == "criar"                                 # sem demanda, Utilidade alta não é atividade

def test_janela_atenta_orcamento_e_limite_de_criacoes(vault):
    imp = Impulsos(vault); imp.subir("curiosidade", 0.7); imp.subir("criacao", 0.7)
    dia = datetime(2026, 9, 15, 10, 0)
    m = Mente(imp, vault, agora=lambda: dia); m.ultima_fala_ts = dia.timestamp() - 60
    assert m.decidir() is None                                              # atento sem demanda: espera
    imp.evento("conversa", canal="voz", texto="oi"); assert m.decidir().atividade == "atender"; imp.evento("fala_fim")
    m.ultima_fala_ts = dia.timestamp() - 3600
    assert m.decidir().atividade == "estudar"                               # ocioso de dia: criar não; estudar sim
    class Orc:
        def pode(self, tipo): return tipo != "estudo"
    m2 = Mente(imp, vault, orcamento=Orc(), agora=lambda: dia)
    assert m2.decidir() is None                                             # orçamento de estudo esgotado
    noite = Mente(imp, vault, agora=lambda: datetime(2026, 9, 15, 23, 0), pode_criar=lambda: False)
    assert noite.decidir().atividade == "estudar"                           # já criou hoje: cai para a próxima vontade
    class SemCriacao:
        def pode(self, tipo): return tipo != "criacao"
    assert Mente(imp, vault, orcamento=SemCriacao(), agora=lambda: datetime(2026, 9, 15, 23, 0)).decidir().atividade == "estudar"
    imp.niveis = {k: 0.1 for k in NOMES}
    assert Mente(imp, vault, agora=lambda: datetime(2026, 9, 15, 19, 0)).decidir() is None   # nada me puxa

def test_ciclo_executa_o_executor_e_registra_falha(vault):
    imp = Impulsos(vault); imp.subir("curiosidade", 0.7)
    chamado = []
    async def estudar(): chamado.append(1)
    m = Mente(imp, vault, executores={"estudar": estudar}, agora=lambda: datetime(2026, 9, 15, 19, 0))
    e = asyncio.run(m.ciclo())
    assert e.atividade == "estudar" and chamado == [1]
    def quebra(): raise RuntimeError("sem rede")
    m2 = Mente(imp, vault, executores={"estudar": quebra}, agora=lambda: datetime(2026, 9, 15, 19, 0))
    assert asyncio.run(m2.ciclo()).atividade == "estudar"
    assert "tentei estudar e falhou" in vault.read(vault.daily_rel())

# ── vitrine ───────────────────────────────────────────
def test_vitrine_cria_lista_persiste_e_vota(vault, tmp_path):
    pasta = tmp_path / "criacoes"
    r = Relogio(datetime(2026, 9, 15, 23, 30).timestamp())
    cri = Criacoes(vault, pasta, criador=criador_falso, relogio=r, por_noite=1)
    assert cri.pode_criar()
    item = asyncio.run(cri.noite())
    assert item["id"] == "C-0001" and item["tipo"] == "texto" and item["caminho"].endswith(".md")
    assert Path(item["caminho"]).read_text(encoding="utf-8").startswith("# Haicai") and pasta in Path(item["caminho"]).parents
    assert not cri.pode_criar() and asyncio.run(cri.noite()) is None      # uma por noite
    assert cri.listar()[0]["id"] == "C-0001" and cri.listar()[0]["voto"] is None
    assert "Haicai" in vault.read("01-Estado/Vitrine.md") and "Criei (texto)" in vault.read(vault.daily_rel())
    v = cri.votar("C-0001", True)
    assert v["voto"] == "gostei" and bus.historico[-1]["tipo"] == "vitrine" and bus.historico[-1]["acao"] == "voto" and bus.historico[-1]["gostou"] is True
    assert cri.votar("C-9999", False) is None
    assert "gostou de Haicai" in vault.read(vault.daily_rel())
    cri2 = Criacoes(vault, pasta, criador=criador_falso, relogio=r)
    assert cri2.por_id("C-0001")["voto"] == "gostei" and "| gostei |" in vault.read("01-Estado/Vitrine.md")
    assert cri2.escolher_tipo() != "imagem"                                # sem chave de imagem
    assert cri2.escolher_tipo() != "texto"                                 # alterna: o último tipo pesa menos

def test_criacao_que_falha_vai_para_o_diario(vault, tmp_path):
    async def ruim(tipo, tema, pasta): return {"erro": "sem modelo"}
    cri = Criacoes(vault, tmp_path / "c", criador=ruim)
    assert asyncio.run(cri.criar("script")) is None and cri.listar() == []
    assert "Noite criativa: tentei um script" in vault.read(vault.daily_rel())

def test_votos_realimentam_as_vontades_pelo_bus(vault, tmp_path):
    imp = Impulsos(vault)
    async def corpo():
        cri = Criacoes(vault, tmp_path / "c", criador=criador_falso)
        item = await cri.criar("script"); await _espera()
        depois_entrega = imp.nivel("criacao")
        cri.votar(item["id"], True); await _espera()
        gostei, maestria = imp.nivel("criacao"), imp.nivel("maestria")
        cri.votar(item["id"], False); await _espera()
        return depois_entrega, gostei, maestria, imp.nivel("criacao")
    entrega, gostei, maestria, nao = asyncio.run(_com_escuta(imp, corpo))
    assert entrega < REPOUSO["criacao"] and gostei > entrega and maestria > REPOUSO["maestria"] and nao < gostei

def test_orcamento_do_prompt_d_recebe_o_vault(vault, tmp_path, monkeypatch):
    import sys, types as _t
    from jaime.vontade import _orcamento
    j = _t.SimpleNamespace(vault=vault)
    class Orcamento:                                                        # a assinatura do D: Orcamento(vault, dia_usd)
        def __init__(self, vault, dia_usd=0.0): self.vault, self.dia_usd = Path(vault), dia_usd
        def pode(self, tipo): return True
    monkeypatch.setitem(sys.modules, "jaime.cortex.orcamento", _t.SimpleNamespace(Orcamento=Orcamento))
    monkeypatch.setenv("JAIME_ORCAMENTO_DIA_USD", "2.5")
    o = _orcamento(j)
    assert isinstance(o, Orcamento) and o.vault == vault.root and o.dia_usd == 2.5
    monkeypatch.setitem(sys.modules, "jaime.cortex.orcamento", None)        # simula o módulo do D ausente (import falha)
    assert type(_orcamento(j)).__name__ == "OrcamentoLivre"                 # sem o módulo do D: stub

def test_ligar_monta_tudo_com_um_jaime_falso(vault, tmp_path):
    j = types.SimpleNamespace(vault=vault, placar=Placar(vault.root), s=types.SimpleNamespace(model_padrao="x"), estudo=None)
    async def go():
        v = ligar(j, lambda: True, intervalo=3600, pasta=tmp_path / "c")
        await asyncio.sleep(0.01)
        j.placar.registrar("m", "código", "erro")
        await _espera()
        v.parar(); await asyncio.sleep(0.01)
        return v
    v = asyncio.run(go())
    assert v.impulsos.nivel("maestria") > REPOUSO["maestria"] and "organizar" in v.mente.executores and "criar" in v.mente.executores
    assert all(t.cancelled() or t.done() for t in v.tasks)


# ── M-16 (Vigília 15/09): a mesma situação não empurra o impulso a cada sonda; Maestria tem piso ──
def test_mesma_pergunta_pendente_so_sobe_uma_vez(vault):
    imp = Impulsos(vault); v0, c0 = imp.nivel("vinculo"), imp.nivel("curiosidade")
    imp.evento("perfil", perguntas_sem_resposta=1, datas_proximas=0)
    v1, c1 = imp.nivel("vinculo"), imp.nivel("curiosidade"); assert v1 > v0 and c1 > c0
    for _ in range(12):                                                   # 2 h de sondas com a mesma pergunta
        imp.evento("perfil", perguntas_sem_resposta=1, datas_proximas=0)
    assert imp.nivel("vinculo") == v1 and imp.nivel("curiosidade") == c1
    imp.evento("perfil", perguntas_sem_resposta=2, datas_proximas=0)      # pergunta NOVA: sobe
    assert imp.nivel("vinculo") > v1
    imp.evento("perfil", perguntas_sem_resposta=0, datas_proximas=0, respondida="cor favorita")
    assert imp.nivel("vinculo") < imp.niveis["vinculo"] + 1e-9 and imp._visto["perguntas"] == 0
    imp.evento("perfil", perguntas_sem_resposta=1, datas_proximas=0)      # voltou a haver 1: conta de novo
    assert imp.nivel("vinculo") > 0
    # inbox e desordem: idem
    o0 = imp.nivel("ordem"); imp.evento("inbox", abertas=30); o1 = imp.nivel("ordem"); assert o1 > o0
    imp.evento("inbox", abertas=30); assert imp.nivel("ordem") == o1
    imp.evento("saude", problemas=["link quebrado x"]); o2 = imp.nivel("ordem"); assert o2 > o1
    imp.evento("saude", problemas=["link quebrado x"]); assert imp.nivel("ordem") == o2

def test_maestria_nao_cai_abaixo_do_repouso_e_sobe_com_estudo_resolvido(vault):
    imp = Impulsos(vault)
    assert imp.nivel("maestria") == REPOUSO["maestria"]
    for _ in range(10): imp.evento("placar", tarefa="voz", resultado="acerto")
    assert imp.nivel("maestria") == REPOUSO["maestria"]                    # acerto não leva a 0,00
    imp.evento("placar", tarefa="voz", resultado="erro"); m = imp.nivel("maestria"); assert m > REPOUSO["maestria"]
    imp.evento("placar", tarefa="voz", resultado="acerto"); assert REPOUSO["maestria"] <= imp.nivel("maestria") < m
    imp.evento("estudo", msg="resolvido P-0009 → 50-Conhecimento/x.md", abertos=0)
    assert imp.nivel("maestria") > REPOUSO["maestria"] and "aprendi" in imp.motivo("maestria")
