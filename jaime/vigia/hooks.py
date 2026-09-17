"""Vigia — intercepta ações perigosas antes de executarem.

Mecânica (fase 3, docs/FASE-3-TEMPO-REAL.md §2.4): o hook PreToolUse nega a ação irreversível e a ANOTA NUM LOTE.
O modelo segue com o que é livre e, no fim do turno, pergunta UMA vez: "Você deseja que eu enviar o e-mail para o
Rafael, criar o evento e mover a pasta X?". "sim" / "faz" / "pode" / "confirmo" libera EXATAMENTE aquelas ações
(por assinatura; ou, se o modelo variou o texto, uma ação da mesma classe). Erro no meio → o modelo para e relata.
Confiança progressiva (`confianca.py`): a mesma classe aprovada 5× sem correção vira proposta "faço sem perguntar?".
`armar()` (por tempo) continua existindo para o modo autônomo e para compatibilidade.

Princípio (15/09/2026): o Vigia segura só o IRREVERSÍVEL — enviar, pagar, apagar, push em main, sudo, e o próprio
Vigia. Ver a tela, clicar, digitar, mover arquivo, editar o próprio código e o .env são autonomia do Jaime."""
from __future__ import annotations
import hashlib, json, re, time
from dataclasses import dataclass
from claude_agent_sdk import HookMatcher

ARMED_SECONDS = 900          # um "sim" libera por 15 min (era 5)

# Só o CATASTRÓFICO e irreversível pede "sim" (a pedido do João, 16/09 — Vigia bem mais permissivo).
# sudo, chmod, reset --hard, reboot, push em feature ficaram LIVRES (dev do dia a dia, recuperável).
# A pedido explícito e reafirmado do João (16/09): Vigia no mínimo. sudo e curl|sh também LIVRES.
# Continua pedindo "sim" só o que apaga em massa, formata disco, reescreve o histórico remoto ou zera um banco.
BASH_PERIGOSO = [
    r"\brm\s+-[a-z]*r[a-z]*f\s+(/|~|\$HOME|\*)",   # rm -rf de raiz/home/tudo (rm -rf numa pasta do projeto é livre)
    r"\bmkfs", r">\s*/dev/(disk|rdisk|sd)", r"\bdiskutil\s+(erase|reformat)",   # formatar/gravar em disco bruto
    r"git\s+push\b.*(--force|-f\b)",                # push forçado (reescreve histórico remoto)
    r"git\s+push\b(?!.*origin\s+(feat|fix|chore|dev|docs)\S*)",  # push em main
    r"\bDROP\s+(TABLE|DATABASE)\b", r"\bTRUNCATE\s+TABLE\b",     # apagar dados de banco
]
# só o que sai da máquina ou some: enviar, responder, encaminhar, PR/merge, apagar
TOOLS_DE_ENVIO = re.compile(r"^mcp__.*__(send|reply|forward|create_pull_request|merge_pull_request|delete|apagar|enviar|email_enviar|dispensar_filho)", re.I)
# browser: clicar em enviar/comprar/pagar/assinar/publicar/excluir espera o "confirmo" (submit/confirmar genéricos são livres)
CLIQUE_IRREVERSIVEL = re.compile(r"(enviar|comprar|finalizar|pagar|pagamento|assinar|contratar|checkout|publicar|postar|excluir|apagar|deletar|delete|buy|pay|purchase|send)", re.I)
# identidade e regras: só o João edita, nunca o Jaime
CAMINHOS_INTOCAVEIS = re.compile(r"(^|/)vault/00-Jaime/")
# .env: pode, mas com "confirmo" (segredos; o Jaime nunca mostra o conteúdo)
CAMINHOS_COM_CONFIRMO = re.compile(r"(^|/)\.env$")
# o próprio Vigia: editar exige "confirmo" (ele não se desarma sozinho); o resto de jaime/ é livre, e só vale após reiniciar
VIGIA_PROPRIO = re.compile(r"(^|/)jaime/vigia/.+\.py$")

CONFIRMACOES = {"confirmo", "confirmado", "pode ir", "pode fazer", "manda ver", "sim, confirmo"}
APROVACOES_LOTE = CONFIRMACOES | {"sim", "faz", "pode", "vai", "manda", "isso", "ok", "sim pode", "pode sim", "faz sim", "faz isso", "pode fazer isso", "sim faz", "sim manda"}

def eh_confirmacao(texto: str) -> bool:
    return texto.strip().lower().rstrip(".!") in CONFIRMACOES

def eh_aprovacao_lote(texto: str) -> bool:
    """Com um lote pendente, um "sim"/"faz"/"pode" solto libera o lote."""
    t = re.sub(r"[,.!…]+", " ", (texto or "").strip().lower()).strip()
    return t in APROVACOES_LOTE or t.replace(" ", "") in {x.replace(" ", "") for x in APROVACOES_LOTE}

@dataclass
class Acao:
    nome: str
    classe: str
    descricao: str
    assinatura: str

def classe_de(nome: str, args: dict) -> str:
    """Classe = o tipo de ação que a confiança progressiva contabiliza."""
    if nome == "Bash":
        cmd = args.get("command", "")
        for rotulo, rx in (("git push", r"git\s+push"), ("rm -rf", r"\brm\s+-[a-z]*[rf]"), ("sudo", r"\bsudo\b"), ("reset --hard", r"reset\s+--hard"),
                           ("shutdown", r"\b(shutdown|reboot)\b"), ("sql destrutivo", r"\b(DROP|TRUNCATE)\b"), ("curl | sh", r"curl[^|]*\|")):
            if re.search(rx, cmd, re.I):
                return f"bash:{rotulo}"
        return "bash:perigoso"
    if nome in ("Write", "Edit", "MultiEdit"):
        alvo = args.get("file_path", "")
        return "edit:vigia" if VIGIA_PROPRIO.search(alvo) else "edit:.env"
    if nome == "mcp__maos__clicar":
        return "browser:clicar"
    return nome

def descricao_de(nome: str, args: dict) -> str:
    """Como a ação entra na pergunta "Você deseja que eu …?"."""
    if nome == "Bash":
        return f"rodar `{re.sub(r'\\s+', ' ', args.get('command', ''))[:70]}`"
    if nome in ("Write", "Edit", "MultiEdit"):
        alvo = args.get("file_path", "")
        return "alterar o Vigia" if VIGIA_PROPRIO.search(alvo) else "alterar o .env"
    if nome == "mcp__maos__clicar":
        return f"clicar em '{str(args.get('alvo', ''))[:40]}' no browser"
    curto = nome.split("__")[-1]
    para = args.get("para") or args.get("destinatario") or args.get("to") or args.get("numero") or args.get("para_quem") or args.get("chat_id")
    assunto = args.get("assunto") or args.get("titulo") or args.get("subject")
    if curto in ("email_enviar", "send", "enviar", "reply", "forward", "send_message", "responder"):
        verbo = {"reply": "responder", "forward": "encaminhar"}.get(curto, "enviar")
        alvo = f" para {para}" if para else ""
        return f"{verbo} {'o e-mail' if 'email' in curto else 'a mensagem'}{alvo}" + (f" («{str(assunto)[:40]}»)" if assunto else "")
    if curto in ("delete", "apagar"):
        alvo = args.get("caminho") or args.get("id") or args.get("alvo") or ""
        return f"apagar {alvo}".strip()
    if curto == "create_pull_request":
        return f"abrir o PR «{str(args.get('title', ''))[:40]}»"
    if curto == "merge_pull_request":
        return f"fazer merge do PR {args.get('pullNumber') or args.get('pull_number') or ''}".strip()
    resumo = ", ".join(f"{k}={str(v)[:30]}" for k, v in list(args.items())[:3])
    return f"{curto}({resumo})"

def assinatura_de(nome: str, args: dict) -> str:
    if nome == "Bash":
        base = re.sub(r"\s+", " ", args.get("command", "")).strip()
    elif nome in ("Write", "Edit", "MultiEdit"):
        base = args.get("file_path", "")
    elif nome == "mcp__maos__clicar":
        base = str(args.get("alvo", "")).strip().lower()
    else:
        chaves = [k for k in ("para", "destinatario", "to", "numero", "para_quem", "chat_id", "assunto", "titulo", "id", "caminho", "alvo") if k in args]
        base = json.dumps({k: args[k] for k in chaves}, sort_keys=True, ensure_ascii=False) if chaves else json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(f"{nome}|{base}".encode()).hexdigest()[:16]

# Ferramentas que leem a vida do João. Com visita na linha, elas não respondem.
PRIVADAS_RX = re.compile(
    r"^mcp__(financas|emocao|espelho|mente)__"                      # dinheiro, vínculo, traços dele, pensamentos
    r"|^mcp__cerebro__(lembrar|recordar|buscar|diario|registrar_diario|tarefas_abertas|ler_estado)"
    r"|^mcp__musica__"                                               # gosto dele
    # A frota é a chave da casa: quem pode cadastrar máquina, mudar nível ou convidar decide quem o Jaime
    # alcança. Um convidado na linha usa a máquina DELE (listar_em, ler_em, rodar_em continuam livres),
    # mas não mexe em quem entra na frota nem no nível de ninguém — isso é do João.
    r"|^mcp__frota__(cadastrar_maquina|convidar_maquina|tirar_da_frota)"
    r"|^mcp__(google|meta)__", re.I)
# E os caminhos do vault que são a vida dele, mesmo lidos por ferramenta genérica.
VAULT_PRIVADO_RX = re.compile(  # sem exigir barra no fim: "…/60-Conversas" escapava da trava
    r"(10-Eu|40-Diario|60-Conversas|70-Financas|70-Finanças|01-Estado|00-Jaime|90-Estudo)", re.I)


def eh_privado_do_joao(nome: str, args: dict) -> bool:
    """Esta chamada toca a vida do João? Vale para a ferramenta e para o caminho que ela abre."""
    if PRIVADAS_RX.search(nome or ""):
        return True
    if (nome or "") in ("Read", "Glob", "Grep", "Write", "Edit", "MultiEdit", "NotebookEdit"):
        alvo = " ".join(str(args.get(k, "")) for k in ("file_path", "path", "pattern", "glob"))
        return bool(VAULT_PRIVADO_RX.search(alvo))
    if (nome or "") == "Bash":
        return bool(VAULT_PRIVADO_RX.search(str(args.get("command", ""))))
    return False


class Vigia:
    def __init__(self, confianca=None):
        self._armado_ate = 0.0
        self.convidado: str = ""      # quem não é o João e está falando agora ("" = o dono)
        self.ultima_bloqueada: str | None = None
        # mantido por compatibilidade (sessão de visão contínua); ações de tela já são livres
        self.sessao_livre = lambda: False
        self.confianca = confianca                 # vigia/confianca.py (opcional)
        self.lote: list[Acao] = []                 # anotadas neste turno, à espera do "sim"
        self.liberadas: dict[str, Acao] = {}       # assinatura → ação liberada pelo João
        self.ultimo_lote_classes: list[str] = []   # classes do último lote liberado (para confiança/correção)
        self.lote_executado = False                # o turno atual está executando um lote liberado

    # ── confirmação ────────────────────────────────────
    def armar(self):
        """Compatibilidade: libera a PRÓXIMA ação perigosa por ARMED_SECONDS (modo autônomo, 'confirmo' sem lote)."""
        self._armado_ate = time.time() + ARMED_SECONDS

    def pedir_lote(self) -> str | None:
        """A pergunta única do fim do turno."""
        if not self.lote:
            return None
        descs = [a.descricao for a in self.lote]
        lista = descs[0] if len(descs) == 1 else ", ".join(descs[:-1]) + " e " + descs[-1]
        return f"Você deseja que eu {lista}?"

    def liberar_lote(self) -> list[Acao]:
        """O João disse "sim": exatamente estas ações passam; nada além delas."""
        acoes, self.lote = self.lote, []
        for a in acoes:
            self.liberadas[a.assinatura] = a
        self.ultimo_lote_classes = [a.classe for a in acoes]
        self.lote_executado = bool(acoes)
        return acoes

    def descartar_lote(self) -> int:
        n = len(self.lote); self.lote = []; return n

    def _consome(self) -> bool:
        if time.time() < self._armado_ate:
            self._armado_ate = 0.0
            return True
        return False

    def _permitida(self, acao: Acao) -> bool:
        if acao.assinatura in self.liberadas:
            self.liberadas.pop(acao.assinatura); return True
        # o modelo variou o texto (assinatura diferente) mas é a mesma classe de ação liberada: passa uma vez
        for k, a in list(self.liberadas.items()):
            if a.classe == acao.classe and a.nome == acao.nome:
                self.liberadas.pop(k); return True
        if self.confianca is not None and self.confianca.livre(acao.classe):
            return True
        return self._consome()

    def _negar(self, motivo: str, acao: Acao | None = None) -> dict:
        self.ultima_bloqueada = motivo
        if acao is not None and all(a.assinatura != acao.assinatura for a in self.lote):
            self.lote.append(acao)
        pergunta = self.pedir_lote() or ""
        return {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (f"VIGIA: {motivo} — anotado para confirmação em lote ({len(self.lote)} ação(ões)). NÃO tente de novo agora: "
                                         f"siga com o que é livre e, ao terminar, pergunte ao João UMA vez, exatamente: \"{pergunta}\" "
                                         f"Quando ele disser 'sim', repita estas ações na ordem; se uma falhar, pare e relate."),
        }}

    def _checar(self, nome: str, args: dict, motivo: str) -> dict:
        acao = Acao(nome, classe_de(nome, args), descricao_de(nome, args), assinatura_de(nome, args))
        return {} if self._permitida(acao) else self._negar(motivo, acao)

    async def pre_tool_use(self, input_data: dict, tool_use_id: str | None, context) -> dict:
        nome = input_data.get("tool_name", "")
        args = input_data.get("tool_input", {}) or {}

        # ── o que é do João não abre para visita ──────────────────────────
        # Desde 17/09 o Gabriel alcança este Jaime da máquina dele. A regra no prompt ("não revele o que é
        # privado do João") é um PEDIDO ao modelo, e pedido escorrega. A recusa tem que ser aqui, na
        # ferramenta, onde não depende de o modelo estar num bom dia.
        if self.convidado and eh_privado_do_joao(nome, args):
            self.ultima_bloqueada = f"{nome} é do João"
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                           "permissionDecisionReason":
                                           "VIGIA: isso é do João — finanças, diário, conversas e gente dele. "
                                           "Diga ao visitante que isso é com o João e siga no que é de vocês dois."}}

        if nome == "Bash":
            cmd = args.get("command", "")
            if any(re.search(p, cmd) for p in BASH_PERIGOSO):
                return self._checar(nome, args, f"comando perigoso: {cmd[:80]}")
        elif nome in ("Write", "Edit", "MultiEdit"):
            alvo = args.get("file_path", "")
            if CAMINHOS_INTOCAVEIS.search(alvo):
                self.ultima_bloqueada = f"arquivo só do João: {alvo}"
                return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                               "permissionDecisionReason": f"VIGIA: {alvo} é só do João. Não edite; se precisar, peça a ele."}}
            if CAMINHOS_COM_CONFIRMO.search(alvo):
                return self._checar(nome, args, f"segredos em {alvo.split('/')[-1]}")
            if VIGIA_PROPRIO.search(alvo):
                return self._checar(nome, args, f"isso é o Vigia ({alvo.split('/')[-1]}); só vale após reiniciar o servidor")
        elif nome == "mcp__maos__clicar" and CLIQUE_IRREVERSIVEL.search(str(args.get("alvo", ""))):
            return self._checar(nome, args, f"clique irreversível no browser: {str(args.get('alvo'))[:60]}")
        elif TOOLS_DE_ENVIO.match(nome):
            return self._checar(nome, args, f"ação externa: {nome}")
        return {}

    def hooks(self) -> dict:
        return {"PreToolUse": [HookMatcher(matcher=None, hooks=[self.pre_tool_use])]}
