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


def test_sem_ferramenta_ele_fica_QUIETO_mesmo_demorando(monkeypatch):
    """Mudou em 17/09, a pedido do João: «eu digo coisas básicas e ele fica ok, um segundo».
    «Peraí» sem estar fazendo nada promete e não entrega — é pior que silêncio. Sem ferramenta,
    ou ele responde, ou espera calado até ter a resposta."""
    from jaime.voice import escuta
    monkeypatch.setattr(escuta, "MULETA_S", 0.3)
    class _Lento(_JaimeComFerramenta):
        async def ask_stream(self, texto, canal="voice", contexto=""):
            await asyncio.sleep(0.8); yield "Sou um robô assistente."
    tts = _turno(_Lento())
    assert not any(f in MULETAS for f in tts.falas), f"falou muleta sem ferramenta: {tts.falas}"
    assert tts.falas[-1] == "Sou um robô assistente."


def test_latencia_conta_a_muleta_como_primeiro_som(monkeypatch):
    """Diário 16/09 08:15: 'texto→1ª frase 14,31 s' num turno em que a muleta soou em ~3 s — o TTS zerava o marcador
    quando a muleta acabava. Agora o 1º som do turno (muleta incluída) é o que vale."""
    from jaime.voice import escuta
    monkeypatch.setattr(escuta, "MULETA_S", 0.2)
    monkeypatch.setattr(escuta, "MULETA_APOS_FERRAMENTA_S", 0.05)
    class _TTSTurno(_TTS):
        def __init__(self):
            super().__init__(); self.t_primeiro_som = 0.0
        def novo_turno(self): self.t_primeiro_som = 0.0
        def enfileirar(self, t):
            self.t_inicio_audio = time.time()                          # cada frase "começa a soar" agora (zera como o TTS real)
            self.t_primeiro_som = self.t_primeiro_som or self.t_inicio_audio
            self.falas.append(t)
    class _Lento(_JaimeComFerramenta):
        def __init__(self):
            super().__init__(); self.vault = SimpleNamespace(diario=lambda t, s="Log": self.linhas.append(t)); self.linhas = []
        async def ask_stream(self, texto, canal="voice", contexto=""):
            # a muleta só existe COM ferramenta desde 17/09; o turno lento tem que usar uma para o
            # marcador de latência ser exercitado — sem ferramenta ele fica calado, e é isso que se quer
            bus.emitir("producao", ferramenta="ler", alvo="notificações")
            await asyncio.sleep(0.9); yield "Sou um robô assistente."
    async def rodar():
        j = _Lento(); o = OuvidoDuplex(j, S, asyncio.get_running_loop(), fluxo=SimpleNamespace(on_parcial=None), antecipador=None)
        o._tts = _TTSTurno(); o.mudo = True
        t0 = time.time()
        await o._tratar_texto("jaime, o que você é", b"", t_fim_fala=t0, t_texto=t0)
        assert o._tts.falas[0] in MULETAS
        lat = o.latencias.turnos[-1]
        assert lat["texto_frase"] < 0.6                                # a muleta (~0,2 s) conta, não a resposta (~0,9 s)
    asyncio.run(rodar())
