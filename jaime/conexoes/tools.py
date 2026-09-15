"""Ferramentas MCP `google`: email_hoje, email_buscar, email_rascunho, email_enviar (Vigia), agenda_dia, agenda_criar; e `conexoes`."""
from __future__ import annotations
from datetime import datetime, timedelta
from claude_agent_sdk import tool, create_sdk_mcp_server
from .google import GoogleConta, texto_emails, texto_agenda, interpretar_quando, FUSO
from .registro import Registro

def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}

def build_google_server(conta: GoogleConta, registro: Registro):
    def _ok():
        if not conta.conectado:
            return "Google não conectado. Rode `python -m jaime conectar google` (docs/CONEXOES.md)."
        return ""

    @tool("email_hoje", "E-mails das últimas 24 h (sem promoções/social). ● = não lido.", {})
    async def email_hoje(args):
        if (e := _ok()): return _txt(e)
        try: r = texto_emails(conta.email_hoje()); registro.usou("Google Gmail"); return _txt(r)
        except Exception as ex: return _txt(f"Gmail falhou: {type(ex).__name__}: {str(ex)[:120]}")

    @tool("email_buscar", "Busca no Gmail com a sintaxe do Gmail (ex.: 'from:fulano is:unread', 'assunto nota fiscal').", {"consulta": str})
    async def email_buscar(args):
        if (e := _ok()): return _txt(e)
        try: r = texto_emails(conta.email_buscar(args["consulta"])); registro.usou("Google Gmail"); return _txt(r)
        except Exception as ex: return _txt(f"Gmail falhou: {type(ex).__name__}: {str(ex)[:120]}")

    @tool("email_rascunho", "Cria um RASCUNHO no Gmail (não envia). Mostre o texto ao João antes.", {"para": str, "assunto": str, "corpo": str})
    async def email_rascunho(args):
        if (e := _ok()): return _txt(e)
        try: i = conta.email_rascunho(args["para"], args["assunto"], args["corpo"]); registro.usou("Google Gmail"); return _txt(f"Rascunho criado ({i}). Enviar exige 'confirmo'.")
        except Exception as ex: return _txt(f"Gmail falhou: {type(ex).__name__}: {str(ex)[:120]}")

    @tool("email_enviar", "ENVIA um e-mail. Ação do Vigia: só executa depois do 'confirmo' do João.", {"para": str, "assunto": str, "corpo": str})
    async def email_enviar(args):
        if (e := _ok()): return _txt(e)
        try: i = conta.email_enviar(args["para"], args["assunto"], args["corpo"]); registro.usou("Google Gmail"); return _txt(f"Enviado ({i}).")
        except Exception as ex: return _txt(f"Gmail falhou: {type(ex).__name__}: {str(ex)[:120]}")

    @tool("agenda_dia", "Eventos do Google Calendar de hoje (ou de 'amanhã', 'dia 20').", {"quando": str})
    async def agenda_dia(args):
        if (e := _ok()): return _txt(e)
        q = (args.get("quando") or "").strip()
        dia = interpretar_quando(f"{q} às 0h", datetime.now(FUSO)) if q and q != "hoje" else datetime.now(FUSO)
        try: r = texto_agenda(conta.agenda_dia(dia or datetime.now(FUSO))); registro.usou("Google Calendar"); return _txt(r)
        except Exception as ex: return _txt(f"Calendar falhou: {type(ex).__name__}: {str(ex)[:120]}")

    @tool("agenda_criar", "Cria um evento no Google Calendar. inicio: 'amanhã às 15h', 'dia 20 às 10:30' ou 'AAAA-MM-DD HH:MM'. duracao_min padrão 60.",
          {"titulo": str, "inicio": str, "duracao_min": int, "descricao": str})
    async def agenda_criar(args):
        if (e := _ok()): return _txt(e)
        ini = interpretar_quando(args["inicio"])
        if not ini:
            return _txt(f"Não entendi '{args['inicio']}'.")
        fim = ini + timedelta(minutes=int(args.get("duracao_min") or 60))
        try: link = conta.agenda_criar(args["titulo"], ini, fim, args.get("descricao", "")); registro.usou("Google Calendar"); return _txt(f"Evento criado: {args['titulo']} em {ini:%d/%m %H:%M}. {link}")
        except Exception as ex: return _txt(f"Calendar falhou: {type(ex).__name__}: {str(ex)[:120]}")

    @tool("conexoes", "Lista o que o Jaime tem acesso (serviço, escopo, como revogar, último uso).", {})
    async def conexoes(args):
        return _txt(registro.texto())

    return create_sdk_mcp_server(name="google", version="1.0.0",
                                 tools=[email_hoje, email_buscar, email_rascunho, email_enviar, agenda_dia, agenda_criar, conexoes])
