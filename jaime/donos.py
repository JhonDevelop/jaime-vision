"""Segundo dono — o J.A.I.M.E reconhece o Gabriel Mello e o conduz a montar a PRÓPRIA cópia.

O João decidiu (17/09/2026) que o Gabriel, sócio dele, passa a ter um assistente também. Isto aqui é o
portão e o roteiro desse começo.

**O que isto NÃO faz, e é o mais importante:** não abre o cérebro do João para o Gabriel. A palavra-passe
aqui serve de PROVA de que o João autorizou — só ele a daria ao sócio —, e é conferida com `Acesso.confere()`,
que valida sem liberar nada. O vault do João continua trancado do lado de cá. O que o Gabriel ganha é o
roteiro para subir a cópia dele, na máquina dele, com vault, diário e memórias dele.

Por que separado: memória de dono não se mistura. O diário do João tem finança, conversa e gente da vida
dele; o do Gabriel terá as dele. Um assistente que mistura os dois não é útil para nenhum dos dois, e é
uma indiscrição com os dois.

O que volta para cá (e o João pediu assim): só o **código de aprendizado** — o que o Jaime aprende a fazer
melhor, que serve a qualquer dono. Isso é commit no repositório principal. Vault, diário, memórias, nome e
cara ficam na worktree de cada dono, de dono para dono."""
from __future__ import annotations
import re, time
from dataclasses import dataclass, field

SOCIO = "Gabriel Mello"
APRESENTACAO_RX = re.compile(
    r"\b(?:oi|olá|ola|e\s*a[ií])?\s*(?:jaime|j\.?a\.?i\.?m\.?e)?[,\s]*"
    r"(?:eu\s+)?s(?:ou|o)\s+(?:o\s+)?gabriel(?:\s+mello)?\b", re.I)
SIM_RX = re.compile(r"\b(sim|isso|sou|exato|correto|confirmo|positivo|é isso|isso mesmo)\b", re.I)
NAO_RX = re.compile(r"\b(n[ãa]o|nao|negativo|errado)\b", re.I)
MAX_TENTATIVAS = 3


def eh_o_socio_se_apresentando(texto: str) -> bool:
    """«Oi JAIME, sou o Gabriel Mello» e as variações naturais dessa frase."""
    return bool(APRESENTACAO_RX.search(texto or ""))


@dataclass
class Porteiro:
    """Conduz o Gabriel da apresentação até o roteiro. Uma etapa por vez, sem atalho."""
    etapa: str = "fechado"            # fechado | confirmando | senha | aberto | barrado
    tentativas: int = 0
    desde: float = field(default_factory=time.time)

    # ── o portão ─────────────────────────────────────────────────────────
    def apresentou(self) -> str:
        self.etapa, self.tentativas, self.desde = "confirmando", 0, time.time()
        return (f"Gabriel. O João me falou de você — sócio e amigo dele. "
                f"Antes de eu te ajudar a montar a sua cópia: você é o {SOCIO}, sócio do João Vitor Leal?")

    def responder(self, texto: str, acesso) -> str | None:
        """A fala do Gabriel dentro do portão. `None` quer dizer 'não é comigo, siga o fluxo normal'."""
        t = (texto or "").strip()
        if self.etapa == "confirmando":
            # a negação ganha primeiro: em "não, não sou" o SIM_RX casaria com o "sou"
            if NAO_RX.search(t):
                self.etapa = "fechado"
                return "Sem problemas. Então eu sigo só com o João."
            if not SIM_RX.search(t):
                return f"Preciso de um sim ou não: você é o {SOCIO}?"
            self.etapa = "senha"
            return ("Certo. Agora a palavra-passe que o João te passou. Ela não abre o cérebro dele para "
                    "você — só me prova que ele autorizou isto.")

        if self.etapa == "senha":
            if acesso is not None and acesso.confere(t):
                self.etapa = "aberto"
                return None                      # quem fala a partir daqui é o roteiro
            self.tentativas += 1
            if self.tentativas >= MAX_TENTATIVAS:
                self.etapa = "barrado"
                return ("Três vezes errado. Vou parar por aqui e avisar o João. "
                        "Peça a ele e a gente recomeça.")
            return f"Não foi essa. Tenta de novo ({self.tentativas} de {MAX_TENTATIVAS})."
        return None

    @property
    def aberto(self) -> bool:
        return self.etapa == "aberto"

    @property
    def barrado(self) -> bool:
        return self.etapa == "barrado"

    def fechar(self) -> None:
        self.etapa, self.tentativas = "fechado", 0


# ── o roteiro, em blocos que cabem numa fala ──────────────────────────────
ROTEIRO: list[tuple[str, str]] = [
    ("Onde a sua cópia vai morar",
     "Na SUA máquina, não na do João. Clone o repositório, crie a sua worktree e o seu vault. "
     "Nada do diário, das finanças ou das conversas dele viaja — memória de dono não se mistura."),
    ("Maestri",
     "Baixe o Maestri e abra um workspace seu. É nele que eu crio os terminais que trabalham em paralelo. "
     "Ligue o Maestro no terminal principal: é a identidade pela qual eu falo com o canvas."),
    ("Os dois hemisférios",
     "No Maestri, abra um terminal com o preset Codex (o lado técnico, da OpenAI) e outro com o Antigravity "
     "ou Gemini (o lado de pesquisa e crítica, do Google). Eu adoto os dois sozinho no primeiro ciclo — "
     "você não precisa configurar nada além de deixá-los abertos e logados na sua conta."),
    ("As permissões da sua máquina",
     "Você decide o que eu posso, uma a uma, em Ajustes, Privacidade e Segurança: Acessibilidade "
     "(teclado e mouse), Gravação de Tela (para eu ver o que você vê), Disco Completo (para ler arquivos) "
     "e Microfone. Comece só pelo Microfone e pela Gravação de Tela, e me dê o resto quando fizer sentido. "
     "Nenhuma delas é obrigatória para eu começar a te ser útil."),
    ("As suas chaves",
     "O seu `.env` é seu: as suas chaves de modelo, a sua palavra-passe (troque a que o João te passou por "
     "uma sua com `python -m jaime senha`). Eu nunca mostro chave, nem a sua nem a dele."),
    ("Quem eu vou ser para você",
     "Eu não preciso me chamar Jaime na sua casa. Escolha o nome e eu me renomeio no código, no vault, na "
     "palavra de acordar e na interface. A cara do cockpit também é sua: cor, telas, o que aparece."),
    ("Como eu vou te conhecer",
     "Do zero, ouvindo você. Nos primeiros dias eu faço poucas perguntas e anoto muito: o seu jeito, o seu "
     "ritmo, o que você me pede sempre. Isso vira o seu vault e os seus traços — nada herdado do João."),
    ("O que volta para o João",
     "Só o código de aprendizado: o que eu aprendo a fazer MELHOR, que serve a qualquer dono, vai para o "
     "repositório principal por commit. O seu vault, o seu diário, as suas memórias, o seu nome e a sua "
     "interface ficam na sua worktree. De dono para dono, nada se mistura."),
]


def roteiro_texto() -> str:
    return "\n\n".join(f"{i}. {titulo}\n   {corpo}" for i, (titulo, corpo) in enumerate(ROTEIRO, 1))


def boas_vindas() -> str:
    return (f"Pronto, {SOCIO.split()[0]}. A partir daqui eu te ajudo a montar a sua cópia — na sua máquina, "
            f"com o seu vault e a sua cara. São {len(ROTEIRO)} passos; posso te dar um de cada vez, "
            f"no seu ritmo. Começamos pelo primeiro?")
