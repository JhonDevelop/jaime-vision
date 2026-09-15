"""Casa (HA com HTTP dublê), câmera (só montagem), visão contínua (decisor/executor offline, kill switch, limite)."""
import asyncio
from pathlib import Path
import pytest
from jaime.brain.vault import Vault
from jaime.casa.homeassistant import Casa, texto_estados
from jaime.maos.visao import Visao, extrair_acao, quer_parar
from jaime.vigia.hooks import Vigia

class _Http:
    def __init__(self):
        self.calls = []
        self.estados = [{"entity_id": "light.escritorio", "state": "off", "attributes": {"friendly_name": "Luz do Escritório"}},
                        {"entity_id": "switch.tomada_sala", "state": "on", "attributes": {"friendly_name": "Tomada da Sala"}},
                        {"entity_id": "sensor.temp", "state": "24.5", "attributes": {"friendly_name": "Temperatura", "unit_of_measurement": "°C"}}]
    async def request(self, metodo, url, json=None, headers=None):
        self.calls.append((metodo, url.split("/api/")[1], json))
        class R:
            content = b"[]"
            def __init__(s, d): s.d = d
            def raise_for_status(s): pass
            def json(s): return s.d
        return R(self.estados if url.endswith("/states") else {})

def test_casa_estados_achar_ligar_desligar():
    http = _Http(); casa = Casa("http://ha:8123", "tok", http=http)
    assert casa.ativa and not Casa("", "").ativa
    est = asyncio.run(casa.estados("escrit"))
    assert len(est) == 1 and "Luz do Escritório (light.escritorio): off" in texto_estados(est)
    assert asyncio.run(casa.ligar("apaga a luz do escritório")) == "turn_on → light.escritorio"
    assert http.calls[-1] == ("POST", "services/light/turn_on", {"entity_id": "light.escritorio"})
    assert asyncio.run(casa.desligar("tomada da sala")) == "turn_off → switch.tomada_sala"
    assert "não achei" in asyncio.run(casa.ligar("piscina"))

def test_extrair_acao_e_kill_switch():
    assert extrair_acao('vou clicar {"acao": "clicar", "x": 10, "y": 20}') == {"acao": "clicar", "x": 10, "y": 20}
    assert extrair_acao("sem json")["acao"] == "parar"
    assert extrair_acao('{"acao": "explodir"}')["acao"] == "parar"
    assert quer_parar("para!") and quer_parar("Chega.") and not quer_parar("para onde?")

class _Jaime:
    def __init__(self, tmp):
        for d in ("00-Jaime", "40-Diario"): (tmp / d).mkdir(parents=True, exist_ok=True)
        self.vault = Vault(tmp)

def test_visao_roda_ate_parar_pelo_modelo(tmp_path):
    j = _Jaime(tmp_path); acoes = []
    async def decisor(s, captura, n):
        return {"acao": "tecla", "combo": "right"} if n < 3 else {"acao": "parar", "motivo": "cheguei"}
    v = Visao(j, max_passos=10, intervalo_s=0, decisor=decisor, executor=lambda a: acoes.append(a["acao"]) or "ok", capturador=lambda: "/tmp/x.png")
    s = asyncio.run(v.rodar("passar de fase"))
    assert not s.ativa and s.fim_motivo == "cheguei" and acoes == ["tecla", "tecla"] and len(s.passos) == 3
    assert "sessão encerrada (3 passos)" in j.vault.read(j.vault.daily_rel())

def test_visao_kill_switch_e_limite(tmp_path):
    j = _Jaime(tmp_path)
    async def decisor(s, captura, n):
        if n == 2: v.parar("o João mandou parar")
        return {"acao": "esperar", "segundos": 0}
    v = Visao(j, max_passos=5, intervalo_s=0, decisor=decisor, executor=lambda a: "ok", capturador=lambda: "x")
    s = asyncio.run(v.rodar("teste"))
    assert s.fim_motivo == "o João mandou parar" and len(s.passos) == 1
    v2 = Visao(j, max_passos=3, intervalo_s=0, decisor=lambda s, c, n: _async({"acao": "esperar", "segundos": 0}), executor=lambda a: "ok", capturador=lambda: "x")
    s2 = asyncio.run(v2.rodar("limite"))
    assert s2.fim_motivo == "limite de 3 passos" and len(s2.passos) == 3

async def _async(x):
    return x

def test_vigia_libera_tela_com_ou_sem_sessao_de_visao():
    v = Vigia()
    h = lambda: asyncio.run(v.pre_tool_use({"tool_name": "mcp__tela__tela_clicar", "tool_input": {"x": 1, "y": 1}}, None, None))
    assert h() == {}
    v.sessao_livre = lambda: True
    assert h() == {}
    v.sessao_livre = lambda: False
    assert h() == {}
