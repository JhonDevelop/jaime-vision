"""Agenda: relógio, lembretes, rotinas, feriados e clima — tudo com relógio falso e sem rede."""
from datetime import datetime, date
from zoneinfo import ZoneInfo
from jaime.agenda import relogio, lembretes as lem, feriados, clima
from jaime.agenda.scheduler import parse_rotinas

TZ = ZoneInfo("America/Sao_Paulo")
AGORA = datetime(2026, 9, 15, 14, 5, tzinfo=TZ)     # terça-feira

def test_relogio_responde_hora_e_data_sem_modelo():
    assert relogio.responder("que horas são?", AGORA) == "São 14 e 05."
    assert relogio.responder("hora é agora", AGORA.replace(minute=30)) == "São 14 e meia."
    assert relogio.responder("que dia é hoje?", AGORA) == "Hoje é terça-feira, 15 de setembro de 2026."
    assert relogio.responder("abre o Finder", AGORA) is None
    assert relogio.texto_hora(AGORA.replace(hour=12, minute=0)) == "meio-dia em ponto"

def test_lembrete_em_minutos_e_horas():
    q, o = lem.interpretar("me lembra em 20 min de ligar pro Zé", AGORA)
    assert q == AGORA.replace(minute=25) and o == "ligar pro Zé"
    q, o = lem.interpretar("lembra de tirar o pão em meia hora", AGORA)
    assert q == AGORA.replace(minute=35) and o == "tirar o pão"

def test_lembrete_as_horas_hoje_ou_amanha_e_dia():
    q, o = lem.interpretar("me lembra às 15h da reunião", AGORA)
    assert (q.hour, q.minute, q.day) == (15, 0, 15) and o == "reunião"
    q, _ = lem.interpretar("me lembra às 9 de pagar o boleto", AGORA)   # 9h já passou → amanhã
    assert q.day == 16 and q.hour == 9
    q, o = lem.interpretar("me lembra amanhã às 10:30 do dentista", AGORA)
    assert (q.day, q.hour, q.minute, o) == (16, 10, 30, "dentista")
    q, _ = lem.interpretar("me lembra dia 20 de renovar o domínio", AGORA)
    assert (q.day, q.month, q.hour) == (20, 9, 9)
    assert lem.interpretar("abre o Finder", AGORA) is None
    assert lem.interpretar("me lembra às 25h de nada", AGORA) is None

def test_lembretes_persistidos_pendentes_e_feitos():
    arq = "# Lembretes\n\n" + lem.linha(AGORA.replace(hour=16), "reunião") + "\n" + lem.linha(AGORA.replace(hour=9), "passou") + "\n"
    p = lem.pendentes(arq, AGORA)
    assert [o for _, o in p] == ["reunião"]
    arq2 = lem.marcar_feito(arq, AGORA.replace(hour=16), "reunião")
    assert "- [x] 2026-09-15 16:05 · reunião" in arq2 and lem.pendentes(arq2, AGORA) == []

def test_parse_rotinas():
    r = parse_rotinas("# Rotinas\n- 0 7 * * 1-5 · briefing\n- 0 18 * * 5 · fecha a semana\n- lixo · sem cron\n")
    assert r[0] == ({"minute": "0", "hour": "7", "day": "*", "month": "*", "day_of_week": "1-5"}, "briefing")
    assert r[1][1] == "fecha a semana" and len(r) == 2

def test_feriados_br_sp():
    assert feriados.feriado(date(2026, 9, 7)) is not None and feriados.feriado(date(2026, 11, 20)) is not None
    assert feriados.feriado(date(2026, 9, 15)) is None
    assert "feriado" in feriados.texto(date(2026, 9, 15)).lower()

def test_clima_texto_sem_rede():
    dados = {"current": {"temperature_2m": 27.4, "apparent_temperature": 30.1, "weather_code": 2, "wind_speed_10m": 12},
             "daily": {"temperature_2m_max": [31.0, 29.0], "temperature_2m_min": [17.0, 16.0], "precipitation_probability_max": [10, 60]}}
    t = clima.texto(dados)
    assert t.startswith("Agora parcialmente nublado, 27 graus") and "sensação de 30" in t and "10% de chance de chuva" in t
    assert clima.texto(dados, amanha=True) == "Amanhã: máxima de 29, mínima de 16 graus, 60% de chance de chuva."
    assert clima.pergunta_de_clima("vai chover hoje?") and not clima.pergunta_de_clima("abre o Finder")
