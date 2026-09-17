"""O crítico da spec: a única trava do ciclo, e é de qualidade.
O que não pode cair: critério de opinião não passa, spec sem teste não passa, e o parecer diz ONDE
está o buraco — crítica sem endereço é ruído."""
import pytest
from jaime.agente.spec import criticar, esqueleto, pedido_de_critica, SECOES

BOA = """# Painel de música

## Problema
O painel de música do cockpit abre vazio quando o Spotify está conectado, e o João não vê o que está tocando.

## Entrada
- o JSON de /hud/musica, com os campos tocando, top_artistas e conectado

## Saída
- o pop-up do cockpit com o que está tocando e os artistas mais ouvidos

## Erros
- Spotify desconectado: mostra "Spotify não conectado" em vez de painel vazio
- rota fora do ar: mostra o erro no lugar do conteúdo

## Critérios de aceite
- o teste test_painel_musica passa
- a rota /hud/musica responde 200 em menos de 300 ms
- com o Spotify desligado, o texto "não conectado" existe na tela
"""


def test_spec_completa_passa():
    p = criticar(BOA)
    assert p.passou, p.texto()
    assert "PRONTO" in p.texto()

@pytest.mark.parametrize("secao", SECOES)
def test_falta_de_secao_e_apontada_com_endereco(secao):
    from jaime.agente.spec import CABECALHOS
    linhas = [l for l in BOA.splitlines() if not CABECALHOS[secao].match(l)]
    p = criticar("\n".join(linhas))
    assert not p.passou
    assert any(f.onde == secao and "não existe" in f.o_que for f in p.falhas), p.texto()

def test_criterio_de_opiniao_nao_passa():
    """'Ficou bom' nunca fecha: ninguém consegue discordar nem concordar."""
    ruim = BOA.replace("- o teste test_painel_musica passa", "- o painel fica bonito e intuitivo")
    p = criticar(ruim)
    assert not p.passou
    assert any("é opinião" in f.o_que for f in p.falhas), p.texto()
    assert any("se confere" in f.como_arrumar for f in p.falhas)

def test_spec_sem_nenhum_teste_no_aceite_nao_passa():
    sem = BOA.replace("- o teste test_painel_musica passa\n", "")
    p = criticar(sem)
    assert any("nenhum critério é um teste" in f.o_que for f in p.falhas), p.texto()

def test_criterio_que_nao_diz_como_conferir_e_apontado():
    vago = BOA.replace("- a rota /hud/musica responde 200 em menos de 300 ms",
                       "- o usuário consegue usar sem dificuldade")
    p = criticar(vago)
    assert any("não diz como conferir" in f.o_que or "é opinião" in f.o_que for f in p.falhas), p.texto()

@pytest.mark.parametrize("palavra", ["etc", "talvez", "idealmente", "se possível", "deveria"])
def test_palavra_que_deixa_o_escopo_aberto_e_pega(palavra):
    p = criticar(BOA.replace("## Erros", f"## Erros\n- {palavra} outros casos"))
    assert any("escopo aberto" in f.o_que for f in p.falhas), p.texto()

def test_secao_com_titulo_e_sem_conteudo_engana_e_e_pega():
    p = criticar(BOA.replace("- o JSON de /hud/musica, com os campos tocando, top_artistas e conectado", ""))
    assert any(f.onde == "entrada" and "vazia" in f.o_que for f in p.falhas), p.texto()

def test_entrada_sem_saida_e_pega():
    sem = BOA.replace("- o pop-up do cockpit com o que está tocando e os artistas mais ouvidos", "")
    p = criticar(sem)
    assert any("não tem saída" in f.o_que or ("saída" == f.onde and "vazia" in f.o_que) for f in p.falhas)

def test_spec_curta_demais_nao_passa():
    p = criticar("# Coisa\n## Problema\nx\n## Entrada\n- a\n## Saída\n- b\n## Erros\n- c\n## Critérios de aceite\n- o teste passa\n")
    assert any("curta demais" in f.o_que for f in p.falhas), p.texto()

def test_spec_vazia_aponta_tudo_sem_quebrar():
    p = criticar("")
    assert not p.passou and len(p.falhas) >= len(SECOES)

def test_o_parecer_sempre_diz_onde_e_como_arrumar():
    for f in criticar("").falhas:
        assert f.onde and f.o_que and f.como_arrumar        # crítica sem endereço é ruído

def test_o_esqueleto_ja_vem_com_as_secoes_certas():
    e = esqueleto("Painel novo", "o painel abre vazio")
    from jaime.agente.spec import CABECALHOS
    for secao in SECOES:
        assert CABECALHOS[secao].search(e), secao
    assert "Painel novo" in e and "o painel abre vazio" in e

def test_o_pedido_ao_critico_pede_so_o_que_a_maquina_nao_pega():
    t = pedido_de_critica(BOA)
    assert "ambíguo" in t and "suposição escondida" in t and "escopo" in t
    assert BOA[:40] in t
