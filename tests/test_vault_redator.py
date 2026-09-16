"""Nenhuma escrita no vault pode conter a palavra-passe (16/09: uma reflexão escreveu a senha no diário)."""
import hashlib
from pathlib import Path
import pytest
from jaime.brain.vault import Vault, redigir_segredos

SENHA = "98765432"

@pytest.fixture
def vault(tmp_path: Path, monkeypatch) -> Vault:
    monkeypatch.setenv("JAIME_PASSPHRASE_HASH", hashlib.sha256(SENHA.encode()).hexdigest())
    for d in ("40-Diario", "60-Conversas"): (tmp_path / d).mkdir()
    return Vault(tmp_path)

def test_mascara_a_senha_em_digitos_falados_e_por_extenso(vault):
    assert redigir_segredos("destrancado por senha digitada no HUD (98765432).") == "destrancado por senha digitada no HUD (••••)."
    assert redigir_segredos("você › 9 8 7 6 5 4 3 2.") == "você › ••••."
    assert redigir_segredos("disse nove oito sete seis cinco quatro três dois e abriu") == "disse •••• e abriu"
    assert redigir_segredos("9-8-7-6-5-4-3-2") == "••••"

def test_outros_numeros_ficam_intactos(vault):
    for t in ("R$ 1250 a cada 15 dias", "2026-09-16 às 07:24", "(016) 3238-2859 — ligação perdida", "1 2 3 4 1 2 3 4", "BUB 1.1.131, Expo SDK 57"):
        assert redigir_segredos(t) == t

def test_diario_conversas_e_append_passam_pelo_redator(vault):
    vault.diario("Cérebro destrancado por senha digitada no HUD (98765432). Respondi.", "Log")
    assert "98765432" not in vault.read(vault.daily_rel()) and "(••••)" in vault.read(vault.daily_rel())
    vault.append("60-Conversas/x.md", "**João:** 9 8 7 6 5 4 3 2\n")
    assert vault.read("60-Conversas/x.md") == "**João:** ••••\n"
