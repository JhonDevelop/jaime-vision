"""Ferramentas MCP `hermes`: o Jaime delega trabalho ao Hermes Agent e responde aos pedidos de aprovação dele.

- hermes_delegar(tarefa): a tarefa vai ao Hermes (terminal, arquivos, web, memória e skills DELE). Se a própria
  tarefa já é do tipo que o Vigia segura (mandar mensagem, comprar, apagar, publicar, push, instalar, abrir a casa),
  ela só sai depois do "sim" do João — o Hermes não é porta dos fundos para o que o Jaime não faria sozinho.
- Quando o Hermes para num comando perigoso, o pedido entra no lote do Vigia; "sim" do João → hermes_aprovar
  com os mesmos argumentos responde `once` (só aquele comando). Qualquer outra coisa → hermes_negar.
- hermes_estado mostra saúde e aprovações em aberto; hermes_parar interrompe um run.
"""
from __future__ import annotations
import re, unicodedata
from claude_agent_sdk import tool, create_sdk_mcp_server
from ..casa.seguranca import SENSIVEL, liberado
from .cliente import HermesCliente, descrever_aprovacao


def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}


def _n(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")).strip()


EXTRA_SENSIVEL = [
    (r"\b(apag|delet|exclu|remov)\w*\b.*\b(arquivo|arquivos|pasta|pastas|repositorio|banco|tabela|conta|e-?mails?)\b|\brm -rf\b", "apagar"),
    (r"\b(publica|publicar|posta|postar|tuita|tuitar)\b", "publicar"),
    (r"\b(envia|enviar|manda|mandar|responde|responder)\b.*\b(e-?mail|mensagem|whats|whatsapp|telegram|dm|sms)\b", "mandar mensagem"),
    (r"\bgit push\b|\bpush (na|pra|para a?) main\b|\bmerge\b.*\bmain\b", "mexer na main"),
    (r"\b(instala|instalar|desinstala|desinstalar)\b|\bsudo\b|\bbrew install\b|\bwinget\b|\bpip install\b", "instalar/mexer no sistema"),
    (r"\b(deploy|producao|produção)\b", "produção"),
]


def motivo_tarefa(texto: str) -> str | None:
    """None = pode delegar direto. Senão, o motivo pelo qual precisa do sim do João antes de sair."""
    t = _n(texto)
    for rx, motivo in SENSIVEL + EXTRA_SENSIVEL:
        if re.search(rx, t):
            return motivo
    return None


INSTRUCOES = ("Você é o Hermes trabalhando para o J.A.I.M.E., o assistente do João (Franca/SP). Responda em português "
              "do Brasil, curto, dizendo o que fez e o resultado. Não mande mensagens, não compre, não publique e não "
              "apague nada que não esteja pedido explicitamente nesta tarefa.")


def build_hermes_server(cliente: HermesCliente, vigia=None):
    async def _seguir(r) -> dict:
        if r.status == "erro":
            return _txt(f"Hermes indisponível: {r.erro}")
        if r.pedindo_aprovacao:
            ap = r.aprovacao
            args = {"run_id": r.run_id, "request_id": str(ap.get("request_id", ""))}
            _, msg = liberado(vigia, "mcp__hermes__hermes_aprovar", args, descrever_aprovacao(ap))
            return _txt(msg + f" (Se ele disser não, chame hermes_negar com run_id={r.run_id} e request_id={args['request_id']}.)")
        if r.status == "running":
            return _txt(f"O Hermes ainda está trabalhando (run {r.run_id}). Consulte depois com hermes_estado.")
        return _txt(f"Hermes ({r.status}): {r.texto or '(sem texto)'}")

    @tool("hermes_delegar", "Delega uma tarefa ao Hermes Agent (agente com terminal, arquivos, web, memória e skills próprias). "
          "Use para trabalho longo ou que ele faz melhor; você continua falando com o João.", {"tarefa": str, "sessao": str})
    async def hermes_delegar(args):
        tarefa = (args.get("tarefa") or "").strip()
        if not tarefa:
            return _txt("Diga qual é a tarefa.")
        if (m := motivo_tarefa(tarefa)):
            ok, msg = liberado(vigia, "mcp__hermes__hermes_delegar", {"tarefa": tarefa}, f"peça ao Hermes: {tarefa[:120]} ({m})")
            if not ok:
                return _txt(msg)
        sessao = re.sub(r"[^\w-]", "", args.get("sessao") or "jaime")[:40] or "jaime"
        return await _seguir(await cliente.executar(tarefa, sessao, instrucoes=INSTRUCOES))

    @tool("hermes_aprovar", "Responde 'sim' a um comando que o Hermes parou para aprovar — só depois do sim do João.",
          {"run_id": str, "request_id": str})
    async def hermes_aprovar(args):
        a = {"run_id": args.get("run_id", ""), "request_id": args.get("request_id", "")}
        ap = cliente.pendentes.get(a["run_id"], {})
        ok, msg = liberado(vigia, "mcp__hermes__hermes_aprovar", a, descrever_aprovacao(ap))
        if not ok:
            return _txt(msg)
        try:
            await cliente.responder_aprovacao(a["run_id"], a["request_id"], "once")
            return await _seguir(await cliente.acompanhar(a["run_id"]))
        except Exception as e:
            return _txt(f"Hermes falhou ao aprovar: {cliente._limpo(e)[:160]}")

    @tool("hermes_negar", "Nega um comando que o Hermes parou para aprovar (livre: negar nunca precisa de confirmação).",
          {"run_id": str, "request_id": str})
    async def hermes_negar(args):
        try:
            await cliente.responder_aprovacao(args.get("run_id", ""), args.get("request_id", ""), "deny")
            return await _seguir(await cliente.acompanhar(args.get("run_id", ""), esperar_s=30))
        except Exception as e:
            return _txt(f"Hermes falhou ao negar: {cliente._limpo(e)[:160]}")

    @tool("hermes_estado", "Saúde do Hermes e aprovações em aberto.", {})
    async def hermes_estado(args):
        ok, det = await cliente.saude()
        linhas = [f"Hermes: {'no ar' if ok else 'fora'} ({det})"]
        for rid, ap in cliente.pendentes.items():
            linhas.append(f"- aguardando aprovação: {descrever_aprovacao(ap)} [run_id={rid} request_id={ap.get('request_id', '')}]")
        return _txt("\n".join(linhas))

    @tool("hermes_parar", "Interrompe um trabalho do Hermes.", {"run_id": str})
    async def hermes_parar(args):
        try:
            await cliente.parar(args.get("run_id", ""))
            return _txt("Parei o Hermes.")
        except Exception as e:
            return _txt(f"Não consegui parar: {cliente._limpo(e)[:160]}")

    return create_sdk_mcp_server(name="hermes", version="1.0.0",
                                 tools=[hermes_delegar, hermes_aprovar, hermes_negar, hermes_estado, hermes_parar])
