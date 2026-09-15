"""Vigia — intercepta ações perigosas antes de executarem.

Mecânica: o hook PreToolUse nega a ação e explica que precisa de "confirmo".
Quando o João diz "confirmo", o orquestrador chama `vigia.armar()` e a próxima
ação perigosa (dentro de ARMED_SECONDS) passa. Uma confirmação = uma ação.

Princípio (15/09/2026): o Vigia segura só o IRREVERSÍVEL — enviar, pagar, apagar,
push em main, sudo, e o próprio Vigia. Ver a tela, clicar, digitar, mover arquivo,
editar o próprio código e o .env são autonomia do Jaime (o git e o backup desfazem)."""
from __future__ import annotations
import re, time
from claude_agent_sdk import HookMatcher

ARMED_SECONDS = 300

BASH_PERIGOSO = [
    r"\brm\s+-[a-z]*r[a-z]*f", r"\brm\s+-[a-z]*f[a-z]*r", r"\bsudo\b", r"\bmkfs", r">\s*/dev/",
    r"git\s+push\b.*(--force|-f\b)", r"git\s+push\b(?!.*origin\s+(feat|fix|chore|dev)\S*)",
    r"git\s+reset\s+--hard", r"curl[^|]*\|\s*(ba)?sh", r"\bDROP\s+TABLE\b", r"\bTRUNCATE\b",
    r"\bshutdown\b", r"\breboot\b", r"\bchmod\s+-R\s+777",
]
# só o que sai da máquina ou some: enviar, responder, encaminhar, PR/merge, apagar
TOOLS_DE_ENVIO = re.compile(r"^mcp__.*__(send|reply|forward|create_pull_request|merge_pull_request|delete|apagar|enviar|email_enviar)", re.I)
# browser: clicar em enviar/comprar/pagar/assinar/publicar/excluir espera o "confirmo" (submit/confirmar genéricos são livres)
CLIQUE_IRREVERSIVEL = re.compile(r"(enviar|comprar|finalizar|pagar|pagamento|assinar|contratar|checkout|publicar|postar|excluir|apagar|deletar|delete|buy|pay|purchase|send)", re.I)
# identidade e regras: só o João edita, nunca o Jaime
CAMINHOS_INTOCAVEIS = re.compile(r"(^|/)vault/00-Jaime/")
# .env: pode, mas com "confirmo" (segredos; o Jaime nunca mostra o conteúdo)
CAMINHOS_COM_CONFIRMO = re.compile(r"(^|/)\.env$")
# o próprio Vigia: editar exige "confirmo" (ele não se desarma sozinho); o resto de jaime/ é livre, e só vale após reiniciar
VIGIA_PROPRIO = re.compile(r"(^|/)jaime/vigia/.+\.py$")

class Vigia:
    def __init__(self):
        self._armado_ate = 0.0
        self.ultima_bloqueada: str | None = None
        # mantido por compatibilidade (sessão de visão contínua); ações de tela já são livres
        self.sessao_livre = lambda: False

    def armar(self):
        self._armado_ate = time.time() + ARMED_SECONDS

    def _consome(self) -> bool:
        if time.time() < self._armado_ate:
            self._armado_ate = 0.0
            return True
        return False

    def _negar(self, motivo: str) -> dict:
        self.ultima_bloqueada = motivo
        return {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"VIGIA: {motivo}. Peça ao João para dizer 'confirmo' e repita a ação.",
        }}

    async def pre_tool_use(self, input_data: dict, tool_use_id: str | None, context) -> dict:
        nome = input_data.get("tool_name", "")
        args = input_data.get("tool_input", {}) or {}

        if nome == "Bash":
            cmd = args.get("command", "")
            if any(re.search(p, cmd) for p in BASH_PERIGOSO):
                return {} if self._consome() else self._negar(f"comando perigoso: {cmd[:80]}")
        elif nome in ("Write", "Edit", "MultiEdit"):
            alvo = args.get("file_path", "")
            if CAMINHOS_INTOCAVEIS.search(alvo):
                return self._negar(f"arquivo só do João: {alvo}")
            if CAMINHOS_COM_CONFIRMO.search(alvo):
                return {} if self._consome() else self._negar(f"segredos em {alvo.split('/')[-1]}; mudança precisa de 'confirmo'")
            if VIGIA_PROPRIO.search(alvo):
                return {} if self._consome() else self._negar(f"isso é o Vigia ({alvo.split('/')[-1]}); mudança precisa de 'confirmo' e de reiniciar o servidor")
        elif nome == "mcp__maos__clicar" and CLIQUE_IRREVERSIVEL.search(str(args.get("alvo", ""))):
            return {} if self._consome() else self._negar(f"clique irreversível no browser: {str(args.get('alvo'))[:60]}")
        elif TOOLS_DE_ENVIO.match(nome):
            return {} if self._consome() else self._negar(f"ação externa: {nome}")
        return {}

    def hooks(self) -> dict:
        return {"PreToolUse": [HookMatcher(matcher=None, hooks=[self.pre_tool_use])]}

CONFIRMACOES = {"confirmo", "confirmado", "pode ir", "pode fazer", "manda ver", "sim, confirmo"}

def eh_confirmacao(texto: str) -> bool:
    return texto.strip().lower().rstrip(".!") in CONFIRMACOES
