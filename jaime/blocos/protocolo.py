"""JBP — Jaime Block Protocol v1. Como qualquer superfície conversa com o gerenciador de blocos.

Transporte: WebSocket em `/blocos/ws` (JSON por mensagem). Qualquer coisa que fale WebSocket vira superfície:
o cockpit web, o cliente de terminal, a janela nativa, um app de óculos (Android/iOS companion, Unity, visionOS,
Android XR, WebXR), um ESP32 com display, um app de carro.

    cliente → servidor
      {"op":"ola", "perfil":"oculos", "nome":"óculos do João", "capacidades":{...}, "v":1}   (primeira mensagem)
      {"op":"fechar", "id":"…"}            {"op":"mover", "id":"…", "ancoragem":{"x":.7,"y":.2}}
      {"op":"ler", "id":"…"}               {"op":"acao", "id":"…", "intencao":"…"}   (botão de bloco `acoes`)
      {"op":"desfazer"}                    {"op":"ping"}
    servidor → cliente
      {"op":"bem_vindo", "sessao":"…", "perfil":"…", "capacidades":{...}, "v":1}
      {"op":"abrir"|"atualizar", "bloco":{…adaptado à superfície…}}     {"op":"fechar", "id":"…"}
      {"op":"falar", "texto":"…"}          {"op":"erro", "msg":"…"}      {"op":"pong"}

O servidor adapta cada bloco às capacidades (superficies.adaptar) e faz o diff por sessão: o cliente só recebe o
que mudou, e nunca recebe bloco privado se não for superfície do dono com o cérebro aberto.
"""
from __future__ import annotations
import asyncio, json, re
from typing import Callable
from uuid import uuid4
from .modelo import Bloco
from .superficies import Capacidades, adaptar, capacidades_de, selecionar

VERSAO = 1
FILA_MAX = 256


class Sessao:
    """Uma superfície conectada. `enviar` recebe cada mensagem (dict) — em WebSocket, vai para uma fila bounded que
    uma task esvazia; cliente lento que enche a fila é desconectado em vez de travar os outros."""
    def __init__(self, perfil: str, caps: Capacidades, enviar: Callable[[dict], None], nome: str = ""):
        self.id = uuid4().hex[:10]
        self.perfil, self.caps, self.enviar, self.nome = perfil, caps, enviar, nome or perfil
        self.versoes: dict[str, int] = {}                 # id do bloco → versão que ESTA superfície já tem

    def sincronizar(self, blocos: list[Bloco], dono_ok: bool) -> int:
        """Diff entre o que existe e o que esta superfície mostra. Devolve quantas mensagens saíram."""
        alvo = {b.id: b for b in selecionar(blocos, self.caps, self.perfil, dono_ok)}
        n = 0
        for bid in [i for i in self.versoes if i not in alvo]:
            self.versoes.pop(bid)
            self.enviar({"op": "fechar", "id": bid}); n += 1
        for bid, b in alvo.items():
            if self.versoes.get(bid) == b.versao:
                continue
            op = "atualizar" if bid in self.versoes else "abrir"
            self.versoes[bid] = b.versao
            self.enviar({"op": op, "bloco": adaptar(b, self.caps, self.perfil)}); n += 1
        return n

    def boas_vindas(self) -> dict:
        return {"op": "bem_vindo", "sessao": self.id, "perfil": self.perfil, "capacidades": self.caps.to_dict(), "v": VERSAO}


def sessao_de_ola(msg: dict, enviar: Callable[[dict], None], confiavel: bool) -> Sessao:
    if not isinstance(msg, dict) or msg.get("op") != "ola":
        raise ValueError("a primeira mensagem tem de ser {'op':'ola', 'perfil':…}")
    perfil = str(msg.get("perfil") or "janela")[:20]
    extra = msg.get("capacidades") if isinstance(msg.get("capacidades"), dict) else {}
    caps = capacidades_de(perfil, {**extra, **({} if confiavel else {"confiavel": False})})
    return Sessao(perfil, caps, enviar, str(msg.get("nome") or "")[:60])


class FilaDeEnvio:
    """Fila bounded entre o gerenciador (síncrono) e o WebSocket (assíncrono)."""
    def __init__(self, maximo: int = FILA_MAX):
        self.q: asyncio.Queue = asyncio.Queue(maxsize=maximo)
        self.estourou = False

    def __call__(self, msg: dict) -> None:
        try:
            self.q.put_nowait(msg)
        except asyncio.QueueFull:
            self.estourou = True
            raise RuntimeError("cliente lento: fila de blocos cheia")


async def tratar_mensagem(g, sessao: Sessao, msg: dict, executar_intencao: Callable | None = None) -> dict | None:
    """Uma mensagem do cliente → efeito no gerenciador. Devolve resposta direta (ou None)."""
    op = msg.get("op") if isinstance(msg, dict) else None
    if op == "ping":
        return {"op": "pong"}
    bid = str(msg.get("id") or "")
    if op in ("fechar", "mover", "ler", "acao") and bid not in sessao.versoes:
        return {"op": "erro", "msg": "esse bloco não está nesta superfície"}      # nada de adivinhar id de bloco privado
    if op == "fechar":
        g.fechar(bid, motivo=f"fechado em {sessao.nome}")
        return None
    if op == "mover" and isinstance(msg.get("ancoragem"), dict):
        if bid in g.blocos:
            g.mover(bid, msg["ancoragem"])
        return None
    if op == "ler":
        return {"op": "falar", "texto": g.ler(bid) or "não achei esse bloco"}
    if op == "desfazer":
        return {"op": "falar", "texto": g.desfazer()}
    if op == "acao":
        b = g.blocos.get(bid)
        intencao = str(msg.get("intencao") or "")
        botoes = {x["intencao"] for x in (b.conteudo.get("botoes", []) if b and b.tipo == "acoes" else [])}
        if not b or intencao not in botoes or not intencao_segura(intencao):
            return {"op": "erro", "msg": "essa ação não existe neste bloco"}   # cliente não inventa intenção
        if not (sessao.caps.confiavel and g.dono_ok()):
            return {"op": "erro", "msg": "ação só pela superfície do dono, com o cérebro aberto"}
        if executar_intencao:
            # o texto que vira turno nunca é só "sim"/"confirmo": botão não aprova lote do Vigia nem arma confirmação
            asyncio.get_running_loop().create_task(executar_intencao(f"[botão «{b.titulo}»] {intencao}"))
        return {"op": "falar", "texto": f"ok: {intencao[:80]}"}
    return {"op": "erro", "msg": f"op desconhecida: {op}"}


def intencao_segura(intencao: str) -> bool:
    """Botão de bloco é pedido, não aprovação: "sim", "confirmo", "pode", senha e "tranca/destranca o cérebro"
    não podem ser intenção de botão (o modelo escreve a intenção; o João só vê o rótulo)."""
    from ..vigia.hooks import eh_aprovacao_lote, eh_confirmacao
    t = (intencao or "").strip()
    if not t or eh_confirmacao(t) or eh_aprovacao_lote(t):
        return False
    if re.fullmatch(r"[\d\s]{4,}", t) or re.search(r"\b(senha|palavra.passe|tranca|destranca)\b", t, re.I):
        return False
    return True


def codificar(msg: dict) -> str:
    return json.dumps(msg, ensure_ascii=False, separators=(",", ":"))
