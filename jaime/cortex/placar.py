"""Placar — o que cada modelo acerta e erra, por tipo de tarefa.

Duas cópias: `vault/.placar.json` (bruto, gitignored, é o que o roteador lê) e `vault/01-Estado/Placar.md`
(tabela legível, para o João e para o próprio Jaime no contexto).

Acerto = tarefa fechada sem correção. Erro = ferramenta falhou, teste quebrou, ou o João corrigiu no turno
seguinte ("errado", "não era isso", "refaz") — nesse caso `corrigir_ultimo()` desfaz o acerto provisório."""
from __future__ import annotations
import json, time
from datetime import datetime
from pathlib import Path

JSON_REL = ".placar.json"
MD_REL = "01-Estado/Placar.md"

class Placar:
    def __init__(self, vault: Path):
        self.vault = Path(vault)
        self.arquivo = self.vault / JSON_REL
        self.dados: dict = {"placar": {}, "ultimo": None, "log": []}
        if self.arquivo.exists():
            try:
                self.dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        self.dados.setdefault("placar", {}); self.dados.setdefault("log", []); self.dados.setdefault("ultimo", None)

    # ── leitura ───────────────────────────────────────
    def _cel(self, modelo: str, tipo: str) -> dict:
        return self.dados["placar"].setdefault(f"{modelo}|{tipo}", {"acertos": 0, "erros": 0, "latencia": 0.0, "custo": 0.0, "n": 0})

    def amostras(self, modelo: str, tipo: str) -> int:
        c = self.dados["placar"].get(f"{modelo}|{tipo}")
        return (c["acertos"] + c["erros"]) if c else 0

    def taxa(self, modelo: str, tipo: str) -> float:
        """Taxa de acerto suavizada (Laplace): modelo sem histórico vale 0,5, não 0."""
        c = self.dados["placar"].get(f"{modelo}|{tipo}") or {"acertos": 0, "erros": 0}
        return (c["acertos"] + 1) / (c["acertos"] + c["erros"] + 2)

    def linha(self, modelo: str, tipo: str) -> str:
        c = self.dados["placar"].get(f"{modelo}|{tipo}")
        if not c or not (c["acertos"] + c["erros"]):
            return "sem histórico"
        n = c["acertos"] + c["erros"]
        return f"{c['acertos']}/{n} acertos ({self.taxa(modelo, tipo):.0%}), latência média {c['latencia'] / max(c['n'], 1):.1f} s, custo US$ {c['custo']:.3f}"

    # ── escrita ───────────────────────────────────────
    def registrar(self, modelo: str, tipo: str, resultado: str, latencia: float = 0.0, custo: float = 0.0, nota: str = "") -> None:
        c = self._cel(modelo, tipo)
        c["acertos" if resultado == "acerto" else "erros"] += 1
        c["latencia"] += float(latencia or 0); c["custo"] += float(custo or 0); c["n"] += 1
        self.dados["ultimo"] = {"modelo": modelo, "tipo": tipo, "resultado": resultado, "t": time.time()}
        self.dados["log"].append({"t": datetime.now().isoformat(timespec="seconds"), "modelo": modelo, "tipo": tipo,
                                  "resultado": resultado, "latencia": round(float(latencia or 0), 2), "nota": nota[:120]})
        self.dados["log"] = self.dados["log"][-200:]
        self._salvar()

    def corrigir_ultimo(self, nota: str = "o João corrigiu") -> dict | None:
        """O turno anterior era um erro: tira o acerto provisório e conta o erro. Devolve o que foi corrigido."""
        u = self.dados.get("ultimo")
        if not u or u.get("resultado") != "acerto" or time.time() - u.get("t", 0) > 1800:
            return None
        c = self._cel(u["modelo"], u["tipo"])
        c["acertos"] = max(0, c["acertos"] - 1); c["erros"] += 1
        u["resultado"] = "erro"
        self.dados["log"].append({"t": datetime.now().isoformat(timespec="seconds"), "modelo": u["modelo"], "tipo": u["tipo"],
                                  "resultado": "erro (correção)", "latencia": 0, "nota": nota[:120]})
        self._salvar()
        return u

    def _salvar(self) -> None:
        self.arquivo.write_text(json.dumps(self.dados, ensure_ascii=False, indent=1), encoding="utf-8")
        self._escrever_md()

    def _escrever_md(self) -> None:
        linhas = ["# Placar dos modelos", "",
                  f"> Gerado por `jaime/cortex/placar.py` em {datetime.now():%d/%m/%Y %H:%M}. Acerto = tarefa fechada sem correção.", "",
                  "| modelo | tipo | acertos | erros | taxa | latência média | custo |", "|---|---|---|---|---|---|---|"]
        for chave, c in sorted(self.dados["placar"].items()):
            modelo, tipo = chave.split("|", 1)
            n = c["acertos"] + c["erros"]
            if not n:
                continue
            linhas.append(f"| {modelo} | {tipo} | {c['acertos']} | {c['erros']} | {self.taxa(modelo, tipo):.0%} | "
                          f"{c['latencia'] / max(c['n'], 1):.1f} s | US$ {c['custo']:.3f} |")
        linhas += ["", "## Últimas correções", ""]
        corr = [l for l in self.dados["log"] if "correção" in l["resultado"]][-10:]
        linhas += [f"- {l['t']} · {l['modelo']} · {l['tipo']} — {l['nota']}" for l in corr] or ["- nenhuma"]
        (self.vault / MD_REL).parent.mkdir(parents=True, exist_ok=True)
        (self.vault / MD_REL).write_text("\n".join(linhas) + "\n", encoding="utf-8")
