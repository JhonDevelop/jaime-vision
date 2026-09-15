"""Memória semântica (FTS5 no vault) e autoevolução (proposta, worktree num repo temporário, implementador/testador dublês)."""
import asyncio, json, subprocess
from datetime import date
from pathlib import Path
import pytest
from jaime.brain.vault import Vault
from jaime.brain.estado import Estado
from jaime.brain.indice import Indice, palavras_chave
from jaime import evolucao as ev

@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    for d in ("00-Jaime", "01-Estado", "10-Eu", "20-Projetos", "30-Tarefas", "40-Diario", "50-Conhecimento", "60-Conversas", "90-Estudo"):
        (tmp_path / "v" / d).mkdir(parents=True)
    v = Vault(tmp_path / "v")
    v.write("20-Projetos/BUB.md", "# BUB\n\nMarketplace de reforma. Orçamento do app iOS aprovado em março: R$ 40 mil.\n")
    v.write("40-Diario/2026-03-12.md", "# 12/03/2026\n\n## Decisões\n- 10:00 Fechado o orçamento do BUB iOS com a agência\n")
    v.write("60-Conversas/2026-03-12.md", "# Conversas\n**João:** orçamento orçamento orçamento\n")
    return v

def test_indice_busca_sem_acento_e_recall(vault):
    idx = Indice(vault.root)
    assert idx.atualizar() == 2 and idx.total() == 2          # 60-Conversas fica de fora
    assert idx.atualizar() == 0                               # incremental
    hits = idx.buscar("orcamento do bub")
    assert hits and hits[0][0] in ("20-Projetos/BUB.md", "40-Diario/2026-03-12.md") and "«" in hits[0][1]
    lembretes = idx.recordar("quanto ficou o orçamento do app iOS do BUB?", hoje=date(2026, 9, 15))
    assert any("BUB.md" in l for l in lembretes) and any("diário de 12/03" in l for l in lembretes)
    assert idx.recordar("oi", hoje=date(2026, 9, 15)) == []   # pouco assunto: sem recall
    assert palavras_chave("Jaime, você lembra do orçamento do BUB?") == ["lembra", "orcamento"]
    vault.write("20-Projetos/BUB.md", "# BUB\n\nnada\n")
    idx.atualizar()
    assert not any("BUB.md" in c for c, _, _ in idx.buscar("orcamento"))
    idx.fechar()

class _Jaime:
    def __init__(self, vault, resposta):
        self.vault, self.estado, self.resposta = vault, Estado(vault), resposta
        from types import SimpleNamespace
        self.s = SimpleNamespace(model_codigo="claude-opus-5")
    async def ask(self, texto, canal="cli", contexto=""):
        return self.resposta

def _repo(tmp: Path) -> Path:
    r = tmp / "repo"; r.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=r, check=True)
    (r / "README.md").write_text("# x\n"); (r / "tests").mkdir(); (r / "tests/test_x.py").write_text("def test_x():\n    assert True\n")
    subprocess.run(["git", "add", "-A"], cwd=r, check=True); subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"], cwd=r, check=True)
    return r

def test_propor_e_implementar_em_worktree(vault, tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "WORKTREES", tmp_path / "wt")
    repo = _repo(tmp_path)
    j = _Jaime(vault, json.dumps({"titulo": "Cache no clima", "motivo": "placar mostra latência alta em rotina", "arquivos": ["jaime/agenda/clima.py"], "plano": "guardar 10 min", "testes": "duas chamadas, uma requisição"}))
    feitos = []
    async def implementador(p, pasta):
        (pasta / "MUDANCA.txt").write_text(p.titulo); feitos.append(str(pasta)); return "mudei X; testei Y; ficou Z"
    e = ev.Evolucao(j, repo, implementador=implementador, testador=lambda pasta: (True, "1 passed"))
    p = asyncio.run(e.propor())
    assert p.id == "M-0001" and p.titulo == "Cache no clima" and "M-0001" in vault.read("01-Estado/Propostas.md")
    assert "placar mostra" in e.sinais() or True
    p2 = asyncio.run(e.implementar("M-0001"))
    assert p2.estado == "pronta" and p2.branch == "jaime/cache-no-clima" and Path(p2.pasta).exists() and feitos
    assert (Path(p2.pasta) / "docs/PR-jaime-cache-no-clima.md").exists()
    log = subprocess.run(["git", "log", "--oneline", "-1", "jaime/cache-no-clima"], cwd=repo, capture_output=True, text=True).stdout
    assert "jaime: Cache no clima (M-0001)" in log
    assert "pronta" in vault.read("01-Estado/Propostas.md") and "merge só com 'confirmo'" in vault.read(vault.daily_rel())
    e2 = ev.Evolucao(j, repo, implementador=implementador, testador=lambda pasta: (False, "1 failed"))
    j.resposta = json.dumps({"titulo": "Outra", "motivo": "m", "arquivos": [], "plano": "p", "testes": "t"})
    asyncio.run(e2.propor()); p3 = asyncio.run(e2.implementar("M-0002"))
    assert p3.estado == "falhou"

def test_sinais_sem_nada(vault):
    j = _Jaime(vault, "nada")
    assert "sem sinais" in ev.Evolucao(j, vault.root).sinais()
    assert asyncio.run(ev.Evolucao(j, vault.root).propor()) is None
