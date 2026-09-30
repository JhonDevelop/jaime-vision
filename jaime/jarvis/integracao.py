"""Liga as cenas do Jarvis ao orquestrador: uma frase reconhecida vira um gerador de falas (voz) + eventos (tela).

`JAIME_JARVIS=off` desliga tudo; `JAIME_BRIEFING_BOM_DIA=off` faz o "bom dia" voltar a ser só cumprimento
(o "me dá o briefing" continua funcionando).
"""
from __future__ import annotations
import os
from datetime import datetime
from ..hud.events import bus
from . import holograma as holo
from . import tela
from .briefing import Briefing, do_jaime, quer_briefing
from .monitor import Monitor
from .rosto import Rostos
from .voz import cena


def ligado(env=None) -> bool:
    e = os.environ if env is None else env
    return (e.get("JAIME_JARVIS", "on") or "on").strip().lower() not in ("0", "off", "false", "nao", "não")


class Jarvis:
    def __init__(self, briefing: Briefing, monitor: Monitor, rostos: Rostos, emitir=None, env=None,
                 modelo_holo=None, sentinela=None, capacidades=None, garantir_tela=None):
        self.briefing, self.monitor, self.rostos = briefing, monitor, rostos
        self.modelo_holo, self.sentinela, self.capacidades = modelo_holo, sentinela, capacidades
        self.garantir_tela = garantir_tela or (lambda: None)
        self.emitir = emitir or bus.emitir
        e = os.environ if env is None else env
        self.bom_dia = (e.get("JAIME_BRIEFING_BOM_DIA", "on") or "on").strip().lower() not in ("0", "off", "false")
        self.cadastrando = False

    def gerador(self, texto: str, agora: datetime | None = None):
        """Um gerador assíncrono de frases se a fala abre uma cena; senão None (o turno segue normal)."""
        agora = agora or datetime.now()
        hoje = agora.strftime("%Y-%m-%d")
        if quer_briefing(texto, agora, ja_deu_hoje=self.briefing.ultimo_dia == hoje or not self.bom_dia):
            self.garantir_tela()
            return self._falas(self.briefing.rodar())
        c = cena(texto)
        if c is None:
            return None
        nome, args = c
        if nome == "monitor":
            self.garantir_tela()                          # "ativar monitor" acorda o monitor e abre o painel
            return self._falas(self.monitor.rodar())
        if nome == "holograma":
            self.garantir_tela()
            return self._falas(self._holograma(args["objeto"]))
        if nome == "capacidades":
            return self._uma(self.capacidades() if callable(self.capacidades) else CAPACIDADES_PADRAO)
        if nome == "sistemas":
            return self._falas(self._sistemas())
        if nome == "fecha_holograma":
            self.emitir("holograma", acao="fechar")
            return self._uma("Holograma fechado.")
        if nome == "aprende_rosto":
            self.cadastrando = True
            self.emitir("rosto", acao="cadastrar", amostras=5)
            return self._uma("Olhe para a câmera por uns segundos; vou aprender o seu rosto. Ele serve para eu te reconhecer, não para destrancar nada.")
        if nome == "esquece_rosto":
            self.rostos.esquecer()
            return self._uma("Pronto, esqueci o seu rosto.")
        if nome == "orbe":
            self.emitir("orbe", estilo=args["estilo"])
            return self._uma("Feito." if args["estilo"] == "fios" else "Modo partículas.")
        return None

    async def _holograma(self, objeto: str):
        """Catálogo ou arquivo .glb: na hora. Qualquer outro objeto: o modelo descreve as peças (uns segundos)."""
        r = holo.resolver(objeto)
        if not r["exato"] and self.modelo_holo is not None:
            self.emitir("holograma", acao="montando", titulo=objeto)
            yield f"Montando o holograma de {objeto}."
            try:
                r = await holo.gerar(objeto, self.modelo_holo)
            except Exception:
                r = {**r, "falhou": True}
        self.emitir("holograma", acao="abrir", **r)
        yield holo.fala(r)

    async def _sistemas(self):
        s = self.sentinela
        if s is None:
            yield "A sentinela está desligada."; return
        if s.alvos and all(a.ok is None for a in s.alvos):
            await s.rodada()
        self.emitir("sentinela", estado=s.estado(), mostrar=True)
        yield s.resumo_falado()

    async def _falas(self, gen):
        async for frase in gen:
            bus.emitir("fala", texto=frase)
            yield frase.rstrip() + " "
        bus.emitir("fala_fim")

    async def _uma(self, frase: str):
        bus.emitir("fala", texto=frase); bus.emitir("fala_fim")
        yield frase


CAPACIDADES_PADRAO = ("Eu analiso dados em tempo real, vigio sistemas críticos, entendo linguagem natural e coordeno várias "
                      "tarefas ao mesmo tempo. Em termos práticos: sou uma central de automação e inteligência operacional.")


def capacidades_de(jaime) -> str:
    """O inventário REAL (o que está ligado agora), no tom do vídeo — nada de prometer o que não está conectado."""
    partes = ["analiso dados em tempo real", "entendo e respondo em linguagem natural, por voz ou texto"]
    s = getattr(jaime, "sentinela", None)
    if s is not None and s.alvos:
        partes.append(f"vigio {len(s.alvos)} sistema{'s' if len(s.alvos) > 1 else ''} crítico{'s' if len(s.alvos) > 1 else ''} e aviso se algum cair")
    try:
        filhos = len(jaime.equipe.vivos()) if hasattr(jaime.equipe, "vivos") else 0
    except Exception:
        filhos = 0
    partes.append("coordeno várias tarefas ao mesmo tempo" + (f", com {filhos} agentes trabalhando para mim agora" if filhos else ""))
    if getattr(getattr(jaime, "google", None), "conectado", False):
        partes.append("leio e organizo seu e-mail e sua agenda")
    if getattr(getattr(jaime, "casa", None), "ativa", False):
        partes.append("comando a casa e a Alexa")
    h = getattr(jaime, "hermes", None)
    if h is not None and h.disponivel:
        partes.append("delego trabalho pesado ao Hermes")
    partes += ["escrevo e corrijo código", "gero relatórios estratégicos a partir do seu vault",
               "e melhoro os meus próprios processos com base nos padrões que observo"]
    return ("Hoje eu " + ", ".join(partes[:-1]) + " " + partes[-1] + ". A maioria dos sistemas só responde a comandos, senhor; "
            "eu acompanho o contexto e ajo antes de precisar. Em termos práticos: sou uma central de automação e inteligência operacional.")


def montar(jaime, env=None) -> Jarvis | None:
    if not ligado(env):
        return None
    rostos = Rostos()
    modelo_holo = None
    try:
        from ..mente.pensar import _pensador_padrao
        modelo_holo = _pensador_padrao(jaime.s)
    except Exception:
        pass
    return Jarvis(do_jaime(jaime), Monitor(rostos), rostos, env=env, modelo_holo=modelo_holo,
                  sentinela=getattr(jaime, "sentinela", None), capacidades=lambda: capacidades_de(jaime),
                  garantir_tela=lambda: tela.garantir(env=env))
