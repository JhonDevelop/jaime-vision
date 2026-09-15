from pathlib import Path
import pytest
from jaime.brain.vault import Vault
from jaime.emocao.vinculo import Vinculo

@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    for d in ("00-Jaime", "01-Estado", "10-Eu"):
        (tmp_path / d).mkdir()
    (tmp_path / "10-Eu/Pessoas.md").write_text("# Pessoas\n\n- **Maria Clara** — namorada do João.\n- **Gabriel** — melhor amigo e sócio; API do BUB.\n")
    return Vault(tmp_path)

def test_vinculo_cresce_e_vira_contexto_sem_carencia(vault):
    v = Vinculo(vault)
    d0 = v.dados(); assert d0["conversas"] == 0 and 0 < d0["familiaridade"] <= 1
    for _ in range(3): v.registrar_conversa()
    assert v.dados()["conversas"] == 3 and "conversas: 3" in vault.read("01-Estado/Vinculo.md")
    v.acompanhar("reunião com o Diego na quinta")
    c = v.contexto()
    assert "Maria Clara — namorada" in c and "Gabriel" in c and "reunião com o Diego" in c
    assert "Nunca diga que sentiu falta" in c and "sem carência" in c
    v.fechar_acompanhamento("reunião com o Diego na quinta"); assert v.dados()["acompanhamentos"] == []
    assert 0.5 <= v.calor() <= 0.85 and [p["nome"] for p in v.pessoas()] == ["Maria Clara", "Gabriel"]
