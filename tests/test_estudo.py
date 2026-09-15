"""Cérebro de estudo: problemas em aberto, um ciclo que resolve offline, sandbox."""
import asyncio
from pathlib import Path
import pytest
from jaime.brain.vault import Vault
from jaime.brain.estado import Estado
from jaime.estudo.problemas import Problemas
from jaime.estudo.loop import Estudo, _fora_do_sandbox, _hook_sandbox, SANDBOX

@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    for d in ("00-Jaime", "01-Estado", "10-Eu", "20-Projetos", "30-Tarefas", "40-Diario", "50-Conhecimento", "60-Conversas", "90-Estudo"):
        (tmp_path / d).mkdir()
    return Vault(tmp_path)

def test_abrir_listar_tentar_resolver(vault):
    pr = Problemas(vault)
    p = pr.abrir("pod install falha no BUB", "CocoaPods could not find compatible versions", "ferramenta_falhou")
    assert p.id == "P-0001" and pr.abertos()[0].titulo == "pod install falha no BUB"
    assert pr.abrir("pod install falhando no BUB", origem="correcao").id == "P-0001"     # parecido: não duplica
    q = pr.abrir("Whisper lento no Intel", origem="joao_pediu")
    assert q.id == "P-0002" and len(pr.abertos()) == 2
    pr.registrar_tentativa("P-0001", "rodei pod repo update", "testar Ruby 3.2")
    assert pr.proximo().id == "P-0002"                    # menos tentativas primeiro
    assert "falta testar Ruby 3.2" in pr.por_id("P-0001").tentativas[0]
    pr.resolver("P-0001", "50-Conhecimento/pod-install.md")
    assert [x.id for x in pr.abertos()] == ["P-0002"] and pr.por_id("P-0001").conhecimento.endswith("pod-install.md")

def test_ciclo_resolve_com_pesquisador_offline(vault):
    est = Estado(vault)
    async def pesquisador(p):
        return {"resolvido": True, "titulo": "Whisper lento no Intel", "como_reproduzir": "rodar small em CPU",
                "o_que_resolveu": "usar base ou Deepgram", "onde_se_aplica": "qualquer Mac Intel", "tentativa": "medi os dois",
                "skill": "1. medir\n2. trocar"}
    e = Estudo(vault, est, None, repo_root=vault.root, pesquisador=pesquisador)
    e.abrir("Whisper lento no Intel", "3,6 s por frase", "joao_pediu")
    r = asyncio.run(e.ciclo())
    assert r["resolvido"] and e.problemas.abertos() == []
    nota = (vault.root / "50-Conhecimento/whisper-lento-no-intel.md").read_text()
    assert "## O que resolveu" in nota and "usar base ou Deepgram" in nota
    assert "Whisper lento" in est.secao("Aprendizados recentes")
    assert (vault.root / ".claude/skills/whisper-lento-no-intel/SKILL.md").exists()
    assert "[[whisper-lento-no-intel]]" in (vault.root / "50-Conhecimento/INDEX.md").read_text()
    assert asyncio.run(e.ciclo()) is None                    # nada mais para estudar

def test_ciclo_sem_solucao_registra_tentativa(vault):
    async def pesquisador(p):
        return {"resolvido": False, "tentativa": "tentei X", "falta": "acesso à API"}
    e = Estudo(vault, pesquisador=pesquisador)
    e.abrir("Integrar Instagram", origem="sem_resposta")
    asyncio.run(e.ciclo())
    p = e.problemas.abertos()[0]
    assert len(p.tentativas) == 1 and "falta acesso à API" in p.tentativas[0]

def test_sandbox_nega_fora_do_laboratorio():
    assert _fora_do_sandbox("/Users/x/projetos/app.py") and not _fora_do_sandbox(str(SANDBOX / "teste.py"))
    negado = asyncio.run(_hook_sandbox({"tool_name": "Write", "tool_input": {"file_path": "/Users/x/jaime-vision/jaime/x.py"}}, None, None))
    assert negado["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert asyncio.run(_hook_sandbox({"tool_name": "Bash", "tool_input": {"command": "cd ~/projetos && ls"}}, None, None)) != {}
    assert asyncio.run(_hook_sandbox({"tool_name": "Bash", "tool_input": {"command": "python3 teste.py"}}, None, None)) == {}
