"""'Jarvis, ativar monitor' — o vídeo do treino: rosto no orbe, "identidade confirmada", e o relatório do treino com
ícones holográficos (passos, chama, bateria) enquanto ele fala.

O relatório de saúde só sai quando o rosto confere com o cadastrado OU quando o João não cadastrou rosto nenhum
(aí vale a palavra-passe que já destrancou o cérebro). Rosto diferente → não lê dado de saúde em voz alta.
"""
from __future__ import annotations
import asyncio
from ..hud.events import bus
from . import saude as sd
from .rosto import Rostos


class Monitor:
    def __init__(self, rostos: Rostos | None = None, carregar=sd.carregar, emitir=None, espera_rosto: float = 10.0):
        self.rostos = rostos or Rostos()
        self.carregar, self.emitir, self.espera_rosto = carregar, emitir or bus.emitir, espera_rosto
        self._resultado: asyncio.Future | None = None
        self.ativo = False

    def receber_rosto(self, resultado: dict) -> None:
        """A rota /jarvis/rosto/verificar chama isto com o resultado da comparação (ou {'status':'sem_camera'})."""
        if self._resultado is not None and not self._resultado.done():
            self._resultado.set_result(resultado)

    async def rodar(self):
        self.ativo = True
        self._resultado = asyncio.get_event_loop().create_future()
        self.emitir("monitor", fase="reconhecimento", cadastrado=self.rostos.cadastrado)
        yield "Ok, senhor, iniciando o reconhecimento facial."
        try:
            res = await asyncio.wait_for(asyncio.shield(self._resultado), self.espera_rosto)
        except asyncio.TimeoutError:
            res = {"status": "sem_rosto"}
        st = res.get("status")
        self.emitir("monitor", fase="identidade", status=st)
        pode_saude = st == "confirmado" or (st in ("sem_cadastro", "sem_camera", "sem_rosto", "desconhecido") and not self.rostos.dono_cadastrado
                                             and st != "desconhecido")
        if st == "confirmado":
            yield "Identidade confirmada, bem-vindo, senhor."
        elif st == "conhecido":
            yield f"Olá, {res.get('nome') or 'visita'}. O monitor é do João; os dados de saúde ficam só com ele."
        elif st == "sem_cadastro":
            yield "Rosto detectado. Ainda não aprendi o seu; quando quiser, diga: aprende meu rosto."
        elif st == "desconhecido":
            yield "Não reconheci esse rosto. O relatório de saúde fica para quando for o senhor."
        elif st == "sem_camera":
            yield "Não consegui abrir a câmera; sigo sem reconhecimento."
        else:
            yield "Não vi ninguém na câmera; sigo sem reconhecimento."
        self.emitir("monitor", fase="ativado")
        yield "Monitor ativado com sucesso."
        if not pode_saude:
            self.emitir("monitor", fase="fim"); self.ativo = False; return
        r = self.carregar()
        itens = sd.falas_do_monitor(r) if r else []
        if not itens:
            yield "Ainda não recebi os dados do treino de hoje. Assim que o celular mandar, eu analiso."
        for i, item in enumerate(itens):
            self.emitir("monitor", fase="item", indice=i, **item)
            yield item["fala"]
        if r and itens:
            yield fechamento(r)
        self.emitir("monitor", fase="fim"); self.ativo = False


def fechamento(r: sd.Resumo) -> str:
    if r.recuperacao is not None and r.recuperacao < 40:
        return "Com essa recuperação, a estatística foi generosa hoje. Vale pegar leve amanhã."
    if r.distancia_km is not None and r.habitual_km and r.distancia_km < r.habitual_km:
        return "Treino abaixo do seu ritmo de costume, mas contou."
    return "Bom treino, senhor."
