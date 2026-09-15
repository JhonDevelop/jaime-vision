"""Vigia — intercepta ações perigosas antes de executarem.

Mecânica: o hook PreToolUse nega a ação e explica que precisa de "confirmo".
Quando o João diz "confirmo", o orquestrador chama `vigia.armar()` e a próxima
ação perigosa (dentro de ARMED_SECONDS) passa. Uma confirmação = uma ação."""
from __future__ import annotations
import re, time
from claude_agent_sdk import HookMatcher

ARMED_SECONDS = 120

BASH_PERIGOSO = [
    r"\brm\s+-[a-z]*r[a-z]*f", r"\brm\s+-[a-z]*f[a-z]*r", r"\bsudo\b", r"\bmkfs", r">\s*/dev/",
    r"git\s+push\b.*(--force|-f\b)", r"git\s+push\b(?!.*origin\s+(feat|fix|chore|dev)\S*)",
    r"git\s+reset\s+--hard", r"curl[^|]*\|\s*(ba)?sh", r"\bDROP\s+TABLE\b", r"\bTRUNCATE\b",
    r"\bshutdown\b", r"\breboot\b", r"\bkillall\b", r"\bchmod\s+-R\s+777",
]
TOOLS_DE_ENVIO = re.compile(r"^mcp__.*__(send|reply|forward|create_pull_request|merge_pull_request|delete|mover|renomear|apagar)", re.I)
# browser: clicar em enviar/comprar/pagar/confirmar/assinar (texto ou seletor de submit) espera o "confirmo"
CLIQUE_IRREVERSIVEL = re.compile(r"(submit|enviar|comprar|finalizar|pagar|pagamento|confirmar|assinar|contratar|checkout|publicar|postar|excluir|apagar|deletar|delete|buy|pay|purchase|send)", re.I)
CAMINHOS_PROTEGIDOS = re.compile(r"(^|/)(\.env|vault/00-Jaime/)")
# o próprio código do Jaime: editar exige "confirmo" (e só vale depois de reiniciar o servidor)
CODIGO_PROPRIO = re.compile(r"(^|/)jaime-vision/(jaime|tests)/.+\.py$|^(jaime|tests)/.+\.py$")

class Vigia:
    def __init__(self):
        self._armado_ate = 0.0
        self.ultima_bloqueada: str | None = None

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
            if CAMINHOS_PROTEGIDOS.search(alvo):
                return self._negar(f"arquivo protegido: {alvo}")
            if CODIGO_PROPRIO.search(alvo):
                return {} if self._consome() else self._negar(f"isso é o seu próprio código ({alvo.split('/')[-1]}); mudança precisa de 'confirmo' e de reiniciar o servidor")
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
