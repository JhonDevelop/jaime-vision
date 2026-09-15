"""Autoconsciência: o bloco 'quem sou' junta origem, identidade, estado e corpo; a frase curta responde 'quem é você?'."""
from pathlib import Path
from types import SimpleNamespace
from jaime.brain.vault import Vault
from jaime.brain import eu
from jaime.voice.rapidas import responder

def _jaime(tmp_path):
    (tmp_path / "00-Jaime").mkdir(); (tmp_path / "01-Estado").mkdir(); (tmp_path / "40-Diario").mkdir()
    (tmp_path / "00-Jaime/Origem.md").write_text("# Origem\n\n## Para que existo\nSer o braço operacional do João.\n\n## O que me define\n- Tenho um cérebro próprio.\n", encoding="utf-8")
    (tmp_path / "00-Jaime/Identidade.md").write_text("---\nnome: Jaime\n---\n# Identidade\n\n## Natureza\nSou um robô assistente autônomo.\n", encoding="utf-8")
    v = Vault(tmp_path)
    return SimpleNamespace(vault=v, identidade=SimpleNamespace(nome="Jaime"),
                           estado=SimpleNamespace(fase=lambda: "3 — Jarvis de verdade", secao=lambda s: "atendendo o João"),
                           s=SimpleNamespace(voz_modo="duplex", deepgram_key="d", camera="0"),
                           acesso=SimpleNamespace(liberado=True),
                           equipe=SimpleNamespace(maestri=SimpleNamespace(disponivel=True), vivos=[SimpleNamespace(nome="Codex")]),
                           vontade=SimpleNamespace(impulsos=SimpleNamespace(dominante=lambda: "Utilidade 0.8")))

def test_quem_sou_junta_tudo(tmp_path):
    j = _jaime(tmp_path)
    b = eu.quem_sou(j)
    assert b.startswith("Eu sou Jaime (J.A.I.M.E). Sou um robô assistente autônomo")
    assert "Por que existo: Ser o braço operacional do João." in b
    assert "Tenho um cérebro próprio." in b and "Sou um robô assistente autônomo." in b
    assert "Fase atual: 3 — Jarvis de verdade." in b and "Situação: atendendo o João" in b
    assert "ouvido duplex (deepgram)" in b and "Maestri disponível" in b and "filhos vivos: Codex" in b and "destrancado" in b
    assert "O que quero agora: Utilidade 0.8" in b and "bem-estar e verdade para o João" in b

def test_frase_curta_e_rapidas(tmp_path):
    j = _jaime(tmp_path)
    f = eu.frase_curta(j)
    assert f.startswith("Sou o Jaime, um robô assistente autônomo do João") and "fase 3" in f and "1 filho" in f and "Não sou humano" in f
    assert responder("quem é você?", j) == f
    assert responder("você é humano?", j) == f and responder("você tem consciência de si?", j) == f
    assert responder("abre o finder", j) is None

def test_despertar_registra_no_diario(tmp_path):
    j = _jaime(tmp_path)
    eu.registrar_despertar(j)
    import datetime
    txt = j.vault.read(f"40-Diario/{datetime.date.today():%Y-%m-%d}.md")
    assert "Despertei: sei quem sou (Jaime, robô assistente autônomo), fase 3" in txt and "1 filho(s) vivo(s)" in txt

def test_sem_vault_nao_quebra():
    j = SimpleNamespace(vault=SimpleNamespace(read=lambda p: (_ for _ in ()).throw(FileNotFoundError())), identidade=SimpleNamespace(nome="X"))
    assert "Eu sou X" in eu.quem_sou(j) and "braço operacional" in eu.quem_sou(j)
