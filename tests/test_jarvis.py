"""Cenas do Jarvis: briefing do bom dia, monitor (rosto + saúde), holograma, frases de voz, rotas e bibliotecas locais."""
import asyncio, io, json, os, stat, zipfile
from datetime import datetime
from pathlib import Path

import pytest

from jaime.jarvis import holograma as holo
from jaime.jarvis import saude as sd
from jaime.jarvis.briefing import Briefing, quer_briefing
from jaime.jarvis.integracao import Jarvis
from jaime.jarvis.monitor import Monitor
from jaime.jarvis.noticias import ler_rss, temas_do_ambiente
from jaime.jarvis.rosto import Rostos
from jaime.jarvis.voz import cena
from jaime.jarvis.vendor import modelo_mao_valido, arquivo

CLIMA = {"current": {"temperature_2m": 26.7, "weather_code": 1},
         "daily": {"temperature_2m_max": [27.5], "temperature_2m_min": [23.3], "precipitation_probability_max": [62]}}


def coletar(gen):
    async def f():
        return [x async for x in gen]
    return asyncio.run(f())


def briefing(eventos, **kw):
    base = dict(clima=lambda: CLIMA, agenda=lambda: [], emails=lambda: [{"de": "Stripe <x@stripe.com>", "assunto": "Atualize os dados"}] * 3,
                noticias=lambda: [{"tema": "tecnologia", "titulo": "Nova GPU", "fonte": "g1", "imagem": "", "link": ""},
                                  {"tema": "política", "titulo": "Pesquisa nova", "fonte": "Veja", "imagem": "", "link": ""}],
                saude=lambda: sd.Resumo(observacoes=["a", "b"]), desvios=lambda: [], cidade="Maragogi",
                emitir=lambda tipo, **d: eventos.append((tipo, d)))
    base.update(kw)
    return Briefing(**base)


def rodar(b):
    return coletar(b.rodar(cps=1e9, pausa_etapa=0))


# ── briefing ──────────────────────────────────────────
@pytest.mark.parametrize("texto,hora,ja,esperado", [
    ("bom dia", 8, False, True), ("Bom dia, Jaime!", 7, False, True), ("bom dia", 8, True, False),
    ("bom dia", 15, False, False), ("bom dia, abre o Finder", 8, False, False), ("me dá o briefing", 20, True, True),
    ("o que eu preciso saber hoje", 22, True, True), ("boa tarde", 14, False, False),
])
def test_quer_briefing(texto, hora, ja, esperado):
    assert quer_briefing(texto, datetime(2026, 9, 30, hora), ja) is esperado


def test_roteiro_na_ordem_do_video():
    ev = []
    falas = rodar(briefing(ev))
    assert falas[0].startswith("Revisei o que já está consolidado desde ontem. Sem desvios relevantes.")
    assert falas[1] == "Em Maragogi, a temperatura mínima será de 23,3 graus e a máxima de 27,5, com chance de chuva de 62%."
    assert falas[2] == "Sua agenda está livre hoje."
    assert falas[3].startswith("Há 3 e-mails na caixa, dos quais três merecem atenção.")
    assert falas[4] == "Nas notícias de tecnologia, Nova GPU. A informação é do g1."
    assert falas[5] == "Na política, Pesquisa nova. A informação é do Veja."
    assert falas[6] == "Tenho duas observações sobre seus dados de saúde."
    assert falas[7] == "Hoje, mantenha o foco no essencial."
    fases = [d["fase"] for t, d in ev if t == "briefing"]
    assert fases[0] == "segmento" and fases[1] == "inicio"            # "sem desvios" antes do card BRIEFING MATINAL
    assert fases.count("etapa") == 5 and "radar" in fases and fases[-1] == "fim"
    segs = [d for t, d in ev if t == "briefing" and d["fase"] == "segmento"]
    assert [s["card"]["tipo"] for s in segs] == ["status", "clima", "agenda", "emails", "noticia", "noticia", "saude", "foco"]


def test_fonte_que_falha_some_sem_derrubar():
    ev = []

    def quebra():
        raise RuntimeError("sem rede")
    falas = rodar(briefing(ev, clima=quebra, emails=lambda: None, noticias=lambda: []))
    assert not any("temperatura" in f for f in falas) and not any("e-mails" in f for f in falas)
    assert any(d.get("etapa") == "CLIMA" and d.get("ok") is False for t, d in ev if t == "briefing" and d["fase"] == "etapa")


def test_desvio_e_foco():
    ev = []
    falas = rodar(briefing(ev, desvios=lambda: ["o microfone está com erro"], foco=lambda: "a proposta da BUB"))
    assert "Há um ponto de atenção: o microfone está com erro." in falas[0]
    assert falas[-1] == "Hoje, mantenha o foco em a proposta da BUB."


def test_emails_resumidos_pelo_modelo_e_fallback():
    async def resumir(prompt, texto):
        return 'aqui: [{"de": "Stripe", "acao": "Envie o documento até 22/10."}]'
    ev = []
    b = briefing(ev, resumir=resumir)
    s = asyncio.run(b.seg_emails([{"de": "a", "assunto": "x"}] * 20))
    assert s.fala == "Há 20 e-mails na caixa, dos quais um merece atenção. O principal: Envie o documento até 22/10."
    assert s.card["total"] == 20 and s.card["agir"] == 1 and s.card["itens"][0]["de"] == "STRIPE"

    async def lixo(prompt, texto):
        return "não sei"
    s2 = asyncio.run(briefing([], resumir=lixo).seg_emails([{"de": "Ana <a@b.c>", "assunto": "Contrato"}]))
    assert "nenhum" not in s2.fala or s2.card["agir"] == 0


def test_agenda_com_compromissos():
    s = briefing([]).seg_agenda([{"titulo": "Reunião BUB", "hora": "09:30", "inicio": "2026-09-30T09:30:00-03:00"}])
    assert s.fala == "Você tem 1 compromisso hoje; o primeiro às 09:30: Reunião BUB."


# ── notícias ──────────────────────────────────────────
G1 = """<?xml version="1.0"?><rss xmlns:media="http://search.yahoo.com/mrss/"><channel><title>g1 &gt; Tecnologia</title>
<item><title>Chip novo &amp; rápido</title><link>https://g1.globo.com/x</link><media:content url="https://s2.glbimg.com/a.jpg" medium="image"/>
<description><![CDATA[<img src="https://outra.jpg"/> Texto da matéria]]></description></item></channel></rss>"""
GNEWS = """<rss><channel><title>Google Notícias</title><item><title>OpenAI freia modelo - Folha de S.Paulo</title>
<link>https://news.google.com/rss/articles/abc</link><source url="https://folha.uol.com.br">Folha de S.Paulo</source>
<description>&lt;a href="x"&gt;OpenAI freia&lt;/a&gt;</description></item></channel></rss>"""


def test_ler_rss():
    n = ler_rss(G1, "tecnologia")[0]
    assert (n.titulo, n.fonte, n.imagem) == ("Chip novo & rápido", "g1", "https://s2.glbimg.com/a.jpg")
    g = ler_rss(GNEWS, "IA")[0]
    assert (g.titulo, g.fonte) == ("OpenAI freia modelo", "Folha de S.Paulo")
    assert ler_rss("não é xml", "x") == []


def test_temas_do_ambiente():
    assert temas_do_ambiente({"JAIME_NOTICIAS": "esportes|https://a.b/rss;ruim|http://inseguro"}) == [("esportes", "https://a.b/rss")]
    assert len(temas_do_ambiente({})) == 3


# ── saúde ─────────────────────────────────────────────
HAE = {"data": {"metrics": [
    {"name": "walking_running_distance", "units": "km", "data": [{"qty": 0.1, "date": "2026-09-30 07:00:00 -0300"}]},
    {"name": "heart_rate", "units": "count/min", "data": [{"Min": 60, "Avg": 120, "Max": 192, "date": "2026-09-30 07:10:00 -0300"}]},
    {"name": "step_count", "units": "count", "data": [{"qty": 100, "date": "2026-09-30"}, {"qty": 50, "date": "2026-09-30"}]}],
    "workouts": [{"name": "Caminhada", "start": "2026-09-30 06:00:00 -0300", "end": "2026-09-30 07:03:00 -0300"}]}}


def test_saude_health_auto_export():
    from datetime import date
    r = sd.interpretar(HAE, hoje=date(2026, 9, 30))
    assert (r.distancia_km, r.fc_pico, r.passos, r.duracao_min) == (0.1, 192, 150, 63)
    assert "pico de 192 bpm" in r.observacoes


def test_saude_simples_e_falas(tmp_path):
    r = sd.salvar({"distancia_km": 0.1, "duracao_min": 63, "habitual_km": 0.5, "fc_pico": 192, "estresse": 13.6, "recuperacao": 34}, tmp_path)
    assert oct(os.stat(tmp_path / "ultimo.json").st_mode & 0o777) == "0o600"
    falas = [i["fala"] for i in sd.falas_do_monitor(r)]
    assert falas == ["O senhor caminhou 0,1 km hoje em 63 minutos, abaixo dos 0,5 habituais.", "O pico foi de 192 batimentos.",
                     "O stress ficou em 13,6.", "Sua recuperação antes desta atividade estava em 34%."]
    assert sd.carregar(tmp_path).fc_pico == 192
    assert sd.interpretar("lixo").distancia_km is None


# ── rosto ─────────────────────────────────────────────
def test_rosto(tmp_path):
    r = Rostos(tmp_path / "id" / "rosto.json")
    assert r.verificar([0.0] * 128)["status"] == "sem_cadastro"
    assert r.verificar([0.0] * 10)["status"] == "invalido"
    with pytest.raises(ValueError):
        r.cadastrar([[1, 2, 3]])
    r.cadastrar([[0.1] * 128, [0.12] * 128])
    assert oct(os.stat(r.arq).st_mode & 0o777) == "0o600"
    assert r.verificar([0.11] * 128)["status"] == "confirmado"
    assert r.verificar([0.3] * 128)["status"] == "desconhecido"
    assert r.verificar([float("nan")] * 128)["status"] == "invalido"
    r.esquecer(); assert not r.cadastrado


# ── monitor ───────────────────────────────────────────
def _monitor(tmp_path, cadastrado, resultado):
    rostos = Rostos(tmp_path / "r.json")
    if cadastrado:
        rostos.cadastrar([[0.1] * 128])
    ev = []
    m = Monitor(rostos, carregar=lambda: sd.Resumo(distancia_km=.1, fc_pico=192, recuperacao=34), emitir=lambda t, **d: ev.append((t, d)), espera_rosto=.5)

    async def f():
        falas = []
        async for x in m.rodar():
            falas.append(x)
            if len(falas) == 1 and resultado:
                m.receber_rosto(resultado)
        return falas
    return asyncio.run(f()), ev


def test_monitor_confirmado_le_saude(tmp_path):
    falas, ev = _monitor(tmp_path, True, {"status": "confirmado"})
    assert falas[:3] == ["Ok, senhor, iniciando o reconhecimento facial.", "Identidade confirmada, bem-vindo, senhor.", "Monitor ativado com sucesso."]
    assert "O pico foi de 192 batimentos." in falas and any(d.get("fase") == "item" for t, d in ev)


def test_monitor_rosto_estranho_nao_le_saude(tmp_path):
    falas, _ = _monitor(tmp_path, True, {"status": "desconhecido"})
    assert "Não reconheci esse rosto" in falas[1] and not any("batimentos" in f for f in falas)


def test_monitor_sem_cadastro_e_sem_camera_usa_a_senha(tmp_path):
    falas, _ = _monitor(tmp_path, False, None)                 # ninguém respondeu: timeout
    assert "Não vi ninguém" in falas[1] and any("batimentos" in f for f in falas)
    falas2, _ = _monitor(tmp_path / "b", True, None)            # cadastrado mas sem rosto: não lê saúde
    assert not any("batimentos" in f for f in falas2)


# ── voz e holograma ───────────────────────────────────
@pytest.mark.parametrize("texto,esperado", [
    ("Jarvis, ativar monitor", ("monitor", {})), ("ativa o monitor", ("monitor", {})),
    ("Jarvis, cria pra mim um holograma do Tesla Model X, pra que eu consiga controlar com a mão na frente do meu computador",
     ("holograma", {"objeto": "Tesla Model X"})),
    ("abre um holograma da casa", ("holograma", {"objeto": "casa"})), ("fecha o holograma", ("fecha_holograma", {})),
    ("aprende meu rosto", ("aprende_rosto", {})), ("esquece meu rosto", ("esquece_rosto", {})),
    ("modo partículas", ("orbe", {"estilo": "particulas"})), ("orbe de fios", ("orbe", {"estilo": "fios"})),
    ("o monitor está ligado?", None), ("me fala do holograma de ontem e manda pro Gabriel", None),
])
def test_cenas(texto, esperado):
    assert cena(texto) == esperado


def test_holograma_resolver(tmp_path, monkeypatch):
    assert holo.resolver("Tesla Model X")["modelo"] == "carro"
    assert holo.resolver("uma moto")["modelo"] == "moto"
    r = holo.resolver("dragão chinês")
    assert r["exato"] is False and "dragao-chines.glb" in holo.fala(r)
    monkeypatch.setattr(holo, "PASTA", tmp_path)
    (tmp_path / "dragao-chines.glb").write_bytes(b"glb")
    assert holo.resolver("Dragão chinês") == {"modelo": "glb", "arquivo": "dragao-chines", "titulo": "Dragão chinês", "exato": True}
    assert holo.arquivo_glb("../../etc/passwd") is None and holo.arquivo_glb("dragao-chines") is not None


def test_gerador_de_cenas():
    ev = []
    b = briefing([])
    j = Jarvis(b, Monitor(Rostos(Path("/nonexistent/x.json"))), Rostos(Path("/nonexistent/x.json")), emitir=lambda t, **d: ev.append((t, d)), env={})
    manha = datetime(2026, 9, 30, 8)
    assert j.gerador("bom dia", manha) is not None
    b.ultimo_dia = "2026-09-30"
    assert j.gerador("bom dia", manha) is None                   # 2º bom dia do dia vira cumprimento normal
    assert j.gerador("que horas são?", manha) is None
    falas = coletar(j.gerador("cria um holograma do carro", manha))
    assert ev[-1][0] == "holograma" and ev[-1][1]["modelo"] == "carro" and "Holograma de carro pronto" in falas[0]
    j2 = Jarvis(briefing([]), None, None, env={"JAIME_BRIEFING_BOM_DIA": "off"})
    assert j2.gerador("bom dia", manha) is None and j2.gerador("me dá o briefing", manha) is not None


# ── rotas ─────────────────────────────────────────────
def test_rotas(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from jaime.jarvis import rotas
    a = FastAPI(); a.include_router(rotas.router); c = TestClient(a)
    rostos = Rostos(tmp_path / "r.json")
    j = Jarvis(briefing([]), Monitor(rostos), rostos, env={})

    class Acesso:
        liberado = True

    class J:
        acesso = Acesso()
    rotas.ESTADO.update(jarvis=j, jaime=J(), falar=None)
    assert c.get("/hud/jarvis").status_code == 200 and c.get("/hud/jarvis/orbe.js").status_code == 200
    assert c.get("/hud/jarvis/../server.py").status_code == 404 and c.get("/hud/jarvis/vendor/../../x").status_code == 404
    assert c.post("/jarvis/rosto/cadastrar", json={"descritores": [[0.1] * 128]}).status_code == 409   # sem "aprende meu rosto"
    j.cadastrando = True
    assert c.post("/jarvis/rosto/cadastrar", json={"descritores": [[0.1] * 128]}).json() == {"amostras": 1}
    assert c.post("/jarvis/rosto/verificar", json={"descritor": [0.1] * 128}).json() == {"status": "confirmado"}
    assert c.post("/jarvis/rosto/verificar", json={"status": "qualquer"}).json() == {"status": "invalido"}
    assert c.post("/jarvis/rosto/verificar", json={"descritor": [0.1] * 128}, headers={"Origin": "https://mal.com"}).status_code == 403
    J.acesso.liberado = False; j.cadastrando = True
    assert c.post("/jarvis/rosto/cadastrar", json={"descritores": [[0.1] * 128]}).status_code == 403
    from jaime.config import settings
    monkeypatch.setattr(sd, "PASTA", tmp_path / "saude")
    assert c.post("/webhook/saude", json={"fc_pico": 150}).status_code == 401
    r = c.post("/webhook/saude", json={"fc_pico": 190}, headers={"X-Jaime-Token": settings.server_token})
    assert r.status_code == 200 and r.json()["observacoes"] == 1


def test_vendor(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hand_detector.tflite", b"x"); z.writestr("hand_landmarks_detector.tflite", b"y")
    assert modelo_mao_valido(buf.getvalue()) and not modelo_mao_valido(b"nao e zip")
    (tmp_path / "face-api.js").write_text("x")
    assert arquivo("face-api.js", tmp_path) is not None
    assert arquivo("../segredo", tmp_path) is None and arquivo("outro.js", tmp_path) is None
