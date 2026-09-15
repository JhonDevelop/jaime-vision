"""Clima pela Open-Meteo (sem chave). Franca/SP por padrão; `JAIME_LAT`/`JAIME_LON` no .env mudam.
Cache de 10 minutos: perguntar duas vezes seguidas não bate na rede duas vezes."""
from __future__ import annotations
import re, time
import httpx

LAT, LON = -20.5386, -47.4008          # Franca/SP
URL = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
       "&current=temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
       "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=America%2FSao_Paulo&forecast_days=2")
CLIMA_RX = re.compile(r"\b(clima|tempo (hoje|agora|amanh[aã]|l[aá] fora)|vai chover|t[aá] chovendo|est[aá] chovendo|temperatura|quantos graus|previs[aã]o)\b", re.I)
CODIGOS = {0: "céu limpo", 1: "quase limpo", 2: "parcialmente nublado", 3: "nublado", 45: "neblina", 48: "neblina",
           51: "garoa", 53: "garoa", 55: "garoa forte", 61: "chuva fraca", 63: "chuva", 65: "chuva forte",
           80: "pancadas de chuva", 81: "pancadas de chuva", 82: "pancadas fortes", 95: "trovoada", 96: "trovoada com granizo", 99: "trovoada com granizo"}
_cache: dict = {"t": 0.0, "dados": None, "chave": None}

def pergunta_de_clima(texto: str) -> bool:
    return bool(CLIMA_RX.search(texto or ""))

async def buscar(lat: float = LAT, lon: float = LON, ttl: int = 600) -> dict:
    chave = (round(lat, 3), round(lon, 3))
    if _cache["dados"] and _cache["chave"] == chave and time.time() - _cache["t"] < ttl:
        return _cache["dados"]
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(URL.format(lat=lat, lon=lon)); r.raise_for_status()
        dados = r.json()
    _cache.update(t=time.time(), dados=dados, chave=chave)
    return dados

def texto(dados: dict, amanha: bool = False) -> str:
    cur, d = dados.get("current", {}), dados.get("daily", {})
    i = 1 if amanha and len(d.get("temperature_2m_max", [])) > 1 else 0
    cond = CODIGOS.get(int(cur.get("weather_code", -1)), "tempo indefinido")
    mx, mn = d.get("temperature_2m_max", [None])[i], d.get("temperature_2m_min", [None])[i]
    chuva = d.get("precipitation_probability_max", [None])[i]
    if amanha:
        return (f"Amanhã: máxima de {mx:.0f}, mínima de {mn:.0f} graus" + (f", {chuva:.0f}% de chance de chuva" if chuva is not None else "") + ".")
    partes = [f"Agora {cond}, {cur.get('temperature_2m', 0):.0f} graus"]
    if abs(float(cur.get("apparent_temperature", cur.get("temperature_2m", 0))) - float(cur.get("temperature_2m", 0))) >= 2:
        partes.append(f"sensação de {cur['apparent_temperature']:.0f}")
    if mx is not None and mn is not None:
        partes.append(f"máxima de {mx:.0f} e mínima de {mn:.0f}")
    if chuva is not None:
        partes.append(f"{chuva:.0f}% de chance de chuva hoje")
    return ", ".join(partes) + "."

async def responder(texto_pergunta: str, lat: float = LAT, lon: float = LON) -> str:
    try:
        dados = await buscar(lat, lon)
    except Exception as e:
        return f"Não consegui ver o clima agora ({type(e).__name__})."
    return texto(dados, amanha=bool(re.search(r"amanh[aã]", texto_pergunta or "", re.I)))
