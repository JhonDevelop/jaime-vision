"""Heurística do observador: quando o João parece travado, e como ele responde à oferta de ajuda.
Nada aqui chama osascript nem tira captura de tela."""
from jaime.ops.observador import parece_travado, eh_aceite, eh_recusa, Observador

def _hist(seq, passo=4):
    """seq: lista de (app, janela) amostrada a cada `passo` segundos, terminando em t=0."""
    n = len(seq); return [(-(n - i) * passo, a, j) for i, (a, j) in enumerate(seq)]

def test_trabalho_focado_nao_e_travado():
    h = _hist([("Code", "jaime.py")] * 40)
    assert parece_travado(h, 0) is None

def test_pular_entre_janelas_sem_parar_e_travado():
    apps = [("Safari", "Google"), ("Finder", "Downloads"), ("Mail", "Inbox"), ("Slack", "geral")]
    h = _hist([apps[i % 4] for i in range(40)])     # troca a cada 4 s por 160 s
    motivo = parece_travado(h, 0)
    assert motivo and "pulando entre" in motivo and "Safari" in motivo

def test_preso_numa_busca_e_travado():
    h = _hist([("Finder", "Pesquisando “nota fiscal”")] * 25)   # 100 s na mesma busca
    motivo = parece_travado(h, 0)
    assert motivo and "procurando" in motivo

def test_aceite_e_recusa():
    assert eh_aceite("Sim.") and eh_aceite("pode sim") and eh_aceite("quero")
    assert eh_recusa("deixa") and eh_recusa("Agora não")
    assert not eh_aceite("abre o Finder") and not eh_recusa("abre o Finder")

class _Jaime:
    class acesso: liberado = True
    class vault:
        @staticmethod
        def diario(*a, **k): pass

def test_responder_oferta_sem_oferta_pendente_e_none():
    o = Observador(_Jaime())
    assert o.responder_oferta("sim") is None

def test_responder_oferta_recusa_limpa_a_oferta(monkeypatch):
    import time
    o = Observador(_Jaime()); o.oferta_pendente = "pulando entre A, B"; o.oferta_em = time.time()
    assert o.responder_oferta("deixa") == "" and o.oferta_pendente == ""

def test_responder_oferta_aceite_gera_prompt(monkeypatch):
    import time, jaime.ops.observador as m
    monkeypatch.setattr(m, "capturar_tela", lambda *a, **k: "/tmp/x.png")
    o = Observador(_Jaime()); o.oferta_pendente = "há 2 min procurando em Finder"; o.oferta_em = time.time()
    p = o.responder_oferta("sim")
    assert p and "/tmp/x.png" in p and "procurando em Finder" in p and o.oferta_pendente == ""
