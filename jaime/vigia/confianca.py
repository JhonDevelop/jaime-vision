"""Confiança progressiva — a mesma classe de ação aprovada 5× sem correção vira proposta "posso passar a fazer X
sem perguntar?" (docs/FASE-3-TEMPO-REAL.md §2.4). O João decide uma vez; o Vigia ganha uma exceção com escopo.

Persistido em `01-Estado/Confianca.md` (tabela: classe · aprovações · livre). Uma correção do João ("não era isso")
logo depois de um lote zera as classes daquele lote."""
from __future__ import annotations
import re
from ..identidade import eh_sim

ARQUIVO = "01-Estado/Confianca.md"
LIMIAR = 3          # 3 aprovações sem correção viram proposta "posso fazer sem perguntar?" (era 5, a pedido do João)
NEGATIVA_RX = re.compile(r"^\s*(n[aã]o|nunca|continua perguntando|deixa como est[aá]|prefiro n[aã]o)\b", re.I)
CABECALHO = (f"# Confiança — o que o Jaime já pode fazer sem perguntar\n\n"
             f"> Cada classe de ação aprovada {LIMIAR} vezes sem correção vira uma proposta; \"sim\" torna a classe livre. "
             f"Apague a linha para voltar a perguntar.\n\n| classe | aprovações | livre |\n|---|---|---|\n")

class Confianca:
    def __init__(self, vault=None):
        self.vault = vault
        self.contagem: dict[str, int] = {}
        self.excecoes: set[str] = set()
        self.pendente: str | None = None       # classe com proposta em aberto
        self._carregar()

    # ── consulta ───────────────────────────────────────
    def livre(self, classe: str) -> bool:
        return classe in self.excecoes

    # ── eventos ────────────────────────────────────────
    def aprovar(self, classes: list[str]) -> str | None:
        """O João liberou um lote com estas classes. Devolve a pergunta de confiança se alguma chegou ao limiar."""
        pergunta = None
        for c in dict.fromkeys(classes):
            if not c or c in self.excecoes:
                continue
            self.contagem[c] = self.contagem.get(c, 0) + 1
            if self.contagem[c] >= LIMIAR and self.pendente is None and pergunta is None:
                self.pendente = c
                pergunta = f"Você já aprovou {descrever(c)} {self.contagem[c]} vezes sem corrigir. Posso passar a fazer isso sem perguntar?"
        self._salvar()
        return pergunta

    def corrigir(self, classes: list[str]) -> None:
        for c in classes:
            if c in self.contagem:
                self.contagem[c] = 0
        self._salvar()

    def responder(self, texto: str) -> str | None:
        """Resposta do João à proposta pendente. None se não há proposta ou a fala não é resposta."""
        if not self.pendente:
            return None
        c = self.pendente
        if eh_sim(texto):
            self.excecoes.add(c); self.pendente = None; self._salvar()
            return f"Combinado: {descrever(c)} passa a ser livre. Se quiser voltar a confirmar, apague a linha em Confianca.md."
        if NEGATIVA_RX.match(texto or ""):
            self.pendente = None; self.contagem[c] = 0; self._salvar()
            return "Certo, continuo perguntando."
        return None

    def revogar(self, classe: str) -> None:
        self.excecoes.discard(classe); self.contagem[classe] = 0; self._salvar()

    # ── persistência ───────────────────────────────────
    def _carregar(self) -> None:
        if self.vault is None:
            return
        try:
            txt = self.vault.read(ARQUIVO)
        except Exception:
            txt = ""
        for m in re.finditer(r"^\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*(sim|n[aã]o)\s*\|", txt or "", re.M | re.I):
            c = m.group(1).strip()
            if c in ("classe", "---"):
                continue
            self.contagem[c] = int(m.group(2))
            if m.group(3).lower() == "sim":
                self.excecoes.add(c)

    def _salvar(self) -> None:
        if self.vault is None:
            return
        linhas = [f"| {c} | {n} | {'sim' if c in self.excecoes else 'não'} |" for c, n in sorted(self.contagem.items())]
        linhas += [f"| {c} | {LIMIAR} | sim |" for c in sorted(self.excecoes - set(self.contagem))]
        try:
            self.vault.write(ARQUIVO, CABECALHO + "\n".join(linhas) + "\n")
        except Exception:
            pass

def descrever(classe: str) -> str:
    """'mcp__google__email_enviar' → 'enviar e-mail'; 'bash:git push' → 'git push'; 'browser:clicar' → 'clicar em enviar/pagar no browser'."""
    c = classe.split("__")[-1] if "__" in classe else classe
    c = c.replace("bash:", "").replace("edit:", "editar ").replace("browser:clicar", "clicar em enviar/pagar no browser")
    return {"email_enviar": "enviar e-mail", "send": "enviar mensagem", "reply": "responder mensagem", "forward": "encaminhar",
            "delete": "apagar", "apagar": "apagar", "enviar": "enviar", "create_pull_request": "abrir PR", "merge_pull_request": "fazer merge"}.get(c, c)
