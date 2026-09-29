"""O que na casa passa pelo "sim" do João — usando o MESMO lote de confirmação do Vigia (sem tocar em jaime/vigia/).

A casa ganhou mãos grandes: via Alexa, qualquer coisa que se fala para ela o Jaime consegue mandar ("compra",
"liga para", "destranca a porta"). Então:
- destrancar/abrir porta ou portão, desarmar alarme, desligar câmera, comprar, ligar/drop in, mandar mensagem
  → a ação entra no lote do Vigia e o modelo pergunta UMA vez no fim do turno ("Você deseja que eu …?");
- "sim" libera exatamente aquela ação (assinatura); "confirmo" arma o Vigia para a próxima;
- com visita na linha (convidado), nada disso roda — nem pergunta.
Presença por Bluetooth NUNCA destranca nada: celular é fácil de clonar/imitar.
"""
from __future__ import annotations
import re

ALEXA_SENSIVEL = [
    (r"\b(compr|pe[çc]a|pedido|encomend|carrinho|assinatura|assina)\w*", "comprar/pedir pela Alexa"),
    (r"\b(liga(r)? para|chama(r)? (o|a)|telefona|drop.?in|entra(r)? na c[aâ]mera)\b", "ligar/drop in"),
    (r"\b(manda|envia|mande|envie)\w* (uma )?mensage", "mandar mensagem"),
    (r"\b(destranc|abr[ea]\w* (a |o )?(porta|port[ãa]o|garagem|fechadura)|desarm|desativ\w* (o )?alarme|deslig\w* (o )?alarme|deslig\w* (a )?c[aâ]mera)", "abrir a casa"),
]
SERVICO_SENSIVEL = {
    ("lock", "unlock"): "destrancar", ("lock", "open"): "abrir a fechadura",
    ("alarm_control_panel", "alarm_disarm"): "desarmar o alarme",
    ("camera", "turn_off"): "desligar a câmera",
}
PORTAO_RX = re.compile(r"(port[aã]o|garag|gate|garage|porta)", re.I)


def motivo_alexa(texto: str) -> str | None:
    t = (texto or "").lower()
    for rx, motivo in ALEXA_SENSIVEL:
        if re.search(rx, t):
            return motivo
    return None


def motivo_servico(dominio: str, acao: str, entity_id: str) -> str | None:
    if (dominio, acao) in SERVICO_SENSIVEL:
        return SERVICO_SENSIVEL[(dominio, acao)]
    if dominio == "cover" and acao in ("open_cover", "toggle") and PORTAO_RX.search(entity_id or ""):
        return "abrir portão/garagem"
    if dominio == "script" or dominio == "scene":
        return None
    return None


def liberado(vigia, nome: str, args: dict, descricao: str) -> tuple[bool, str]:
    """(pode seguir?, mensagem para o modelo). Sem Vigia (testes/CLI) → só com confirmação impossível: nega."""
    if vigia is None:
        return False, "ação sensível sem Vigia disponível — não executo"
    if getattr(vigia, "convidado", ""):
        return False, "isso é da casa do João: com visita na linha eu não faço"
    from ..vigia.hooks import Acao, assinatura_de
    a = Acao(nome, f"casa:{descricao}", descricao, assinatura_de(nome, args))
    if a.assinatura in vigia.liberadas:
        vigia.liberadas.pop(a.assinatura)
        return True, ""
    if vigia._consome():                                  # o João disse "confirmo" agora há pouco
        return True, ""
    if all(x.assinatura != a.assinatura for x in vigia.lote):
        vigia.lote.append(a)
    pergunta = vigia.pedir_lote() or ""
    return False, (f"VIGIA: {descricao} precisa do sim do João — anotado. Siga com o resto e, ao terminar, pergunte UMA vez, "
                   f"exatamente: \"{pergunta}\". Quando ele disser 'sim', chame esta ferramenta de novo com os mesmos argumentos.")
