"""Problemas em aberto — `90-Estudo/Problemas.md`.

Cada entrada tem ID, título, origem, contexto e a lista de tentativas. Formato (uma seção por problema):

    ## P-0003 · Deploy do BUB falha no pod install · aberto · 2026-09-15
    - origem: ferramenta_falhou
    - contexto: `pod install` devolve "CocoaPods could not find compatible versions"
    - tentativas: 1
    ### Tentativas
    - 2026-09-15 10:12 — tentou `pod repo update`; falta testar com Ruby 3.2

Resolvido: o cabeçalho vira `· resolvido · <data>` e ganha `- conhecimento: 50-Conhecimento/<slug>.md`."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from ..brain.vault import Vault
from ..emocao.perguntas import similaridade

ARQUIVO = "90-Estudo/Problemas.md"
ARQUIVO_PRIORIDADES = "90-Estudo/Prioridades.md"      # escrito por jaime/telemetria/prioridades.py no fecha-dia
PRIORIDADE_RX = re.compile(r"^\|\s*(P-\d{4})\s*\|[^|]*\|\s*([\d.]+)\s*\|", re.M)
CABECALHO = "# Problemas em aberto\n\n"
SECAO_RX = re.compile(r"^## (P-\d{4}) · (.+?) · (aberto|resolvido) · (\d{4}-\d{2}-\d{2})\s*$", re.M)
ORIGENS = ("ferramenta_falhou", "teste_quebrou", "joao_pediu", "sem_resposta", "correcao", "manual")

@dataclass
class Problema:
    id: str
    titulo: str
    estado: str
    aberto_em: date
    origem: str = "manual"
    contexto: str = ""
    tentativas: list[str] = field(default_factory=list)
    conhecimento: str = ""

    def secao(self) -> str:
        linhas = [f"## {self.id} · {self.titulo} · {self.estado} · {self.aberto_em.isoformat()}",
                  f"- origem: {self.origem}", f"- contexto: {self.contexto.replace(chr(10), ' ')[:600]}",
                  f"- tentativas: {len(self.tentativas)}"]
        if self.conhecimento:
            linhas.append(f"- conhecimento: {self.conhecimento}")
        linhas.append("### Tentativas")
        linhas += self.tentativas or ["- (nenhuma)"]
        return "\n".join(linhas) + "\n"

def ler_prioridades(texto: str) -> dict[str, float]:
    """Linhas `| P-0003 | título | 4.20 | ...` → {"P-0003": 4.2}."""
    out = {}
    for pid, valor in PRIORIDADE_RX.findall(texto or ""):
        try:
            out[pid] = float(valor)
        except ValueError:
            pass
    return out

class Problemas:
    def __init__(self, vault: Vault):
        self.vault = vault

    # ── leitura ───────────────────────────────────────
    def todos(self) -> list[Problema]:
        txt = self.vault.read(ARQUIVO)
        out = []
        partes = SECAO_RX.split(txt)
        # split devolve [prefixo, id, titulo, estado, data, corpo, id, ...]
        for i in range(1, len(partes), 5):
            pid, titulo, estado, data, corpo = partes[i], partes[i + 1], partes[i + 2], partes[i + 3], partes[i + 4]
            p = Problema(pid, titulo.strip(), estado, datetime.strptime(data, "%Y-%m-%d").date())
            if (m := re.search(r"^- origem:\s*(.+)$", corpo, re.M)): p.origem = m.group(1).strip()
            if (m := re.search(r"^- contexto:\s*(.*)$", corpo, re.M)): p.contexto = m.group(1).strip()
            if (m := re.search(r"^- conhecimento:\s*(.+)$", corpo, re.M)): p.conhecimento = m.group(1).strip()
            if "### Tentativas" in corpo:
                bloco = corpo.split("### Tentativas", 1)[1]
                p.tentativas = [l.rstrip() for l in bloco.splitlines() if l.startswith("- ") and "(nenhuma)" not in l]
            out.append(p)
        return out

    def abertos(self) -> list[Problema]:
        return [p for p in self.todos() if p.estado == "aberto"]

    def por_id(self, pid: str) -> Problema | None:
        return next((p for p in self.todos() if p.id == pid), None)

    def prioridades(self) -> dict[str, float]:
        """{id: prioridade} lido de Prioridades.md (frequência × taxa de erro × tempo sem estudar). Vazio se não existe."""
        return ler_prioridades(self.vault.read(ARQUIVO_PRIORIDADES))

    def proximo(self) -> Problema | None:
        """O que estudar agora: o aberto de maior prioridade em Prioridades.md (fase 3, §4). Sem o arquivo — ou
        sem nenhum dos abertos nele — cai na heurística antiga: menos tentativas primeiro; empate → o mais antigo."""
        ab = self.abertos()
        if not ab:
            return None
        prio = self.prioridades()
        if any(p.id in prio for p in ab):
            return max(ab, key=lambda p: (prio.get(p.id, 0.0), -len(p.tentativas), -p.aberto_em.toordinal()))
        return min(ab, key=lambda p: (len(p.tentativas), p.aberto_em))

    # ── escrita ───────────────────────────────────────
    def _salvar(self, lista: list[Problema]) -> None:
        self.vault.write(ARQUIVO, CABECALHO + "\n".join(p.secao() for p in lista))

    def abrir(self, titulo: str, contexto: str = "", origem: str = "manual") -> Problema:
        """Abre um problema; se já existe um aberto parecido, devolve o existente (não duplica)."""
        lista = self.todos()
        for p in lista:
            if p.estado == "aberto" and similaridade(p.titulo, titulo) >= 0.7:
                return p
        n = max((int(p.id[2:]) for p in lista), default=0) + 1
        p = Problema(f"P-{n:04d}", titulo.strip()[:120], "aberto", date.today(), origem if origem in ORIGENS else "manual", contexto.strip())
        lista.append(p); self._salvar(lista)
        return p

    def registrar_tentativa(self, pid: str, tentou: str, falta: str = "") -> None:
        lista = self.todos()
        for p in lista:
            if p.id == pid:
                p.tentativas.append(f"- {datetime.now():%Y-%m-%d %H:%M} — {tentou.strip()}" + (f"; falta {falta.strip()}" if falta else ""))
        self._salvar(lista)

    def resolver(self, pid: str, conhecimento_rel: str) -> None:
        lista = self.todos()
        for p in lista:
            if p.id == pid:
                p.estado = "resolvido"; p.conhecimento = conhecimento_rel
        self._salvar(lista)
