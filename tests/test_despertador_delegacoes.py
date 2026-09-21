"""M-37 (Vigília 20/09): P-0008 delegado 10× em 7 h sem fecho. Duas delegações sem resolução viram 'aguardando o João'."""
from pathlib import Path
import pytest
from jaime.brain.vault import Vault
from jaime.cerebros.despertador import pode_delegar, ARQUIVO_DELEGACOES, MAX_DELEGACOES

@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    for d in ("40-Diario", ".jaime"): (tmp_path / d).mkdir()
    return Vault(tmp_path)

def test_mesma_pauta_so_e_delegada_duas_vezes_e_depois_avisa_uma_vez(vault):
    pauta = "P-0008: Ferramenta falha repetidamente: Input validation error: 'corpo' is a required property — descubra a causa"
    assert pode_delegar(vault, pauta) and pode_delegar(vault, pauta)
    assert not pode_delegar(vault, pauta) and not pode_delegar(vault, pauta)
    d = vault.read(vault.daily_rel())
    assert d.count("Já deleguei 2× sem fecho, aguardando o João: P-0008") == 1
    assert pode_delegar(vault, "TODO em jaime/x.py: outra coisa")                  # outra pauta segue normal
    assert "P-0008" in vault.read(ARQUIVO_DELEGACOES) and MAX_DELEGACOES == 2

def test_contagem_sobrevive_a_reinicio(vault):
    pauta = "P-0009: fim de turno duvidoso"
    pode_delegar(vault, pauta)
    v2 = Vault(vault.root)                                                          # "reinício": outra instância, mesmo vault
    assert pode_delegar(v2, pauta) and not pode_delegar(v2, pauta)
