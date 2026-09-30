"""Cliente do Hermes Agent (Nous Research) — o "programa que transforma a IA em agente de verdade" (passo 3).

O Hermes roda como um serviço à parte (`hermes gateway`, API compatível com OpenAI em 127.0.0.1:8642) com as
ferramentas dele: terminal, arquivos, navegador, memória própria, skills, cron, Telegram/WhatsApp, voz. O Jaime
continua sendo quem fala com o João e quem decide; o Hermes é mais um par de mãos, por DELEGAÇÃO EXPLÍCITA.

Regras:
- desligado por padrão (`JAIME_HERMES=off`); endpoint só do .env do dono, nunca de fala/prompt; fora do loopback
  exige HTTPS; a chave (`HERMES_API_KEY`) nunca aparece em erro, log ou resposta;
- aprovação: quando o Hermes para num comando perigoso (`waiting_for_approval`), a resposta sai SÓ com o "sim"
  do João pelo lote do Vigia, e sempre como `once` — nunca `session`/`always` (um sim vale para uma ação);
- negar é sempre livre.
"""
from __future__ import annotations
import asyncio, os, time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx

HOSTS_LOCAIS = {"localhost", "127.0.0.1", "::1"}
TERMINAIS = {"completed", "failed", "cancelled", "interrupted"}
ESCOLHAS = {"once", "deny"}               # o Jaime nunca manda "session"/"always"


@dataclass
class Resultado:
    status: str                       # completed | failed | cancelled | interrupted | waiting_for_approval | running | erro
    texto: str = ""
    run_id: str = ""
    aprovacao: dict = field(default_factory=dict)
    erro: str = ""

    @property
    def pedindo_aprovacao(self) -> bool:
        return self.status == "waiting_for_approval" and bool(self.aprovacao)


def _on(v: str) -> bool:
    return (v or "").strip().lower() in ("1", "on", "true", "sim")


class HermesCliente:
    def __init__(self, url: str = "http://127.0.0.1:8642", chave: str = "", ligado: bool = False, timeout: float = 30.0,
                 transporte: httpx.AsyncBaseTransport | None = None, relogio=time.monotonic, dormir=asyncio.sleep):
        self.url, self.chave, self.ligado, self.timeout = url.rstrip("/"), chave, ligado, timeout
        self._transporte, self.relogio, self.dormir = transporte, relogio, dormir
        self.motivo_indisponivel = self._validar()
        self.pendentes: dict[str, dict] = {}       # run_id → pedido de aprovação em aberto (para o HUD/estado)

    @classmethod
    def do_ambiente(cls, env=None, **kw) -> "HermesCliente":
        e = os.environ if env is None else env
        g = lambda k, d="": (e.get(k, "") or "").strip() or d
        try:
            timeout = float(g("HERMES_TIMEOUT_S", "30").replace(",", "."))
        except ValueError:
            timeout = 30.0
        return cls(url=g("HERMES_URL", "http://127.0.0.1:8642"), chave=g("HERMES_API_KEY"),
                   ligado=_on(g("JAIME_HERMES", "off")), timeout=timeout, **kw)

    def _validar(self) -> str:
        if not self.ligado:
            return "JAIME_HERMES=off"
        u = urlsplit(self.url)
        if u.scheme not in ("http", "https") or not u.hostname:
            return "HERMES_URL inválida"
        if u.hostname not in HOSTS_LOCAIS and u.scheme != "https":
            return "Hermes fora desta máquina exige HTTPS"
        if not self.chave:
            return "HERMES_API_KEY vazia (a API do Hermes exige a chave)"
        return ""

    @property
    def disponivel(self) -> bool:
        return not self.motivo_indisponivel

    def _http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.url, timeout=self.timeout, transport=self._transporte,
                                 headers={"Authorization": f"Bearer {self.chave}"})

    def _limpo(self, e: Exception) -> str:
        msg = f"{type(e).__name__}: {e}"
        return msg.replace(self.chave, "•••") if self.chave else msg

    async def saude(self) -> tuple[bool, str]:
        if not self.disponivel:
            return False, self.motivo_indisponivel
        try:
            async with self._http() as c:
                r = await c.get("/health")
                return r.status_code == 200, f"HTTP {r.status_code}"
        except Exception as e:
            return False, self._limpo(e)[:160]

    async def iniciar(self, tarefa: str, sessao: str = "jaime", instrucoes: str = "") -> str:
        corpo = {"input": tarefa, "session_id": sessao}
        if instrucoes:
            corpo["instructions"] = instrucoes
        async with self._http() as c:
            r = await c.post("/v1/runs", json=corpo)
            r.raise_for_status()
            return r.json()["run_id"]

    async def estado(self, run_id: str) -> dict:
        async with self._http() as c:
            r = await c.get(f"/v1/runs/{run_id}")
            r.raise_for_status()
            return r.json()

    async def responder_aprovacao(self, run_id: str, request_id: str, escolha: str) -> dict:
        if escolha not in ESCOLHAS:
            raise ValueError("o Jaime só responde 'once' ou 'deny'")
        async with self._http() as c:
            r = await c.post(f"/v1/runs/{run_id}/approval", json={"choice": escolha, "request_id": request_id})
            r.raise_for_status()
            self.pendentes.pop(run_id, None)
            return r.json()

    async def parar(self, run_id: str) -> dict:
        async with self._http() as c:
            r = await c.post(f"/v1/runs/{run_id}/stop")
            r.raise_for_status()
            self.pendentes.pop(run_id, None)
            return r.json()

    async def acompanhar(self, run_id: str, esperar_s: float = 240.0, intervalo: float = 1.0) -> Resultado:
        """Espera o run terminar OU parar pedindo aprovação (o que vier primeiro, até `esperar_s`)."""
        fim = self.relogio() + esperar_s
        d: dict = {}
        while True:
            d = await self.estado(run_id)
            st = d.get("status", "")
            if st in TERMINAIS:
                self.pendentes.pop(run_id, None)
                return Resultado(st, str(d.get("output") or d.get("error") or ""), run_id)
            if st == "waiting_for_approval":
                ap = dict(d.get("approval") or {})
                self.pendentes[run_id] = ap
                return Resultado(st, "", run_id, ap)
            if self.relogio() >= fim:
                return Resultado("running", "", run_id)
            await self.dormir(intervalo)

    async def executar(self, tarefa: str, sessao: str = "jaime", esperar_s: float = 240.0, instrucoes: str = "") -> Resultado:
        if not self.disponivel:
            return Resultado("erro", erro=self.motivo_indisponivel)
        try:
            run_id = await self.iniciar(tarefa, sessao, instrucoes)
            return await self.acompanhar(run_id, esperar_s)
        except Exception as e:
            return Resultado("erro", erro=self._limpo(e)[:200])


def descrever_aprovacao(ap: dict) -> str:
    """Uma linha para o João decidir: o comando (já mascarado pelo Hermes) e o motivo do alerta."""
    cmd = str(ap.get("command") or "").strip()
    motivo = str(ap.get("description") or ap.get("pattern_key") or "comando perigoso").strip()
    return (f"deixe o Hermes rodar `{cmd[:160]}` ({motivo})" if cmd else f"libere o que o Hermes pediu ({motivo})")
