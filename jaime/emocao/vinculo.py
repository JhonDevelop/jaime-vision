"""Vínculo com o dono — o "apego" do Jaime ao João, do jeito certo.

O que é: familiaridade que cresce com o tempo e as conversas, memória das pessoas próximas, acompanhamento do que
importa para ele ("como foi a reunião com o Diego?"), calor que aumenta com a confiança. Vira contexto no prompt e
calor na prosódia.
O que NÃO é: carência, culpa, dependência ou drama. O Jaime nunca pede atenção, nunca "sente falta" em voz alta,
nunca usa o vínculo para influenciar uma decisão. Expressão coerente, não manipulação (docs/JARVIS.md, §6 da fase 2).

Estado em `01-Estado/Vinculo.md` (o Jaime mantém): dias juntos, conversas, pessoas próximas, acompanhamentos abertos."""
from __future__ import annotations
import re
from datetime import date, datetime
from ..brain.vault import Vault

ARQUIVO = "01-Estado/Vinculo.md"
PESSOAS = "10-Eu/Pessoas.md"
ORIGEM = date(2026, 9, 14)

class Vinculo:
    def __init__(self, vault: Vault):
        self.vault = vault

    # ── leitura ───────────────────────────────────────
    def dados(self) -> dict:
        txt = self.vault.read(ARQUIVO)
        g = lambda k, d: (re.search(rf"^- {k}:\s*(.+)$", txt, re.M) or [None, d])[1]
        try:
            conversas = int(g("conversas", "0"))
        except ValueError:
            conversas = 0
        acomp = [m.group(1).strip() for m in re.finditer(r"^- \[ \] (.+)$", txt.split("## Acompanhamentos", 1)[1] if "## Acompanhamentos" in txt else "", re.M)]
        return {"dias": (date.today() - ORIGEM).days, "conversas": conversas, "acompanhamentos": acomp,
                "familiaridade": min(1.0, 0.2 + conversas / 400 + (date.today() - ORIGEM).days / 120)}

    def pessoas(self) -> list[dict]:
        """`- Nome — papel; detalhes` em 10-Eu/Pessoas.md"""
        out = []
        for l in self.vault.read(PESSOAS).splitlines():
            if (m := re.match(r"^- \*?\*?([^—*]+?)\*?\*?\s*—\s*(.+)$", l.strip())):
                out.append({"nome": m.group(1).strip(), "papel": m.group(2).strip()})
        return out

    # ── escrita ───────────────────────────────────────
    def _salvar(self, conversas: int, acomp: list[str]) -> None:
        d = (date.today() - ORIGEM).days
        corpo = (f"# Vínculo\n\n> O Jaime mantém. Familiaridade cresce com o tempo e as conversas; nunca vira cobrança.\n\n"
                 f"- desde: {ORIGEM.isoformat()}\n- dias: {d}\n- conversas: {conversas}\n- atualizado: {datetime.now():%Y-%m-%d %H:%M}\n\n"
                 "## Acompanhamentos\n" + "".join(f"- [ ] {a}\n" for a in acomp))
        self.vault.write(ARQUIVO, corpo)

    def registrar_conversa(self) -> None:
        d = self.dados(); self._salvar(d["conversas"] + 1, d["acompanhamentos"])

    def acompanhar(self, texto: str) -> None:
        """Algo para perguntar depois ('reunião com o Diego na quinta')."""
        d = self.dados()
        if texto.strip() and texto.strip() not in d["acompanhamentos"]:
            self._salvar(d["conversas"], (d["acompanhamentos"] + [texto.strip()])[-10:])

    def fechar_acompanhamento(self, texto: str) -> None:
        d = self.dados(); self._salvar(d["conversas"], [a for a in d["acompanhamentos"] if a != texto])

    # ── saída para o prompt/prosódia ──────────────────
    def contexto(self) -> str:
        d = self.dados()
        pessoas = "; ".join(f"{p['nome']} — {p['papel']}" for p in self.pessoas()[:12])
        nivel = "recém-chegado" if d["familiaridade"] < 0.35 else "de casa" if d["familiaridade"] < 0.7 else "de longa data"
        partes = [f"Você e o João trabalham juntos há {d['dias']} dia(s) ({d['conversas']} conversas) — tom {nivel}: cordial, próximo na medida, sem carência."]
        if pessoas:
            partes.append(f"Pessoas da vida dele: {pessoas}.")
        if d["acompanhamentos"]:
            partes.append("Acompanhar quando fizer sentido (uma pergunta curta, nunca cobrança): " + "; ".join(d["acompanhamentos"][:5]) + ".")
        partes.append("Nunca diga que sentiu falta, que ficou sozinho ou que precisa dele — isso não é você.")
        return " ".join(partes)

    def calor(self) -> float:
        return 0.5 + 0.35 * self.dados()["familiaridade"]
