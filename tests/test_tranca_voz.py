"""Tranca por voz (M-02 do MENTE.md): trancado, o Jaime não responde "Palavra-passe, por favor." a conversa ambiente;
senha certa com voz incerta pede para repetir e depois para digitar; senha digitada não depende da voz."""
import asyncio, time
from types import SimpleNamespace
from jaime.vigia.acesso import Acesso, hash_senha
from jaime.voice.duplex import OuvidoDuplex

SENHA = "98 76 54 32"

class _TTS:
    def __init__(self): self.falas = []; self.t_inicio_audio = 0.0; self.ajustes = None; self.instrucoes = ""
    def enfileirar(self, t): self.falas.append(t)
    def falar(self, t): self.falas.append(t)
    def aguardar(self, timeout=0): pass
    def parar(self): return 0
    def pre_sintetizar(self, t): return b""
    def tocar_pronto(self, t, p): self.falas.append(t)
    @property
    def ocupado(self): return False

class _Jaime:
    def __init__(self):
        self.acesso = Acesso(hash_senha(SENHA)); self.vault = None; self.humor = None
        self.falante_atual = ""; self.pedidos = []; self.aguardando_nome = False
        self._client = SimpleNamespace(interrupt=None)
    def avisos_do_dia(self): return ""
    async def ask_stream(self, texto, canal="voice", contexto=""):
        self.pedidos.append(texto); yield "ok"

S = SimpleNamespace(ativacao="nome", janela_ativa_s=25, nome="jaime", deepgram_key="", openai_key="")

def _ouvido():
    loop = asyncio.get_running_loop()
    j = _Jaime(); o = OuvidoDuplex(j, S, loop, fluxo=SimpleNamespace(on_parcial=None), antecipador=None)
    o._tts = _TTS(); o.mudo = True
    return j, o

async def _fala(o, texto):
    await o._tratar_texto(texto, b"", t_fim_fala=time.time(), t_texto=time.time())

def test_trancado_conversa_ambiente_fica_em_silencio():
    async def rodar():
        j, o = _ouvido()
        for t in ("vai para o caralho.", "Meu Deus,", "ele está criando um monte de tarefas"):
            await _fala(o, t)
        assert j.pedidos == [] and o._tts.falas == []            # nada chegou ao modelo, nada foi falado
        await _fala(o, SENHA)                                     # a senha, mesmo sem o nome, passa
        assert j.pedidos == [SENHA]
        await _fala(o, "jaime, abre o finder")                    # e chamar pelo nome também passa
        assert j.pedidos[-1] == "abre o finder"
    asyncio.run(rodar())

def test_trancado_com_janela_ativa_ainda_responde():
    async def rodar():
        j, o = _ouvido(); o.ativo_ate = float("inf")             # "Jaime, está aí?" já foi dito
        await _fala(o, "abre o finder")
        assert j.pedidos == ["abre o finder"]                     # chega a _porta, que pede a senha
    asyncio.run(rodar())

# ── _porta: voz incerta e canal digitado ───────────────────────────────────────
def _jaime_porta(falante="", liberado=False):
    from jaime.orchestrator.jaime import Jaime
    j = Jaime.__new__(Jaime)
    j.acesso = Acesso(hash_senha(SENHA)); j.falante_atual = falante; j._senha_incerta = 0
    j.diario_linhas = []; j.vault = SimpleNamespace(diario=lambda t, s: j.diario_linhas.append((t, s)))
    j.proposta_renomear = None; j.aguardando_nome = False
    j.vigia = SimpleNamespace(lote=None); j.confianca = SimpleNamespace(pendente=None)
    j.estado = SimpleNamespace(resumo_curto=lambda: "Tudo certo.")
    j.gravador = SimpleNamespace(gravando=False)
    if liberado: j.acesso.tentar(SENHA)
    return j

def test_senha_com_voz_incerta_repete_uma_vez_depois_pede_para_digitar():
    j = _jaime_porta("incerto")
    assert j._porta(SENHA).startswith("Não reconheci bem") and not j.acesso.liberado
    assert j._porta(SENHA).startswith("Não consegui confirmar") and not j.acesso.liberado
    assert j.diario_linhas and "digitar" in j.diario_linhas[-1][0]
    j.falante_atual = "João"                                      # repetiu, a EMA fechou em João
    assert j._porta(SENHA).startswith("Acesso liberado") and j.acesso.liberado

def test_senha_de_outra_voz_conhecida_continua_recusada_mas_desconhecido_sem_perfil_passa():
    j = _jaime_porta("Gabriel")
    assert j._porta(SENHA) == "Isso só com o João, Gabriel." and not j.acesso.liberado
    j = _jaime_porta("desconhecido")
    assert j._porta(SENHA) == "Isso só com o João." and not j.acesso.liberado
    j = _jaime_porta("")                                          # sem perfil de voz: comportamento antigo
    assert j._porta(SENHA).startswith("Acesso liberado")

def test_senha_digitada_no_hud_ignora_a_voz_da_ultima_fala():
    j = _jaime_porta("desconhecido")
    assert j._porta(SENHA, canal="hud").startswith("Acesso liberado") and j.acesso.liberado
    j = _jaime_porta("Gabriel")
    assert j._porta(SENHA, canal="telegram").startswith("Acesso liberado")
