"""Espelho do cérebro no Notion — para outra máquina (ou o celular do João) ler o mesmo estado.

Requer uma integração interna (NOTION_TOKEN) com acesso à página raiz "Jaime — Cérebro compartilhado".
IDs criados em 14/09/2026 já estão no .env.example. Tudo aqui é best-effort: falha de rede não trava o Jaime."""
from __future__ import annotations
import json, re
from datetime import date
from pathlib import Path
import httpx
from ..config import Settings
from .vault import Vault
from .estado import Estado, maquina

API = "https://api.notion.com/v1"

class NotionSync:
    def __init__(self, s: Settings, vault: Vault, estado: Estado):
        self.s, self.vault, self.estado = s, vault, estado
        self.ativo = bool(s.notion_token and s.notion_root)
        self._cache = vault.root / "01-Estado" / "notion.json"

    def _h(self) -> dict:
        return {"Authorization": f"Bearer {self.s.notion_token}", "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"}

    @staticmethod
    def _rt(texto: str) -> dict:
        return {"rich_text": [{"text": {"content": texto[:1900]}}]}

    @staticmethod
    def _paragrafos(md: str) -> list[dict]:
        blocos = []
        for linha in md.splitlines():
            if not linha.strip():
                continue
            if linha.startswith("## "):
                blocos.append({"object": "block", "type": "heading_2",
                               "heading_2": {"rich_text": [{"text": {"content": linha[3:]}}]}})
            elif linha.startswith("# "):
                continue
            else:
                blocos.append({"object": "block", "type": "paragraph",
                               "paragraph": {"rich_text": [{"text": {"content": linha.lstrip("> ")[:1900]}}]}})
        return blocos[:95]

    def _ids(self) -> dict:
        return json.loads(self._cache.read_text()) if self._cache.exists() else {}

    async def sincronizar_estado(self):
        if not self.ativo:
            return
        async with httpx.AsyncClient(timeout=20, headers=self._h()) as c:
            ids = self._ids()
            md = self.estado.ler()
            if "estado_page" not in ids:
                r = await c.post(f"{API}/pages", json={
                    "parent": {"page_id": self.s.notion_root}, "icon": {"emoji": "🫀"},
                    "properties": {"title": {"title": [{"text": {"content": "Estado do Jaime"}}]}},
                    "children": self._paragrafos(md)})
                r.raise_for_status(); ids["estado_page"] = r.json()["id"]
                self._cache.write_text(json.dumps(ids)); return
            pid = ids["estado_page"]
            filhos = (await c.get(f"{API}/blocks/{pid}/children?page_size=100")).json().get("results", [])
            for b in filhos:
                await c.delete(f"{API}/blocks/{b['id']}")
            await c.patch(f"{API}/blocks/{pid}/children", json={"children": self._paragrafos(md)})

    async def sincronizar_diario(self):
        if not (self.ativo and self.s.notion_db_diario):
            return
        md = self.vault.read(self.vault.daily_rel())
        if not md:
            return
        sec = lambda t: (md.split(f"## {t}", 1)[1].split("\n## ", 1)[0].strip() if f"## {t}" in md else "")
        hoje = date.today().isoformat()
        async with httpx.AsyncClient(timeout=20, headers=self._h()) as c:
            q = await c.post(f"{API}/databases/{self.s.notion_db_diario}/query",
                             json={"filter": {"property": "Dia", "title": {"equals": hoje}}})
            props = {"Feito": self._rt(sec("Feito")), "Decisões": self._rt(sec("Decisões")),
                     "Pendente": self._rt(sec("Pendente")), "Máquina": self._rt(maquina()["host"]),
                     "Data": {"date": {"start": hoje}}}
            res = q.json().get("results", [])
            if res:
                await c.patch(f"{API}/pages/{res[0]['id']}", json={"properties": props})
            else:
                props["Dia"] = {"title": [{"text": {"content": hoje}}]}
                await c.post(f"{API}/pages", json={"parent": {"database_id": self.s.notion_db_diario}, "properties": props})

    async def sincronizar_tarefas(self):
        if not (self.ativo and self.s.notion_db_tarefas):
            return
        ids = self._ids(); enviadas = set(ids.get("tarefas", []))
        async with httpx.AsyncClient(timeout=20, headers=self._h()) as c:
            for linha in self.vault.tarefas_abertas():
                if linha in enviadas:
                    continue
                desc = re.sub(r"^- \[ \] ", "", linha)
                proj = re.search(r"@(\S+)", desc); prazo = re.search(r"⏳\s*(\d{4}-\d{2}-\d{2})", desc)
                desc = re.sub(r"\s*@\S+|\s*⏳\s*\S+", "", desc).strip()
                props = {"Tarefa": {"title": [{"text": {"content": desc}}]}, "Status": {"select": {"name": "Aberta"}},
                         "Origem": {"select": {"name": "Jaime"}}}
                if proj: props["Projeto"] = {"select": {"name": proj.group(1)}}
                if prazo: props["Prazo"] = {"date": {"start": prazo.group(1)}}
                r = await c.post(f"{API}/pages", json={"parent": {"database_id": self.s.notion_db_tarefas}, "properties": props})
                if r.status_code < 300:
                    enviadas.add(linha)
        ids["tarefas"] = sorted(enviadas); self._cache.write_text(json.dumps(ids))

    async def registrar_sessao(self, canal: str, tema: str, resultado: str):
        if not (self.ativo and self.s.notion_db_conversas):
            return
        async with httpx.AsyncClient(timeout=20, headers=self._h()) as c:
            await c.post(f"{API}/pages", json={"parent": {"database_id": self.s.notion_db_conversas}, "properties": {
                "Sessão": {"title": [{"text": {"content": f"{date.today()} · {self.estado.sessao_id}"}}]},
                "Data": {"date": {"start": date.today().isoformat()}}, "Canal": {"select": {"name": canal}},
                "Tema": self._rt(tema), "Resultado": self._rt(resultado), "Máquina": self._rt(maquina()["host"]),
                "Turnos": {"number": self.estado.turnos}}})

    async def tudo(self):
        for fn in (self.sincronizar_estado, self.sincronizar_diario, self.sincronizar_tarefas):
            try:
                await fn()
            except Exception as e:  # nunca derruba o Jaime por causa do espelho
                print(f"[notion] {fn.__name__}: {e}")
