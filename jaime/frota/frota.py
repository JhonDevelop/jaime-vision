"""A frota: várias máquinas ligadas ao mesmo tempo, cada uma com seu dono, seu nível e sua fila.

A ponte antiga (`jaime/ponte/`) era um cano para UMA máquina: registrar a segunda apagava a primeira. Isto
aqui é o mesmo cano, várias vezes, com a matrícula (`registro.py`) decidindo quem é quem.

O sentido da conexão continua sendo o que mais importa e não mudou: **nada entra nas outras máquinas.** O
agente de lá liga para cá e pergunta se tem trabalho (long-poll). Não há porta aberta na máquina do Gabriel,
não há porta aberta no Mac do quarto, e nenhuma delas precisa de IP fixo nem de firewall mexido. Se uma
máquina sai da tomada, ela simplesmente para de aparecer — e o Jaime diz isso em vez de travar.

Tudo aqui é memória, de propósito. Reiniciar o servidor derruba a frota e cada máquina se reapresenta
sozinha (as do João, pelo launchd; as dos outros, quando o dono liga). Fila de comando que sobrevive a
reinício é fila que executa coisa velha numa máquina que já mudou — é assim que se apaga o arquivo errado."""
from __future__ import annotations
import asyncio, time, uuid
from dataclasses import dataclass, field

from .registro import NaFrota, Registro, normalizar_host

ESPERA_S = 90.0          # quanto ele espera a resposta de uma máquina antes de desistir
SILENCIO_S = 75.0        # sem aparecer por este tempo, a máquina conta como fora do ar
CONVITE_S = 600.0        # o convite de entrada na frota vale 10 minutos e uma vez só


@dataclass
class Pedido:
    id: str
    acao: str
    args: dict
    resposta: asyncio.Future = field(default_factory=asyncio.Future)
    criado: float = field(default_factory=time.time)


@dataclass
class Ligacao:
    """Uma máquina ligada agora. O que ela É vem da matrícula; o que ela ESTÁ vem daqui."""
    matricula: NaFrota
    host_cru: str = ""
    usuario: str = ""
    so: str = ""
    raiz: str = ""
    visto: float = field(default_factory=time.time)
    fila: asyncio.Queue = field(default_factory=asyncio.Queue)
    pendentes: dict[str, Pedido] = field(default_factory=dict)

    @property
    def viva(self) -> bool:
        return (time.time() - self.visto) < SILENCIO_S

    @property
    def apelido(self) -> str:
        return self.matricula.apelido

    def __str__(self) -> str:
        q = int(time.time() - self.visto)
        estado = f"viva (falou há {q}s)" if self.viva else f"FORA DO AR (sumiu há {q}s)"
        return (f"{self.apelido} · {self.matricula.dono} · {self.so or '?'} · "
                f"{self.matricula.nivel} em {self.raiz or '?'} · {estado}")


class Frota:
    """Todas as máquinas que o J.A.I.M.E alcança, e as ferramentas para atravessar até elas."""

    def __init__(self, registro: Registro | None = None):
        self.registro = registro or Registro()
        self.ligacoes: dict[str, Ligacao] = {}
        self.convites: dict[str, tuple[str, float]] = {}      # código -> (chave da máquina, quando nasceu)

    # ── entrar na frota sem ninguém falar segredo em voz alta ────────────
    def convidar(self, host: str) -> tuple[str, str]:
        """Um código curto, de uso único, que vale 10 minutos e SÓ para esta máquina.

        Por que não entregar o token direto: o token daquela máquina é permanente, e o Jaime falaria ele
        em voz alta ou escreveria numa nota — e a regra da casa é que segredo não aparece em resposta,
        commit ou diário. O convite é diferente: é curto (dá para ditar), morre em dez minutos, serve uma
        vez e não serve para outra máquina. Quem o usa recebe o token definitivo pela rede, direto na
        máquina, sem passar pela conversa."""
        m = self.registro.por_host(host)
        if m is None:
            return "", f"«{host}» não está na frota. Cadastre primeiro."
        self.convites = {c: v for c, v in self.convites.items() if time.time() - v[1] < CONVITE_S}
        codigo = uuid.uuid4().hex[:8].upper()
        self.convites[codigo] = (m.chave, time.time())
        return codigo, (f"convite para {m.apelido}: {codigo} (vale 10 minutos, uma vez). "
                        f"Na máquina, rodar: curl -fsSL http://ESTE_IP:8787/frota/instalar?c={codigo} | sh")

    def usar_convite(self, codigo: str) -> NaFrota | None:
        """Gasta o convite e devolve a matrícula. Segunda tentativa com o mesmo código não funciona."""
        v = self.convites.pop((codigo or "").strip().upper(), None)
        if v is None or time.time() - v[1] >= CONVITE_S:
            return None
        return next((m for m in self.registro.todas() if m.chave == v[0]), None)

    # ── entrada ──────────────────────────────────────────────────────────
    def registrar(self, host: str, usuario: str, so: str, raiz: str) -> tuple[bool, str]:
        """A máquina se apresenta. Quem ela é, porém, é a matrícula que diz.

        Devolve (aceita?, o que dizer). Máquina fora da matrícula é recusada aqui, com o nome dela na
        mensagem — para o João poder cadastrar sem adivinhar o hostname."""
        m = self.registro.por_host(host)
        if m is None:
            return False, (f"«{host}» não está na frota. Cadastre com `cadastrar_maquina` antes de "
                           f"ligar o agente nela.")
        lig = self.ligacoes.get(m.chave)
        if lig is None:
            lig = self.ligacoes[m.chave] = Ligacao(matricula=m)
        else:
            lig.matricula = m                       # relê a matrícula: nível trocado vale no próximo registro
        lig.host_cru, lig.usuario, lig.so, lig.raiz = host, usuario, so, raiz
        lig.visto = time.time()
        return True, f"ligada: {lig}"

    # ── achar a máquina de que ele está falando ──────────────────────────
    def achar(self, quem: str) -> Ligacao | None:
        """Aceita apelido, hostname ou nome do dono — é assim que o João fala («roda isso no mini»)."""
        k = normalizar_host(quem)
        if not k:
            return None
        for lig in self.ligacoes.values():
            if lig.matricula.chave == k or normalizar_host(lig.apelido) == k:
                return lig
        candidatas = [l for l in self.ligacoes.values() if k in normalizar_host(l.matricula.dono)]
        return candidatas[0] if len(candidatas) == 1 else None

    def estado(self) -> str:
        if not self.ligacoes:
            cadastradas = self.registro.todas()
            if not cadastradas:
                return ("Minha frota está vazia: nenhuma máquina cadastrada ainda. Use "
                        "`cadastrar_maquina` e depois rode o instalador na máquina.")
            return ("Nenhuma máquina ligada agora. Cadastradas: "
                    + "; ".join(f"{m.apelido} ({m.dono})" for m in cadastradas)
                    + ". Nas suas, o agente sobe no boot; nas dos outros, o dono precisa ligar.")
        return "\n".join(f"- {lig}" for lig in sorted(self.ligacoes.values(), key=lambda l: l.apelido.lower()))

    # ── atravessar ───────────────────────────────────────────────────────
    async def pedir(self, quem: str, acao: str, **args) -> str:
        lig = self.achar(quem)
        if lig is None:
            return (f"não tenho «{quem}» ligada. " + self.estado())
        if not lig.viva:
            dono_e_joao = lig.matricula.dono.startswith("João")
            return (f"{lig.apelido} está fora do ar (sem falar comigo há "
                    f"{int(time.time() - lig.visto)}s). "
                    + ("Pode ser que ela esteja dormindo ou desligada."
                       if dono_e_joao else
                       f"Peça para o {lig.matricula.dono} ligar o agente de novo."))
        if not lig.matricula.pode(acao):
            return (f"em {lig.apelido} eu sou {lig.matricula.nivel}, e {lig.matricula.nivel} não "
                    f"{'roda comando' if acao == 'rodar' else 'escreve'}. Suba o nível na matrícula se quiser.")
        p = Pedido(uuid.uuid4().hex[:12], acao, args)
        lig.pendentes[p.id] = p
        await lig.fila.put(p)
        try:
            return await asyncio.wait_for(p.resposta, timeout=ESPERA_S)
        except asyncio.TimeoutError:
            return f"{lig.apelido} não respondeu em {int(ESPERA_S)}s"
        finally:
            lig.pendentes.pop(p.id, None)

    async def proximo(self, host: str, espera: float = 25.0) -> dict | None:
        """O agente de uma máquina chama isto e fica pendurado até haver trabalho para ELA."""
        lig = self.achar(host)
        if lig is None:
            return None
        lig.visto = time.time()
        try:
            p = await asyncio.wait_for(lig.fila.get(), timeout=espera)
        except asyncio.TimeoutError:
            return None
        return {"id": p.id, "acao": p.acao, "args": p.args}

    def responder(self, host: str, pedido_id: str, saida: str) -> bool:
        lig = self.achar(host)
        if lig is None:
            return False
        lig.visto = time.time()
        p = lig.pendentes.get(pedido_id)
        if p and not p.resposta.done():
            p.resposta.set_result(saida)
            return True
        return False
