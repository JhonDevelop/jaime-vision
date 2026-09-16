"""Telemetria local (fase 3, §4): janela ativa com relógio falso, exclusão, pedidos por tipo, temas, Uso.md e prioridades."""
import json
from datetime import datetime
from pathlib import Path
import pytest
from jaime.brain.vault import Vault
from jaime.cortex.placar import Placar
from jaime.estudo.problemas import Problemas, ler_prioridades, ARQUIVO_PRIORIDADES
from jaime.telemetria import prioridades as prio
from jaime.telemetria.uso import Telemetria, agrupar_temas, palavras_chave, tokens, config_env, USO_REL, ARQUIVO_REL

T0 = datetime(2026, 9, 15, 14, 0).timestamp()      # terça, 14:00 (hora local)

@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    for d in ("00-Jaime", "01-Estado", "10-Eu", "20-Projetos", "30-Tarefas", "40-Diario", "50-Conhecimento", "60-Conversas", "90-Estudo"):
        (tmp_path / d).mkdir()
    return Vault(tmp_path)

class Relogio:
    def __init__(self, t=T0): self.t = t
    def __call__(self): return self.t
    def avancar(self, s): self.t += s

def test_amostra_agrega_por_hora_e_respeita_exclusao(vault):
    rel = Relogio()
    tel = Telemetria(vault, ligada=True, excluir=("1Password", "banco"), agora=rel)
    for _ in range(10):                                  # 5 min no VS Code
        tel.amostrar("Code", "bub — main.dart"); rel.avancar(30)
    for _ in range(4):                                   # 2 min no Safari
        tel.amostrar("Safari", "Supabase RLS docs"); rel.avancar(30)
    assert tel.amostrar("1Password 8", "cofre") is False          # excluído: nem conta, nem título
    assert tel.amostrar("Banco Inter", "") is False
    assert tel.amostrar("", "") is False
    rel.avancar(3600)                                    # próxima hora
    tel.amostrar("Code", "bub — main.dart")
    assert tel.uso_apps(agora=rel.t) == [("Code", 330), ("Safari", 120)]
    assert set(tel.dados["horas"]) == {"2026-09-15T14", "2026-09-15T15"}
    assert "1Password 8" not in tel.dados["titulos"]
    assert tel.titulos("Code")[0] == ("bub — main.dart", 330)
    assert tel.uso_por_hora(agora=rel.t) == {14: 420, 15: 30}
    tel.salvar()
    bruto = json.loads((vault.root / ARQUIVO_REL).read_text())
    assert bruto["horas"]["2026-09-15T14"]["Safari"] == 120
    # relê do disco
    tel2 = Telemetria(vault, ligada=True, excluir=(), agora=rel)
    assert tel2.uso_apps(agora=rel.t)[0] == ("Code", 330)

def test_desligada_nao_registra_nada(vault):
    tel = Telemetria(vault, ligada=False, excluir=(), agora=Relogio())
    assert tel.amostrar("Code", "x") is False
    tel.registrar_pedido("arruma o bug do deploy", "código", "voice")
    assert tel.dados == {"horas": {}, "titulos": {}, "pedidos": []}
    assert "Telemetria desligada" in tel.resumo_semanal()

def test_config_env(monkeypatch):
    monkeypatch.setenv("JAIME_TELEMETRIA", "0"); monkeypatch.setenv("JAIME_TELEMETRIA_EXCLUIR", "1Password, Nubank ,")
    assert config_env() == (False, ("1Password", "Nubank"))
    monkeypatch.delenv("JAIME_TELEMETRIA"); monkeypatch.delenv("JAIME_TELEMETRIA_EXCLUIR")
    assert config_env() == (True, ())

def test_pedidos_tipos_e_classificacao_pelo_evento_cortex(vault):
    rel = Relogio()
    tel = Telemetria(vault, ligada=True, excluir=(), agora=rel)
    tel.registrar_pedido("arruma o bug do deploy do BUB", "", "voice"); tel.classificar_ultimo("código")
    tel.registrar_pedido("•••", "", "hud")                                  # trancado: não registra
    tel.registrar_pedido("escreve um e-mail pro Rafael", "", "hud"); tel.classificar_ultimo("redação")
    tel.registrar_pedido("qual o clima hoje", "rotina", "voice"); tel.classificar_ultimo("código")   # já tinha tipo: não sobrescreve
    assert [p["tipo"] for p in tel.pedidos()] == ["código", "redação", "rotina"]
    assert tel.tipos().most_common(1)[0][1] == 1
    rel.avancar(8 * 86400)                                                # 8 dias depois: fora da janela semanal
    assert tel.pedidos(agora=rel.t) == []

def test_palavras_chave_e_temas_por_agrupamento_simples():
    assert tokens("Jaime, arruma os erros das funções do deploy") == ["arruma", "erro", "função", "deploy"]
    textos = ["arruma o erro de RLS do Supabase no BUB", "por que a policy RLS do Supabase bloqueia o insert?",
              "o RLS do Supabase tá negando o select", "escreve a legenda do post da Oldsen",
              "faz a legenda do post de amanhã da Oldsen", "que horas são"]
    kws = palavras_chave(textos)
    assert "rls" in kws[0] and "supabase" in kws[0]
    temas = agrupar_temas(textos, embeddings=False)
    assert temas[0].n == 3 and {"rls", "supabase"} <= set(temas[0].palavras)
    assert temas[1].n == 2 and "legenda" in temas[1].palavras and "oldsen" in temas[1].palavras
    assert sum(t.n for t in temas) == 6
    assert agrupar_temas([], embeddings=False) == []

def test_uso_md_tem_as_quatro_perguntas(vault):
    rel = Relogio()
    placar = Placar(vault.root)
    tel = Telemetria(vault, ligada=True, excluir=(), placar=placar, agora=rel)
    for _ in range(20): tel.amostrar("Code", "bub — rls.sql"); rel.avancar(30)
    for _ in range(5): tel.amostrar("Safari", "Supabase — Row Level Security"); rel.avancar(30)
    for txt, tipo in [("arruma a policy RLS do Supabase", "código"), ("por que o RLS bloqueia o insert", "código"),
                      ("escreve o post da Oldsen", "redação")]:
        tel.registrar_pedido(txt, tipo, "voice")
    placar.registrar("claude-opus-5", "código", "erro", 3.0, 0.02, "RLS negou o insert")
    placar.registrar("claude-opus-5", "código", "acerto", 2.0, 0.01, "ok")
    placar.registrar("claude-sonnet-5", "redação", "acerto", 1.0, 0.01, "ok")
    placar.registrar("estudo", "pesquisa", "erro", 0, 0.05, "loop de estudo não conta como erro meu")
    rel_md = tel.escrever_uso()
    md = (vault.root / rel_md).read_text()
    assert rel_md == USO_REL
    for secao in ("## O que o João mais usa", "## O que mais pede", "## O que mais pergunta", "## Onde eu mais erro"):
        assert secao in md
    assert "| Code | 10 min | 80% |" in md and "Supabase — Row Level Security" in md
    assert "| código | 2 | 67% |" in md
    assert "rls" in md.lower() and "supabase" in md.lower()
    assert "| código | 2 | 1 | 50% |" in md and "loop de estudo" not in md
    assert "nunca vai ao Notion" in md
    assert tel.erros() == {"código": {"n": 2, "erros": 1, "taxa": 0.5, "notas": ["RLS negou o insert"]},
                           "redação": {"n": 1, "erros": 0, "taxa": 0.0, "notas": []}}

# ── prioridades ──────────────────────────────────────────────────────────────
def test_prioridade_formula_frequencia_x_erro_x_tempo(vault):
    agora = datetime(2026, 9, 15, 18, 0)
    pr = Problemas(vault)
    pr.abrir("RLS do Supabase nega insert no BUB", "policy de insert", "ferramenta_falhou")          # P-0001
    pr.abrir("Whisper lento no Intel", "3,6 s por frase", "joao_pediu")                             # P-0002
    # os problemas abrem com date.today(); o teste raciocina em 15/09 → fixa a data de abertura (quebrava a partir de 16/09)
    from datetime import date as _date
    rel = "90-Estudo/Problemas.md"; vault.write(rel, vault.read(rel).replace(_date.today().isoformat(), "2026-09-15"))
    pedidos = [{"t": "2026-09-15T10:00:00", "tipo": "código", "texto": "arruma a policy RLS do Supabase"},
               {"t": "2026-09-15T11:00:00", "tipo": "código", "texto": "por que o RLS bloqueia o insert"},
               {"t": "2026-09-15T12:00:00", "tipo": "redação", "texto": "escreve o post"}]
    log = [{"t": "2026-09-15T10:01:00", "modelo": "claude-opus-5", "tipo": "código", "resultado": "erro"},
           {"t": "2026-09-15T11:01:00", "modelo": "claude-opus-5", "tipo": "código", "resultado": "acerto"},
           {"t": "2026-09-01T11:01:00", "modelo": "claude-opus-5", "tipo": "código", "resultado": "erro"},     # velho: fora
           {"t": "2026-09-15T12:01:00", "modelo": "estudo", "tipo": "pesquisa", "resultado": "erro"}]          # estudo: fora
    ps = prio.calcular(pr.abertos(), pedidos, log, agora)
    p1 = next(p for p in ps if p.id == "P-0001"); p2 = next(p for p in ps if p.id == "P-0002")
    assert p1.tipo == "código" and p1.relacionados == 2
    assert p1.frequencia == pytest.approx(1 + 2 + 0.2 * 2)      # 2 relacionados + 2 pedidos de código
    assert p1.taxa_erro == pytest.approx((1 + 1) / (2 + 2))     # Laplace sobre os 2 turnos de código da semana
    assert p1.dias_sem_estudar == 0 and p1.valor == pytest.approx(3.4 * 0.5 * 1, abs=0.01)
    assert p2.relacionados == 0 and p2.taxa_erro == 0.5          # tipo sem histórico → 0,5
    assert ps[0].id == "P-0001"
    # 10 dias sem estudar sobe a prioridade; tentativa de hoje zera o tempo
    ps10 = prio.calcular(pr.abertos(), pedidos, log, datetime(2026, 9, 25, 18, 0))
    assert next(p for p in ps10 if p.id == "P-0002").dias_sem_estudar == 10
    assert next(p for p in ps10 if p.id == "P-0002").valor == pytest.approx(1.0 * 0.5 * 11)
    pr.registrar_tentativa("P-0002", "troquei para base")
    hoje = datetime.now().replace(hour=18)
    assert next(p for p in prio.calcular(pr.abertos(), [], [], hoje) if p.id == "P-0002").dias_sem_estudar == 0
    assert prio.ultimo_estudo(pr.por_id("P-0002")) == hoje.date()

def test_recalcular_escreve_arquivo_e_proximo_escolhe_por_prioridade(vault):
    rel = Relogio(datetime(2026, 9, 15, 18, 0).timestamp())
    pr = Problemas(vault)
    pr.abrir("Whisper lento no Intel", "3,6 s por frase", "joao_pediu")                              # P-0001 (mais antigo, 0 tentativas)
    pr.abrir("RLS do Supabase nega insert no BUB", "policy de insert", "ferramenta_falhou")           # P-0002
    pr.registrar_tentativa("P-0002", "tentei policy permissiva")                                     # heurística antiga preferiria P-0001
    assert pr.proximo().id == "P-0001"                                                                # sem Prioridades.md: menos tentativas
    tel = Telemetria(vault, ligada=True, excluir=(), agora=rel)
    for txt in ("arruma a policy RLS do Supabase", "o insert do BUB tá sendo negado pelo RLS", "RLS de novo"):
        tel.registrar_pedido(txt, "código", "voice")
    ps = prio.recalcular(vault, tel, None, datetime(2026, 9, 15, 18, 0))
    md = vault.read(ARQUIVO_PRIORIDADES)
    assert ps[0].id == "P-0002" and "| P-0002 |" in md and "frequência × taxa de erro" in md
    assert ler_prioridades(md) == {p.id: p.valor for p in ps}
    assert pr.proximo().id == "P-0002"                                                                # agora escolhe pela prioridade
    # problema aberto depois do recálculo (fora do arquivo) fica atrás dos priorizados
    pr.abrir("Deploy do site da Oldsen falha", "", "manual")
    assert pr.proximo().id == "P-0002"
    # arquivo sem nenhum dos abertos → heurística antiga
    vault.write(ARQUIVO_PRIORIDADES, "# Prioridades de estudo\n\n| P-0099 | x | 9.00 | 1 | 1 | 1 | voz | 0 |\n")
    assert pr.proximo().id == "P-0001"

def test_prioridades_sem_problemas(vault):
    ps = prio.recalcular(vault, None, None, datetime(2026, 9, 15, 18, 0))
    assert ps == [] and "nenhum problema em aberto" in vault.read(ARQUIVO_PRIORIDADES)
    assert ler_prioridades(vault.read(ARQUIVO_PRIORIDADES)) == {}
