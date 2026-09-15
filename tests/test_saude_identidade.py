"""Saúde do cérebro (jaime cerebro check) e identidade editável (nome no frontmatter, renomear)."""
from pathlib import Path
import pytest
from jaime.brain.saude import verificar, gerar_indices, relatorio, resumo_falado
from jaime.identidade import Identidade, quer_renomear, eh_sim, slug

def _vault(tmp: Path, com_identidade=True) -> Path:
    for d in ("00-Jaime", "01-Estado", "10-Eu", "20-Projetos", "30-Tarefas", "40-Diario", "50-Conhecimento", "60-Conversas"):
        (tmp / d).mkdir(parents=True)
    if com_identidade:
        (tmp / "00-Jaime/Identidade.md").write_text("---\nnome: Jaime\napelidos: []\nwake_word: jaime\nconfirmado: false\n---\n# Identidade\n\nSou o Jaime.\n")
    (tmp / "01-Estado/Estado.md").write_text("# Estado\n\n## Fase\n1 — operando\n")
    (tmp / "20-Projetos/BUB.md").write_text("# BUB\nApp de delivery.\n")
    (tmp / "50-Conhecimento/Deploy.md").write_text("# Deploy\nComo subir o BUB. Ver [[BUB]].\n")
    (tmp / "40-Diario/2026-09-15.md").write_text("# 15/09/2026\n")
    return tmp

def _repo(tmp: Path) -> Path:
    (tmp / "docs").mkdir(parents=True); (tmp / "docs/ROADMAP.md").write_text("| Fase | x |\n|---|---|\n| 0 | a |\n| 1 | b |\n")
    (tmp / "CLAUDE.md").write_text("# Jaime — constituição\n\nVocê é o **Jaime**, assistente.\n")
    (tmp / ".env.example").write_text("JAIME_NOME=jaime\n")
    return tmp

# ── saúde ──────────────────────────────────────────────
def test_vault_saudavel(tmp_path):
    from datetime import date
    v = _vault(tmp_path / "v"); r = _repo(tmp_path / "r")
    probs = verificar(v, r, hoje=date(2026, 9, 15))
    assert [p for p in probs if p.nivel == "erro"] == []
    assert any("órfã" in p.msg for p in probs)       # Deploy.md não tem quem aponte para ela

def test_detecta_pasta_faltando_identidade_sem_nome_e_link_quebrado(tmp_path):
    v = _vault(tmp_path / "v", com_identidade=False)
    (tmp_path / "v/00-Jaime/Identidade.md").write_text("# Identidade\nSou o Jaime.\n")
    (tmp_path / "v/50-Conhecimento/Deploy.md").write_text("Ver [[NaoExiste]].\n")
    import shutil; shutil.rmtree(tmp_path / "v/60-Conversas")
    probs = verificar(v)
    msgs = [str(p) for p in probs]
    assert any("60-Conversas" in m and "✘" in m for m in msgs)
    assert any("Identidade.md" in m and "nome" in m for m in msgs)
    assert any("[[NaoExiste]]" in m for m in msgs)
    assert "erro" in relatorio(probs) and resumo_falado(probs).startswith("Atenção")

def test_fase_fora_do_roadmap_e_diario_parado(tmp_path):
    from datetime import date
    v = _vault(tmp_path / "v"); r = _repo(tmp_path / "r")
    (v / "01-Estado/Estado.md").write_text("# Estado\n\n## Fase\n9 — futuro\n")
    probs = verificar(v, r, hoje=date(2026, 9, 30))
    assert any("fase 9" in p.msg for p in probs) and any("diário" in p.msg for p in probs)

def test_gera_indices(tmp_path):
    v = _vault(tmp_path / "v")
    gerados = gerar_indices(v)
    assert set(gerados) == {"50-Conhecimento/INDEX.md", "20-Projetos/INDEX.md"}
    idx = (v / "20-Projetos/INDEX.md").read_text()
    assert "[[BUB]] — App de delivery." in idx and "Não edite" in idx
    # com o índice, a nota deixa de ser órfã
    assert not any("órfã" in p.msg for p in verificar(v))

# ── identidade ─────────────────────────────────────────
def test_le_nome_do_frontmatter_e_variantes(tmp_path):
    v = _vault(tmp_path / "v")
    i = Identidade(v)
    assert i.nome == "Jaime" and not i.confirmado
    assert "jardim" in i.variantes() and i.variantes()[0] == "jaime"
    i.confirmar(); assert i.confirmado and "Sou o Jaime." in i.arquivo.read_text()

def test_sem_frontmatter_cai_no_padrao(tmp_path):
    v = _vault(tmp_path / "v", com_identidade=False)
    (v / "00-Jaime/Identidade.md").write_text("# Identidade\n")
    assert Identidade(v).nome == "Jaime"

def test_renomear_atualiza_identidade_claude_md_e_env(tmp_path):
    v = _vault(tmp_path / "v"); r = _repo(tmp_path / "r")
    i = Identidade(v, r)
    alterados = i.renomear("Vega", git=False)
    assert i.nome == "Vega" and not i.confirmado and i.ler()["wake_word"] == "vega"
    assert "Sou o Vega." in i.arquivo.read_text()
    assert "Você é o **Vega**" in (r / "CLAUDE.md").read_text() and "# Vega — constituição" in (r / "CLAUDE.md").read_text()
    assert "JAIME_NOME=vega" in (r / ".env.example").read_text()
    assert len(alterados) == 3
    assert i.renomear("vega", git=False) == []     # mesmo nome: nada a fazer

def test_frases_de_renomear_e_sim():
    assert quer_renomear("me chama de Fred") == "Fred"
    assert quer_renomear("Seu nome agora é vega.") == "Vega"
    assert quer_renomear("pode me chamar de Atlas") is None or quer_renomear("pode me chamar de Atlas") == "Atlas"
    assert quer_renomear("abre o Finder") is None
    assert eh_sim("Sim.") and eh_sim("isso mesmo") and not eh_sim("não")
    assert slug("Zé Ninguém") == "ze-ninguem"
