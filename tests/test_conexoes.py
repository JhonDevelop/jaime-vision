"""Conexões com clientes falsos: registro, Gmail/Calendar (serviços dublês), Telegram (só o dono), Vigia no envio."""
import asyncio
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pytest
from jaime.brain.vault import Vault
from jaime.conexoes.registro import Registro
from jaime.conexoes.google import GoogleConta, texto_emails, texto_agenda, interpretar_quando
from jaime.conexoes.telegram import Telegram
from jaime.vigia.hooks import Vigia

TZ = ZoneInfo("America/Sao_Paulo")

@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    for d in ("00-Jaime", "01-Estado", "40-Diario"):
        (tmp_path / d).mkdir()
    return Vault(tmp_path)

def test_registro_de_conexoes(vault):
    r = Registro(vault)
    r.registrar("Google Gmail", "ler, rascunhar, enviar", "OAuth 15/09/2026", "myaccount.google.com › acesso de terceiros")
    r.registrar("Telegram", "bot @jaime", "token do BotFather", "@BotFather /revoke")
    r.usou("Google Gmail")
    txt = vault.read("01-Estado/Conexoes.md")
    assert "| Google Gmail |" in txt and "| Telegram |" in txt and "último uso" in txt
    assert "Google Gmail" in r.texto() and r._linhas()["Google Gmail"][4] != "—"
    r.remover("Telegram"); assert "Telegram" not in vault.read("01-Estado/Conexoes.md")

class _Chain:
    """Dublê encadeável: qualquer método devolve self; execute() devolve a resposta programada."""
    def __init__(self, respostas): self.respostas = respostas; self.chamadas = []
    def __getattr__(self, n):
        def f(*a, **k): self.chamadas.append((n, k)); return self
        return f
    def execute(self):
        return self.respostas.pop(0) if self.respostas else {}

def test_gmail_e_calendar_com_dubles(tmp_path):
    gmail = _Chain([{"messages": [{"id": "1"}]},
                    {"payload": {"headers": [{"name": "From", "value": "Zé <ze@x.com>"}, {"name": "Subject", "value": "Orçamento"}]}, "snippet": "segue", "labelIds": ["UNREAD"]},
                    {"id": "d1"}, {"id": "m9"}])
    cal = _Chain([{"items": [{"id": "e1", "summary": "Reunião Oldsen", "start": {"dateTime": "2026-09-15T14:00:00-03:00"}, "location": "sala 2"}]},
                  {"htmlLink": "https://cal/e2"}])
    conta = GoogleConta(tmp_path / "token.json", servicos={"gmail": gmail, "calendar": cal})
    assert conta.conectado
    emails = conta.email_hoje()
    assert emails[0]["assunto"] == "Orçamento" and emails[0]["nao_lido"]
    assert "● Zé <ze@x.com> — Orçamento" in texto_emails(emails)
    assert conta.email_rascunho("a@b.c", "Oi", "corpo") == "d1" and conta.email_enviar("a@b.c", "Oi", "corpo") == "m9"
    ag = conta.agenda_dia(datetime(2026, 9, 15, tzinfo=TZ))
    assert texto_agenda(ag) == "- 14:00 Reunião Oldsen (sala 2)"
    link = conta.agenda_criar("Dentista", datetime(2026, 9, 16, 10, tzinfo=TZ))
    assert link == "https://cal/e2" and cal.chamadas[-1][0] == "insert"
    assert not GoogleConta(tmp_path / "nao-existe.json").conectado

def test_interpretar_quando():
    agora = datetime(2026, 9, 15, 14, 0, tzinfo=TZ)
    assert interpretar_quando("2026-09-20 15:00").hour == 15
    q = interpretar_quando("amanhã às 15h", agora); assert (q.day, q.hour) == (16, 15)
    assert interpretar_quando("xyz", agora) is None

class _Jaime:
    def __init__(self, vault): self.vault = vault; self.perguntas = []
    async def ask(self, texto, canal="cli", contexto=""): self.perguntas.append((texto, canal)); return "resposta curta"

class _Http:
    def __init__(self): self.posts = []
    async def post(self, url, json=None):
        self.posts.append((url.rsplit("/", 1)[-1], json))
        class R:
            def raise_for_status(self): pass
            def json(self): return {"ok": True, "result": []}
        return R()

def test_telegram_so_o_dono(vault):
    j = _Jaime(vault); http = _Http()
    t = Telegram("tok", "111", j, http=http)
    up = lambda de, txt: {"update_id": 1, "message": {"text": txt, "from": {"id": de}, "chat": {"id": de}}}
    assert asyncio.run(t.tratar(up(111, "que horas são?"))) == "resposta curta"
    assert j.perguntas == [("que horas são?", "telegram")] and http.posts[0][0] == "sendMessage" and http.posts[0][1]["chat_id"] == 111
    assert asyncio.run(t.tratar(up(222, "oi"))) is None and len(j.perguntas) == 1
    assert "desconhecido 222" in vault.read(vault.daily_rel())
    assert not Telegram("", "", j).ativo

def test_vigia_segura_envio_de_email():
    v = Vigia()
    r = asyncio.run(v.pre_tool_use({"tool_name": "mcp__google__email_enviar", "tool_input": {"para": "a@b.c"}}, None, None))
    assert r["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert asyncio.run(v.pre_tool_use({"tool_name": "mcp__google__email_rascunho", "tool_input": {}}, None, None)) == {}
