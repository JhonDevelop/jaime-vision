"""Emoção a partir de fatos reais: tipos válidos, frase fixa (sem fingir sofrimento humano), humor modulado
com coerência (humor.py) e registro no diário."""
from pathlib import Path
import pytest
from jaime.brain.vault import Vault
from jaime.emocao.humor import Humor
from jaime.emocao.eventos import criar, processar, TIPOS, Evento


@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    for d in ("40-Diario",):
        (tmp_path / d).mkdir()
    return Vault(tmp_path)


# ── criar ────────────────────────────────────────────────────────────────
def test_criar_valida_tipo():
    with pytest.raises(ValueError):
        criar("tipo_que_nao_existe", "qualquer coisa")


def test_criar_clampa_intensidade():
    assert criar("conquista", "fechou contrato", intensidade=5).intensidade == 1.0
    assert criar("perda", "cliente saiu", intensidade=-3).intensidade == 0.0


def test_todos_os_seis_tipos_existem():
    assert set(TIPOS) == {"projeto_avancou", "projeto_travou", "data_importante", "pessoa_reapareceu", "perda", "conquista"}


# ── frase (nunca finge sofrimento humano) ──────────────────────────────
@pytest.mark.parametrize("tipo", TIPOS)
def test_frase_nunca_usa_primeira_pessoa_de_sofrimento(tipo):
    e = criar(tipo, "o BUB avançou na integração")
    f = e.frase()
    proibidas = ("sinto", "sofro", "medo", "cansad", "dor")
    assert not any(p in f.lower() for p in proibidas)


def test_frase_projeto_avancou_soa_contente_nao_ansiosa():
    e = criar("projeto_avancou", "fechou a integração com o gateway", projeto="BUB")
    assert e.frase() == "Fico contente que BUB avançou: fechou a integração com o gateway."


def test_frase_filtra_sofrimento_colado_na_causa():
    e = criar("projeto_travou", "eu tenho medo de mexer nisso de novo", projeto="Oldsen")
    f = e.frase()
    assert "medo" not in f.lower()
    assert f.startswith("Registro sem drama: Oldsen travou")


def test_frase_sem_alvo_usa_isso():
    e = criar("perda", "cliente cancelou o contrato")
    assert e.frase() == "Anoto: cliente cancelou o contrato."


# ── aplicar no humor, com coerência ─────────────────────────────────────
def test_projeto_avancou_sobe_confianca_e_energia():
    h = Humor()
    antes = h.e.confianca
    criar("projeto_avancou", "deploy no ar", intensidade=0.8, projeto="BUB").aplicar(h)
    assert h.e.confianca > antes
    assert h.e.gravidade <= 0.35   # não fica grave por causa de uma coisa boa


def test_projeto_travou_sobe_gravidade_e_desce_confianca():
    h = Humor()
    antes_conf, antes_grav = h.e.confianca, h.e.gravidade
    criar("projeto_travou", "API fora do ar", intensidade=0.9, projeto="Oldsen").aplicar(h)
    assert h.e.confianca < antes_conf
    assert h.e.gravidade > antes_grav


def test_conquista_alta_nunca_fica_grave_mesmo_partindo_de_grave():
    h = Humor()
    h.e.gravidade = 0.7   # já estava grave (ex.: um problema anterior)
    criar("conquista", "fechou contrato grande", intensidade=0.9).aplicar(h)
    assert h.conquista_recente is True
    assert h.e.gravidade <= 0.35   # regra de humor.py: nunca grave em conquista


def test_perda_alta_marca_joao_em_problema_e_nunca_fica_leve():
    h = Humor()
    criar("perda", "perdeu um cliente grande", intensidade=0.9).aplicar(h)
    assert h.joao_em_problema is True
    assert h.e.gravidade >= 0.6 and h.e.energia <= 0.55   # regra de humor.py: nunca leve com o João em problema


def test_intensidade_baixa_mexe_pouco(tmp_path):
    h1, h2 = Humor(), Humor()
    criar("projeto_avancou", "pequeno ajuste", intensidade=0.1).aplicar(h1)
    criar("projeto_avancou", "lançamento grande", intensidade=1.0).aplicar(h2)
    assert (h1.e.confianca - Humor().e.confianca) < (h2.e.confianca - Humor().e.confianca)


# ── processar: humor + diário + (best-effort) bus ───────────────────────
def test_processar_grava_no_diario_e_muda_humor(vault):
    h = Humor()
    antes = h.e.confianca
    e = criar("pessoa_reapareceu", "o Gabriel voltou depois de duas semanas", pessoa="Gabriel", intensidade=0.7)
    rel = processar(vault, h, e)
    texto = vault.read(rel)
    assert "Bom ver Gabriel de volta" in texto
    assert h.e.calor > Humor().e.calor
    assert antes == pytest.approx(Humor().e.confianca)  # pessoa_reapareceu não mexe em confiança


def test_processar_nao_falha_se_bus_indisponivel(vault, monkeypatch):
    import jaime.emocao.eventos as mod

    def _bus_quebrado(*a, **k):
        raise RuntimeError("bus fora")

    monkeypatch.setattr("jaime.hud.events.bus.emitir", _bus_quebrado)
    e = criar("data_importante", "aniversário da Maria Clara")
    rel = processar(vault, Humor(), e)   # não deve lançar
    assert "Hoje é aniversário da Maria Clara." in vault.read(rel)


def test_evento_e_dataclass_com_quando_padrao():
    e = criar("conquista", "fechou o mês no azul")
    assert isinstance(e, Evento) and e.quando is not None
