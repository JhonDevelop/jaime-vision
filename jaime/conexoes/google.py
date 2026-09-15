"""Google (Gmail + Calendar + Drive) pelo SEU projeto no Google Cloud — OAuth de app Desktop, token local.

Fluxo: `python -m jaime conectar google` abre o navegador uma vez; o token fica em `GOOGLE_TOKEN_FILE`
(~/Jaime/google-token.json) e é renovado sozinho. Revogar: myaccount.google.com → Segurança → Acesso de terceiros.
Passo a passo do console em docs/CONEXOES.md.

Ler e rascunhar são livres; ENVIAR e-mail é ação do Vigia (só com "confirmo")."""
from __future__ import annotations
import base64, re
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path
from zoneinfo import ZoneInfo

ESCOPOS = ["https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/calendar",
           "https://www.googleapis.com/auth/drive.readonly"]
FUSO = ZoneInfo("America/Sao_Paulo")

def conectar(client_secret: Path, token: Path) -> str:
    """Abre o consentimento no navegador e salva o token. Devolve o e-mail conectado."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    if not Path(client_secret).exists():
        raise FileNotFoundError(f"credencial não encontrada: {client_secret} — veja docs/CONEXOES.md")
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), ESCOPOS)
    creds = flow.run_local_server(port=0, prompt="consent")
    Path(token).parent.mkdir(parents=True, exist_ok=True)
    Path(token).write_text(creds.to_json(), encoding="utf-8")
    return GoogleConta(token).email()

class GoogleConta:
    """Clientes Gmail/Calendar/Drive a partir do token salvo. `servicos` é injetável para testes."""
    def __init__(self, token: Path, servicos: dict | None = None):
        self.token = Path(token)
        self._creds = None
        self._servicos = servicos or {}

    @property
    def conectado(self) -> bool:
        return bool(self._servicos) or self.token.exists()

    def _cred(self):
        if self._creds:
            return self._creds
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        c = Credentials.from_authorized_user_file(str(self.token), ESCOPOS)
        if c.expired and c.refresh_token:
            c.refresh(Request()); self.token.write_text(c.to_json(), encoding="utf-8")
        self._creds = c
        return c

    def _svc(self, nome: str, versao: str):
        if nome in self._servicos:
            return self._servicos[nome]
        from googleapiclient.discovery import build
        return build(nome, versao, credentials=self._cred(), cache_discovery=False)

    def email(self) -> str:
        return self._svc("gmail", "v1").users().getProfile(userId="me").execute().get("emailAddress", "")

    # ── Gmail ────────────────────────────────────────
    def email_buscar(self, consulta: str, limite: int = 10) -> list[dict]:
        g = self._svc("gmail", "v1")
        ids = g.users().messages().list(userId="me", q=consulta, maxResults=limite).execute().get("messages", [])
        out = []
        for m in ids:
            msg = g.users().messages().get(userId="me", id=m["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"]).execute()
            h = {x["name"]: x["value"] for x in msg.get("payload", {}).get("headers", [])}
            out.append({"id": m["id"], "de": h.get("From", ""), "assunto": h.get("Subject", "(sem assunto)"), "data": h.get("Date", ""),
                        "resumo": msg.get("snippet", ""), "nao_lido": "UNREAD" in msg.get("labelIds", [])})
        return out

    def email_hoje(self, limite: int = 15) -> list[dict]:
        return self.email_buscar("newer_than:1d -category:promotions -category:social", limite)

    def email_rascunho(self, para: str, assunto: str, corpo: str) -> str:
        msg = MIMEText(corpo, "plain", "utf-8"); msg["to"] = para; msg["subject"] = assunto
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        d = self._svc("gmail", "v1").users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
        return d.get("id", "")

    def email_enviar(self, para: str, assunto: str, corpo: str) -> str:
        """Ação do Vigia — a ferramenta só chega aqui depois do 'confirmo'."""
        msg = MIMEText(corpo, "plain", "utf-8"); msg["to"] = para; msg["subject"] = assunto
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        r = self._svc("gmail", "v1").users().messages().send(userId="me", body={"raw": raw}).execute()
        return r.get("id", "")

    # ── Calendar ─────────────────────────────────────
    def agenda_dia(self, dia: datetime | None = None) -> list[dict]:
        dia = dia or datetime.now(FUSO)
        ini = dia.replace(hour=0, minute=0, second=0, microsecond=0); fim = ini + timedelta(days=1)
        r = self._svc("calendar", "v3").events().list(calendarId="primary", timeMin=ini.isoformat(), timeMax=fim.isoformat(),
                                                       singleEvents=True, orderBy="startTime").execute()
        out = []
        for e in r.get("items", []):
            s = e.get("start", {}); inicio = s.get("dateTime") or s.get("date", "")
            out.append({"id": e.get("id"), "titulo": e.get("summary", "(sem título)"), "inicio": inicio,
                        "hora": inicio[11:16] if "T" in inicio else "dia todo", "local": e.get("location", "")})
        return out

    def agenda_criar(self, titulo: str, inicio: datetime, fim: datetime | None = None, descricao: str = "") -> str:
        fim = fim or inicio + timedelta(hours=1)
        corpo = {"summary": titulo, "description": descricao,
                 "start": {"dateTime": inicio.isoformat(), "timeZone": "America/Sao_Paulo"},
                 "end": {"dateTime": fim.isoformat(), "timeZone": "America/Sao_Paulo"}}
        e = self._svc("calendar", "v3").events().insert(calendarId="primary", body=corpo).execute()
        return e.get("htmlLink", e.get("id", ""))

def texto_emails(lista: list[dict]) -> str:
    if not lista:
        return "Nenhum e-mail."
    return "\n".join(f"- {'● ' if m['nao_lido'] else ''}{m['de'][:40]} — {m['assunto'][:70]}" + (f" · {m['resumo'][:80]}" if m.get("resumo") else "") for m in lista)

def texto_agenda(lista: list[dict]) -> str:
    if not lista:
        return "Agenda livre."
    return "\n".join(f"- {e['hora']} {e['titulo']}" + (f" ({e['local']})" if e.get("local") else "") for e in lista)

def interpretar_quando(texto: str, agora: datetime | None = None) -> datetime | None:
    """'amanhã às 15h', 'dia 20 às 10:30', 'hoje 14h', '2026-09-20 15:00' → datetime no fuso do João."""
    agora = agora or datetime.now(FUSO)
    t = (texto or "").strip().lower()
    try:
        return datetime.strptime(t, "%Y-%m-%d %H:%M").replace(tzinfo=FUSO)
    except ValueError:
        pass
    from ..agenda.lembretes import interpretar
    r = interpretar(f"me lembra {t} de x", agora)
    return r[0] if r else None
