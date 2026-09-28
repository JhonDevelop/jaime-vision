"""IA local — endpoint OpenAI-compatible (Ollama, LM Studio, llama.cpp, vLLM; PAIR/OpenShell como proxy opcional).

O que "não gasta tokens" quer dizer aqui: não há cobrança POR TOKEN de API quando a inferência roda em hardware
próprio. A máquina continua processando tokens e custa GPU, energia, memória e tempo.

Regras (docs/ESPACIAL.md §IA local):
- desligado por padrão (`JAIME_LOCAL_AI=off`); o Central (Claude) continua sendo o cérebro — o local entra por
  ROTA EXPLÍCITA (`JAIME_LOCAL_AI_TIPOS`, ou o João pedindo "pelo modelo local"), depois de benchmark no placar;
- endpoint só de host configurado pelo dono (nunca URL vinda da fala/prompt); fora do loopback exige HTTPS —
  HTTP na LAN só com token E `JAIME_LOCAL_AI_LAN_HTTP=on` (vai em claro); `inference.local`/OpenShell entram pela
  lista do dono como qualquer host de rede;
- `JAIME_LOCAL_AI_STRICT=on`: uma chamada roteada ao local que falha NÃO cai silenciosamente na nuvem;
- produz só TEXTO (sem as mãos do Agent SDK): as ações continuam pelo cliente da Anthropic + Vigia;
- disjuntor: falhas seguidas abrem o circuito por um tempo (um servidor caído não segura cada turno 30 s).
Mac Intel não roda CUDA; um nó RTX da frota (Windows/Linux) serve o endpoint e o Jaime aponta para ele.
"""
from __future__ import annotations
import asyncio, os, time
from urllib.parse import urlsplit
from .base import Resposta, Cronometro

HOSTS_LOCAIS = {"localhost", "127.0.0.1", "::1"}      # loopback DE VERDADE; ".local"/".internal" resolvem na rede (mDNS)


class ProvedorLocal:
    nome = "local"

    def __init__(self, base_url: str = "", modelo: str = "", ligado: bool = False, estrito: bool = True,
                 hosts_extra: set[str] | None = None, token: str = "", timeout: float = 30.0, lan_http: bool = False,
                 max_concorrencia: int = 2, falhas_para_abrir: int = 3, aberto_por_s: float = 60.0,
                 transporte=None, relogio=time.monotonic):
        self.base_url, self.modelo, self.ligado, self.estrito = base_url.rstrip("/"), modelo, ligado, estrito
        self.token, self.timeout, self.lan_http = token, timeout, lan_http
        self.hosts = HOSTS_LOCAIS | set(hosts_extra or ())
        self._sem = asyncio.Semaphore(max_concorrencia)
        self.falhas_para_abrir, self.aberto_por_s = falhas_para_abrir, aberto_por_s
        self._falhas, self._aberto_ate = 0, 0.0
        self._transporte, self.relogio = transporte, relogio
        self.motivo_indisponivel = self._validar()

    @classmethod
    def do_ambiente(cls, env=None, **kw) -> "ProvedorLocal":
        e = os.environ if env is None else env
        g = lambda k, d="": (e.get(k, "") or "").strip() or d
        on = lambda v: v.lower() in ("1", "on", "true", "sim")
        try:
            timeout = float(g("JAIME_LOCAL_AI_TIMEOUT_S", "30").replace(",", "."))
        except ValueError:
            timeout = 30.0
        return cls(base_url=g("JAIME_LOCAL_AI_BASE_URL", "http://127.0.0.1:11434/v1"), modelo=g("JAIME_LOCAL_AI_MODEL"),
                   ligado=on(g("JAIME_LOCAL_AI", "off")), estrito=on(g("JAIME_LOCAL_AI_STRICT", "on")),
                   hosts_extra={h.strip() for h in g("JAIME_LOCAL_AI_HOSTS").split(",") if h.strip()},
                   token=g("JAIME_LOCAL_AI_TOKEN"), timeout=timeout, lan_http=on(g("JAIME_LOCAL_AI_LAN_HTTP", "off")), **kw)

    def _validar(self) -> str:
        if not self.ligado:
            return "JAIME_LOCAL_AI=off"
        if not self.modelo:
            return "JAIME_LOCAL_AI_MODEL vazio (escolha o modelo depois do benchmark)"
        u = urlsplit(self.base_url)
        if u.scheme not in ("http", "https") or not u.hostname:
            return "URL inválida"
        if u.hostname not in self.hosts:
            return f"host {u.hostname} não está na lista do dono (JAIME_LOCAL_AI_HOSTS)"
        loopback = u.hostname in HOSTS_LOCAIS
        if not loopback and u.scheme != "https":
            # HTTP na LAN manda o prompt (e o token) em claro: só com token E opt-in explícito do dono
            if not (self.token and self.lan_http):
                return "fora desta máquina exige HTTPS (ou JAIME_LOCAL_AI_TOKEN + JAIME_LOCAL_AI_LAN_HTTP=on, sabendo que vai em claro)"
        return ""

    @property
    def disponivel(self) -> bool:
        return not self.motivo_indisponivel

    @property
    def circuito_aberto(self) -> bool:
        return self.relogio() < self._aberto_ate

    def _cliente(self):
        import httpx
        h = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        return httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout, headers=h, transport=self._transporte)

    async def saude(self) -> tuple[bool, str]:
        if not self.disponivel:
            return False, self.motivo_indisponivel
        try:
            async with self._cliente() as c:
                r = await c.get("/models")
            if r.status_code != 200:
                return False, f"HTTP {r.status_code}"
            ids = [m.get("id") for m in (r.json().get("data") or [])]
            return (self.modelo in ids, "ok" if self.modelo in ids else f"modelo {self.modelo} não carregado (tem: {', '.join(ids[:5])})")
        except Exception as e:
            return False, f"{type(e).__name__}"

    async def responder(self, prompt: str, contexto: str = "", ferramentas: list[str] | None = None) -> Resposta:
        if not self.disponivel:
            return Resposta("", self.nome, self.modelo, erro=self.motivo_indisponivel)
        if self.circuito_aberto:
            return Resposta("", self.nome, self.modelo, erro="circuito aberto (falhas seguidas) — tentando de novo em instantes")
        msgs = ([{"role": "system", "content": contexto}] if contexto else []) + [{"role": "user", "content": prompt}]
        try:
            async with self._sem:
                with Cronometro() as cr:
                    async with self._cliente() as c:
                        r = await c.post("/chat/completions", json={"model": self.modelo, "messages": msgs,
                                                                    "stream": False, "temperature": 0.2})
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
            d = r.json()
            texto = (d["choices"][0]["message"].get("content") or "").strip()
            uso = d.get("usage") or {}
            self._falhas = 0
            # custo por token = 0 (hardware próprio); energia/GPU não entram no placar como US$
            return Resposta(texto, self.nome, f"local:{self.modelo}", cr.s, 0.0,
                            int(uso.get("prompt_tokens", 0)) + int(uso.get("completion_tokens", 0)))
        except Exception as e:
            self._falhas += 1
            if self._falhas >= self.falhas_para_abrir:
                self._aberto_ate = self.relogio() + self.aberto_por_s
            return Resposta("", self.nome, self.modelo, erro=f"{type(e).__name__}: {str(e)[:160]}")
