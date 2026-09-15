"""Meta (assinatura, handshake, parsing, dono vs terceiro) e modo autônomo (planejador/executor offline, pausa e retomada)."""
import asyncio, hashlib, hmac, json
from pathlib import Path
import pytest
from jaime.brain.vault import Vault
from jaime.conexoes.meta import Meta, verificar_assinatura, handshake, extrair
from jaime.autonomo import Autonomo, Etapa
from jaime.vigia.hooks import Vigia

@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    for d in ("00-Jaime", "40-Diario"):
        (tmp_path / d).mkdir()
    return Vault(tmp_path)

class _Jaime:
    def __init__(self, vault, respostas=None):
        self.vault = vault; self.vigia = Vigia(); self.pedidos = []; self.respostas = list(respostas or []); self._custo_sessao = 0.0
    async def ask(self, texto, canal="cli", contexto=""):
        self.pedidos.append((texto, canal)); self._custo_sessao += 0.01
        return self.respostas.pop(0) if self.respostas else "ok"

class _Http:
    def __init__(self): self.posts = []
    async def post(self, url, json=None, headers=None):
        self.posts.append((url, json))
        class R:
            def raise_for_status(self): pass
            def json(self): return {"messages": [{"id": "wamid.1"}], "message_id": "ig.1"}
        return R()

def test_assinatura_e_handshake():
    corpo = b'{"x":1}'; seg = "segredo"
    assinatura = "sha256=" + hmac.new(seg.encode(), corpo, hashlib.sha256).hexdigest()
    assert verificar_assinatura(seg, corpo, assinatura) and not verificar_assinatura(seg, corpo + b" ", assinatura)
    assert not verificar_assinatura("", corpo, assinatura)
    assert handshake({"hub.mode": "subscribe", "hub.verify_token": "t", "hub.challenge": "123"}, "t") == "123"
    assert handshake({"hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "123"}, "t") is None

WA = {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {
    "contacts": [{"wa_id": "5516999990000", "profile": {"name": "Zé"}}],
    "messages": [{"from": "5516999990000", "id": "wamid.a", "type": "text", "text": {"body": "Tem capacete tamanho G?"}}]}}]}]}
IG = {"object": "instagram", "entry": [{"messaging": [{"sender": {"id": "777"}, "message": {"mid": "m1", "text": "oi, faz frete?"}},
                                                        {"sender": {"id": "999"}, "message": {"mid": "m2", "text": "eco", "is_echo": True}}]}]}

def test_extrair_mensagens():
    ms = extrair(WA); assert ms[0].plataforma == "whatsapp" and ms[0].nome == "Zé" and "capacete" in ms[0].texto
    ms = extrair(IG); assert len(ms) == 1 and ms[0].plataforma == "instagram" and ms[0].de == "777"

def test_dono_responde_terceiro_vira_rascunho(vault):
    j = _Jaime(vault, ["Tenho sim, G e GG.", "RESUMO: cliente pergunta se faz frete | RASCUNHO: Fazemos sim, para todo o Brasil."])
    http = _Http()
    meta = Meta("tok", "seg", "vt", "PHONE", "IGID", j, dono_whatsapp="5516999990000", http=http)
    assert meta.ativo
    feitos = asyncio.run(meta.receber(WA))
    assert feitos[0]["acao"] == "respondido" and http.posts[0][1]["to"] == "5516999990000" and http.posts[0][1]["text"]["body"] == "Tenho sim, G e GG."
    feitos = asyncio.run(meta.receber(IG))
    assert feitos[0]["acao"] == "rascunho" and "todo o Brasil" in feitos[0]["rascunho"] and len(http.posts) == 1   # nada enviado
    assert "rascunho pendente" in vault.read(vault.daily_rel()) and len(meta.pendentes) == 1

def test_vigia_segura_envio_meta():
    v = Vigia()
    r = asyncio.run(v.pre_tool_use({"tool_name": "mcp__meta__enviar_whatsapp", "tool_input": {"para": "x", "texto": "y"}}, None, None))
    assert r["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert asyncio.run(v.pre_tool_use({"tool_name": "mcp__meta__mensagens_pendentes", "tool_input": {}}, None, None)) == {}

def test_autonomo_objetivo_offline_com_pausa_e_retomada(vault):
    j = _Jaime(vault)
    async def planejador(m):
        return [Etapa("criar pasta", "pasta existe"), Etapa("enviar e-mail", "e-mail enviado"), Etapa("relatório", "nota escrita")]
    chamadas = []
    async def executor(m, i):
        chamadas.append(i)
        if i == 1 and chamadas.count(1) == 1:
            j.vigia.ultima_bloqueada = "ação externa: email_enviar"
            return "Tentei enviar, mas o VIGIA bloqueou. Aceite: NÃO."
        return f"Feito. Critério de aceite: SIM."
    a = Autonomo(j, horas=1, custo_usd=1, ferramentas="Read", planejador=planejador, executor=executor)
    async def rodar():
        t = asyncio.create_task(a.objetivo("organizar o lançamento", 1))
        for _ in range(50):
            await asyncio.sleep(0.01)
            if a.missao and a.missao.estado == "pausada": break
        assert a.missao.estado == "pausada" and a.confirmar()
        return await t
    m = asyncio.run(rodar())
    assert m.estado == "concluida" and [e.estado for e in m.etapas] == ["ok", "ok", "ok"] and chamadas == [0, 1, 1, 2]
    d = vault.read(vault.daily_rel())
    assert "Plano: criar pasta → enviar e-mail → relatório" in d and "pausada pelo Vigia" in d and "Relatório do objetivo" in d
    with pytest.raises(RuntimeError):
        a.missao.estado = "rodando"; asyncio.run(a.objetivo("outro", 1))

def test_autonomo_respeita_limite_de_custo(vault):
    j = _Jaime(vault)
    async def planejador(m): return [Etapa("a", "x"), Etapa("b", "y")]
    async def executor(m, i): m.custo += 5; return "Aceite: SIM."
    a = Autonomo(j, horas=1, custo_usd=1, ferramentas="Read", planejador=planejador, executor=executor)
    m = asyncio.run(a.objetivo("gastar", 1))
    assert m.estado == "interrompida" and m.etapas[0].estado == "ok" and m.etapas[1].estado == "pendente"
