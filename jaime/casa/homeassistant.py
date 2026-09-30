"""Casa — Home Assistant pela REST API (token de acesso de longa duração). HomeKit entra via HA (integração HomeKit
Controller), então um único cliente cobre luzes, tomadas, sensores e câmeras. `http` é injetável para teste."""
from __future__ import annotations
import re
import httpx

DOMINIOS_ACAO = {"light": ("turn_on", "turn_off", "toggle"), "switch": ("turn_on", "turn_off", "toggle"),
                 "fan": ("turn_on", "turn_off"), "media_player": ("turn_on", "turn_off", "media_play", "media_pause"),
                 "cover": ("open_cover", "close_cover"), "lock": ("lock", "unlock"), "climate": ("turn_on", "turn_off")}

class Casa:
    def __init__(self, url: str, token: str, http: httpx.AsyncClient | None = None):
        self.url, self.token, self.http = url.rstrip("/"), token, http

    @property
    def ativa(self) -> bool:
        return bool(self.url and self.token)

    async def _req(self, metodo: str, caminho: str, corpo: dict | None = None):
        cliente = self.http or httpx.AsyncClient(timeout=15)
        try:
            r = await cliente.request(metodo, f"{self.url}/api/{caminho}", json=corpo,
                                      headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
            r.raise_for_status()
            return r.json() if r.content else {}
        finally:
            if cliente is not self.http:
                await cliente.aclose()

    async def template(self, t: str) -> str:
        """Renderiza um template do HA (/api/template devolve TEXTO, não JSON) — é por aqui que se descobre a que
        integração uma entidade pertence e o device_id de um Echo."""
        cliente = self.http or httpx.AsyncClient(timeout=15)
        try:
            r = await cliente.request("POST", f"{self.url}/api/template", json={"template": t},
                                      headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
            r.raise_for_status()
            return r.text if hasattr(r, "text") else ""
        finally:
            if cliente is not self.http:
                await cliente.aclose()

    async def dominios_de_servico(self) -> set[str]:
        """Quais domínios de serviço existem (ex.: 'alexa_devices', 'notify', 'scene')."""
        return {d.get("domain", "") for d in (await self._req("GET", "services") or [])}

    async def servicos_do_dominio(self, dominio: str) -> set[str]:
        for d in (await self._req("GET", "services") or []):
            if d.get("domain") == dominio:
                return set((d.get("services") or {}).keys())
        return set()

    async def estados(self, filtro: str = "") -> list[dict]:
        est = await self._req("GET", "states")
        rx = re.compile(re.escape(filtro), re.I) if filtro else None
        out = []
        for e in est:
            nome = (e.get("attributes") or {}).get("friendly_name", e.get("entity_id", ""))
            if rx and not (rx.search(nome) or rx.search(e.get("entity_id", ""))):
                continue
            out.append({"id": e.get("entity_id", ""), "nome": nome, "estado": e.get("state", ""),
                        "unidade": (e.get("attributes") or {}).get("unit_of_measurement", "")})
        return out

    async def achar(self, nome: str, dominio: str | None = None) -> dict | None:
        """Entidade cujo nome amigável mais parece com `nome` (ex.: 'luz do escritório' → light.escritorio)."""
        cand = await self.estados()
        tokens = {t for t in re.findall(r"\w+", nome.lower()) if len(t) > 2 and t not in ("luz", "das", "dos", "the")}
        melhor, nota = None, 0
        for e in cand:
            if dominio and not e["id"].startswith(dominio + "."):
                continue
            alvo = f"{e['nome']} {e['id']}".lower()
            n = sum(1 for t in tokens if t in alvo)
            if n > nota:
                melhor, nota = e, n
        return melhor if nota else None

    async def servico(self, dominio: str, acao: str, entity_id: str, dados: dict | None = None) -> str:
        await self._req("POST", f"services/{dominio}/{acao}", {"entity_id": entity_id, **(dados or {})})
        return f"{acao} → {entity_id}"

    async def ligar(self, nome: str) -> str:
        e = await self.achar(nome)
        if not e:
            return f"não achei nada parecido com '{nome}'"
        dom = e["id"].split(".")[0]
        return await self.servico(dom, "turn_on" if dom in DOMINIOS_ACAO else "turn_on", e["id"])

    async def desligar(self, nome: str) -> str:
        e = await self.achar(nome)
        if not e:
            return f"não achei nada parecido com '{nome}'"
        return await self.servico(e["id"].split(".")[0], "turn_off", e["id"])

    async def snapshot_camera(self, entity_id: str) -> bytes:
        cliente = self.http or httpx.AsyncClient(timeout=20)
        try:
            r = await cliente.get(f"{self.url}/api/camera_proxy/{entity_id}", headers={"Authorization": f"Bearer {self.token}"})
            r.raise_for_status(); return r.content
        finally:
            if cliente is not self.http:
                await cliente.aclose()

def texto_estados(lista: list[dict]) -> str:
    if not lista:
        return "Nada encontrado."
    return "\n".join(f"- {e['nome']} ({e['id']}): {e['estado']}{(' ' + e['unidade']) if e['unidade'] else ''}" for e in lista[:40])
