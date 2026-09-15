"""Orçamento diário do Jaime — quanto ele pode gastar por dia, e em quê.

`JAIME_ORCAMENTO_DIA_USD` (0 ou vazio = sem teto) dividido em três fatias fixas (§5 da fase 3):
demandas 60% · estudo 25% · criação 15%. O gasto entra pelo custo de cada turno — o placar já recebe
`custo` em `registrar()`, então `ligar_ao_placar()` envolve esse método e classifica: modelo "estudo" → estudo;
modelos de criação (prefixo "criacao") são contabilizados pela própria Vitrine via `gastar()`; o resto é demanda.

Regra de bloqueio: demanda NUNCA é bloqueada — quando o dia acaba, o Jaime só atende demandas. Estudo e criação
param quando a própria fatia esgota (sem empréstimo entre fatias: previsível e fácil de explicar ao João).

Persistência legível em `vault/01-Estado/Orcamento.md` (relido no boot, para um reinício não zerar o dia);
o dia vira à meia-noite pelo `hoje()` injetável — os testes passam um relógio falso."""
from __future__ import annotations
import re
from datetime import date, datetime
from pathlib import Path

ARQUIVO_REL = "01-Estado/Orcamento.md"
FATIAS = ("demanda", "estudo", "criacao")
SPLIT = {"demanda": 0.60, "estudo": 0.25, "criacao": 0.15}
NOMES = {"demanda": "demandas", "estudo": "estudo", "criacao": "criação"}
HISTORICO_DIAS = 14
LINHA_RX = re.compile(r"^\|\s*(demandas|estudo|criação)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|", re.M)
DIA_RX = re.compile(r"^>\s*dia\s+(\d{4}-\d{2}-\d{2})", re.M)
HIST_RX = re.compile(r"^- (\d{4}-\d{2}-\d{2}) · (.+)$", re.M)

def classificar_gasto(modelo: str, tipo: str = "") -> str | None:
    """Em qual fatia cai um registro do placar. None = não contabiliza aqui (a Vitrine faz o dela)."""
    m = (modelo or "").lower()
    if m.startswith("estudo"):
        return "estudo"
    if m.startswith(("criacao", "criação", "vontade", "vitrine")):
        return None
    return "demanda"

class Orcamento:
    def __init__(self, vault: Path, dia_usd: float = 0.0, split: dict | None = None, hoje=date.today, agora=datetime.now):
        self.vault = Path(vault)
        self.dia_usd = max(0.0, float(dia_usd or 0))
        self.split = dict(split or SPLIT)
        self.hoje, self.agora = hoje, agora
        self.dia: date = self.hoje()
        self.gasto: dict[str, float] = {f: 0.0 for f in FATIAS}
        self.historico: list[str] = []
        self._carregar()

    # ── consulta ──────────────────────────────────────
    @property
    def ativo(self) -> bool:
        return self.dia_usd > 0

    def cota(self, fatia: str) -> float:
        return round(self.dia_usd * self.split.get(fatia, 0.0), 4)

    def restante(self, fatia: str) -> float:
        self._virar_dia()
        return max(0.0, self.cota(fatia) - self.gasto.get(fatia, 0.0))

    def pode(self, tipo: str) -> bool:
        """'demanda' sempre pode. 'estudo'/'criacao' só enquanto a fatia tem saldo. Sem teto configurado, tudo pode."""
        self._virar_dia()
        if not self.ativo or tipo == "demanda":
            return True
        return self.restante(tipo) > 1e-9

    def total(self) -> float:
        self._virar_dia()
        return round(sum(self.gasto.values()), 4)

    def estado(self) -> dict:
        self._virar_dia()
        return {"dia": self.dia.isoformat(), "teto": self.dia_usd, "total": self.total(),
                "fatias": {f: {"cota": self.cota(f), "gasto": round(self.gasto[f], 4), "pode": self.pode(f)} for f in FATIAS}}

    def resumo(self) -> str:
        e = self.estado()
        if not self.ativo:
            return f"sem teto diário (gasto hoje US$ {e['total']:.2f})"
        partes = [f"{NOMES[f]} {e['fatias'][f]['gasto']:.2f}/{e['fatias'][f]['cota']:.2f}" for f in FATIAS]
        return f"US$ {e['total']:.2f} de {self.dia_usd:.2f} · " + " · ".join(partes)

    # ── gasto ─────────────────────────────────────────
    def gastar(self, tipo: str, usd: float) -> float:
        """Soma `usd` à fatia e persiste. Devolve o restante da fatia."""
        self._virar_dia()
        if tipo not in FATIAS:
            tipo = "demanda"
        usd = float(usd or 0)
        if usd > 0:
            self.gasto[tipo] = round(self.gasto[tipo] + usd, 6)
            self._salvar()
        return self.restante(tipo)

    def ligar_ao_placar(self, placar) -> None:
        """Envolve `placar.registrar` para que todo custo de turno entre no orçamento (um funil só)."""
        original = placar.registrar
        if getattr(original, "_orcamento", None) is self:
            return
        def registrar(modelo, tipo, resultado, latencia=0.0, custo=0.0, nota=""):
            original(modelo, tipo, resultado, latencia, custo, nota)
            fatia = classificar_gasto(modelo, tipo)
            if fatia and custo:
                self.gastar(fatia, custo)
        registrar._orcamento = self          # type: ignore[attr-defined]
        placar.registrar = registrar

    # ── dia ───────────────────────────────────────────
    def _virar_dia(self) -> None:
        h = self.hoje()
        if h == self.dia:
            return
        if any(v > 0 for v in self.gasto.values()):
            self.historico.append(f"{self.dia.isoformat()} · " + " · ".join(f"{NOMES[f]} {self.gasto[f]:.2f}" for f in FATIAS)
                                  + f" · total {sum(self.gasto.values()):.2f}")
            self.historico = self.historico[-HISTORICO_DIAS:]
        self.dia = h
        self.gasto = {f: 0.0 for f in FATIAS}
        self._salvar()

    # ── persistência ──────────────────────────────────
    def _arquivo(self) -> Path:
        return self.vault / ARQUIVO_REL

    def _carregar(self) -> None:
        p = self._arquivo()
        if not p.exists():
            return
        txt = p.read_text(encoding="utf-8")
        m = DIA_RX.search(txt)
        self.historico = [f"{d} · {resto}" for d, resto in HIST_RX.findall(txt)][-HISTORICO_DIAS:]
        if not m:
            return
        try:
            dia = date.fromisoformat(m.group(1))
        except ValueError:
            return
        if dia != self.hoje():
            return                                   # arquivo de outro dia: começa zerado (histórico fica)
        self.dia = dia
        inv = {v: k for k, v in NOMES.items()}
        for nome, _cota, gasto in LINHA_RX.findall(txt):
            self.gasto[inv[nome]] = float(gasto)

    def _salvar(self) -> None:
        linhas = ["# Orçamento do dia", "",
                  f"> dia {self.dia.isoformat()} · teto US$ {self.dia_usd:.2f} (JAIME_ORCAMENTO_DIA_USD; 0 = sem teto) · "
                  f"atualizado {self.agora():%H:%M} por `jaime/cortex/orcamento.py`. Quando a fatia acaba, o Jaime só atende demandas.", "",
                  "| fatia | cota | gasto | restante | pode? |", "|---|---|---|---|---|"]
        for f in FATIAS:
            pode = "sempre" if f == "demanda" else ("sim" if (not self.ativo or self.cota(f) - self.gasto[f] > 1e-9) else "não")
            linhas.append(f"| {NOMES[f]} | {self.cota(f):.2f} | {self.gasto[f]:.4f} | {max(0.0, self.cota(f) - self.gasto[f]):.2f} | {pode} |")
        linhas += ["", f"Total hoje: US$ {sum(self.gasto.values()):.4f}", "", f"## Histórico (últimos {HISTORICO_DIAS} dias)", ""]
        linhas += [f"- {h}" for h in self.historico] or ["- (ainda nenhum dia fechado)"]
        p = self._arquivo()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(linhas) + "\n", encoding="utf-8")
