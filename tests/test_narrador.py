from jaime.voice.narrador import Narrador, frase_para

def test_frases():
    assert frase_para("Bash", "pytest -q") == "rodando os testes"
    assert frase_para("Bash", "ffmpeg -i x") == "rodando um comando"
    assert frase_para("Read") == "lendo os arquivos" and frase_para("mcp__google__email_hoje") == "olhando os e-mails"
    assert frase_para("mcp__desconhecida__x") == ""

def test_narra_so_em_tarefas_longas_e_sem_repetir():
    t = [0.0]; ditas = []
    n = Narrador(ditas.append, primeira_s=5, a_cada_s=8, relogio=lambda: t[0])
    n.comecar()
    t[0] = 2; assert n.evento("Read") is None                    # cedo demais
    t[0] = 6; assert n.evento("Read") == "Lendo os arquivos…"
    t[0] = 9; assert n.evento("Bash", "pytest -q") is None        # intervalo
    t[0] = 15; assert n.evento("Read") is None                    # igual à anterior
    t[0] = 16; assert n.evento("Bash", "pytest -q") == "Rodando os testes."
    n.parar(); t[0] = 40; assert n.evento("Write") is None
    assert ditas == ["Lendo os arquivos…", "Rodando os testes."]
