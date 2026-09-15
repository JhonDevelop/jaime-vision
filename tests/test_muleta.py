"""M-09 (MENTE.md): em tarefa com ferramenta, o 1º som saía em ~4,5 s porque a muleta esperava 2 s depois da ferramenta.
Agora ela vem logo depois da 1ª ferramenta, se a resposta ainda não começou."""
import asyncio, time
from types import SimpleNamespace
from jaime.hud.events import bus
from jaime.voice.duplex import OuvidoDuplex
from jaime.voice.escuta import MULETAS, MULETA_APOS_FERRAMENTA_S
from tests.test_duplex import _TTS, _Fluxo, S

class _JaimeComFerramenta:
    def __init__(self, demora=1.2):
        self.acesso = SimpleNamespace(liberado=True); self.vault = None; self.humor = None; self.falante_atual = ""
        self.aguardando_nome = False; self.demora = demora; self.t_ferramenta = 0.0
    def avisos_do_dia(self): return ""
    async def ask_stream(self, texto, canal="voice", contexto=""):
        await asyncio.sleep(0.05)
        self.t_ferramenta = time.time(); bus.emitir("producao", ferramenta="ler", alvo="notificações")
        await asyncio.sleep(self.demora)
        yield "Foram três mensagens."

def _turno(j):
    async def rodar():
        o = OuvidoDuplex(j, S, asyncio.get_running_loop(), fluxo=SimpleNamespace(on_parcial=None), antecipador=None)
        o._tts = _TTS(); o.mudo = True
        o._tts.t_muleta = 0.0
        enf = o._tts.enfileirar
        def marcado(t): o._tts.t_muleta = o._tts.t_muleta or time.time(); enf(t)
        o._tts.enfileirar = marcado
        await o._tratar_texto("jaime, quem me mandou mensagem", b"", t_fim_fala=time.time(), t_texto=time.time())
        return o._tts
    return asyncio.run(rodar())

def test_muleta_vem_logo_depois_da_ferramenta():
    j = _JaimeComFerramenta(demora=1.2)
    tts = _turno(j)
    assert tts.falas[0] in MULETAS and tts.falas[-1] == "Foram três mensagens."
    assert tts.t_muleta - j.t_ferramenta < MULETA_APOS_FERRAMENTA_S + 0.4     # e não 2 s depois

def test_sem_ferramenta_ou_resposta_rapida_nao_tem_muleta():
    class _Rapido(_JaimeComFerramenta):
        async def ask_stream(self, texto, canal="voice", contexto=""):
            await asyncio.sleep(0.05); yield "Duas mensagens."
    assert _turno(_Rapido()).falas == ["Duas mensagens."]
    j = _JaimeComFerramenta(demora=0.1)                                         # ferramenta, mas a resposta veio antes
    assert _turno(j).falas == ["Foram três mensagens."]
