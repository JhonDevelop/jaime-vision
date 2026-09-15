"""Notificações do Mac — o Jaime lê a Central de Notificações (banco do `usernoted`) e avisa o que importa.

Banco: ~/Library/Group Containers/group.com.apple.usernoted/db2/db (SQLite; `record.data` é um plist com
req.titl / req.subt / req.body; `app.identifier` é o bundle id; `delivered_date` conta segundos desde 2001).
Exige **Acesso Total ao Disco** para o processo (Terminal ou python) — sem isso o SQLite devolve "authorization denied"
e o Jaime avisa uma vez e para de tentar por 10 min. Só leitura, nunca escreve no banco.

O que ele FALA (15/09/2026, a pedido do João): só mensagem de PESSOA SALVA — nem grupo, nem número sem nome,
nem e-mail automático, nem curtida/seguidor do Instagram. O resto vai só para o HUD e o diário.
Mensagens seguidas da mesma pessoa viram um aviso só ("Maria mandou 3 mensagens no WhatsApp: …").
`JAIME_AVISAR=off` silencia; `JAIME_AVISAR_TUDO=on` volta a falar tudo dos apps importantes."""
from __future__ import annotations
import asyncio, os, plistlib, re, sqlite3, time
from dataclasses import dataclass, field
from pathlib import Path
from ..hud.events import bus

DB = Path(os.environ.get("JAIME_NOTIFICACOES_DB", "~/Library/Group Containers/group.com.apple.usernoted/db2/db")).expanduser()
EPOCH_2001 = 978307200
INTERVALO_S = 8
AGRUPAR_S = 10          # espera este tanto para juntar mensagens seguidas da mesma pessoa num aviso só
# apps cujas notificações interessam (nome falado); o resto só vai para o HUD e o diário
IMPORTANTES = {"com.apple.MobileSMS": "Mensagens", "com.apple.mail": "Mail", "net.whatsapp.WhatsApp": "WhatsApp",
               "com.tinyspeck.slackmacgap": "Slack", "com.hnc.Discord": "Discord", "com.apple.iCal": "Calendário",
               "com.apple.reminders": "Lembretes", "com.apple.FaceTime": "FaceTime", "com.google.Chrome": "Chrome",
               "com.apple.Safari": "Safari", "ru.keepcoder.Telegram": "Telegram", "com.microsoft.teams2": "Teams",
               "us.zoom.xos": "Zoom", "com.apple.Notes": "Notas", "com.apple.Passwords": "Senhas",
               "com.apple.mobilephone": "Telefone", "com.burbn.instagram": "Instagram"}
IGNORAR = {"com.apple.ScreenTimeNotifications", "com.apple.Photos", "com.apple.Music", "com.apple.Spotify", "com.spotify.client"}

# --- filtro do que vale falar ---------------------------------------------------------------------------------
MENSAGEIROS = {"net.whatsapp.WhatsApp", "com.apple.MobileSMS", "ru.keepcoder.Telegram", "com.tinyspeck.slackmacgap",
               "com.hnc.Discord", "com.microsoft.teams2", "com.apple.mobilephone", "com.apple.FaceTime"}
SEMPRE = {"com.apple.iCal", "com.apple.reminders", "us.zoom.xos"}
INVISIVEIS = re.compile(r"[‎‏‪- ⁦-⁩]")
NUMERO = re.compile(r"^\+?\d[\d\s().\-]{6,}$")                      # "+55 16 99999-9999": contato não salvo
NAO_SALVO = re.compile(r"^[~〜]\s*")                                  # WhatsApp mostra "~ nome" quando não está na agenda
RESUMO = re.compile(r"^\d+\s+(mensagens|messages|novas)", re.I)
AUTOMATICO = re.compile(r"no-?reply|n[aã]o[\s.-]*responda|donotreply|newsletter|notifica[çc](ão|ao|tion)s?\b|marketing|"
                        r"promo|digest|mailer|boletim|unsubscribe|@", re.I)
ASSUNTO_RUIDO = re.compile(r"promo|oferta|cupom|desconto|newsletter|unsubscribe|black friday|\d+\s*%", re.I)
INSTAGRAM_RUIDO = re.compile(r"curtiu|come[çc]ou a seguir|liked|started following|comentou|mencionou|reels?\b|sugest|"
                             r"ao vivo|\blive\b|publicou|posted|story|stories", re.I)

@dataclass
class Notificacao:
    id: int
    app: str
    nome_app: str
    titulo: str
    texto: str
    quando: float
    sub: str = ""                       # subtítulo cru (no WhatsApp/Telegram é o nome do grupo)

    def frase(self) -> str:
        return f"{self.nome_app}: {self.titulo}" + (f" — {self.texto}" if self.texto else "")

    @property
    def remetente(self) -> str:
        return INVISIVEIS.sub("", self.titulo.split(" · ")[0]).strip()

def classificar(n: Notificacao) -> tuple[bool, str]:
    """(vale falar?, motivo). Regra: pessoa salva, em conversa direta; nada automático."""
    t = n.remetente; s = INVISIVEIS.sub("", n.sub).strip(); b = n.texto or ""
    tudo = f"{t} {s} {b}".lower()
    if "instagram" in n.app.lower() or "instagram" in tudo:
        if INSTAGRAM_RUIDO.search(f"{t} {b}"): return False, "instagram: não é mensagem"
        if not t or NUMERO.match(t) or NAO_SALVO.match(t): return False, "instagram: sem remetente"
        return True, "instagram: mensagem"
    if n.app in MENSAGEIROS:
        if s: return False, "grupo"
        if not t or NUMERO.match(t) or NAO_SALVO.match(t): return False, "número não salvo"
        if RESUMO.match(b) or t.lower() in {"whatsapp", "telegram", "mensagens", "messages"}: return False, "resumo do app"
        return True, "pessoa salva"
    if n.app == "com.apple.mail":
        if not t: return False, "sem remetente"
        if AUTOMATICO.search(t) or AUTOMATICO.search(s) or ASSUNTO_RUIDO.search(s): return False, "e-mail automático"
        return True, "e-mail de pessoa"
    if n.app in SEMPRE: return True, "agenda"
    return False, "fora do filtro"

def _limpar_texto(b: str) -> str:
    b = INVISIVEIS.sub("", b).strip()
    b = re.sub(r"^🎤\s*", "áudio: ", b); b = re.sub(r"^📷\s*", "foto: ", b); b = re.sub(r"^🎥\s*", "vídeo: ", b)
    b = re.sub(r"^📄\s*", "documento: ", b)
    return b

def frase_falada(nome_app: str, remetente: str, textos: list[str]) -> str:
    textos = [_limpar_texto(x) for x in textos if x]
    if len(textos) <= 1:
        return f"Senhor, {remetente} no {nome_app}" + (f": {textos[0][:160]}" if textos else ".")
    corpo = ". ".join(x[:90] for x in textos[:3]) + (f". E mais {len(textos) - 3}" if len(textos) > 3 else "")
    return f"Senhor, {remetente} mandou {len(textos)} mensagens no {nome_app}: {corpo}"

# --- leitura do banco -----------------------------------------------------------------------------------------
def _parse(rec_id: int, app_id: str, delivered: float, data: bytes) -> Notificacao:
    try:
        d = plistlib.loads(data); req = d.get("req", {}) or {}
    except Exception:
        req = {}
    titulo = str(req.get("titl") or "").strip(); sub = str(req.get("subt") or "").strip(); corpo = str(req.get("body") or "").strip()
    return Notificacao(rec_id, app_id, IMPORTANTES.get(app_id, app_id.split(".")[-1].capitalize()),
                       (titulo + (f" · {sub}" if sub else "")).strip(), corpo[:200], (delivered or 0) + EPOCH_2001, sub)

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
    def __init__(self, jaime, ouvido=None, db: Path = DB, falar_importantes: bool | None = None):
        self.jaime, self.ouvido, self.db = jaime, ouvido, Path(db)
        self.falar = (os.environ.get("JAIME_AVISAR", "on").lower() != "off") if falar_importantes is None else falar_importantes
        self.falar_tudo = os.environ.get("JAIME_AVISAR_TUDO", "").lower() in ("1", "on", "true")
        self.desde = -1
        self.erro = ""
        self.vistas: list[Notificacao] = []
        self.pendentes: dict[tuple[str, str], list[Notificacao]] = {}   # (app, remetente) → mensagens à espera de agrupar

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
                await self.falar_pendentes()
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
        avisar, motivo = (n.app in IMPORTANTES, "tudo") if self.falar_tudo else classificar(n)
        bus.emitir("notificacao", app=n.nome_app, titulo=n.titulo, texto=n.texto, avisar=avisar, motivo=motivo,
                   quando=time.strftime("%H:%M", time.localtime(n.quando)))
        self.jaime.vault.diario(f"Notificação {n.frase()[:140]}", "Log")
        if self.falar and avisar:
            self.pendentes.setdefault((n.nome_app, n.remetente), []).append(n)

    def _pode_falar(self) -> bool:
        return bool(self.ouvido) and self.jaime.acesso.liberado and not getattr(self.ouvido, "ocupado", False)

    async def falar_pendentes(self, agora: float | None = None):
        """Fala os grupos cuja primeira mensagem já espera AGRUPAR_S (junta as seguidas da mesma pessoa)."""
        agora = time.time() if agora is None else agora
        prontos = [k for k, ms in self.pendentes.items() if agora - ms[0].quando >= AGRUPAR_S]
        for k in prontos:
            ms = self.pendentes.pop(k)
            if not self._pode_falar():
                continue
            await asyncio.to_thread(self.ouvido.falar, frase_falada(k[0], k[1], [m.texto for m in ms]))

    def resumo(self, n: int = 10) -> str:
        return "\n".join(f"- {time.strftime('%H:%M', time.localtime(x.quando))} {x.frase()}" for x in self.vistas[-n:]) or "Nenhuma notificação desde que liguei."
