"""Notificações do Mac — o Jaime lê a Central de Notificações (banco do `usernoted`) e avisa o que importa.

Banco: ~/Library/Group Containers/group.com.apple.usernoted/db2/db (SQLite; `record.data` é um plist com
req.titl / req.subt / req.body; `app.identifier` é o bundle id; `delivered_date` conta segundos desde 2001).
Exige **Acesso Total ao Disco** para o processo (Terminal ou python) — sem isso o SQLite devolve "authorization denied"
e o Jaime avisa uma vez e para de tentar por 10 min. Só leitura, nunca escreve no banco."""
from __future__ import annotations
import asyncio, os, plistlib, sqlite3, time
from dataclasses import dataclass
from pathlib import Path
from ..hud.events import bus

DB = Path(os.environ.get("JAIME_NOTIFICACOES_DB", "~/Library/Group Containers/group.com.apple.usernoted/db2/db")).expanduser()
EPOCH_2001 = 978307200
INTERVALO_S = 8
# apps cujas notificações ele fala em voz alta; o resto só vai para o HUD e o diário
IMPORTANTES = {"com.apple.MobileSMS": "Mensagens", "com.apple.mail": "Mail", "net.whatsapp.WhatsApp": "WhatsApp",
               "com.tinyspeck.slackmacgap": "Slack", "com.hnc.Discord": "Discord", "com.apple.iCal": "Calendário",
               "com.apple.reminders": "Lembretes", "com.apple.FaceTime": "FaceTime", "com.google.Chrome": "Chrome",
               "com.apple.Safari": "Safari", "ru.keepcoder.Telegram": "Telegram", "com.microsoft.teams2": "Teams",
               "us.zoom.xos": "Zoom", "com.apple.Notes": "Notas", "com.apple.Passwords": "Senhas"}
IGNORAR = {"com.apple.ScreenTimeNotifications", "com.apple.Photos", "com.apple.Music", "com.apple.Spotify", "com.spotify.client"}

@dataclass
class Notificacao:
    id: int
    app: str
    nome_app: str
    titulo: str
    texto: str
    quando: float

    def frase(self) -> str:
        return f"{self.nome_app}: {self.titulo}" + (f" — {self.texto}" if self.texto else "")

def _parse(rec_id: int, app_id: str, delivered: float, data: bytes) -> Notificacao:
    try:
        d = plistlib.loads(data); req = d.get("req", {}) or {}
    except Exception:
        req = {}
    titulo = str(req.get("titl") or "").strip(); sub = str(req.get("subt") or "").strip(); corpo = str(req.get("body") or "").strip()
    return Notificacao(rec_id, app_id, IMPORTANTES.get(app_id, app_id.split(".")[-1].capitalize()),
                       (titulo + (f" · {sub}" if sub else "")).strip(), corpo[:200], (delivered or 0) + EPOCH_2001)

def ler_novas(db: Path, desde_id: int, limite: int = 50) -> list[Notificacao]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT r.rec_id, a.identifier, r.delivered_date, r.data FROM record r JOIN app a ON a.app_id = r.app_id "
                           "WHERE r.rec_id > ? ORDER BY r.rec_id ASC LIMIT ?", (desde_id, limite)).fetchall()
    finally:
        con.close()
    return [_parse(*r) for r in rows if r[1] not in IGNORAR]

def ultimo_id(db: Path) -> int:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return int(con.execute("SELECT COALESCE(MAX(rec_id), 0) FROM record").fetchone()[0])
    finally:
        con.close()

class Notificacoes:
    def __init__(self, jaime, ouvido=None, db: Path = DB, falar_importantes: bool = True):
        self.jaime, self.ouvido, self.db, self.falar = jaime, ouvido, Path(db), falar_importantes
        self.desde = -1
        self.erro = ""
        self.vistas: list[Notificacao] = []

    async def rodar(self):
        while True:
            try:
                if self.desde < 0:
                    self.desde = await asyncio.to_thread(ultimo_id, self.db)   # começa do agora: não repete o histórico
                    bus.emitir("notificacoes", ligado=True, msg="lendo a Central de Notificações")
                novas = await asyncio.to_thread(ler_novas, self.db, self.desde)
                for n in novas:
                    self.desde = max(self.desde, n.id); self.vistas.append(n); self.vistas = self.vistas[-100:]
                    await self.tratar(n)
                self.erro = ""
                await asyncio.sleep(INTERVALO_S)
            except asyncio.CancelledError:
                return
            except Exception as e:
                msg = f"{type(e).__name__}: {e}"
                if msg != self.erro:
                    self.erro = msg
                    dica = " — dê Acesso Total ao Disco ao Terminal/python em Ajustes › Privacidade" if "authorization" in msg.lower() or "unable to open" in msg.lower() else ""
                    bus.emitir("notificacoes", ligado=False, erro=(msg + dica)[:220])
                await asyncio.sleep(600)

    async def tratar(self, n: Notificacao):
        bus.emitir("notificacao", app=n.nome_app, titulo=n.titulo, texto=n.texto, quando=time.strftime("%H:%M", time.localtime(n.quando)))
        self.jaime.vault.diario(f"Notificação {n.frase()[:140]}", "Log")
        if self.falar and n.app in IMPORTANTES and self.jaime.acesso.liberado and self.ouvido and not getattr(self.ouvido, "ocupado", False):
            await asyncio.to_thread(self.ouvido.falar, f"Senhor, {n.frase()[:160]}")

    def resumo(self, n: int = 10) -> str:
        return "\n".join(f"- {time.strftime('%H:%M', time.localtime(x.quando))} {x.frase()}" for x in self.vistas[-n:]) or "Nenhuma notificação desde que liguei."
