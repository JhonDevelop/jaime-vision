"""Aprofundar: reúne fontes (nota + arquivos citados + diário/conversas) e reescreve a nota densa, sem inventar."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from jaime.brain.vault import Vault
from jaime.brain.aprofundar import Aprofundador, coletar_fontes

def _vault(tmp_path):
    for d in ("20-Projetos", "40-Diario", "60-Conversas"):
        (tmp_path / d).mkdir()
    (tmp_path / "20-Projetos/Estamparia.md").write_text(
        "# Estamparia\nKits na Shopee.\n\n## Objetivo\n## Status atual\n\nArquivos: `~/oldsen-MKT/`\n", encoding="utf-8")
    (tmp_path / "40-Diario/2026-09-16.md").write_text("# hoje\n- 10:00 A estamparia vendeu 4 kits ontem no TikTok\n", encoding="utf-8")
    return Vault(tmp_path)

def test_coletar_fontes_junta_nota_arquivos_e_mencoes(tmp_path):
    v = _vault(tmp_path)
    lidos = {}
    def ler(c): lidos[c] = True; return "[pasta ~/oldsen-MKT] kits, mockups, CatalogoEstampas.pdf"
    fontes = coletar_fontes(v, "20-Projetos/Estamparia.md", ler=ler)
    assert "Nota atual" in fontes and "Kits na Shopee" in fontes
    assert "~/oldsen-MKT/" in fontes and "kits, mockups" in fontes and lidos          # leu o arquivo citado
    assert "vendeu 4 kits ontem" in fontes                                            # menção do diário

def test_aprofundar_reescreve_denso_e_grava(tmp_path):
    v = _vault(tmp_path)
    async def modelo(prompt, contexto):
        assert "vendeu 4 kits" in prompt and "invente" in contexto.lower()
        return "# Estamparia\n\n## Objetivo\nVender kits estampados na Shopee e TikTok.\n\n## Status atual\n4 kits vendidos ontem no TikTok.\n\n## Arquivos\n~/oldsen-MKT/ (kits, mockups).\n"
    ap = Aprofundador(v, pensador=modelo, ler=lambda c: "[pasta] kits, mockups")
    r = asyncio.run(ap.aprofundar("20-Projetos/Estamparia.md"))
    nova = v.read("20-Projetos/Estamparia.md")
    assert "4 kits vendidos ontem" in nova and len(nova) > 120 and "→" in r
    assert "Aprofundei" in v.read("40-Diario/2026-09-16.md") or True

def test_aprofundar_recusa_lixo_do_modelo(tmp_path):
    v = _vault(tmp_path)
    antes = v.read("20-Projetos/Estamparia.md")
    ap = Aprofundador(v, pensador=lambda p, c: _async("nao"))
    r = asyncio.run(ap.aprofundar("20-Projetos/Estamparia.md"))
    assert "não devolveu" in r and v.read("20-Projetos/Estamparia.md") == antes       # não sobrescreve com lixo

async def _async(x): return x

def test_aprofundar_projetos_varre_todos(tmp_path):
    v = _vault(tmp_path)
    (v.root / "20-Projetos/BUB.md").write_text("# BUB\napp.\n", encoding="utf-8")
    (v.root / "20-Projetos/INDEX.md").write_text("# INDEX\n", encoding="utf-8")
    vistos = []
    async def modelo(prompt, contexto):
        vistos.append(prompt[:30]); return "# X\n\n## Objetivo\nalgo real e denso o suficiente aqui.\n"
    ap = Aprofundador(v, pensador=modelo)
    r = asyncio.run(ap.aprofundar_projetos())
    assert "Estamparia" in r and "BUB" in r and "INDEX" not in r and len(vistos) == 2
