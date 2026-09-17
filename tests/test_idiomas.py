"""Multilíngue: ouvir outras línguas e FALAR nome em inglês.
O que não pode cair: o reconhecedor recebe os nomes dos projetos do João (erro de nome próprio é o que
mais atrapalha) e a instrução da voz não proíbe mais pronúncia estrangeira."""
from pathlib import Path
from types import SimpleNamespace
import pytest
from jaime.voice.idiomas import (query_deepgram, termos_do_vault, BASE, MAX_KEYTERMS,
                                 IDIOMA_STT, IDIOMA_WHISPER, IDIOMA_REALTIME)


class _Vault:
    def __init__(self, raiz): self.root = raiz
    def read(self, rel):
        p = self.root / rel
        return p.read_text(encoding="utf-8") if p.is_file() else ""


@pytest.fixture
def vault(tmp_path):
    (tmp_path / "20-Projetos").mkdir(parents=True)
    for n in ("GearHead-Brasil", "BUB", "Estamparia", "INDEX"):
        (tmp_path / "20-Projetos" / f"{n}.md").write_text(f"# {n}\n")
    (tmp_path / "10-Eu").mkdir()
    (tmp_path / "10-Eu" / "Pessoas.md").write_text("## Rafael Souza\n- sócio\n\n## Mariana\n- advogada\n")
    return _Vault(tmp_path)


def test_o_stt_em_fluxo_e_multilingue_por_padrao():
    """`multi` reconhece troca de língua na MESMA frase — é o caso de quem fala português citando
    nome em inglês. Antes era pt-BR fixo e «GearHead» virava «guiar head»."""
    assert IDIOMA_STT == "multi"
    assert "language=multi" in query_deepgram(None)

def test_o_whisper_local_fica_em_portugues_de_proposito():
    """A autodetecção dele vira a frase INTEIRA para o inglês por causa de uma palavra estrangeira,
    e errar a frase toda é pior que errar uma palavra."""
    assert IDIOMA_WHISPER == "pt" and IDIOMA_REALTIME == "pt"

def test_os_projetos_do_joao_vao_para_o_reconhecedor(vault):
    t = termos_do_vault(vault)
    assert "GearHead-Brasil" in t and "BUB" in t and "Estamparia" in t
    assert "INDEX" not in t                                   # índice não é projeto

def test_as_pessoas_do_vault_tambem(vault):
    t = termos_do_vault(vault)
    assert "Rafael Souza" in t and "Mariana" in t

def test_o_que_sempre_entra_mesmo_sem_vault():
    t = termos_do_vault(None)
    for esperado in ("Jaime", "Maestri", "worktree", "escrow", "Gabriel Mello"):
        assert esperado in t, esperado

def test_nao_repete_nome_nem_estoura_o_limite(vault):
    t = termos_do_vault(vault)
    assert len(t) == len({x.lower() for x in t}) and len(t) <= MAX_KEYTERMS

def test_a_query_escapa_espaco_e_acento(vault):
    q = query_deepgram(vault)
    assert "Jo%C3%A3o%20Vitor%20Leal" in q and " " not in q

def test_vault_quebrado_nao_derruba_o_reconhecimento():
    class _Ruim:
        root = Path("/nao/existe")
        def read(self, r): raise RuntimeError("sem vault")
    t = termos_do_vault(_Ruim())
    assert set(BASE) <= set(t)                                # cai para a base e segue funcionando


# ── falar nome em inglês ──────────────────────────────────────────────────
def test_a_voz_nao_proibe_mais_pronuncia_estrangeira():
    """Eu tinha escrito «nenhuma sílaba em inglês» para consertar o sotaque, e de quebra proibi o Jaime
    de pronunciar o nome dos projetos do próprio João."""
    from jaime.voice.tts import ESTILO_JARVIS
    assert "nenhuma sílaba em inglês" not in ESTILO_JARVIS
    assert "língua de origem" in ESTILO_JARVIS or "pronúncia da língua" in ESTILO_JARVIS

def test_a_voz_continua_exigindo_portugues_nativo_na_base():
    """Liberar o inglês não pode trazer o sotaque estrangeiro de volta — foi a reclamação anterior dele."""
    from jaime.voice.tts import ESTILO_JARVIS
    assert "NATIVO de português do Brasil" in ESTILO_JARVIS
    assert "nenhum sotaque estrangeiro no português" in ESTILO_JARVIS

def test_a_voz_continua_rapida():
    from jaime.voice.tts import ESTILO_JARVIS
    assert "FALE RÁPIDO" in ESTILO_JARVIS
