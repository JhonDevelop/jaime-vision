"""Ouvido passivo (guardar/consolidar/lembrar), notificações do Mac (banco sintético), gravador de processos (sem pynput)."""
import plistlib, sqlite3, time
from datetime import date, datetime
from pathlib import Path
import pytest
from jaime.brain.vault import Vault
from jaime.brain import ouvido_passivo as op
from jaime.ops import notificacoes as nt
from jaime.maos import gravador as gr

@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    for d in ("00-Jaime", "30-Tarefas", "40-Diario", "50-Conhecimento", "60-Conversas"):
        (tmp_path / d).mkdir()
    (tmp_path / "30-Tarefas/Inbox.md").write_text("# Inbox\n- [ ] ligar pro contador @BUB\n")
    return Vault(tmp_path)

def test_ouvido_passivo_guarda_consolida_e_lembra(vault):
    agora = datetime(2026, 9, 15, 15, 30)
    op.guardar(vault, "o Zé disse que a entrega do capacete atrasa pra sexta", agora)
    op.guardar(vault, "ok", agora)                                   # curto: ignorado
    txt = vault.read("60-Conversas/ouvido-2026-09-15.md")
    assert "15:30 o Zé disse" in txt and txt.count("\n- ") == 1
    assert "ouvido-2026-09-15.md" in op.prompt_consolidar(vault, date(2026, 9, 15)) and "atrasa pra sexta" in op.prompt_consolidar(vault, date(2026, 9, 15))
    op.anotar_para_lembrar(vault, "entrega do capacete atrasou para sexta", date(2026, 9, 15))
    assert op.pendentes(vault) == ["entrega do capacete atrasou para sexta"]
    f = op.frase_dos_pendentes(vault, vault.tarefas_abertas())
    assert f.startswith("Guardei uma coisa de ontem") and "Tarefa do dia: ligar pro contador" in f
    assert op.marcar_entregues(vault) == 1 and op.pendentes(vault) == [] and "- [x] 2026-09-15" in vault.read(op.PARA_LEMBRAR)

def _db(tmp: Path) -> Path:
    db = tmp / "db"; c = sqlite3.connect(db)
    c.executescript("CREATE TABLE app(app_id INTEGER PRIMARY KEY, identifier TEXT); CREATE TABLE record(rec_id INTEGER PRIMARY KEY, app_id INTEGER, delivered_date REAL, data BLOB);")
    c.execute("INSERT INTO app VALUES (1, 'net.whatsapp.WhatsApp'), (2, 'com.spotify.client'), (3, 'com.apple.mail')")
    def rec(i, app, titl, body):
        c.execute("INSERT INTO record VALUES (?, ?, ?, ?)", (i, app, time.time() - nt.EPOCH_2001, plistlib.dumps({"req": {"titl": titl, "body": body}})))
    rec(1, 1, "Zé", "chegou a peça"); rec(2, 2, "Spotify", "tocando"); rec(3, 3, "Contador", "nota fiscal de agosto")
    c.commit(); c.close(); return db

def test_notificacoes_le_novas_e_ignora_ruido(tmp_path):
    db = _db(tmp_path)
    assert nt.ultimo_id(db) == 3
    novas = nt.ler_novas(db, 0)
    assert [n.nome_app for n in novas] == ["WhatsApp", "Mail"] and novas[0].frase() == "WhatsApp: Zé — chegou a peça"
    assert nt.ler_novas(db, 3) == []

class _Jaime:
    def __init__(self, vault): self.vault = vault; from types import SimpleNamespace; self.acesso = SimpleNamespace(liberado=True)

def test_gravador_interpretar_salvar_carregar_repetir(vault, tmp_path, monkeypatch):
    monkeypatch.setattr(gr, "PASTA", tmp_path / "proc")
    assert gr.interpretar("Jaime, grava esse processo: emitir nota") == ("gravar", "emitir nota")
    assert gr.interpretar("para de gravar") == ("parar", "")
    assert gr.interpretar("repete o processo emitir nota") == ("repetir", "emitir nota")
    assert gr.interpretar("abre o Finder") is None
    g = gr.Gravador(_Jaime(vault))
    p = gr.Processo("emitir nota", "emitir-nota", time.time())
    p.passos = [gr.Passo("app", p.inicio, app="Safari", janela="NFe"), gr.Passo("clique", p.inicio + 1, x=100, y=200, app="Safari"),
                gr.Passo("texto", p.inicio + 2, texto="12345"), gr.Passo("tecla", p.inicio + 3, combo="enter")]
    p.fim = p.inicio + 4
    g.salvar(p)
    assert gr.Gravador.listar() == ["emitir-nota"]
    nota = vault.read("50-Conhecimento/processos/emitir-nota.md")
    assert "Abrir **Safari**" in nota and "Clicar em (100, 200)" in nota and "Digitar: `12345`" in nota
    feitos = []
    ex = {t: (lambda x, t=t: feitos.append((t, x.texto or x.combo or x.app or x.x))) for t in ("app", "clique", "tecla", "texto")}
    r = g.repetir("emitir nota", executor=ex, esperar=lambda s: None)
    assert "4 passos" in r and feitos == [("app", "Safari"), ("clique", "Safari"), ("texto", "12345"), ("tecla", "enter")]
    assert "Parei no passo 1" in g.repetir("emitir nota", executor=ex, deve_parar=lambda: True, esperar=lambda s: None)
    assert "Não conheço" in g.repetir("outro", executor=ex, esperar=lambda s: None)

# --- filtro do que o Jaime fala (15/09/2026) ---
def _n(app, titl, body, sub="", i=1):
    return nt.Notificacao(i, app, nt.IMPORTANTES.get(app, app), (titl + (f" · {sub}" if sub else "")).strip(), body, time.time(), sub)

def test_classificar_fala_so_pessoa_salva_em_conversa_direta():
    wa = "net.whatsapp.WhatsApp"
    assert nt.classificar(_n(wa, "‎Maria Clara", "to com sono")) == (True, "pessoa salva")
    assert nt.classificar(_n(wa, "Diego", "bora?", sub="🏎️🏁 Turma da pista")) == (False, "grupo")
    assert nt.classificar(_n(wa, "~ Fulano", "oi, vi seu anúncio")) == (False, "número não salvo")
    assert nt.classificar(_n(wa, "+55 16 99999-9999", "olá")) == (False, "número não salvo")
    assert nt.classificar(_n(wa, "WhatsApp", "5 mensagens de 2 conversas")) == (False, "resumo do app")
    assert nt.classificar(_n("com.apple.mobilephone", "Gabriel", "Ligação recebida")) == (True, "pessoa salva")
    assert nt.classificar(_n("com.apple.mobilephone", "+55 11 4002-8922", "Ligação recebida")) == (False, "número não salvo")

def test_classificar_email_e_instagram():
    mail = "com.apple.mail"
    assert nt.classificar(_n(mail, "Contador", "nota fiscal de agosto", sub="NF agosto")) == (True, "e-mail de pessoa")
    assert nt.classificar(_n(mail, "Loja X <no-reply@lojax.com>", "50% off", sub="Promoção")) == (False, "e-mail automático")
    assert nt.classificar(_n(mail, "Nubank", "sua fatura", sub="Cupom de 20% de desconto")) == (False, "e-mail automático")
    ig = "com.burbn.instagram"
    assert nt.classificar(_n(ig, "piloto.leal", "joaozinho curtiu sua publicação")) == (False, "instagram: não é mensagem")
    assert nt.classificar(_n(ig, "carla_estampas", "te enviou uma mensagem")) == (True, "instagram: mensagem")
    assert nt.classificar(_n("com.google.Chrome", "instagram.com", "Ana: quanto custa a camiseta?")) == (True, "instagram: mensagem")
    assert nt.classificar(_n("com.google.Chrome", "youtube.com", "novo vídeo")) == (False, "fora do filtro")
    assert nt.classificar(_n("com.apple.iCal", "Reunião BUB", "em 10 min")) == (True, "agenda")

def test_frase_falada_agrupa_e_traduz_midia():
    assert nt.frase_falada("WhatsApp", "Maria Clara", ["to com sono"]) == "Senhor, Maria Clara no WhatsApp: to com sono"
    f = nt.frase_falada("WhatsApp", "David", ["🎤 ‎Mensagem de voz (0:09)", "Fx", "Dps manda um vídeo ai", "kkk"])
    assert f.startswith("Senhor, David mandou 4 mensagens no WhatsApp: áudio: Mensagem de voz (0:09). Fx. Dps manda um vídeo ai. E mais 1")

def test_notificacoes_agrupa_e_fala_so_o_que_passa_no_filtro(vault):
    import asyncio
    from types import SimpleNamespace
    falas = []
    ouvido = SimpleNamespace(falar=falas.append, ocupado=False)
    ns = nt.Notificacoes(_Jaime(vault), ouvido, db=Path("/nao/existe"), falar_importantes=True)
    ns.falar_tudo = False
    t0 = time.time() - 60
    for i, (titl, body, sub) in enumerate([("‎Maria Clara", "oi", ""), ("‎Maria Clara", "tá aí?", ""), ("Diego", "bora", "Grupo da pista"), ("~ Zé", "spam", "")]):
        n = nt.Notificacao(i, "net.whatsapp.WhatsApp", "WhatsApp", titl, body, t0 + i, sub)
        asyncio.run(ns.tratar(n))
    assert list(ns.pendentes) == [("WhatsApp", "Maria Clara")] and len(ns.pendentes[("WhatsApp", "Maria Clara")]) == 2
    asyncio.run(ns.falar_pendentes(agora=t0 + 5))      # ainda dentro da janela de agrupar: não fala
    assert falas == []
    asyncio.run(ns.falar_pendentes(agora=t0 + nt.AGRUPAR_S + 1))
    assert falas == ["Senhor, Maria Clara mandou 2 mensagens no WhatsApp: oi. tá aí?"] and ns.pendentes == {}
    assert "Notificação WhatsApp: Diego — bora" in vault.read(f"40-Diario/{date.today():%Y-%m-%d}.md")
