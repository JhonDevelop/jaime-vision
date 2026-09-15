"""Ferramentas MCP `mundo`: agora, clima, feriado_hoje, criar_lembrete, rotinas."""
from __future__ import annotations
from datetime import datetime
from claude_agent_sdk import tool, create_sdk_mcp_server
from . import relogio, clima as clima_mod, feriados, lembretes as lem

def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}

def build_mundo_server(agenda, lat: float, lon: float):
    @tool("agora", "Data e hora atuais em Franca/SP (fuso America/Sao_Paulo).", {})
    async def agora(args):
        dt = relogio.agora()
        return _txt(f"{relogio.texto_data(dt)}, {dt:%H:%M}.")

    @tool("clima", "Clima agora e previsão do dia (Open-Meteo). amanha=true para amanhã.", {"amanha": bool})
    async def clima(args):
        try:
            d = await clima_mod.buscar(lat, lon)
        except Exception as e:
            return _txt(f"Clima indisponível: {type(e).__name__}")
        return _txt(clima_mod.texto(d, amanha=bool(args.get("amanha"))))

    @tool("feriado_hoje", "Se hoje é feriado (BR + SP) e qual o próximo.", {})
    async def feriado_hoje(args):
        return _txt(feriados.texto())

    @tool("criar_lembrete", "Cria um lembrete. quando: linguagem natural ('em 20 min', 'às 15h', 'amanhã às 9', 'dia 20 às 10') ou 'AAAA-MM-DD HH:MM'.",
          {"quando": str, "o_que": str})
    async def criar_lembrete(args):
        q, o = (args.get("quando") or "").strip(), (args.get("o_que") or "").strip()
        try:
            quando = datetime.strptime(q, "%Y-%m-%d %H:%M").replace(tzinfo=relogio.FUSO)
        except ValueError:
            r = lem.interpretar(f"me lembra {q} de {o}")
            if not r:
                return _txt(f"Não entendi '{q}'. Use 'em 20 min', 'às 15h', 'amanhã às 9' ou 'AAAA-MM-DD HH:MM'.")
            quando = r[0]
        return _txt(agenda.criar_lembrete(quando, o or "lembrete"))

    @tool("rotinas", "Lista as rotinas agendadas (30-Tarefas/Rotinas.md) e os lembretes pendentes.", {})
    async def rotinas(args):
        rs = [f"- {' '.join(c.values())} · {o}" for c, o in agenda.rotinas] or ["- nenhuma"]
        ls = [f"- {q:%d/%m %H:%M} · {o}" for q, o in agenda.lembretes()] or ["- nenhum"]
        return _txt("Rotinas:\n" + "\n".join(rs) + "\n\nLembretes pendentes:\n" + "\n".join(ls))

    return create_sdk_mcp_server(name="mundo", version="1.0.0", tools=[agora, clima, feriado_hoje, criar_lembrete, rotinas])
