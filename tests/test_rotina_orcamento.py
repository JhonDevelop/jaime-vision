"""Rotina (§5) e orçamento (60/25/15): tabela de Rotinas.md, modo atento, noite criativa, ganchos do fecha-dia,
orçamento com relógio falso, funil do placar e a Mente respeitando tudo isso."""
import asyncio
from datetime import date, datetime
from pathlib import Path
import pytest
from jaime.brain.vault import Vault
from jaime.cortex.placar import Placar
from jaime.cortex.orcamento import Orcamento, classificar_gasto, ARQUIVO_REL
from jaime.estudo.loop import Estudo
from jaime.agenda.scheduler import (parse_rotinas, modo_atento, noite_criativa, pode_estudar, pode_criar, Atencao, Agenda,
                                    ATENTO_JANELA_S)

RAIZ = Path(__file__).resolve().parent.parent
T0 = datetime(2026, 9, 15, 14, 0).timestamp()

@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    for d in ("00-Jaime", "01-Estado", "10-Eu", "20-Projetos", "30-Tarefas", "40-Diario", "50-Conhecimento", "60-Conversas", "90-Estudo"):
        (tmp_path / d).mkdir()
    return Vault(tmp_path)

class Relogio:
    def __init__(self, t=T0): self.t = t
    def __call__(self): return self.t
    def avancar(self, s): self.t += s
    def hoje(self): return date.fromtimestamp(self.t)
    def agora(self): return datetime.fromtimestamp(self.t)

# ── tabela do §5 ─────────────────────────────────────────────────────────────
def test_rotinas_md_tem_a_tabela_do_paragrafo_5():
    from apscheduler.triggers.cron import CronTrigger
    from jaime.agenda.relogio import FUSO
    rot = parse_rotinas((RAIZ / "vault/30-Tarefas/Rotinas.md").read_text(encoding="utf-8"))
    por_ordem = {o.split(":")[0].split(" e depois")[0].strip(): c for c, o in rot}
    esperado = {"preparar o dia": ("30", "6", "mon-fri"), "briefing": ("0", "7", "mon-fri"), "revisão de tarefas": ("0", "13", "mon-fri"),
                "fecha o dia": ("0", "18", None), "auto-avaliação": ("0", "20", "sun"), "consolida o que ouvi hoje": ("0", "22", "*")}
    for nome, (m, h, dow) in esperado.items():
        assert nome in por_ordem, nome
        assert (por_ordem[nome]["minute"], por_ordem[nome]["hour"]) == (m, h)
        if dow: assert por_ordem[nome]["day_of_week"] == dow
    # sexta 18:00 fecha o dia E a semana, uma ordem só (o modelo fecha o dia antes)
    sexta = [o for c, o in rot if c["hour"] == "18" and c["day_of_week"] == "fri"]
    assert len(sexta) == 1 and "fecha a semana" in sexta[0] and "fecha o dia" in sexta[0]
    # noite criativa NÃO é cron
    assert not any("noite criativa" in o for _, o in rot)
    # todas as linhas viram triggers válidos e caem no dia certo (APScheduler: 0 = segunda)
    terca = datetime(2026, 9, 15, 12, 0, tzinfo=FUSO)
    proximos = {o[:13]: CronTrigger(**c, timezone=FUSO).get_next_fire_time(None, terca) for c, o in rot}
    assert proximos["briefing"].strftime("%a %H:%M") == "Wed 07:00"
    assert proximos["fecha o dia e"].strftime("%a %d") == "Fri 18"
    assert proximos["auto-avaliaçã"].strftime("%a") == "Sun"

# ── modo atento e noite criativa ─────────────────────────────────────────────
def test_modo_atento_e_pura_e_respeita_15_min():
    assert modo_atento(None, T0) is False
    assert modo_atento(T0 - 60, T0) is True                           # falou há 1 min
    assert modo_atento(T0 - ATENTO_JANELA_S + 1, T0) is True
    assert modo_atento(T0 - ATENTO_JANELA_S, T0) is False             # 15 min cravados: já pode
    assert modo_atento(T0 - 3600, T0) is False
    assert modo_atento(T0 + 100, T0) is False                         # relógio no futuro não trava

def test_noite_criativa_como_janela():
    assert noite_criativa(datetime(2026, 9, 15, 21, 0)) and noite_criativa(datetime(2026, 9, 16, 2, 30)) and noite_criativa(datetime(2026, 9, 16, 5, 59))
    assert not noite_criativa(datetime(2026, 9, 16, 6, 0)) and not noite_criativa(datetime(2026, 9, 15, 14, 0)) and not noite_criativa(datetime(2026, 9, 15, 20, 59))

def test_pode_estudar_e_pode_criar(vault):
    orc = Orcamento(vault.root, 1.0, hoje=lambda: date(2026, 9, 15))
    assert pode_estudar(None, T0, orc) == (True, "")
    ok, motivo = pode_estudar(T0 - 120, T0, orc)
    assert not ok and motivo.startswith("modo atento")
    orc.gastar("estudo", 0.25)
    ok, motivo = pode_estudar(None, T0, orc)
    assert not ok and "esgotado" in motivo
    noite = datetime(2026, 9, 15, 22, 0)
    assert pode_criar(None, noite, orc) == (True, "")
    assert pode_criar(None, datetime(2026, 9, 15, 15, 0), orc)[1].startswith("fora da noite")
    assert pode_criar(noite.timestamp() - 60, noite, orc)[1].startswith("modo atento")
    orc.gastar("criacao", 0.15)
    assert "esgotado" in pode_criar(None, noite, orc)[1]

def test_atencao_atualiza_pelos_eventos_do_bus():
    rel = Relogio(); at = Atencao(agora=rel)
    assert not at.atento()
    assert at.evento({"tipo": "conversa", "texto": "•••", "t": rel.t}) is False     # trancado: não conta
    assert at.evento({"tipo": "ouvido", "texto": "oi", "ignorado": True, "t": rel.t}) is False
    assert at.evento({"tipo": "fala", "texto": "eu falando", "t": rel.t}) is False   # fala do Jaime não conta
    assert at.evento({"tipo": "transcricao_viva", "texto": "jaime, arruma", "t": rel.t}) is True
    assert at.atento()
    rel.avancar(ATENTO_JANELA_S)
    assert not at.atento()
    at.ouviu(); assert at.ultima_fala == rel.t

# ── ganchos do scheduler ─────────────────────────────────────────────────────
class _Acesso: liberado = True
class _Jaime:
    def __init__(self, vault):
        self.vault, self.acesso, self.ordens = vault, _Acesso(), []
    async def ask(self, ordem, canal="rotina", contexto=""):
        self.ordens.append(ordem); return "ok"

def test_ganchos_rodam_antes_da_ordem_e_erro_nao_derruba(vault):
    j = _Jaime(vault); ag = Agenda(j)
    chamadas = []
    ag.ao("fecha o dia", lambda: chamadas.append("prioridades"))
    async def semana(): chamadas.append("uso")
    ag.ao("fecha a semana", semana)
    ag.ao("fecha o dia", lambda: 1 / 0)
    assert asyncio.run(ag.executar_ganchos("briefing")) == []
    assert asyncio.run(ag.executar_ganchos("Fecha o dia e depois fecha a semana: ...")) == ["fecha o dia", "fecha a semana"]
    assert chamadas == ["prioridades", "uso"]
    asyncio.run(ag._rodar_ordem("fecha o dia"))
    assert chamadas == ["prioridades", "uso", "prioridades"] and j.ordens == ["fecha o dia"]

# ── orçamento ────────────────────────────────────────────────────────────────
def test_orcamento_split_60_25_15_e_bloqueio_so_de_extras(vault):
    rel = Relogio()
    orc = Orcamento(vault.root, 10.0, hoje=rel.hoje, agora=rel.agora)
    assert (orc.cota("demanda"), orc.cota("estudo"), orc.cota("criacao")) == (6.0, 2.5, 1.5)
    assert all(orc.pode(t) for t in ("demanda", "estudo", "criacao"))
    orc.gastar("estudo", 2.4); assert orc.pode("estudo") and orc.restante("estudo") == pytest.approx(0.1)
    orc.gastar("estudo", 0.2); assert not orc.pode("estudo") and orc.restante("estudo") == 0
    orc.gastar("criacao", 1.5); assert not orc.pode("criacao")
    orc.gastar("demanda", 9.0); assert orc.pode("demanda")           # demanda nunca bloqueia
    assert orc.total() == pytest.approx(13.1)
    assert "13.10 de 10.00" in orc.resumo()
    md = (vault.root / ARQUIVO_REL).read_text()
    assert "| estudo | 2.50 | 2.6000 | 0.00 | não |" in md and "| demandas | 6.00 | 9.0000 | 0.00 | sempre |" in md
    # sem teto: tudo pode, nada bloqueia
    livre = Orcamento(vault.root / "outra", 0)
    assert livre.pode("estudo") and livre.pode("criacao") and "sem teto" in livre.resumo()

def test_orcamento_persiste_no_dia_e_vira_a_meia_noite(vault):
    rel = Relogio()
    orc = Orcamento(vault.root, 4.0, hoje=rel.hoje, agora=rel.agora)
    orc.gastar("demanda", 1.0); orc.gastar("estudo", 0.5)
    # reinício no mesmo dia: relê o gasto
    orc2 = Orcamento(vault.root, 4.0, hoje=rel.hoje, agora=rel.agora)
    assert orc2.gasto == {"demanda": 1.0, "estudo": 0.5, "criacao": 0.0} and orc2.dia == date(2026, 9, 15)
    # meia-noite: zera e arquiva o dia no histórico
    rel.avancar(86400)
    assert orc2.pode("estudo") and orc2.total() == 0 and orc2.dia == date(2026, 9, 16)
    md = (vault.root / ARQUIVO_REL).read_text()
    assert "- 2026-09-15 · demandas 1.00 · estudo 0.50 · criação 0.00 · total 1.50" in md and "> dia 2026-09-16" in md
    # reinício em outro dia com arquivo velho: começa zerado, histórico fica
    rel.avancar(86400)
    orc3 = Orcamento(vault.root, 4.0, hoje=rel.hoje, agora=rel.agora)
    assert orc3.total() == 0 and any("2026-09-15" in h for h in orc3.historico)

def test_funil_do_placar_alimenta_o_orcamento(vault):
    placar = Placar(vault.root)
    orc = Orcamento(vault.root, 2.0, hoje=lambda: date(2026, 9, 15))
    orc.ligar_ao_placar(placar); orc.ligar_ao_placar(placar)          # idempotente: não envolve duas vezes
    placar.registrar("claude-opus-5", "código", "acerto", 2.0, 0.30, "turno do João")
    placar.registrar("estudo", "pesquisa", "erro", 0, 0.10, "ciclo de estudo")
    placar.registrar("criacao:poema", "criação", "acerto", 0, 0.05, "a Vitrine contabiliza por conta própria")
    assert orc.gasto == pytest.approx({"demanda": 0.30, "estudo": 0.10, "criacao": 0.0})
    assert placar.amostras("claude-opus-5", "código") == 1              # o placar continua registrando normalmente
    assert classificar_gasto("juiz:openai", "decisão") == "demanda" and classificar_gasto("vontade", "") is None

def test_mente_respeita_modo_atento_e_orcamento(vault):
    rel = Relogio()
    placar = Placar(vault.root)
    orc = Orcamento(vault.root, 1.0, hoje=rel.hoje, agora=rel.agora); orc.ligar_ao_placar(placar)
    at = Atencao(agora=rel)
    ciclos = []
    async def pesquisador(p):
        ciclos.append(p.id); return {"resolvido": False, "tentativa": "li a doc", "falta": "testar", "custo": 0.20}
    e = Estudo(vault, None, placar, pesquisador=pesquisador, orcamento=orc, atencao=at)
    e.abrir("RLS nega insert", "policy", "ferramenta_falhou")
    at.ouviu()                                                          # o João acabou de falar
    assert asyncio.run(e.tick()) is None and ciclos == []
    rel.avancar(ATENTO_JANELA_S)                                        # 15 min de silêncio
    r = asyncio.run(e.tick())
    assert ciclos == ["P-0001"] and r["custo"] == 0.20
    assert orc.gasto["estudo"] == pytest.approx(0.20) and orc.restante("estudo") == pytest.approx(0.05)
    asyncio.run(e.tick())                                               # 0.40 > cota de 0.25: estourou
    assert ciclos == ["P-0001", "P-0001"] and not orc.pode("estudo")
    assert asyncio.run(e.tick()) is None and len(ciclos) == 2           # orçamento esgotado: adia
    assert asyncio.run(e.tick(lambda: False)) is None                   # ocupado: nem olha
    rel.avancar(86400)                                                  # dia novo: volta a estudar
    assert asyncio.run(e.tick()) is not None and len(ciclos) == 3


# ── M-15 (Mente 15/09): o Mac dorme, o timer acorda atrasado, e o APScheduler descartava a rotina (grace de 1 s) ──
def test_rotinas_e_lembretes_toleram_atraso_do_timer(vault):
    from datetime import timedelta
    from jaime.agenda.scheduler import GRACE_ROTINA_S, GRACE_LEMBRETE_S, ROTINAS_REL
    vault.write(ROTINAS_REL, "# Rotinas\n\n- 0 18 * * mon-thu,sat,sun · fecha o dia\n- 0 22 * * * · consolida o que ouvi hoje\n")
    async def rodar():
        ag = Agenda(_Jaime(vault)); ag.start()
        try:
            rotinas = [j for j in ag._sched.get_jobs() if j.id.startswith("rotina:")]
            assert len(rotinas) == 2 and all(j.misfire_grace_time == GRACE_ROTINA_S and j.coalesce for j in rotinas)
            ag._agendar_lembrete(datetime.now() + timedelta(hours=1), "beber água")
            lem = [j for j in ag._sched.get_jobs() if j.id.startswith("lembrete:")]
            assert len(lem) == 1 and lem[0].misfire_grace_time == GRACE_LEMBRETE_S
        finally:
            ag.stop()
    asyncio.run(rodar())


# ── M-19 (Vigília 16/09): rotinas que caíram enquanto o processo não existia rodam no boot, uma vez ──
def test_rotinas_perdidas_no_sono_rodam_no_boot(vault):
    from datetime import timedelta
    from jaime.agenda.scheduler import ROTINAS_REL, FUSO
    vault.write(ROTINAS_REL, "# Rotinas\n\n- 30 6 * * mon-fri · preparar o dia\n- 0 7 * * mon-fri · briefing\n- 0 13 * * mon-fri · revisão de tarefas\n- 0 22 * * * · consolida o que ouvi hoje\n")
    j = _Jaime(vault); ag = Agenda(j); ag.rotinas = parse_rotinas(vault.read(ROTINAS_REL))
    agora = datetime(2026, 9, 16, 7, 14, tzinfo=FUSO)                      # quarta, o Mac acordou às 07:14
    assert ag.perdidas(agora) == ["preparar o dia", "briefing"]
    vault.diario("Rotina disparada: briefing", "Log") if False else None
    hoje = vault.daily_rel(agora.date()); vault.write(hoje, "# 16/09\n\n## Log\n- 07:00 Rotina disparada: briefing\n")
    assert ag.perdidas(agora) == ["preparar o dia"]                       # a que já consta no diário não repete
    vault.diario("Rotina perdida enquanto eu estava desligado, vou rodar agora: preparar o dia", "Log")
    vault.write(hoje, vault.read(hoje).replace(f"- {__import__('datetime').datetime.now():%H:%M} Rotina perdida", "- 07:14 Rotina perdida"))
    assert ag.perdidas(agora) == []                                       # outro boot já agendou: não duplica (07:35 rodou 2×)
    vault.write(hoje, "# 16/09\n\n## Log\n- 07:00 Rotina disparada: briefing\n")
    assert ag.perdidas(datetime(2026, 9, 16, 12, 0, tzinfo=FUSO)) == []   # fora da janela de 3 h: não recupera
    assert ag.perdidas(datetime(2026, 9, 16, 1, 30, tzinfo=FUSO)) == []   # 22:00 de ontem: diário de ontem, não de hoje → mas fora da janela
    async def rodar():
        ag.start()
        try:
            rec = [jb for jb in ag._sched.get_jobs() if jb.id.startswith("recuperada:")]
            return rec
        finally:
            ag.stop()
    # com o relógio real, o que está nas últimas 3 h depende da hora: só garantimos que o boot não quebra
    asyncio.run(rodar())


def test_rotina_registra_duracao_reagenda_e_nao_fala_o_que_sobrou_quando_cedida(vault):
    from datetime import timedelta
    from jaime.agenda.scheduler import FUSO, GRACE_ROTINA_S
    class _Ouvido:
        def __init__(self): self.falas = []
        def falar(self, t): self.falas.append(t)
    j = _Jaime(vault); ag = Agenda(j, ouvido=_Ouvido())
    asyncio.run(ag._rodar_ordem("briefing"))
    hoje = vault.read(vault.daily_rel())
    assert "Rotina disparada: briefing" in hoje and "Rotina concluída em 0 s: briefing" in hoje and ag.ouvido.falas == ["ok"]
    j._rotina_cedida = "revisão de tarefas"                     # o João falou no meio
    asyncio.run(ag._rodar_ordem("revisão de tarefas"))
    assert ag.ouvido.falas == ["ok"] and j._rotina_cedida == "" and "Rotina concluída em 0 s: revisão" not in vault.read(vault.daily_rel())
    async def rodar():
        ag.start()
        try:
            quando = ag.reagendar("briefing", minutos=10)
            job = ag._sched.get_job("reagendada:briefing")
            assert job is not None and job.misfire_grace_time == GRACE_ROTINA_S
            assert abs((quando - datetime.now(FUSO)) - timedelta(minutes=10)) < timedelta(seconds=5)
        finally:
            ag.stop()
    asyncio.run(rodar())
