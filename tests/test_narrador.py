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


def test_nao_narra_a_contabilidade_interna():
    """Pedido do João em 17/09: «não quero que ele fique me avisando sobre: escrevendo no vault,
    não quero saber isso».

    É o terceiro pedido da mesma família (antes vieram «não quero que ele fique me falando gemini ou
    codex entregou» e «eu digo coisas básicas e ele fica ok um segundo»), então a regra que este teste
    tranca é a geral, não só a frase: ele narra o que o João PEDIU, e fica calado sobre o que precisa
    fazer para lembrar. O painel do cockpit continua mostrando tudo."""
    for ferramenta in ("mcp__cerebro__lembrar", "mcp__cerebro__registrar_diario",
                       "mcp__cerebro__criar_tarefa", "mcp__cerebro__atualizar_estado",
                       "mcp__cerebro__buscar_memoria", "mcp__cerebro__ler_nota",
                       "mcp__mente__pensar_agora", "mcp__emocao__humor_atual",
                       "mcp__espelho__sincronizar"):
        assert frase_para(ferramenta) == "", f"narrou contabilidade interna: {ferramenta}"


def test_o_que_o_joao_pediu_continua_sendo_narrado():
    """O outro lado da moeda: calar a contabilidade não pode calar o trabalho de verdade. Se este teste
    cair junto com o de cima, alguém silenciou demais."""
    assert frase_para("mcp__google__agenda_hoje") == "olhando a agenda"
    assert frase_para("mcp__maos__abrir") == "no browser"
    assert frase_para("Task") == "delegando a um maester"
    assert frase_para("Bash", "git status") == "mexendo no git"
