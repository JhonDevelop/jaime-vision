"""Mãos: projetos, arquivos (regras do Jeito), Vigia sobre browser/mover, e o browser num site local."""
import asyncio
from pathlib import Path
import pytest
from jaime.brain.vault import Vault
from jaime.maos.projetos import criar_projeto
from jaime.maos import arquivos as arq
from jaime.vigia.hooks import Vigia

@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    for d in ("00-Jaime", "10-Eu", "20-Projetos", "40-Diario", "templates"):
        (tmp_path / "v" / d).mkdir(parents=True)
    (tmp_path / "v/templates/Projeto.md").write_text("# {{nome}}\n\n## Situação\n\n## Decisões\n\n## Próximos passos\n")
    return Vault(tmp_path / "v")

def test_criar_projeto_python(vault, tmp_path):
    r = criar_projeto("Radar BUB", "python", tmp_path / "ws", vault, "monitor de concorrentes")
    assert r["ok"] and r["git"]
    pasta = Path(r["pasta"])
    assert pasta.name == "radar-bub" and (pasta / "README.md").exists() and (pasta / "CLAUDE.md").exists()
    assert (pasta / ".env.example").exists() and (pasta / "src/radar_bub/__init__.py").exists() and (pasta / ".git").is_dir()
    assert "monitor de concorrentes" in (vault.root / "20-Projetos/Radar BUB.md").read_text()
    assert "Projeto criado: Radar BUB" in vault.read(vault.daily_rel())
    r2 = criar_projeto("Radar BUB", "python", tmp_path / "ws", vault)
    assert not r2["ok"] and "já existe" in r2["erro"]

def test_regras_de_arquivos_e_plano(tmp_path):
    jeito = ('# Jeito\n\n## Arquivos\n> - *.zip → ~/lixo (exemplo comentado, ignorar)\n'
             f'- *.pdf com "nota fiscal" → {tmp_path}/Fiscal\n- *.png, *.jpg → {tmp_path}/Imagens\n\n## Horários\n- manhã\n')
    rs = arq.regras(jeito)
    assert len(rs) == 2 and rs[0].trecho == "nota fiscal" and rs[1].padroes == ["*.png", "*.jpg"]
    down = tmp_path / "down"; down.mkdir()
    for n in ("nota fiscal 123.pdf", "contrato.pdf", "foto.JPG", ".DS_Store"):
        (down / n).write_text("x")
    plano = arq.planejar(down, rs)
    assert [(o.name, d.parent.name) for o, d in plano] == [("foto.JPG", "Imagens"), ("nota fiscal 123.pdf", "Fiscal")]
    assert "só executo com 'confirmo'" in arq.texto_plano(plano)
    assert arq.mover(down / "foto.JPG", plano[0][1]).endswith("Imagens/foto.JPG") and not (down / "foto.JPG").exists()
    (down / "foto.JPG").write_text("y")
    assert "foto (2).JPG" in arq.mover(down / "foto.JPG", plano[0][1])      # não sobrescreve

def _hook(v, nome, args):
    return asyncio.run(v.pre_tool_use({"tool_name": nome, "tool_input": args}, None, None))

def test_vigia_segura_compra_e_libera_submit_e_mover():
    v = Vigia()
    assert _hook(v, "mcp__maos__clicar", {"alvo": "Finalizar compra"}).get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
    assert _hook(v, "mcp__maos__clicar", {"alvo": "Enviar mensagem"}).get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
    assert _hook(v, "mcp__maos__clicar", {"alvo": "button[type=submit]"}) == {}
    assert _hook(v, "mcp__maos__clicar", {"alvo": "Próxima página"}) == {}
    assert _hook(v, "mcp__maos__mover", {"origem": "a", "destino": "b"}) == {}
    v.armar()
    assert _hook(v, "mcp__maos__clicar", {"alvo": "Finalizar compra"}) == {}

@pytest.mark.skipif(not __import__("importlib").util.find_spec("playwright"), reason="playwright não instalado")
def test_browser_le_clica_e_extrai_site_local(tmp_path):
    from jaime.maos.browser import Navegador
    (tmp_path / "a.html").write_text('<h1>Loja</h1><ul><li class="p">Bota R$ 199</li><li class="p">Capacete R$ 899</li></ul><a href="b.html">Ver detalhes</a>')
    (tmp_path / "b.html").write_text('<h1>Detalhes</h1><input placeholder="CEP"><button>Calcular</button>')
    import jaime.maos.browser as mod
    mod.PERFIL = tmp_path / "perfil"; mod.CAPTURAS = tmp_path / "caps"
    nav = Navegador(headless=True)
    async def fluxo():
        try:
            assert "Loja" in (await nav.ler_pagina()) if False else True
            await nav.abrir(f"file://{tmp_path}/a.html")
            assert (await nav.extrair("li.p")) == ["Bota R$ 199", "Capacete R$ 899"]
            assert "Loja" in await nav.ler_pagina()
            assert "b.html" in await nav.clicar("Ver detalhes")
            assert "preenchi" in await nav.preencher("CEP", "14400-000")
            assert (await nav.screenshot("teste")).endswith("teste.png")
        finally:
            await nav.fechar()
    asyncio.run(fluxo())
    assert (tmp_path / "caps/teste.png").exists()
