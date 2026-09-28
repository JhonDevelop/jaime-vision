"""Fase 9 — evolução medida: promove parâmetro reversível que passa no gate, rejeita regressão, reverte."""
import asyncio, json
import pytest
from jaime.spatial.experimentos import Laboratorio, Parametros, PADRAO, medir


@pytest.fixture
def lab(tmp_path):
    return Laboratorio(Parametros(tmp_path / "parametros.json"), tmp_path / "experimentos.jsonl", repeticoes=10)


def test_baseline_acerta_tudo_sem_falsas_ativacoes():
    m = medir(PADRAO, repeticoes=6)
    assert m.accuracy == 1.0 and m.false_activations_per_hour == 0.0 and m.sample_count == 30


def test_promove_parametro_reversivel_que_passa_e_reverte(lab, tmp_path):
    e = lab.testar("dwell menor deixa a pega mais responsiva sem falsos", {"dwell_s": 0.06})
    assert e.decisao == "promovido" and e.cand["accuracy"] >= e.base["accuracy"]
    assert lab.p.valores["dwell_s"] == 0.06 and lab.p.versao == 1
    assert json.loads((tmp_path / "parametros.json").read_text())["valores"]["dwell_s"] == 0.06
    lab.reverter()
    assert lab.p.valores["dwell_s"] == 0.09 and Parametros(tmp_path / "parametros.json").valores["dwell_s"] == 0.09


def test_rejeita_regressao_de_falsas_ativacoes(lab):
    e = lab.testar("fechar a pinça mais cedo", {"close_ratio": 0.34})
    assert e.decisao == "rejeitado" and ("false" in e.motivo or "accuracy" in e.motivo)
    assert e.cand["false_activations_per_hour"] > 0 and lab.p.valores["close_ratio"] == 0.28 and lab.p.versao == 0


def test_rejeita_regressao_de_acerto(lab):
    e = lab.testar("dwell longo evita pega sem querer", {"dwell_s": 0.25})
    assert e.decisao == "rejeitado" and "accuracy" in e.motivo and lab.p.valores["dwell_s"] == 0.09


@pytest.mark.parametrize("mud,trecho", [({"dwell_s": 0.9}, "fora da faixa"), ({"open_ratio": 0.35, "close_ratio": 0.35}, "histerese"),
                                        ({"vigia_off": 1}, "desconhecido")])
def test_fora_das_faixas_nao_chega_nem_a_medir(lab, mud, trecho):
    e = lab.testar("x", mud)
    assert e.decisao == "rejeitado" and trecho in e.motivo and not e.cand


@pytest.mark.parametrize("classe", ["vigia", "acesso", "codigo_acao_so", "modelo", "dependencia", "egress"])
def test_classes_sensiveis_nunca_se_promovem_sozinhas(lab, classe):
    e = lab.testar("relaxar confirmação", {"dwell_s": 0.06}, classe=classe)
    assert e.decisao == "revisao_humana" and lab.p.versao == 0


def test_registro_de_experimentos(lab, tmp_path):
    lab.testar("a", {"dwell_s": 0.06}); lab.testar("b", {"close_ratio": 0.34})
    linhas = [json.loads(l) for l in (tmp_path / "experimentos.jsonl").read_text().splitlines()]
    assert [l["decisao"] for l in linhas] == ["promovido", "rejeitado"] and all(l["base"] for l in linhas)


# ── o gate no fluxo de PR existente (jaime/evolucao.py) ─────────────────────
def test_evolucao_com_gate_que_reprova_marca_falhou_e_documenta(tmp_path, monkeypatch):
    import subprocess
    from jaime import evolucao as ev
    from jaime.brain.vault import Vault
    from jaime.brain.estado import Estado
    from types import SimpleNamespace
    for d in ("00-Jaime", "01-Estado", "40-Diario", "90-Estudo"):
        (tmp_path / "v" / d).mkdir(parents=True)
    vault = Vault(tmp_path / "v")
    repo = tmp_path / "repo"; repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    (repo / "README.md").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    monkeypatch.setattr(ev, "WORKTREES", tmp_path / "wt")

    class J:
        def __init__(self):
            self.vault, self.estado, self.s = vault, Estado(vault), SimpleNamespace(model_codigo="m")
        async def ask(self, texto, canal="cli", contexto=""):
            return json.dumps({"titulo": "Pinça mais sensível", "motivo": "m", "arquivos": [], "plano": "p", "testes": "t"})

    async def impl(p, pasta):
        (pasta / "X.txt").write_text("x"); return "ok"
    e = ev.Evolucao(J(), repo, implementador=impl, testador=lambda pasta: (True, "1 passed"),
                    gate=lambda pasta, p: (False, "accuracy regression (0.74 < 1.00) em 50 replays"))
    asyncio.run(e.propor()); p = asyncio.run(e.implementar("M-0001"))
    assert p.estado == "falhou"
    doc = next((tmp_path / "wt").rglob("PR-jaime-*.md")).read_text()
    assert "Medição contra o baseline" in doc and "accuracy regression" in doc and "Rollback" in doc
