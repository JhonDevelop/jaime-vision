"""O lado do João: a fila de trabalho da ponte e as ferramentas que o J.A.I.M.E usa para atravessar.

Como funciona, em uma frase: o Jaime põe um pedido na fila, o agente na máquina do Gabriel busca, executa
lá e devolve a resposta. Nenhuma conexão entra na máquina do Gabriel — ela só sai.

Tudo aqui é memória: se o servidor reinicia, a ponte cai e o Gabriel religa o agente. É de propósito. Fila
de comando que sobrevive a reinício é fila que executa coisa velha numa máquina que mudou."""
from __future__ import annotations
import asyncio, time, uuid
from dataclasses import dataclass, field

from claude_agent_sdk import tool, create_sdk_mcp_server

ESPERA_S = 90.0          # quanto o Jaime espera pela resposta antes de desistir
SILENCIO_S = 75.0        # sem o agente aparecer por este tempo, a ponte é considerada caída


def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}


@dataclass
class Pedido:
    id: str
    acao: str                       # listar | ler | escrever | rodar
    args: dict
    resposta: asyncio.Future = field(default_factory=asyncio.Future)
    criado: float = field(default_factory=time.time)


@dataclass
class Ponte:
    """A fila entre o Jaime (aqui) e o agente (na máquina do dono convidado)."""
    dono: str = ""
    maquina: str = ""
    raiz: str = ""
    pode_rodar: bool = False
    visto: float = 0.0
    fila: asyncio.Queue = field(default_factory=asyncio.Queue)
    pendentes: dict[str, Pedido] = field(default_factory=dict)

    @property
    def viva(self) -> bool:
        return bool(self.dono) and (time.time() - self.visto) < SILENCIO_S

    def registrar(self, dono: str, maquina: str, raiz: str, pode_rodar: bool) -> None:
        self.dono, self.maquina, self.raiz, self.pode_rodar = dono, maquina, raiz, bool(pode_rodar)
        self.visto = time.time()

    def estado(self) -> str:
        if not self.dono:
            return "ninguém ligou a ponte ainda."
        quanto = int(time.time() - self.visto)
        return (f"{self.dono} · {self.maquina} · raiz {self.raiz} · "
                f"rodar comando: {'sim' if self.pode_rodar else 'não'} · "
                + (f"viva (falou há {quanto}s)" if self.viva else f"CAÍDA (sumiu há {quanto}s)"))

    async def pedir(self, acao: str, **args) -> str:
        if not self.viva:
            return ("A ponte com a máquina dele está caída. Peça para ele rodar "
                    "`python -m jaime.ponte.agente` e tentar de novo.")
        if acao == "rodar" and not self.pode_rodar:
            return "Ele não liberou rodar comando na máquina dele — só leitura e escrita na pasta escolhida."
        p = Pedido(uuid.uuid4().hex[:12], acao, args)
        self.pendentes[p.id] = p
        await self.fila.put(p)
        try:
            return await asyncio.wait_for(p.resposta, timeout=ESPERA_S)
        except asyncio.TimeoutError:
            return f"a máquina dele não respondeu em {int(ESPERA_S)}s"
        finally:
            self.pendentes.pop(p.id, None)

    async def proximo(self, espera: float = 25.0) -> dict | None:
        """O agente chama isto e fica pendurado até haver trabalho (long-poll)."""
        self.visto = time.time()
        try:
            p = await asyncio.wait_for(self.fila.get(), timeout=espera)
        except asyncio.TimeoutError:
            return None
        return {"id": p.id, "acao": p.acao, "args": p.args}

    def responder(self, pedido_id: str, saida: str) -> bool:
        self.visto = time.time()
        p = self.pendentes.get(pedido_id)
        if p and not p.resposta.done():
            p.resposta.set_result(saida)
            return True
        return False


def build_ponte_server(ponte: Ponte):
    @tool("ponte", "Como está a ponte com a máquina do outro dono: quem ligou, de qual máquina, qual pasta "
                   "ele abriu e se autorizou rodar comando. Cheque antes de prometer que vai mexer lá.", {})
    async def estado(args):
        return _txt(ponte.estado())

    @tool("listar_la", "LISTA arquivos e pastas na máquina DELE, dentro da pasta que ele abriu. `caminho` é "
                       "relativo a essa pasta ('' é a raiz). Use antes de ler, para saber o que existe.",
          {"caminho": str})
    async def listar_la(args):
        return _txt(await ponte.pedir("listar", caminho=(args.get("caminho") or "").strip()))

    @tool("ler_la", "LÊ um arquivo na máquina dele, dentro da pasta que ele abriu. Caminho relativo a essa "
                    "pasta.", {"caminho": str})
    async def ler_la(args):
        c = (args.get("caminho") or "").strip()
        return _txt(await ponte.pedir("ler", caminho=c) if c else "faltou o caminho")

    @tool("escrever_la", "ESCREVE um arquivo na máquina dele, dentro da pasta que ele abriu. Sobrescreve: "
                         "leia antes se o arquivo já existe e você não quer perder o que está lá.",
          {"caminho": str, "conteudo": str})
    async def escrever_la(args):
        c = (args.get("caminho") or "").strip()
        if not c:
            return _txt("faltou o caminho")
        return _txt(await ponte.pedir("escrever", caminho=c, conteudo=args.get("conteudo") or ""))

    @tool("rodar_la", "RODA um comando na máquina dele, na pasta que ele abriu. Só funciona se ele tiver "
                      "autorizado isso ao ligar a ponte. Use para git, teste, build — o trabalho dele, na "
                      "máquina dele.", {"comando": str})
    async def rodar_la(args):
        cmd = (args.get("comando") or "").strip()
        return _txt(await ponte.pedir("rodar", comando=cmd) if cmd else "faltou o comando")

    return create_sdk_mcp_server(name="ponte", version="1.0.0",
                                 tools=[estado, listar_la, ler_la, escrever_la, rodar_la])
