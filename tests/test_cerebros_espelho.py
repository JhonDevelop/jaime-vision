"""Os três cérebros (central Claude, esquerdo Codex, direito Gemini), o Espelho do João e a agenda de
dois trilhos. O que não pode cair: o roteamento aprende de verdade, o Espelho nunca guarda segredo,
e o que o Jaime decide fazer sozinho não entra na agenda do João."""
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import pytest
from jaime.cerebros import Cerebros, tipo_do_pedido, POR_ID
from jaime.espelho import Espelho
from jaime.agenda.semana import montar as montar_semana, rotina_no_dia


class _Vault:
    def __init__(self, raiz: Path):
        self.root = raiz
    def read(self, rel):
        p = self.root / rel
        return p.read_text(encoding="utf-8") if p.is_file() else ""
    def write(self, rel, txt):
        p = self.root / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(txt, encoding="utf-8")


# ── os três cérebros ──────────────────────────────────────────────────────
@pytest.mark.parametrize("pedido,tipo,lado", [
    ("implementa o cache de frases", "codigo", "esquerdo"),
    ("testa o barge-in de novo", "teste", "esquerdo"),
    ("roda a suíte inteira", "execucao", "esquerdo"),
    ("pesquisa alternativas de TTS", "pesquisa", "direito"),
    ("critica o meu plano da semana", "critica", "direito"),
    ("cria alguma coisa para o cockpit", "criacao", "direito"),
    ("o que você acha disso", "decisao", "central"),
    ("bom dia", "decisao", "central"),
])
def test_cada_trabalho_vai_para_o_lado_certo(tmp_path, pedido, tipo, lado):
    c = Cerebros(_Vault(tmp_path))
    assert tipo_do_pedido(pedido) == tipo
    assert c.escolher(pedido).id == lado

def test_o_roteamento_aprende_errar_custa_o_dobro_de_acertar(tmp_path):
    v = _Vault(tmp_path); c = Cerebros(v)
    assert c.peso("esquerdo", "codigo") == 1.0                       # é a casa dele
    c.registrar("esquerdo", "codigo", ok=False)
    assert c.peso("esquerdo", "codigo") == pytest.approx(0.84)       # errou: -0.16
    c.registrar("esquerdo", "codigo", ok=True)
    assert c.peso("esquerdo", "codigo") == pytest.approx(0.92)       # acertou: +0.08
    # errando seguido, o trabalho migra para o outro lado
    for _ in range(9):
        c.registrar("esquerdo", "pesquisa", ok=False)
    c.registrar("direito", "pesquisa", ok=True)
    assert c.escolher("pesquisa").id == "direito"
    # e nada disso se perde: está em Markdown, que o João pode corrigir na mão
    nota = v.read("01-Estado/Cerebros.md")
    assert "| esquerdo | codigo |" in nota and "Central · claude" in nota
    assert Cerebros(v).peso("esquerdo", "codigo") == pytest.approx(0.92)

def test_o_central_nao_delega_para_si_mesmo(tmp_path):
    c = Cerebros(_Vault(tmp_path))
    assert "sou eu" in c.acordar("central")
    assert "sozinho" in c.delegar("central", "qualquer coisa")
    assert "central" in c.vivos()                                    # o Central está sempre de pé: é o processo
    assert {d["id"] for d in c.estado()} == {"central", "esquerdo", "direito"}
    assert POR_ID["esquerdo"].preset == "codex" and POR_ID["direito"].preset == "antigravity"


# ── o espelho ─────────────────────────────────────────────────────────────
def _conversas(tmp_path, falas):
    d = tmp_path / "60-Conversas"; d.mkdir(parents=True)
    corpo = "\n\n".join(f"### {h} · voice · s\n**João:** {t}" for h, t in falas)
    (d / "2026-09-16.md").write_text("# Conversas\n\n" + corpo, encoding="utf-8")
    return _Vault(tmp_path)

def test_espelho_conta_o_jeito_do_joao_com_evidencia(tmp_path):
    v = _conversas(tmp_path, [("09:10", "faz o cockpit"), ("09:20", "arruma isso"),
                              ("10:00", "confirmo"), ("10:30", "pode fazer"), ("11:00", "manda ver"),
                              ("08:00", "roda os testes do cockpit")])
    t = {x.chave: x for x in Espelho(v).tracos()}
    assert t["ritmo"].valor == "mais ativo de manhã" and "6 de 6 falas" in t["ritmo"].evidencia
    assert t["jeito"].valor == "direto e curto"
    assert "faz" in t["demanda"].valor and t["decisao"].valor == "autoriza direto, sem rodeio"
    assert "cockpit" in t["vocabulario"].valor

def test_espelho_nunca_guarda_segredo(tmp_path):
    v = _conversas(tmp_path, [("09:00", "minha senha é 4823 abracadabra"), ("09:01", "o token é ghp_xxxxx"),
                              ("09:02", "••••"), ("09:03", "arruma o cockpit do jaime agora")])
    ctx = Espelho(v).contexto()
    for proibido in ("4823", "abracadabra", "ghp_", "senha", "token"):
        assert proibido not in ctx
    assert "cockpit" in ctx                                           # a fala limpa continua contando

def test_espelho_sem_material_nao_inventa(tmp_path):
    assert "ainda não ouvi" in Espelho(_Vault(tmp_path)).contexto()


# ── a agenda de dois trilhos ──────────────────────────────────────────────
def _vault_agenda(tmp_path):
    v = _Vault(tmp_path)
    v.write("30-Tarefas/Rotinas.md",
            "# Rotinas\n\n- 0 7 * * mon-fri · briefing\n- 0 22 * * * · consolida o que ouvi hoje\n"
            "- 30 23 * * sat,sun · estuda os projetos\n")
    v.write("30-Tarefas/Lembretes.md", "# Lembretes\n\n- [ ] 2026-09-17 11:00 · dentista\n")
    v.write("30-Tarefas/Inbox.md", "# Inbox\n\n- [ ] fechar o contrato @bub ⏳ 2026-09-18\n- [ ] sem prazo\n")
    v.write("01-Estado/Agenda-Jaime.md", "# Agenda\n\n- 2026-09-17 15:00 · criacao · refazer o painel de música\n")
    return v

def test_a_agenda_do_jaime_nao_entra_na_agenda_do_joao(tmp_path):
    s = montar_semana(_vault_agenda(tmp_path), None, dias=7, hoje=date(2026, 9, 17))   # quinta
    d = {x["data"]: x for x in s["dias"]}
    hoje = d["2026-09-17"]
    assert hoje["hoje"] and hoje["semana"] == "quinta"
    # o que é do João fica só na faixa dele
    assert [x["titulo"] for x in hoje["joao"]] == ["dentista"]
    assert [x["titulo"] for x in d["2026-09-18"]["joao"]] == ["fechar o contrato @bub"]
    # o que o Jaime decidiu fazer fica só na dele, e nunca aparece na do João
    titulos_jaime = [x["titulo"] for x in hoje["jaime"]]
    assert "briefing" in titulos_jaime and "refazer o painel de música" in titulos_jaime
    for dia in s["dias"]:
        for item in dia["joao"]:
            assert item["tipo"] in ("compromisso", "lembrete", "prazo", "tarefa")
        for item in dia["jaime"]:
            assert item["tipo"] in ("rotina", "estudo", "criacao", "melhoria", "pensar", "manutencao")
    assert s["total_joao"] == 2 and s["total_jaime"] > 5

def test_o_cron_das_rotinas_cai_no_dia_certo(tmp_path):
    quinta, sabado = date(2026, 9, 17), date(2026, 9, 19)
    assert rotina_no_dia(("0", "7", "*", "*", "mon-fri"), quinta)
    assert not rotina_no_dia(("0", "7", "*", "*", "mon-fri"), sabado)
    assert rotina_no_dia(("30", "23", "*", "*", "sat,sun"), sabado)
    assert not rotina_no_dia(("30", "23", "*", "*", "sat,sun"), quinta)
    assert rotina_no_dia(("0", "22", "*", "*", "*"), quinta) and rotina_no_dia(("0", "22", "*", "*", "*"), sabado)

def test_cada_tipo_tem_cor_propria(tmp_path):
    s = montar_semana(_vault_agenda(tmp_path), None, dias=3, hoje=date(2026, 9, 17))
    cores = {i["tipo"]: i["cor"] for d in s["dias"] for i in d["joao"] + d["jaime"]}
    assert len(set(cores.values())) == len(cores) and all(c.startswith("#") for c in cores.values())
