"""As ferramentas da frota — o que o J.A.I.M.E chama para reconhecer, conhecer e mexer nas outras máquinas.

A ordem das ferramentas aqui é a ordem em que ele deve pensar, e está escrita nas descrições de propósito
(a descrição é o que o modelo lê para escolher):

    frota                 quem está ligado agora
    de_quem_e_a_maquina   de quem é aquele hostname — a pergunta antes de qualquer ação
    conhecer_maquina      o que tem nela e com o que se trabalha ali (e guarda isso no vault)
    listar_em / ler_em / escrever_em / rodar_em      o trabalho

`conhecer_maquina` guardar no vault é o que faz o «saber como mexer neles» durar mais que um turno: na
segunda vez ele já sabe que naquela máquina é `brew` e não `apt`, que o projeto está em `~/dev` e não em
`~/Projetos`, e que ali o python é `python3`."""
from __future__ import annotations

from claude_agent_sdk import tool, create_sdk_mcp_server

from .frota import Frota
from .registro import NIVEIS


def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}


def build_frota_server(frota: Frota, vault=None):

    @tool("frota", "Quais computadores eu alcanço AGORA, de quem é cada um, com qual nível e se estão no "
                   "ar. Cheque antes de prometer ao João que vai mexer em outra máquina.", {})
    async def estado(args):
        return _txt(frota.estado())

    @tool("de_quem_e_a_maquina", "DE QUEM É este computador, pelo nome dele (hostname). Use sempre que "
                                 "aparecer um nome de máquina que você não reconhece, ANTES de agir: quem "
                                 "é o dono decide o que você pode fazer ali. Máquina fora da frota é "
                                 "máquina em que você não mexe.", {"host": str})
    async def de_quem_e_a_maquina(args):
        h = (args.get("host") or "").strip()
        return _txt(frota.registro.quem_e(h) if h else "faltou o nome da máquina")

    @tool("cadastrar_maquina", "Põe um computador na frota do João. `nivel`: 'leitor' (só lê), 'operador' "
                               "(lê, escreve e roda comando na pasta) ou 'dono' (o mesmo, na casa inteira "
                               "— só para as máquinas do próprio João). `pasta` é obrigatória fora do "
                               "nível dono. Depois de cadastrar, use `convidar_maquina` para instalar lá.",
          {"apelido": str, "host": str, "dono": str, "nivel": str, "pasta": str})
    async def cadastrar_maquina(args):
        nivel = (args.get("nivel") or "operador").strip().lower()
        if nivel not in NIVEIS:
            return _txt(f"nível tem que ser um de: {', '.join(NIVEIS)}")
        pasta = (args.get("pasta") or "").strip()
        if nivel != "dono" and not pasta:
            return _txt("leitor e operador precisam de uma pasta: só o nível dono alcança a casa inteira")
        r = frota.registro.cadastrar(args.get("apelido") or "", args.get("host") or "",
                                     args.get("dono") or "", nivel, pasta)
        return _txt(r)

    @tool("convidar_maquina", "Gera o convite de entrada de uma máquina já cadastrada: um código curto, de "
                              "uso único, que vale 10 minutos. Dite o código e o comando ao dono da "
                              "máquina — nunca um token. O token definitivo vai pela rede, direto para a "
                              "máquina.", {"host": str})
    async def convidar_maquina(args):
        _, msg = frota.convidar((args.get("host") or "").strip())
        return _txt(msg)

    @tool("tirar_da_frota", "Tira um computador da frota. O acesso acaba no próximo registro dele.",
          {"host": str})
    async def tirar_da_frota(args):
        return _txt(frota.registro.remover((args.get("host") or "").strip()))

    @tool("conhecer_maquina", "O RETRATO de uma máquina da frota: sistema, shell, o que está instalado, "
                              "onde ficam os projetos. Use na primeira vez que for mexer nela e quando "
                              "algo não funcionar como você esperava — é assim que você sabe se ali é brew "
                              "ou apt, python ou python3. O que voltar fica guardado no vault.",
          {"maquina": str})
    async def conhecer_maquina(args):
        quem = (args.get("maquina") or "").strip()
        if not quem:
            return _txt("faltou dizer qual máquina")
        retrato = await frota.pedir(quem, "conhecer")
        lig = frota.achar(quem)
        if lig is not None and vault is not None and not retrato.startswith(("não tenho", "em ")):
            try:
                vault.write(f"01-Estado/Maquina-{lig.apelido}.md",
                            f"# {lig.apelido} — máquina do {lig.matricula.dono}\n\n"
                            f"Retrato tirado por mim, para eu saber como mexer aqui.\n\n"
                            f"```\n{retrato}\n```\n")
            except Exception:
                pass
        return _txt(retrato)

    @tool("listar_em", "LISTA arquivos e pastas em outra máquina da frota. `caminho` é relativo ao alcance "
                       "que o dono dela me deu ('' é a raiz desse alcance).",
          {"maquina": str, "caminho": str})
    async def listar_em(args):
        return _txt(await frota.pedir((args.get("maquina") or "").strip(), "listar",
                                      caminho=(args.get("caminho") or "").strip()))

    @tool("ler_em", "LÊ um arquivo em outra máquina da frota.", {"maquina": str, "caminho": str})
    async def ler_em(args):
        c = (args.get("caminho") or "").strip()
        if not c:
            return _txt("faltou o caminho")
        return _txt(await frota.pedir((args.get("maquina") or "").strip(), "ler", caminho=c))

    @tool("escrever_em", "ESCREVE um arquivo em outra máquina da frota. SOBRESCREVE: leia antes se o "
                         "arquivo já existe e você não quer perder o que está lá.",
          {"maquina": str, "caminho": str, "conteudo": str})
    async def escrever_em(args):
        c = (args.get("caminho") or "").strip()
        if not c:
            return _txt("faltou o caminho")
        return _txt(await frota.pedir((args.get("maquina") or "").strip(), "escrever",
                                      caminho=c, conteudo=args.get("conteudo") or ""))

    @tool("rodar_em", "RODA um comando em outra máquina da frota, dentro do alcance que o dono dela deu. "
                      "Use para git, teste, build. Só funciona onde meu nível for operador ou dono. "
                      "Confira o retrato da máquina antes: o comando certo depende do sistema dela.",
          {"maquina": str, "comando": str})
    async def rodar_em(args):
        cmd = (args.get("comando") or "").strip()
        if not cmd:
            return _txt("faltou o comando")
        return _txt(await frota.pedir((args.get("maquina") or "").strip(), "rodar", comando=cmd))

    return create_sdk_mcp_server(
        name="frota", version="1.0.0",
        tools=[estado, de_quem_e_a_maquina, cadastrar_maquina, convidar_maquina, tirar_da_frota,
               conhecer_maquina, listar_em, ler_em, escrever_em, rodar_em])
