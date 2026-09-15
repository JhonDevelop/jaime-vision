"""Fase 3, Prompt B: fila de demandas (interrupção sem perda), Vigia por lote + confiança progressiva,
critérios da interjeição, e um turno de voz interrompido no meio da resposta que vira pergunta de retomada."""
import asyncio, time
from pathlib import Path
from types import SimpleNamespace
import pytest
from jaime.voice.fila import FilaDemandas
from jaime.vigia.hooks import Vigia, eh_aprovacao_lote, classe_de, descricao_de, assinatura_de
from jaime.vigia.confianca import Confianca, LIMIAR
from jaime.voice.duplex import hesitando, interjeicao, OuvidoDuplex
from jaime.voice.antecipador import Antecipacao
from jaime.brain.vault import Vault

def _hook(v, nome, args):
    return asyncio.run(v.pre_tool_use({"tool_name": nome, "tool_input": args}, None, None))

def _negada(r):
    return r.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

# ── fila ──────────────────────────────────────────────────────────────────
def test_fila_interrompe_guarda_o_que_faltou_e_planeja_retomada():
    f = FilaDemandas()
    d = f.nova("Jaime, me explica o plano da semana"); f.comecar(d)
    for s in ["Primeiro, o vídeo.", "Depois, a estamparia.", "Por fim, o BUB."]:
        f.gerada(d, s)
    f.interromper(d, nao_ditas=2)                      # o TTS cortou as duas últimas
    assert d.estado == "interrompida" and d.ditas == ["Primeiro, o vídeo."] and len(d.pendentes) == 2
    assert f.plano_de_retomada(d)[0] == "perguntar"    # o modelo não tinha terminado
    d.gerou_tudo = True
    assert f.plano_de_retomada(d) == ("automatica", "Voltando: Depois, a estamparia. Por fim, o BUB.")
    f.pedir_retomada(d)
    assert f.responder_retomada("sim, continua") == "sim" and f.responder_retomada("não, deixa") == "nao" and f.responder_retomada("abre o finder") is None
    assert "de onde parou" in f.texto_de_continuacao(d) and "Primeiro, o vídeo." in f.texto_de_continuacao(d)
    f.descartar(d)
    assert f.aguardando is None and f.responder_retomada("sim") is None and d.estado == "descartada"
    e = f.nova("outra"); f.comecar(e); f.gerada(e, "x."); f.concluir(e)
    assert e.estado == "concluida" and e.gerou_tudo and e.ditas == ["x."] and f.atual is None

# ── vigia por lote ────────────────────────────────────────────────────────
def test_vigia_anota_lote_pergunta_uma_vez_e_libera_exatamente_aquelas_acoes():
    v = Vigia()
    email = ("mcp__google__email_enviar", {"para": "rafael@x.com", "assunto": "Atraso", "corpo": "Vou atrasar 10 min"})
    r = _hook(v, *email)
    assert _negada(r) and "confirmação em lote" in r["hookSpecificOutput"]["permissionDecisionReason"]
    assert _negada(_hook(v, "Bash", {"command": "git push origin main"}))
    assert _negada(_hook(v, *email)) and len(v.lote) == 2                 # repetiu: não duplica
    assert v.pedir_lote() == "Você deseja que eu enviar o e-mail para rafael@x.com («Atraso») e rodar `git push origin main`?"
    assert eh_aprovacao_lote("Sim.") and eh_aprovacao_lote("pode fazer") and eh_aprovacao_lote("faz") and not eh_aprovacao_lote("sim, mas depois")
    acoes = v.liberar_lote()
    assert [a.classe for a in acoes] == ["mcp__google__email_enviar", "bash:git push"] and v.lote == [] and v.lote_executado
    assert _hook(v, *email) == {}                                          # mesma assinatura: passa
    assert _hook(v, "Bash", {"command": "git  push origin main"}) == {}    # espaços a mais: mesma assinatura
    assert _negada(_hook(v, *email))                                       # só uma vez
    assert _negada(_hook(v, "mcp__google__email_enviar", {"para": "outro@x.com", "corpo": "x"}))   # não estava no lote
    assert v.descartar_lote() == 2 and v.lote == []                       # a repetida e a 'outro@' voltaram ao lote

def test_vigia_lote_tolera_variacao_de_texto_na_mesma_classe():
    v = Vigia()
    _hook(v, "mcp__meta__enviar", {"para": "5516999", "texto": "chego às 10"})
    v.liberar_lote()
    assert _hook(v, "mcp__meta__enviar", {"para": "5516999", "texto": "chego às 10h"}) == {}   # texto variou, mesma classe/ferramenta
    assert _negada(_hook(v, "mcp__meta__enviar", {"para": "5516999", "texto": "outra"}))

def test_classes_descricoes_e_assinaturas():
    assert classe_de("Bash", {"command": "sudo rm -rf /x"}) == "bash:rm -rf" or classe_de("Bash", {"command": "sudo rm -rf /x"}) == "bash:sudo"
    assert classe_de("Edit", {"file_path": "/a/.env"}) == "edit:.env" and classe_de("Edit", {"file_path": "/a/jaime/vigia/hooks.py"}) == "edit:vigia"
    assert descricao_de("mcp__google__email_enviar", {"para": "a@b", "assunto": "Oi"}) == "enviar o e-mail para a@b («Oi»)"
    assert descricao_de("mcp__maos__clicar", {"alvo": "Finalizar compra"}) == "clicar em 'Finalizar compra' no browser"
    assert descricao_de("mcp__x__delete", {"id": "42"}) == "apagar 42"
    assert assinatura_de("Bash", {"command": "a  b"}) == assinatura_de("Bash", {"command": "a b"})
    assert assinatura_de("mcp__g__email_enviar", {"para": "a", "corpo": "1"}) == assinatura_de("mcp__g__email_enviar", {"para": "a", "corpo": "2"})

def test_confianca_progressiva_propoe_na_quinta_e_libera_com_sim(tmp_path):
    (tmp_path / "01-Estado").mkdir()
    vault = Vault(tmp_path)
    c = Confianca(vault); v = Vigia(c)
    email = ("mcp__google__email_enviar", {"para": "a@b", "corpo": "x"})
    for i in range(LIMIAR):
        assert _negada(_hook(v, *email)); v.liberar_lote()
        assert _hook(v, *email) == {}                                              # executa a ação liberada
        prop = c.aprovar(v.ultimo_lote_classes)
        assert (prop is None) == (i < LIMIAR - 1)
    assert "sem perguntar" in prop and c.pendente == "mcp__google__email_enviar"
    assert c.responder("abre o finder") is None
    assert "passa a ser livre" in c.responder("sim")
    assert c.livre("mcp__google__email_enviar") and _hook(v, *email) == {}          # sem lote, sem confirmo
    c2 = Confianca(vault)                                                          # persistiu no vault
    assert c2.livre("mcp__google__email_enviar") and "| mcp__google__email_enviar | 5 | sim |" in vault.read("01-Estado/Confianca.md")
    c2.corrigir(["mcp__google__email_enviar"]); c2.revogar("mcp__google__email_enviar")
    assert not c2.livre("mcp__google__email_enviar") and _negada(_hook(Vigia(c2), *email))
    c3 = Confianca(vault); c3.contagem["bash:git push"] = LIMIAR - 1
    assert c3.aprovar(["bash:git push"]) and c3.responder("não, continua perguntando") == "Certo, continuo perguntando." and c3.contagem["bash:git push"] == 0

def test_vigia_armar_por_tempo_continua_valendo_para_o_autonomo():
    v = Vigia(); v.armar()
    assert _hook(v, "Bash", {"command": "git push origin main"}) == {}
    assert _negada(_hook(v, "Bash", {"command": "git push origin main"}))
    assert _negada(_hook(v, "Write", {"file_path": "vault/00-Jaime/Origem.md"}))
    assert [a.classe for a in v.lote] == ["bash:git push"]                   # 00-Jaime nunca entra no lote

# ── interjeição ───────────────────────────────────────────────────────────
def test_hesitando_e_interjeicao():
    assert hesitando("é… tipo… então eu queria que você, hum, abrisse")
    assert hesitando("abre abre abre o finder")
    assert hesitando("manda mensagem pro rafael manda mensagem pro rafael dizendo que")
    assert not hesitando("abre o finder e o terminal agora")
    a = Antecipacao(texto="x", acao_prevista="Mandar mensagem pro Rafael", completude=0.95)
    assert interjeicao(a) == "Entendi. Quer que eu mandar mensagem pro Rafael?"
    assert interjeicao(Antecipacao(texto="x", acao_prevista="a b c d e f g h i j k")) == ""
    assert interjeicao(Antecipacao(texto="x")) == ""

# ── turno interrompido → fila → retomada ─────────────────────────────────
class _TTS:
    def __init__(self): self.falas = []; self.t_inicio_audio = 0.0; self.ajustes = None; self.instrucoes = ""; self.parou = 0
    def enfileirar(self, t): self.t_inicio_audio = self.t_inicio_audio or time.time(); self.falas.append(t)
    def falar(self, t): self.enfileirar(t)
    def aguardar(self, timeout=0): pass
    def parar(self): self.parou += 1; return 1
    def pre_sintetizar(self, t): return b""
    def tocar_pronto(self, t, p): self.falas.append(t)
    @property
    def ocupado(self): return False

class _Jaime:
    def __init__(self):
        self.acesso = SimpleNamespace(liberado=True); self.vault = SimpleNamespace(diario=lambda *a, **k: None); self.humor = None
        self.falante_atual = ""; self.pedidos = []; self.aguardando_nome = False; self.interrupts = 0
        self._client = SimpleNamespace(interrupt=self._interrupt)
    async def _interrupt(self): self.interrupts += 1
    def avisos_do_dia(self): return ""
    async def ask_stream(self, texto, canal="voice", contexto=""):
        self.pedidos.append(texto)
        if texto.startswith("Continue a resposta anterior"):
            yield "Por fim, o BUB. "; return
        for t in ["Primeiro, o vídeo. ", "Depois, a estamparia. ", "Por fim, o BUB."]:
            yield t; await asyncio.sleep(0.03)

S = SimpleNamespace(ativacao="nome", janela_ativa_s=25, nome="jaime", deepgram_key="", openai_key="")

def test_barge_in_interrompe_o_modelo_guarda_na_fila_e_retoma_com_sim():
    async def rodar():
        loop = asyncio.get_running_loop()
        j = _Jaime(); o = OuvidoDuplex(j, S, loop, fluxo=SimpleNamespace(on_parcial=None), antecipador=None)
        o._tts = _TTS(); o.mudo = True; o.barge_in = "on"          # independente do .env da máquina
        turno = asyncio.create_task(o._tratar_texto("jaime, me explica o plano da semana", b"", t_fim_fala=time.time(), t_texto=time.time()))
        await asyncio.sleep(0.045)                                   # 1ª frase já saiu; o modelo ainda gera
        for _ in range(10): o._barge(0.1, 200.0, b"\x00" * 1024)     # calibra o eco
        for _ in range(8): o._barge(0.99, 2000.0, b"\x00" * 1024)    # o João fala por cima
        await turno
        assert o._tts.parou == 1 and j.interrupts == 1
        d = o.fila.itens[0]
        assert d.estado == "interrompida" and "Primeiro, o vídeo." in d.ditas and not d.gerou_tudo
        # demanda nova (curta) atendida; depois ele pergunta se continua a antiga
        o.interrompido = False; o.mudo = False
        await o._tratar_texto("jaime, que horas são", b"", t_fim_fala=time.time(), t_texto=time.time())
        assert o.fila.aguardando is d and o._tts.falas[-1] == "Continuo o que eu dizia sobre me explica o plano da semana?"
        await o._tratar_texto("sim", b"", t_fim_fala=time.time(), t_texto=time.time())
        assert j.pedidos[-1].startswith("Continue a resposta anterior") and o._tts.falas[-1] == "Por fim, o BUB." and o.fila.aguardando is None
        assert d.estado in ("retomada", "interrompida")
    asyncio.run(rodar())
