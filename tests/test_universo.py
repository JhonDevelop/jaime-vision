"""O universo do J.A.I.M.E: o mapa dos mundos vivos dele, montado do vault de verdade.
Regra que não pode cair: nenhum mundo quebrado derruba a rota — vira um mundo apagado com o motivo."""
from pathlib import Path
from types import SimpleNamespace
from jaime.hud.universo import montar

MUNDOS = {"mente", "vontade", "estudo", "memoria", "equipe", "feitoria",
          "vigilancia", "cuidado", "servico", "maos", "consultoria", "conexoes",
          "cerebros", "espelho"}

def _vault(tmp):
    (tmp / "01-Estado").mkdir(parents=True); (tmp / "90-Estudo").mkdir(); (tmp / "30-Tarefas").mkdir()
    (tmp / "01-Estado/Vontades.md").write_text(
        "| impulso | nível | barra |\n|---|---|---|\n| Curiosidade | 0.86 | x |\n| Ordem | 0.30 | x |\n")
    (tmp / "01-Estado/Pensamentos.md").write_text(
        "## 2026-09-17 09:01 · Gargalo do workflow ·dizer\nTexto.\n\n## 2026-09-16 08:00 · Outra coisa\nTexto.\n")
    (tmp / "90-Estudo/Problemas.md").write_text(
        "## P-0001 · whisper na gpu · resolvido · 2026-09-15\n\n## P-0002 · eco do microfone · aberto · 2026-09-16\n")
    (tmp / "01-Estado/Equipe.md").write_text(
        "## vigilancia\n- tipo: codigo · estado: vivo\n- missão: olhar a câmera\n\n## antigo\n- tipo: codigo · estado: morto\n- missão: x\n")
    (tmp / "30-Tarefas/Inbox.md").write_text("- [ ] fechar o contrato @bub\n- [x] feito\n- [ ] ligar pro rafael\n")
    return SimpleNamespace(root=tmp)

def test_o_universo_tem_os_doze_mundos_e_le_o_vault_de_verdade(tmp_path):
    u = montar(_vault(tmp_path), None)
    assert {m["id"] for m in u["mundos"]} == MUNDOS
    por = {m["id"]: m for m in u["mundos"]}
    # vontade: o impulso mais alto vira o nível do mundo e aparece no resumo
    assert por["vontade"]["nivel"] == 0.86 and "Curiosidade" in por["vontade"]["resumo"]
    assert por["vontade"]["corpos"][0] == {"nome": "Curiosidade", "detalhe": "nível 0.86", "peso": 0.86}
    # mente: cada pensamento é um corpo, com o assunto dele
    assert por["mente"]["total"] == 2 and por["mente"]["corpos"][0]["nome"] == "Gargalo do workflow"
    # estudo: conta só o que está aberto
    assert "1 em aberto de 2" in por["estudo"]["resumo"]
    # equipe: separa filho vivo de dispensado
    assert "1 filhos vivos de 2" in por["equipe"]["resumo"]
    assert por["equipe"]["corpos"][0]["peso"] == 1.0 and por["equipe"]["corpos"][1]["peso"] == 0.35
    # serviço: só as tarefas em aberto
    assert "2 tarefas abertas" in por["servico"]["resumo"]
    # todo mundo tem cor, nível entre 0 e 1, e um resumo
    for m in u["mundos"]:
        assert m["cor"].startswith("#") and 0.05 <= m["nivel"] <= 1.0 and m["resumo"]
    assert u["total_corpos"] > 0

def test_mundo_que_falha_nao_derruba_a_rota(tmp_path, monkeypatch):
    import jaime.hud.universo as U
    monkeypatch.setattr(U, "PENSAMENTO_RX", None)          # quebra só a Mente
    u = montar(_vault(tmp_path), None)
    por = {m["id"]: m for m in u["mundos"]}
    assert "apagado" in por["mente"]["resumo"] and por["mente"]["nivel"] == 0.05
    assert {m["id"] for m in u["mundos"]} == MUNDOS        # os outros 11 continuam de pé
    assert por["vontade"]["nivel"] == 0.86

def test_vault_vazio_nao_quebra(tmp_path):
    u = montar(SimpleNamespace(root=tmp_path), None)
    assert {m["id"] for m in u["mundos"]} == MUNDOS and u["total_corpos"] >= 0
