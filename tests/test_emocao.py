"""Cérebro emocional: perguntas não repetidas, aniversário detectado, humor coerente, prosódia muda com humor."""
from datetime import date
from pathlib import Path
import pytest
from jaime.brain.vault import Vault
from jaime.emocao.perfil import Perfil, parse_datas
from jaime.emocao.perguntas import Perguntas, similaridade
from jaime.emocao.momento import momento
from jaime.emocao.humor import Humor, detectar_tom
from jaime.emocao.prosodia import prosodia

@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    for d in ("00-Jaime", "10-Eu", "30-Tarefas", "40-Diario"):
        (tmp_path / d).mkdir()
    (tmp_path / "30-Tarefas/Inbox.md").write_text("# Inbox\n")
    return Vault(tmp_path)

# ── perguntas ──────────────────────────────────────────
def test_pergunta_repetida_nao_e_feita(vault):
    p = Perguntas(vault)
    assert p.decidir("qual é o seu aniversário?", date(2026, 9, 15))["acao"] == "perguntar"
    p.registrar("qual é o seu aniversário?", "12 de março", date(2026, 9, 1))
    d = p.decidir("quando é seu aniversário?", date(2026, 9, 15))
    assert d["acao"] == "usar" and d["resposta"] == "12 de março" and d["dias"] == 14

def test_resposta_antiga_pede_confirmacao(vault):
    p = Perguntas(vault)
    p.registrar("qual cartão você usa para assinaturas?", "Nubank", date(2026, 1, 10))
    d = p.decidir("qual cartão usa nas assinaturas?", date(2026, 9, 15))
    assert d["acao"] == "confirmar" and d["resposta"] == "Nubank" and d["dias"] > 90

def test_registrar_atualiza_pergunta_parecida_e_similaridade(vault):
    p = Perguntas(vault)
    p.registrar("qual é o seu aniversário?")                       # feita, sem resposta
    assert p.decidir("qual é o seu aniversário?")["acao"] == "perguntar"
    p.registrar("quando é o seu aniversário?", "12/03")             # resposta chega com outra redação
    assert len(p.todas()) == 1 and p.todas()[0].resposta == "12/03"
    assert similaridade("qual é o seu aniversário", "quando é seu aniversário") >= 0.6
    assert similaridade("aniversário", "abre o Finder") == 0.0

# ── momento ────────────────────────────────────────────
def test_aniversario_e_prazos(vault):
    (vault.root / "10-Eu/Datas.md").write_text("- 15/09 — Aniversário do João\n- 2026-09-18 — Entrega BUB v2 @BUB\n- 2026-09-20 — Reunião Oldsen @Oldsen\n- 2026-09-21 — Boleto @GearHead\n")
    m = momento(Perfil(vault), date(2026, 9, 15))
    assert m.aniversario and m.texto().startswith("HOJE É O ANIVERSÁRIO")
    assert [d.nome for _, d in m.prazos] == ["Entrega BUB v2", "Reunião Oldsen", "Boleto"]
    assert m.semana_pesada and m.peso == "leve"          # aniversário vence a semana pesada
    m2 = momento(Perfil(vault), date(2026, 9, 16))
    assert not m2.aniversario and m2.peso == "pesado"
    assert parse_datas("- 31/02 — inválida\n")[0].proxima(date(2026, 1, 1)) is None

def test_feriado_fixo(vault):
    m = momento(Perfil(vault), date(2026, 12, 25), tarefas_abertas=0)
    assert m.feriado == "Natal" and m.peso == "leve"

# ── humor ──────────────────────────────────────────────
def test_humor_nao_fica_leve_com_joao_em_problema():
    h = Humor()
    h.registrar_tom("animado"); h.registrar_tom("animado")
    assert h.rotulo() == "leve"
    h.registrar_tom("em_problema")
    assert h.rotulo() != "leve" and h.e.gravidade >= 0.6 and h.joao_em_problema
    h.registrar_momento("leve", aniversario=True)          # nem no aniversário, enquanto o problema durar
    assert h.rotulo() != "leve"

def test_humor_nao_fica_grave_em_conquista_e_sem_drama():
    h = Humor()
    h.registrar_resultado(False, grave=True); h.registrar_resultado(False, grave=True)
    assert h.e.gravidade <= 0.85 and h.e.confianca < 0.7
    h.registrar_tom("animado")
    assert h.e.gravidade <= 0.35 and h.rotulo() in ("leve", "neutro", "caloroso")

def test_detectar_tom():
    assert detectar_tom("droga, o build quebrou de novo") == "em_problema"   # problema pesa mais que irritação
    assert detectar_tom("tá errado, refaz") == "irritado"
    assert detectar_tom("funcionou, valeu!") == "animado"
    assert detectar_tom("abre o Finder") == "neutro"

def test_prosodia_muda_com_humor():
    grave, leve = Humor(), Humor()
    grave.registrar_tom("em_problema"); leve.registrar_tom("animado"); leve.registrar_tom("animado")
    pg, pl = prosodia(grave), prosodia(leve)
    assert pg["instructions"] != pl["instructions"]
    assert pg["eleven"]["stability"] > pl["eleven"]["stability"] and "[serious]" in pg["tags"]
