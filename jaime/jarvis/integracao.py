"""Liga as cenas do Jarvis ao orquestrador: uma frase reconhecida vira um gerador de falas (voz) + eventos (tela).

`JAIME_JARVIS=off` desliga tudo; `JAIME_BRIEFING_BOM_DIA=off` faz o "bom dia" voltar a ser só cumprimento
(o "me dá o briefing" continua funcionando).
"""
from __future__ import annotations
import os
from datetime import datetime
from ..hud.events import bus
from . import holograma as holo
from .briefing import Briefing, do_jaime, quer_briefing
from .monitor import Monitor
from .rosto import Rostos
from .voz import cena


def ligado(env=None) -> bool:
    e = os.environ if env is None else env
    return (e.get("JAIME_JARVIS", "on") or "on").strip().lower() not in ("0", "off", "false", "nao", "não")


class Jarvis:
    def __init__(self, briefing: Briefing, monitor: Monitor, rostos: Rostos, emitir=None, env=None):
        self.briefing, self.monitor, self.rostos = briefing, monitor, rostos
        self.emitir = emitir or bus.emitir
        e = os.environ if env is None else env
        self.bom_dia = (e.get("JAIME_BRIEFING_BOM_DIA", "on") or "on").strip().lower() not in ("0", "off", "false")
        self.cadastrando = False

    def gerador(self, texto: str, agora: datetime | None = None):
        """Um gerador assíncrono de frases se a fala abre uma cena; senão None (o turno segue normal)."""
        agora = agora or datetime.now()
        hoje = agora.strftime("%Y-%m-%d")
        if quer_briefing(texto, agora, ja_deu_hoje=self.briefing.ultimo_dia == hoje or not self.bom_dia):
            return self._falas(self.briefing.rodar())
        c = cena(texto)
        if c is None:
            return None
        nome, args = c
        if nome == "monitor":
            return self._falas(self.monitor.rodar())
        if nome == "holograma":
            r = holo.resolver(args["objeto"])
            self.emitir("holograma", acao="abrir", **r)
            return self._uma(holo.fala(r))
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

    async def _falas(self, gen):
        async for frase in gen:
            bus.emitir("fala", texto=frase)
            yield frase.rstrip() + " "
        bus.emitir("fala_fim")

    async def _uma(self, frase: str):
        bus.emitir("fala", texto=frase); bus.emitir("fala_fim")
        yield frase


def montar(jaime, env=None) -> Jarvis | None:
    if not ligado(env):
        return None
    rostos = Rostos()
    return Jarvis(do_jaime(jaime), Monitor(rostos), rostos, env=env)
