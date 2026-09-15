"""Persona de voz: nada de auto-apresentação, muletas ou fechos de atendente; prosódia muda o texto de estilo."""
from jaime.voice.persona import aplicar
from jaime.emocao.humor import Humor
from jaime.emocao.prosodia import prosodia

def test_tira_apresentacao_muletas_e_fecho():
    t = aplicar("Olá, João! Sou o Jaime, seu assistente. Claro! O build terminou sem erros. Como posso ajudar hoje?")
    assert t == "O build terminou sem erros."
    assert aplicar("Ótima pergunta! São 14 e 05.") == "São 14 e 05."
    assert aplicar("Sim, senhor. Já fiz.") == "Sim, senhor. Já fiz."
    assert aplicar("Bom dia, João. Hoje é seu aniversário.", primeira_do_dia=True).startswith("Bom dia, João.")
    assert aplicar("bom dia, João. Hoje é seu aniversário.") == "Hoje é seu aniversário."

def test_prosodia_gera_instrucoes_diferentes_para_grave_e_leve():
    g, l = Humor(), Humor()
    g.registrar_tom("em_problema"); l.registrar_tom("animado"); l.registrar_tom("animado")
    ig, il = prosodia(g)["instructions"], prosodia(l)["instructions"]
    assert "sério" in ig and "animado" in il and ig != il
