"""Juiz e provedores com dublês — nada aqui chama a OpenAI nem o CLI do Claude."""
import asyncio, json
from pathlib import Path
from jaime.cortex.juiz import Juiz, pede_juiz
from jaime.cortex.provedores.base import Resposta
from jaime.cortex.provedores.openai import ProvedorOpenAI
from jaime.cortex.roteador import Roteador
from jaime.cortex.placar import Placar

class Falso:
    def __init__(self, nome, modelo, texto="", erro="", custo=0.01):
        self.nome, self.modelo, self.texto, self.erro, self.custo = nome, modelo, texto, erro, custo
        self.chamadas = []
    async def responder(self, prompt, contexto="", ferramentas=None):
        self.chamadas.append(prompt)
        return Resposta(self.texto, self.nome, self.modelo, 0.5, self.custo, erro=self.erro)

def test_pede_juiz():
    assert pede_juiz("qualquer coisa", "decisão") and pede_juiz("pensa bem: devo assinar?") and pede_juiz("compara os dois")
    assert not pede_juiz("abre o Finder", "rotina")

def test_juiz_escolhe_B_e_registra_justificativa():
    a = Falso("anthropic", "claude", "Assine o Starter.")
    b = Falso("openai", "gpt", "Não assine ainda; teste a voz premade uma semana.")
    arbitro = Falso("anthropic", "fable", json.dumps({"escolha": "B", "justificativa": "B pondera custo antes de gastar.", "resposta": "Espere uma semana com a voz premade."}))
    v = asyncio.run(Juiz(a, b, arbitro).julgar("devo assinar o Starter?"))
    assert v.escolha == "B" and v.texto == "Espere uma semana com a voz premada.".replace("premada", "premade")
    assert "pondera" in v.justificativa and abs(v.custo - 0.03) < 1e-9
    assert "<A provedor=\"anthropic\"" in arbitro.chamadas[0] and "<B provedor=\"openai\"" in arbitro.chamadas[0]

def test_juiz_sem_um_provedor_devolve_o_outro_sem_arbitrar():
    a = Falso("anthropic", "claude", "Resposta A.")
    b = Falso("openai", "gpt", erro="RateLimitError: sem créditos")
    arbitro = Falso("anthropic", "fable", "não deveria ser chamado")
    v = asyncio.run(Juiz(a, b, arbitro).julgar("e aí?"))
    assert v.escolha == "unica" and v.texto == "Resposta A." and "sem créditos" in v.justificativa
    assert arbitro.chamadas == []

def test_juiz_com_arbitro_quebrado_fica_com_A():
    a = Falso("anthropic", "claude", "A."); b = Falso("openai", "gpt", "B.")
    arbitro = Falso("anthropic", "fable", "isso não é json")
    v = asyncio.run(Juiz(a, b, arbitro).julgar("?"))
    assert v.escolha == "A" and v.texto == "A." and "árbitro" in v.justificativa

def test_provedor_openai_sem_chave_nao_quebra():
    p = ProvedorOpenAI("", "gpt-5.5")
    r = asyncio.run(p.responder("oi"))
    assert not p.disponivel and not r.ok and "OPENAI_API_KEY" in r.erro

def test_roteador_considera_openai_para_pesquisa_e_redacao(tmp_path: Path):
    (tmp_path / "01-Estado").mkdir()
    m = {"decisao": "fable", "codigo": "opus", "padrao": "sonnet", "rotina": "haiku"}
    r = Roteador(m, Placar(tmp_path), exploracao=0.0, openai="gpt-5.5")
    assert "openai:gpt-5.5" in r.candidatos("pesquisa") and "openai:gpt-5.5" in r.candidatos("redação")
    assert "openai:gpt-5.5" not in r.candidatos("código")     # ações no mundo: só Anthropic
    # placar favorável à OpenAI em pesquisa → ela é escolhida
    p = r.placar
    for _ in range(3): p.registrar("sonnet", "pesquisa", "erro")
    for _ in range(3): p.registrar("openai:gpt-5.5", "pesquisa", "acerto")
    assert r.escolher("pesquisa")[0] == "openai:gpt-5.5"
    assert Roteador(m, Placar(tmp_path), openai="").candidatos("pesquisa") == ["sonnet", "opus"]
