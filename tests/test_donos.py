"""Segundo dono: o portão do Gabriel e o roteiro da cópia dele.
O que NÃO pode cair: a palavra-passe aqui prova autorização e NÃO abre o cérebro do João."""
import pytest
from jaime.donos import (eh_o_socio_se_apresentando, Porteiro, roteiro_texto, ROTEIRO, SOCIO, MAX_TENTATIVAS)
from jaime.vigia.acesso import Acesso, hash_senha


@pytest.fixture
def acesso():
    return Acesso(hash_senha("12341234"), timeout_min=30)


@pytest.mark.parametrize("frase", [
    "Oi JAIME sou o Gabriel Mello", "oi jaime, sou o gabriel mello", "olá Jaime, eu sou o Gabriel",
    "sou o Gabriel Mello", "e aí Jaime, sou o Gabriel", "Jaime, sou Gabriel Mello.",
])
def test_reconhece_o_socio_se_apresentando(frase):
    assert eh_o_socio_se_apresentando(frase)

@pytest.mark.parametrize("frase", [
    "o Gabriel ligou", "manda uma mensagem pro Gabriel", "sou o João", "quem é o Gabriel?", "",
])
def test_nao_confunde_falar_sobre_o_gabriel_com_ele_se_apresentando(frase):
    assert not eh_o_socio_se_apresentando(frase)


def test_o_caminho_inteiro_ate_o_roteiro(acesso):
    p = Porteiro()
    assert SOCIO in p.apresentou() and p.etapa == "confirmando"
    assert "palavra-passe" in p.responder("sim, sou eu", acesso) and p.etapa == "senha"
    assert p.responder("12341234", acesso) is None and p.aberto        # None = pode entregar o roteiro
    assert not acesso.liberado                                          # E O CÉREBRO DO JOÃO SEGUE TRANCADO

def test_a_senha_prova_autorizacao_mas_nunca_libera_o_cerebro_do_joao(acesso):
    p = Porteiro(); p.apresentou(); p.responder("sim", acesso)
    p.responder("um dois três quatro um dois três quatro", acesso)      # falada por extenso também vale
    assert p.aberto and not acesso.liberado

def test_senha_errada_tres_vezes_barra_e_avisa_o_joao(acesso):
    p = Porteiro(); p.apresentou(); p.responder("sim", acesso)
    assert "1 de 3" in p.responder("0000", acesso)
    assert "2 de 3" in p.responder("1111", acesso)
    r = p.responder("2222", acesso)
    assert p.barrado and "avisar o João" in r
    assert not acesso.liberado

def test_quem_diz_que_nao_e_o_socio_sai_sem_atrito(acesso):
    p = Porteiro(); p.apresentou()
    assert "só com o João" in p.responder("não, não sou", acesso) and p.etapa == "fechado"

def test_resposta_ambigua_pede_sim_ou_nao(acesso):
    p = Porteiro(); p.apresentou()
    assert "sim ou não" in p.responder("talvez, depende", acesso) and p.etapa == "confirmando"

def test_nao_da_para_pular_a_confirmacao_e_ir_direto_na_senha(acesso):
    p = Porteiro()
    assert p.responder("12341234", acesso) is None and not p.aberto     # portão fechado ignora
    assert not acesso.liberado


def test_o_roteiro_cobre_o_que_o_joao_pediu():
    t = roteiro_texto().lower()
    for assunto in ("maestri", "codex", "antigravity", "gemini", "acessibilidade", "gravação de tela",
                    "worktree", "vault", "nome", "commit"):
        assert assunto in t, assunto
    assert len(ROTEIRO) >= 8

def test_o_roteiro_diz_que_memoria_de_dono_nao_se_mistura():
    t = roteiro_texto().lower()
    assert "não se mistura" in t or "nada se mistura" in t
    assert "na sua máquina, não na do joão" in t
    assert "só o código de aprendizado" in t                            # e só ele volta para o principal


# ── a trava de verdade: com visita na linha, a vida do João não abre ──────
import asyncio
from jaime.vigia.hooks import Vigia, eh_privado_do_joao


@pytest.mark.parametrize("nome,args", [
    ("mcp__financas__saldo", {}),
    ("mcp__emocao__momento_de_hoje", {}),
    ("mcp__espelho__tracos_do_joao", {}),
    ("mcp__mente__pensamentos", {}),
    ("mcp__cerebro__lembrar", {"o_que": "x"}),
    ("mcp__musica__tocar", {"o_que": "x"}),
    ("mcp__google__email_listar", {}),
    ("Read", {"file_path": "/r/vault/40-Diario/2026-09-17.md"}),
    ("Read", {"file_path": "/r/vault/70-Financas/livro.md"}),
    ("Grep", {"pattern": "x", "path": "/r/vault/60-Conversas"}),
    ("Bash", {"command": "cat vault/10-Eu/Joao.md"}),
])
def test_o_que_e_da_vida_do_joao_e_privado(nome, args):
    assert eh_privado_do_joao(nome, args)

@pytest.mark.parametrize("nome,args", [
    ("mcp__mundo__clima", {}), ("mcp__interface__mostrar", {"titulo": "x", "html": "<p>"}),
    ("Read", {"file_path": "/r/jaime/server.py"}), ("Bash", {"command": "pytest -q"}),
    ("mcp__web__ler_web", {"url": "https://x.com"}),
])
def test_o_trabalho_em_comum_continua_livre(nome, args):
    assert not eh_privado_do_joao(nome, args)

def _hook(v, nome, args):
    return asyncio.run(v.pre_tool_use({"tool_name": nome, "tool_input": args}, None, None))

def test_visita_na_linha_faz_a_ferramenta_recusar_e_nao_so_o_modelo_se_comportar():
    v = Vigia()
    assert _hook(v, "mcp__financas__saldo", {}) == {}            # o João: passa
    v.convidado = "Gabriel"
    r = _hook(v, "mcp__financas__saldo", {})
    assert r["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "do João" in r["hookSpecificOutput"]["permissionDecisionReason"]
    assert _hook(v, "mcp__mundo__clima", {}) == {}               # o que é de vocês dois segue livre
    v.convidado = ""
    assert _hook(v, "mcp__financas__saldo", {}) == {}            # o João de volta: passa de novo
