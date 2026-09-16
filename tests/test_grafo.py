"""Grafo dos agentes: junta notas + diário + ferramentas + loops num grafo denso, com clusters e arestas reais."""
from pathlib import Path
from jaime.brain.vault import Vault
from jaime.hud.grafo import montar

def _vault(tmp_path):
    for d in ("00-Jaime", "20-Projetos", "40-Diario", "90-Estudo", "01-Estado"):
        (tmp_path / d).mkdir()
    (tmp_path / "20-Projetos/BUB.md").write_text("# BUB\napp.\n", encoding="utf-8")
    (tmp_path / "00-Jaime/Regras.md").write_text("# Regras\nver [[BUB]].\n", encoding="utf-8")
    (tmp_path / "40-Diario/2026-09-16.md").write_text("# hoje\n- 10:00 avancei no BUB hoje\n- 11:00 outra coisa qualquer\n", encoding="utf-8")
    return Vault(tmp_path)

def test_monta_grafo_denso_com_clusters_e_arestas(tmp_path):
    g = montar(_vault(tmp_path), None)
    ids = {n["id"] for n in g["nos"]}
    assert "agente:orquestrador" in ids                      # hub central
    assert "20-Projetos/BUB.md" in ids and "40-Diario/2026-09-16.md" in ids
    # a linha do diário virou nó e ligou ao projeto que cita
    diario_bub = [n for n in g["nos"] if n["pasta"] == "diário" and "BUB" in n["nome"]]
    assert diario_bub and [diario_bub[0]["id"], "20-Projetos/BUB.md"] in g["arestas"]
    # o [[BUB]] em Regras virou aresta
    assert ["00-Jaime/Regras.md", "20-Projetos/BUB.md"] in g["arestas"]
    # clusters e contagem
    clusters = dict(g["clusters"])
    assert clusters.get("diário", 0) == 2 and clusters.get("loops", 0) == 8 and "núcleo" in clusters
    assert g["total"] == len(g["nos"]) and g["total_arestas"] == len(g["arestas"])
    assert all(n["nome"] and n["pasta"] for n in g["nos"])   # nada sem rótulo/cluster
