from pathlib import Path
import pytest
from jaime.brain.vault import Vault
from jaime.vigia.hooks import eh_confirmacao

@pytest.fixture
def vault(tmp_path: Path):
    for d in ("00-Jaime", "10-Eu", "20-Projetos", "30-Tarefas", "40-Diario"):
        (tmp_path / d).mkdir()
    (tmp_path / "20-Projetos/BUB.md").write_text("# BUB\nMarketplace de reforma.\n", encoding="utf-8")
    return Vault(tmp_path)

def test_tarefa_e_busca(vault):
    item = vault.tarefa("Ligar para o Rafael", "BUB", "2026-09-20")
    assert item == "- [ ] Ligar para o Rafael @BUB ⏳ 2026-09-20"
    assert vault.tarefas_abertas() == [item]
    assert vault.buscar("rafael")[0][0] == "30-Tarefas/Inbox.md"

def test_diario_insere_na_secao(vault):
    vault.diario("decidimos usar escrow", "Decisões")
    txt = vault.read(vault.daily_rel())
    assert "## Decisões\n- " in txt and "escrow" in txt

def test_protege_identidade(vault):
    with pytest.raises(PermissionError):
        vault.write("00-Jaime/Regras.md", "hack")

def test_contexto_lista_projetos(vault):
    assert "[[BUB]] — Marketplace de reforma." in vault.contexto_inicial()

def test_confirmacao():
    assert eh_confirmacao("Confirmo!") and not eh_confirmacao("confirmo o quê?")
