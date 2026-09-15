"""Modo conversa (Realtime) com WebSocket falso: gate 'é comigo?', transcrição → response.create, ferramenta jaime → output."""
import asyncio, base64, json, time
from types import SimpleNamespace
from jaime.voice.tempo_real import Conversa, Gate, instrucoes

class _WS:
    def __init__(self): self.enviados = []
    async def send(self, s): self.enviados.append(json.loads(s))
    def tipos(self): return [e["type"] for e in self.enviados]

class _Jaime:
    def __init__(self, liberado=True):
        self.acesso = SimpleNamespace(liberado=liberado); self.identidade = SimpleNamespace(nome="Jaime"); self.humor = None
        self.pedidos = []
    async def ask(self, texto, canal="cli", contexto=""):
        self.pedidos.append(texto); return "Palavra-passe, por favor." if not self.acesso.liberado else f"feito: {texto}"
    async def _mundo(self, texto): return "Combinado: 15/09 às 09:00 — beber água."

S = SimpleNamespace(ativacao="nome", janela_ativa_s=25, realtime_model="gpt-realtime-2", realtime_voz="cedar", openai_key="x", lat=0, lon=0)

def _conversa(jaime):
    loop = asyncio.new_event_loop()
    c = Conversa(jaime, S, loop); c.ws = _WS(); return c

def test_gate_nome_janela_e_trancado():
    g = Gate("nome", 25)
    assert g.avaliar("ô jaime, abre o finder", True) == (True, "abre o finder")
    assert g.avaliar("e aí, tudo bem?", True)[0]                      # janela ativa depois de chamado
    g.ativo_ate = 0
    assert g.avaliar("e aí, tudo bem?", True) == (False, "")
    assert g.avaliar("1 2 3 4 1 2 3 4", False) == (True, "1 2 3 4 1 2 3 4")   # trancado: tudo vai ao Jaime
    assert g.avaliar("ok", True) == (False, "")

def test_transcricao_com_nome_pede_resposta_e_sem_nome_ignora():
    c = _conversa(_Jaime())
    asyncio.run(c.tratar({"type": "conversation.item.input_audio_transcription.completed", "transcript": "Jaime, que horas são?"}))
    assert c.ws.tipos() == ["response.create"]
    asyncio.run(c.tratar({"type": "conversation.item.input_audio_transcription.completed", "transcript": "conversa da sala"}))
    assert c.ws.tipos() == ["response.create", "response.create"]   # janela ativa (25 s): continua sem repetir o nome
    c.gate.ativo_ate = 0
    asyncio.run(c.tratar({"type": "conversation.item.input_audio_transcription.completed", "transcript": "conversa da sala"}))
    assert len(c.ws.enviados) == 2                     # ignorada

def test_trancado_vai_ao_jaime_e_realtime_repete():
    j = _Jaime(liberado=False); c = _conversa(j)
    asyncio.run(c.tratar({"type": "conversation.item.input_audio_transcription.completed", "transcript": "um dois três quatro"}))
    assert j.pedidos == ["um dois três quatro"]
    assert c.ws.enviados[0]["response"]["instructions"].endswith("Palavra-passe, por favor.")

def test_ferramenta_jaime_devolve_output_e_pede_resposta():
    j = _Jaime(); c = _conversa(j)
    asyncio.run(c.tratar({"type": "response.function_call_arguments.done", "name": "jaime", "arguments": json.dumps({"texto": "abre o Finder"}), "call_id": "c1"}))
    assert j.pedidos == ["abre o Finder"]
    assert c.ws.enviados[0]["item"]["call_id"] == "c1" and c.ws.enviados[0]["item"]["output"] == "feito: abre o Finder"
    assert c.ws.tipos()[-1] == "response.create" and not c.ocupado

def test_audio_e_transcricao_de_saida_viram_eventos():
    c = _conversa(_Jaime())
    asyncio.run(c.tratar({"type": "response.output_audio.delta", "delta": base64.b64encode(b"\x00\x01" * 100).decode()}))
    assert c._saida.qsize() == 1
    asyncio.run(c.tratar({"type": "response.output_audio_transcript.delta", "delta": "São 14 e 05."}))
    asyncio.run(c.tratar({"type": "response.output_audio_transcript.done"}))
    assert c._fala_atual == ""
    assert "jaime" in instrucoes("Jaime") and "Vega" in instrucoes("Vega")
    sess = c._sessao()["session"]
    assert sess["audio"]["input"]["turn_detection"]["create_response"] is False and [t["name"] for t in sess["tools"]] == ["jaime", "hora", "clima", "lembrete"]

def test_gate_esta_ai_liga_ate_dispensar():
    g = Gate("nome", 25)
    assert g.avaliar("Jaime, está aí?", True)[0] and g.ativo_ate == float("inf")
    assert g.avaliar("qualquer coisa sem nome", True)[0]
    assert g.avaliar("por enquanto é só isso", True) == (True, "__descansar__")
    assert g.avaliar("qualquer coisa sem nome", True) == (False, "")
