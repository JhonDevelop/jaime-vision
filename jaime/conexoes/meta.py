"""Meta — WhatsApp Cloud API (número comercial) e Instagram Messaging API (conta profissional), pelo webhook
próprio do Jaime (`/webhook/meta`). Só APIs oficiais: bibliotecas não oficiais derrubam a conta.

Fluxo: Meta → POST /webhook/meta (assinatura X-Hub-Signature-256 verificada com o app secret) → `receber()`:
  - mensagem do João (número/ID do dono) → `jaime.ask(..., canal="whatsapp"|"instagram")` → resposta enviada;
  - mensagem de terceiro → resumo + rascunho de resposta guardado em `pendentes`; ENVIAR é ação do Vigia ("confirmo").
Passo a passo do app no Meta for Developers em docs/CONEXOES.md."""
from __future__ import annotations
import hashlib, hmac, json, time
from dataclasses import dataclass, field
import httpx
from ..hud.events import bus

GRAPH = "https://graph.facebook.com/v21.0"

@dataclass
class Mensagem:
    plataforma: str          # "whatsapp" | "instagram"
    de: str                  # número (wa) ou id do usuário (ig)
    nome: str
    texto: str
    id: str = ""
    quando: float = field(default_factory=time.time)

def verificar_assinatura(app_secret: str, corpo: bytes, cabecalho: str | None) -> bool:
    """X-Hub-Signature-256: 'sha256=<hmac>' do corpo cru com o app secret."""
    if not app_secret or not cabecalho or not cabecalho.startswith("sha256="):
        return False
    esperado = hmac.new(app_secret.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, cabecalho[7:])

def handshake(params: dict, verify_token: str) -> str | None:
    """GET de verificação do webhook: devolve o hub.challenge se o token bater."""
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == verify_token:
        return params.get("hub.challenge", "")
    return None

def extrair(payload: dict) -> list[Mensagem]:
    """Mensagens de texto do payload do webhook (WhatsApp e Instagram); ignora status/echo."""
    out = []
    objeto = payload.get("object", "")
    for entry in payload.get("entry", []):
        # WhatsApp Cloud API
        for ch in entry.get("changes", []):
            v = ch.get("value", {})
            contatos = {c.get("wa_id"): (c.get("profile") or {}).get("name", "") for c in v.get("contacts", [])}
            for m in v.get("messages", []):
                if m.get("type") == "text":
                    out.append(Mensagem("whatsapp", m.get("from", ""), contatos.get(m.get("from", ""), ""), m["text"].get("body", ""), m.get("id", "")))
        # Instagram Messaging
        for ev in entry.get("messaging", []):
            msg = ev.get("message") or {}
            if msg.get("is_echo") or not msg.get("text"):
                continue
            out.append(Mensagem("instagram", str((ev.get("sender") or {}).get("id", "")), "", msg["text"], msg.get("mid", "")))
    if objeto == "instagram" and not out:
        pass
    return out

class Meta:
    def __init__(self, token: str, app_secret: str, verify_token: str, whatsapp_phone_id: str, instagram_id: str,
                 jaime, dono_whatsapp: str = "", dono_instagram: str = "", http: httpx.AsyncClient | None = None):
        self.token, self.app_secret, self.verify_token = token, app_secret, verify_token
        self.wa_id, self.ig_id, self.jaime = whatsapp_phone_id, instagram_id, jaime
        self.dono_wa, self.dono_ig = dono_whatsapp, dono_instagram
        self.http = http
        self.pendentes: dict[str, dict] = {}     # id da mensagem → {mensagem, resumo, rascunho}

    @property
    def ativo(self) -> bool:
        return bool(self.token and self.app_secret and (self.wa_id or self.ig_id))

    # ── envio (ação do Vigia) ────────────────────────
    async def _post(self, url: str, corpo: dict) -> dict:
        cliente = self.http or httpx.AsyncClient(timeout=30)
        try:
            r = await cliente.post(url, json=corpo, headers={"Authorization": f"Bearer {self.token}"})
            r.raise_for_status(); return r.json()
        finally:
            if cliente is not self.http:
                await cliente.aclose()

    async def enviar_whatsapp(self, para: str, texto: str) -> dict:
        return await self._post(f"{GRAPH}/{self.wa_id}/messages",
                                {"messaging_product": "whatsapp", "to": para, "type": "text", "text": {"body": texto[:4096]}})

    async def enviar_instagram(self, para: str, texto: str) -> dict:
        return await self._post(f"{GRAPH}/{self.ig_id}/messages", {"recipient": {"id": para}, "message": {"text": texto[:1000]}})

    async def enviar(self, plataforma: str, para: str, texto: str) -> dict:
        return await (self.enviar_whatsapp if plataforma == "whatsapp" else self.enviar_instagram)(para, texto)

    # ── recepção ─────────────────────────────────────
    def eh_dono(self, m: Mensagem) -> bool:
        alvo = self.dono_wa if m.plataforma == "whatsapp" else self.dono_ig
        return bool(alvo) and m.de.endswith(alvo[-8:]) if m.plataforma == "whatsapp" else (bool(alvo) and m.de == alvo)

    async def receber(self, payload: dict) -> list[dict]:
        """Trata cada mensagem; devolve o que fez com cada uma (para log e teste)."""
        feitos = []
        for m in extrair(payload):
            bus.emitir("conexoes_canal", canal=m.plataforma, de=m.nome or m.de, texto=m.texto[:80])
            if self.eh_dono(m):
                resposta = await self.jaime.ask(m.texto, canal=m.plataforma)
                await self.enviar(m.plataforma, m.de, resposta)
                feitos.append({"id": m.id, "acao": "respondido", "resposta": resposta})
            else:
                pedido = (f"[mensagem de terceiro no {m.plataforma}] De: {m.nome or m.de}. Texto: \"{m.texto[:500]}\". "
                          "Resuma em 1 frase para o João e proponha UMA resposta curta (como o João escreveria). "
                          "Formato: RESUMO: … | RASCUNHO: …  Não envie nada.")
                analise = await self.jaime.ask(pedido, canal="meta")
                resumo, _, rascunho = analise.partition("RASCUNHO:")
                self.pendentes[m.id or f"{m.de}-{int(m.quando)}"] = {"mensagem": m, "resumo": resumo.replace("RESUMO:", "").strip(), "rascunho": rascunho.strip()}
                self.jaime.vault.diario(f"{m.plataforma} de {m.nome or m.de}: {m.texto[:80]} → rascunho pendente", "Pendente")
                bus.emitir("fala", texto=f"{m.plataforma}: {m.nome or m.de} disse \"{m.texto[:60]}\". Tenho um rascunho; diga 'confirmo' para enviar."); bus.emitir("fala_fim")
                feitos.append({"id": m.id, "acao": "rascunho", "rascunho": rascunho.strip()})
        return feitos
