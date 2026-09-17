"""O acervo: alcançar qualquer especialista sem carregar todos a cada turno.
O que não pode cair: busca em PORTUGUÊS acha o acervo em inglês, nada some, e o resumo diz quantos
ele realmente carrega — não quantos arquivos existem."""
import os
from pathlib import Path
import pytest
from jaime.acervo.busca import Acervo, _expandir, _palavras


@pytest.fixture
def repo(tmp_path):
    ag = tmp_path / ".claude/agents"; ac = tmp_path / ".claude/acervo/agents"; sk = tmp_path / ".claude/skills"
    for d in (ag, ac, sk): d.mkdir(parents=True)
    def agente(pasta, nome, desc):
        (pasta / f"{nome}.md").write_text(f'---\nname: {nome}\ndescription: "{desc}"\n---\n\nCorpo do {nome}.\n')
    agente(ag, "maester-dev", "Código, repositórios, deploy.")
    agente(ag, "kubernetes-specialist", "Design, deploy and troubleshoot Kubernetes clusters in production.")
    agente(ac, "gdpr-ccpa-compliance", "Understand GDPR and CCPA privacy compliance and data subject rights.")
    agente(ac, "postgres-pro", "Optimize PostgreSQL performance, replication and slow queries.")
    (ag / "README.md").write_text("não sou agente")
    d = sk / "animate"; d.mkdir()
    (d / "SKILL.md").write_text('---\nname: animate\ndescription: "Build a web animation with the right easing and motion."\n---\n\nCorpo.\n')
    return tmp_path


def test_indexa_carregados_acervo_e_skills_sem_contar_o_readme(repo):
    a = Acervo(repo)
    nomes = {i.nome for i in a.itens}
    assert nomes == {"maester-dev", "kubernetes-specialist", "gdpr-ccpa-compliance", "postgres-pro", "animate"}
    assert "README" not in nomes
    por = {i.nome: i for i in a.itens}
    assert por["kubernetes-specialist"].carregado and not por["gdpr-ccpa-compliance"].carregado
    assert por["animate"].tipo == "skill"

@pytest.mark.parametrize("termo,esperado", [
    ("kubernetes", "kubernetes-specialist"),
    ("lgpd privacidade", "gdpr-ccpa-compliance"),        # português achando descrição em inglês
    ("banco de dados lento", "postgres-pro"),
    ("animação", "animate"),
    ("código deploy", "maester-dev"),
])
def test_busca_em_portugues_acha_o_acervo_em_ingles(repo, termo, esperado):
    r = Acervo(repo).buscar(termo, 3)
    assert r and r[0][0].nome == esperado, [i.nome for i, _ in r]

def test_o_que_esta_guardado_continua_alcancavel(repo):
    a = Acervo(repo)
    achados = {i.nome for i, _ in a.buscar("privacy compliance", 5)}
    assert "gdpr-ccpa-compliance" in achados                 # está fora do contexto, mas não sumiu

def test_consultar_traz_o_texto_inteiro_para_usar_agora(repo):
    a = Acervo(repo)
    assert "Corpo do postgres-pro" in a.consultar("postgres-pro")
    assert "Corpo do postgres-pro" in a.consultar("POSTGRES-PRO")     # sem ligar para maiúscula

def test_consultar_o_que_nao_existe_sugere_em_vez_de_mentir(repo):
    t = Acervo(repo).consultar("kubernets")                  # com erro de digitação
    assert "não tenho" in t and "kubernetes-specialist" in t

def test_busca_vazia_nao_quebra(repo):
    assert Acervo(repo).buscar("") == [] and Acervo(repo).buscar("   ") == []

def test_o_resumo_conta_quantos_ele_carrega_e_nao_quantos_arquivos_existem(repo, monkeypatch):
    a = Acervo(repo)
    monkeypatch.setenv("JAIME_AGENTES_MAX", "2")
    r = a.resumo()
    assert "4 agentes no total" in r and "2 carregados" in r and "2 alcançáveis por busca" in r
    monkeypatch.setenv("JAIME_AGENTES_MAX", "0")
    assert "4 carregados" in a.resumo()                      # 0 = carrega tudo

def test_sinonimo_junta_portugues_e_ingles_sem_perder_o_original():
    e = _expandir(_palavras("animação bonita"))
    assert "animação" in e and "animation" in e and "design" in e

def test_teto_de_agentes_mantem_os_maesters_e_corta_o_resto(repo, monkeypatch):
    from jaime.orchestrator.maesters import carregar_maesters
    monkeypatch.setenv("JAIME_AGENTES_MAX", "1")
    m = carregar_maesters(repo)
    assert list(m) == ["maester-dev"]                        # a casa entra primeiro, sempre
