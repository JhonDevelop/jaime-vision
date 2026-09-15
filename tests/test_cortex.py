"""Córtex: classificação da tarefa, política de escolha com placar sintético, correção do João."""
import random
from pathlib import Path
from jaime.cortex.roteador import Roteador, classificar, eh_correcao
from jaime.cortex.placar import Placar

MODELOS = {"decisao": "fable", "codigo": "opus", "padrao": "sonnet", "rotina": "haiku"}

def _placar(tmp_path: Path) -> Placar:
    (tmp_path / "01-Estado").mkdir(parents=True)
    return Placar(tmp_path)

def test_classifica_por_pistas():
    assert classificar("corrige o bug no deploy do BUB")[0] == "código"
    assert classificar("pesquisa quem é o dono da Evolution API")[0] == "pesquisa"
    assert classificar("escreve um e-mail para o fornecedor")[0] == "redação"
    assert classificar("devo assinar o Starter da ElevenLabs? pensa bem")[0] == "decisão"
    assert classificar("gera uma imagem de logo para a estamparia")[0] == "imagem"
    assert classificar("que horas são?")[0] == "rotina"
    tipo, conf = classificar("e aí, tudo bem?", canal="voice")
    assert tipo == "voz" and conf == 0.5

def test_escolha_padrao_sem_placar(tmp_path):
    r = Roteador(MODELOS, _placar(tmp_path), exploracao=0.0)
    assert r.escolher("código")[0] == "opus"
    assert r.escolher("decisão")[0] == "fable"
    assert r.escolher("rotina")[0] == "haiku"
    assert "placar ainda vazio" in r.escolher("redação")[1]

def test_placar_muda_a_escolha(tmp_path):
    p = _placar(tmp_path)
    for _ in range(4): p.registrar("opus", "código", "erro", 5.0)
    for _ in range(3): p.registrar("sonnet", "código", "acerto", 2.0)
    r = Roteador(MODELOS, p, exploracao=0.0)
    modelo, motivo, expl = r.escolher("código")
    assert modelo == "sonnet" and "80%" in motivo and not expl
    assert (tmp_path / "01-Estado/Placar.md").read_text().count("| sonnet | código |") == 1

def test_exploracao_testa_o_outro(tmp_path):
    r = Roteador(MODELOS, _placar(tmp_path), exploracao=1.0, rng=random.Random(1))
    escolhas = {r.escolher("código")[0] for _ in range(20)}
    assert escolhas == {"opus", "sonnet"}

def test_correcao_do_joao_vira_erro_do_turno_anterior(tmp_path):
    p = _placar(tmp_path)
    p.registrar("opus", "código", "acerto", 3.0)
    assert eh_correcao("não era isso, refaz") and not eh_correcao("perfeito, obrigado")
    u = p.corrigir_ultimo("o João disse 'refaz'")
    assert u["modelo"] == "opus" and p.dados["placar"]["opus|código"] == {"acertos": 0, "erros": 1, "latencia": 3.0, "custo": 0.0, "n": 1}
    assert p.corrigir_ultimo() is None            # não corrige duas vezes
    assert "refaz" in (tmp_path / "01-Estado/Placar.md").read_text()

def test_explicar(tmp_path):
    r = Roteador(MODELOS, _placar(tmp_path), exploracao=0.0)
    out = r.explicar("implementa o endpoint de login")
    assert "tipo:      código" in out and "modelo:    opus" in out and "sem histórico" in out
