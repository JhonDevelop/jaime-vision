"""Funções (não só aparência) dos vídeos: sentinela de sistemas, holograma de qualquer objeto, saúde contra a média,
desvios de ontem, notícias contadas, capacidades reais, tela que se abre sozinha, wake word "Jarvis"."""
import asyncio, json
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from jaime.jarvis import holograma as holo, saude as sd, tela
from jaime.jarvis.briefing import Briefing, do_jaime
from jaime.jarvis.integracao import Jarvis, capacidades_de
from jaime.jarvis.sentinela import Alvo, Sentinela, alvos_do_ambiente
from jaime.jarvis.voz import cena


def coletar(gen):
    async def f():
        return [x async for x in gen]
    return asyncio.run(f())


# ── sentinela ─────────────────────────────────────────
def test_alvos_do_ambiente_so_https_ou_local():
    a = alvos_do_ambiente({"JAIME_SENTINELA": "BUB|https://bubapp.com.br;Local|http://127.0.0.1:8787/health;Ruim|http://exemplo.com;;sem-url|"})
    assert [x.nome for x in a] == ["BUB", "Local"]


def test_sentinela_cai_volta_e_conta_no_briefing():
    estado = {"ok": True}
    t = [1000.0]

    def handler(req):
        if not estado["ok"]:
            raise httpx.ConnectError("recusado")
        return httpx.Response(200, text="ok")
    ev, falas, diario = [], [], []
    s = Sentinela([Alvo("BUB", "https://bubapp.com.br")], http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
                  emitir=lambda tp, **d: ev.append((tp, d)), falar=falas.append, diario=diario.append, relogio=lambda: t[0])
    asyncio.run(s.rodada()); assert s.alvos[0].ok is True and s.resumo_falado() == "BUB está no ar, respondendo normal."
    estado["ok"] = False
    t[0] += 60; asyncio.run(s.rodada()); assert s.alvos[0].ok is True          # 1 falha não derruba (rede pisca)
    t[0] += 60; asyncio.run(s.rodada()); assert s.alvos[0].ok is False
    assert falas == ["BUB está fora do ar (ConnectError)."] and "fora do ar" in s.desvios()[0]
    t[0] += 60; asyncio.run(s.rodada()); assert len(falas) == 1                 # avisa uma vez só
    estado["ok"] = True
    t[0] += 600; asyncio.run(s.rodada())
    assert s.alvos[0].ok is True and "voltou, depois de 11 minutos fora" in diario[-1]
    assert s.desvios() == [f"BUB ficou fora 11 minutos e voltou às {datetime.fromtimestamp(t[0]).strftime('%H:%M')}"]
    assert [d["tipo"] for tp, d in ev if tp == "sentinela"] == ["caiu", "voltou"]


def test_sentinela_sem_alvos():
    assert "JAIME_SENTINELA" in Sentinela([]).resumo_falado() and asyncio.run(Sentinela([]).rodada()) == []


# ── holograma de qualquer objeto ──────────────────────
def test_holograma_gerado_pelo_modelo(tmp_path, monkeypatch):
    monkeypatch.setattr(holo, "PASTA", tmp_path)
    chamadas = []

    async def modelo(prompt, ctx):
        chamadas.append(prompt)
        return "claro: " + json.dumps({"pecas": [
            {"nome": "corpo", "forma": "caixa", "pos": [0, 0, 0], "tam": [2, 1, 1], "rot": [0, 0, 0], "explode": [0, 1, 0]},
            {"nome": "braço", "forma": "cilindro", "pos": [99, 0, 0], "tam": [0.2, 3, 0], "explode": [5, 0, 0]},
            {"nome": "<script>", "forma": "esfera", "pos": [0, 2, 0], "tam": [0.5, 0, 0], "explode": [0, 2, 0]},
            {"nome": "anel", "forma": "toro", "pos": [0, 0, 1], "tam": [1, 0.1, 0], "explode": [0, 0, 2]},
            {"nome": "hack", "forma": "codigo", "pos": [0, 0, 0], "tam": [1, 1, 1]},
            {"nome": "ponta", "forma": "cone", "pos": [0, 3, 0], "tam": [0.3, 1, 0], "explode": [0, 3, 0]}]})
    r = asyncio.run(holo.gerar("guitarra elétrica", modelo))
    assert r["modelo"] == "gerado" and len(r["pecas"]) == 5 and r["pecas"][1]["pos"][0] == 6 and r["pecas"][1]["explode"][0] == 4
    assert r["pecas"][2]["nome"] == "script" and "guitarra elétrica" in chamadas[0]
    assert (tmp_path / "guitarra-eletrica.json").is_file()
    assert holo.resolver("Guitarra elétrica")["modelo"] == "gerado"                     # 2ª vez: do cache, sem modelo
    assert asyncio.run(holo.gerar("guitarra elétrica", modelo)) and len(chamadas) == 1

    async def ruim(prompt, ctx):
        return "não sei desenhar isso"
    r2 = asyncio.run(holo.gerar("dragão", ruim))
    assert r2.get("falhou") and r2["exato"] is False


def test_cena_holograma_desconhecido_monta_com_modelo(tmp_path, monkeypatch):
    monkeypatch.setattr(holo, "PASTA", tmp_path)

    async def modelo(prompt, ctx):
        return json.dumps({"pecas": [{"forma": "caixa", "pos": [i, 0, 0], "tam": [1, 1, 1], "explode": [i, 1, 0]} for i in range(6)]})
    ev, telas = [], []
    j = Jarvis(Briefing(), None, None, emitir=lambda t, **d: ev.append((t, d)), env={}, modelo_holo=modelo, garantir_tela=lambda: telas.append(1))
    falas = coletar(j.gerador("cria um holograma de uma estação espacial"))
    assert falas[0].startswith("Montando o holograma de uma estação espacial") and "pronto" in falas[1]
    assert [d["acao"] for t, d in ev if t == "holograma"] == ["montando", "abrir"] and telas == [1]


# ── saúde contra a média do próprio João ──────────────
def test_saude_media_dos_ultimos_dias(tmp_path):
    hoje = date.today()
    for i in range(5, 0, -1):
        d = (hoje - timedelta(days=i)).isoformat()
        linha = {"dia": d, "resumo": {"distancia_km": 5.0, "passos": 8000, "fc_repouso": 55, "vfc": 60, "sono_h": 7.5, "calorias": 500}}
        with open(tmp_path / "historico.jsonl", "a") as f:
            f.write(json.dumps(linha) + "\n")
    r = sd.salvar({"distancia_km": 1.0, "passos": 3000, "fc_repouso": 63, "vfc": 40, "sono_h": 5.2}, tmp_path)
    assert r.base["fc_repouso"] == 55 and r.habitual_km == 5.0
    texto = " | ".join(r.observacoes)
    for trecho in ("distância abaixo do habitual", "passos bem abaixo", "8 bpm acima da sua média", "VFC 33% abaixo", "dormiu 5,2 h"):
        assert trecho in texto
    assert sum(1 for _ in open(tmp_path / "historico.jsonl")) == 6


def test_sono_no_health_auto_export():
    r = sd.interpretar({"data": {"metrics": [{"name": "sleep_analysis", "data": [{"asleep": 6.8, "date": date.today().isoformat()}]}]}})
    assert r.sono_h == 6.8


# ── briefing mais esperto ─────────────────────────────
def test_noticias_contadas_pelo_modelo():
    async def resumir(prompt, texto):
        if "UMA frase" in prompt:
            return '["Nas notícias de tecnologia, uma nova GPU dobra o desempenho em IA."]'
        return "[]"
    b = Briefing(resumir=resumir)
    segs = asyncio.run(b.seg_noticias([{"tema": "tecnologia", "titulo": "GPU nova", "fonte": "g1"}]))
    assert segs[0].fala == "Nas notícias de tecnologia, uma nova GPU dobra o desempenho em IA. A informação é do g1."


class FakeVault:
    def __init__(self, arquivos):
        self.a = arquivos

    def read(self, caminho):
        return self.a.get(caminho, "")


def test_desvios_de_ontem():
    ontem = (date.today() - timedelta(days=1)).isoformat()
    vencida = (date.today() - timedelta(days=2)).isoformat()

    class J:
        google = None
        hermes = None
        sentinela = Sentinela([])
        s = None
        vault = FakeVault({"30-Tarefas/Inbox.md": f"- [ ] Enviar proposta da BUB @bub ⏳ {vencida}\n- [ ] Futuro ⏳ 2099-01-01\n",
                           f"40-Diario/{ontem}.md": "- 02:00 ⚠ CoreAudio travado\n- 03:00 rotina falhou\n- 04:00 erro no Notion\n- 05:00 fim_turno erro\n"})
    d = do_jaime(J()).desvios()
    assert d[0] == "1 tarefa vencida, a primeira: Enviar proposta da BUB"
    assert d[1].startswith("o diário de ontem registrou 3 falhas; a última: erro no Notion")


# ── capacidades, sistemas, tela, wake word ────────────
@pytest.mark.parametrize("texto,esperado", [
    ("Jarvis fala para mim qual sua capacidade máxima", "capacidades"), ("quais são suas capacidades?", "capacidades"),
    ("o que você consegue fazer?", "capacidades"), ("como estão os sistemas?", "sistemas"), ("status dos servidores", "sistemas"),
    ("como estão os sistemas da BUB e manda pro Gabriel", None),
])
def test_cenas_novas(texto, esperado):
    c = cena(texto)
    assert (c[0] if c else None) == esperado


def test_capacidades_reais():
    class Eq:
        def vivos(self):
            return ["a", "b"]

    class G:
        conectado = True

    class J:
        sentinela = Sentinela([Alvo("BUB", "https://b.com"), Alvo("API", "https://a.com")])
        equipe = Eq(); google = G(); casa = None; hermes = None
    t = capacidades_de(J())
    assert "vigio 2 sistemas críticos" in t and "2 agentes trabalhando" in t and "e-mail e sua agenda" in t
    assert "Alexa" not in t and "Hermes" not in t and t.endswith("central de automação e inteligência operacional.")


def test_cena_sistemas_checa_na_hora():
    def handler(req):
        return httpx.Response(200)
    s = Sentinela([Alvo("BUB", "https://bubapp.com.br")], http=httpx.AsyncClient(transport=httpx.MockTransport(handler)), emitir=lambda *a, **k: None)
    j = Jarvis(Briefing(), None, None, emitir=lambda *a, **k: None, env={}, sentinela=s)
    assert coletar(j.gerador("como estão os sistemas?")) == ["BUB está no ar, respondendo normal. "]


def test_tela_abre_so_se_nao_estiver_aberta():
    rodados = []
    tela._ultimo_sinal = 0.0
    assert tela.garantir(rodar=rodados.append, sistema="Darwin", env={}) == "abri"
    assert rodados == [["caffeinate", "-u", "-t", "2"], ["open", "http://127.0.0.1:8787/hud/jarvis"]]
    tela.sinal_de_vida(); rodados.clear()
    assert tela.garantir(rodar=rodados.append, sistema="Windows", env={}) == "aberta" and rodados[0][0] == "powershell"
    assert tela.garantir(rodar=rodados.append, env={"JAIME_JARVIS_ABRIR_TELA": "off"}) == "desligado"
    tela._ultimo_sinal = 0.0


def test_wake_word_jarvis():
    from jaime.voice.escuta import interpretar_chamada
    assert interpretar_chamada("Jarvis, ativar monitor") == ("pediu", "ativar monitor")
    from jaime.identidade import VARIANTES_CONHECIDAS
    assert "jarvis" in VARIANTES_CONHECIDAS["jaime"]
