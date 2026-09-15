from pathlib import Path
import pytest
from jaime.vigia.acesso import Acesso, hash_senha, normalizar
from jaime.brain.vault import Vault
from jaime.brain.estado import Estado

def test_normaliza_fala():
    assert normalizar("um dois três quatro, um dois tres quatro") == "12341234"
    assert normalizar("1234 1234") == "12341234"

def test_acesso_libera_e_tranca():
    a = Acesso(hash_senha("12341234"), timeout_min=1)
    assert not a.liberado and not a.tentar("oi jaime")
    assert a.tentar("a senha é um dois três quatro um dois três quatro") and a.liberado
    a.trancar(); assert not a.liberado

@pytest.fixture
def estado(tmp_path: Path):
    for d in ("00-Jaime", "10-Eu", "20-Projetos", "30-Tarefas", "40-Diario", "60-Conversas"):
        (tmp_path / d).mkdir()
    return Estado(Vault(tmp_path))

def test_estado_cria_e_atualiza(estado):
    assert estado.fase().startswith("0")
    estado.atualizar_secao("Fase", "1 — operando")
    estado.atualizar_secao("Próximos passos", "- testar voz")
    assert estado.fase() == "1 — operando" and "testar voz" in estado.secao("Próximos passos")

def test_turno_registra_conversa_e_maquina(estado):
    assert estado.registrar_maquina() is True and estado.registrar_maquina() is False
    estado.registrar_turno("hud", "que horas são?", "Dez e meia.")
    assert "que horas são" in estado.secao("Última conversa")
    assert any(p.name.endswith(".md") for p in (estado.vault.root / "60-Conversas").iterdir())
    assert estado.turnos == 1 and not estado.precisa_refletir()

def test_vigia_protege_o_proprio_codigo():
    import asyncio
    from jaime.vigia.hooks import Vigia
    v = Vigia()
    negado = asyncio.run(v.pre_tool_use({"tool_name": "Edit", "tool_input": {"file_path": "/x/jaime-vision/jaime/voice/tts.py"}}, None, None))
    assert negado.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
    v.armar()
    assert asyncio.run(v.pre_tool_use({"tool_name": "Edit", "tool_input": {"file_path": "jaime/voice/tts.py"}}, None, None)) == {}
    assert asyncio.run(v.pre_tool_use({"tool_name": "Write", "tool_input": {"file_path": "/Users/x/projetos/app/main.py"}}, None, None)) == {}

def test_confere_nao_libera():
    a = Acesso(hash_senha("12341234"), timeout_min=1)
    assert a.confere("um dois três quatro um dois três quatro") and not a.liberado
    assert not a.confere("oi")
