"""Finanças pessoais — um livro-caixa simples que o J.A.I.M.E mantém para o João.

Nada de ERP: só registrar o que entra e o que sai ("gastei 50 de gasolina", "recebi 2 mil da Oldsen"), ver o saldo,
os gastos por categoria e a evolução por mês, e dar os dados para o painel do HUD desenhar em gráfico. Guardado num
CSV dentro do vault (`70-Financas/lancamentos.csv`) — fácil de ler, de versionar e de exportar para planilha."""
from __future__ import annotations
import csv, io, re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

ARQUIVO = "70-Financas/lancamentos.csv"
CABECALHO = ["data", "tipo", "valor", "categoria", "descricao"]
CATEGORIAS = ["mercado", "combustível", "alimentação", "moradia", "saúde", "assinaturas", "transporte", "lazer",
              "educação", "impostos", "salário", "vendas", "investimento", "transferência", "outros"]

def _num(txt: str) -> float:
    """'1.234,56' | 'R$ 50' | '2 mil' → float."""
    t = (txt or "").lower().replace("r$", "").strip()
    mult = 1
    if re.search(r"\bmil\b", t):
        mult = 1000; t = re.sub(r"\bmil\b", "", t)
    t = t.replace(".", "").replace(",", ".")
    m = re.search(r"-?\d+(\.\d+)?", t)
    return round(float(m.group(0)) * mult, 2) if m else 0.0

class Lancamento:
    __slots__ = ("data", "tipo", "valor", "categoria", "descricao")
    def __init__(self, data: str, tipo: str, valor: float, categoria: str, descricao: str):
        self.data, self.tipo, self.valor, self.categoria, self.descricao = data, tipo, round(valor, 2), categoria, descricao
    def linha(self) -> list[str]:
        return [self.data, self.tipo, f"{self.valor:.2f}", self.categoria, self.descricao]
    def dados(self) -> dict:
        return {"data": self.data, "tipo": self.tipo, "valor": self.valor, "categoria": self.categoria, "descricao": self.descricao}

class Livro:
    def __init__(self, vault):
        self.vault = vault

    def _ler(self) -> list[Lancamento]:
        try:
            txt = self.vault.read(ARQUIVO)
        except Exception:
            txt = ""
        out = []
        for row in csv.DictReader(io.StringIO(txt)):
            try:
                out.append(Lancamento(row["data"], row["tipo"], float(row["valor"]), row.get("categoria", "outros"), row.get("descricao", "")))
            except (KeyError, ValueError):
                continue
        return out

    def _gravar(self, lancs: list[Lancamento]) -> None:
        buf = io.StringIO(); w = csv.writer(buf); w.writerow(CABECALHO)
        for l in sorted(lancs, key=lambda x: x.data):
            w.writerow(l.linha())
        self.vault.write(ARQUIVO, buf.getvalue())

    # ── registrar ──────────────────────────────────────
    def registrar(self, valor, categoria: str = "outros", descricao: str = "", tipo: str = "", quando: str = "") -> Lancamento:
        v = _num(valor) if isinstance(valor, str) else round(float(valor), 2)
        if not tipo:
            tipo = "entrada" if (categoria in ("salário", "vendas", "investimento") or v > 0 and "receb" in descricao.lower()) else "saída"
        v = abs(v)
        cat = categoria if categoria in CATEGORIAS else self._adivinhar_categoria(descricao) or (categoria or "outros")
        dia = quando or date.today().isoformat()
        l = Lancamento(dia, tipo, v, cat, descricao.strip())
        lancs = self._ler(); lancs.append(l); self._gravar(lancs)
        try:
            self.vault.diario(f"Finança: {tipo} R$ {v:.2f} · {cat}" + (f" · {descricao[:60]}" if descricao else ""), "Log")
        except Exception:
            pass
        return l

    @staticmethod
    def _adivinhar_categoria(descricao: str) -> str:
        d = (descricao or "").lower()
        for cat, chaves in {"combustível": ["gasolina", "álcool", "etanol", "diesel", "posto", "combustí"],
                            "mercado": ["mercado", "supermercado", "feira", "compras"],
                            "alimentação": ["ifood", "restaurante", "lanche", "almoço", "jantar", "comida", "padaria"],
                            "assinaturas": ["spotify", "netflix", "assinatura", "openai", "chatgpt", "google", "icloud"],
                            "transporte": ["uber", "99", "ônibus", "metrô", "estacionamento"],
                            "salário": ["salário", "salario"], "vendas": ["venda", "vendi", "recebi", "cliente"]}.items():
            if any(k in d for k in chaves):
                return cat
        return ""

    # ── consultas ──────────────────────────────────────
    def resumo(self, mes: str = "") -> dict:
        """Saldo, entradas, saídas, por categoria e por mês. `mes`='2026-09' filtra."""
        lancs = [l for l in self._ler() if (not mes or l.data.startswith(mes))]
        entra = sum(l.valor for l in lancs if l.tipo == "entrada")
        sai = sum(l.valor for l in lancs if l.tipo == "saída")
        por_cat = defaultdict(float)
        for l in lancs:
            if l.tipo == "saída":
                por_cat[l.categoria] += l.valor
        por_mes = defaultdict(lambda: {"entrada": 0.0, "saída": 0.0})
        for l in self._ler():
            por_mes[l.data[:7]][l.tipo] += l.valor
        return {"saldo": round(entra - sai, 2), "entradas": round(entra, 2), "saidas": round(sai, 2), "lancamentos": len(lancs),
                "por_categoria": sorted(([c, round(v, 2)] for c, v in por_cat.items()), key=lambda x: -x[1]),
                "por_mes": [[m, round(d["entrada"], 2), round(d["saída"], 2)] for m, d in sorted(por_mes.items())],
                "ultimos": [l.dados() for l in sorted(lancs, key=lambda x: x.data)[-10:]]}

    def texto_resumo(self, mes: str = "") -> str:
        r = self.resumo(mes or date.today().strftime("%Y-%m"))
        top = "; ".join(f"{c} R$ {v:.0f}" for c, v in r["por_categoria"][:4])
        return (f"No mês: entrou R$ {r['entradas']:.2f}, saiu R$ {r['saidas']:.2f}, saldo R$ {r['saldo']:.2f}."
                + (f" Mais gastei em: {top}." if top else " Ainda sem gastos registrados."))
