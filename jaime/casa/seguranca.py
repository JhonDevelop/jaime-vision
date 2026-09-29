"""O que na casa passa pelo "sim" do João — usando o MESMO lote de confirmação do Vigia (sem tocar em jaime/vigia/).

A casa ganhou mãos grandes: via Alexa, qualquer coisa que se fala para ela o Jaime consegue mandar ("compra",
"liga para", "destranca a porta"). Então:
- destrancar/abrir porta ou portão, desarmar alarme, desligar câmera, comprar, ligar/drop in, mandar mensagem
  → a ação entra no lote do Vigia e o modelo pergunta UMA vez no fim do turno ("Você deseja que eu …?");
- "sim"/"confirmo" à pergunta libera exatamente aquela ação (assinatura), por 15 min — nunca "a próxima que vier";
- Alexa: NEGA POR PADRÃO — só música, mídia, volume, aparelhos comuns, perguntas e timer saem sem perguntar;
- com visita na linha (convidado), nada disso roda — nem pergunta.
Presença por Bluetooth NUNCA destranca nada: celular é fácil de clonar/imitar.
"""
from __future__ import annotations
import re, time, unicodedata

def _n(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")).strip(" .!?")


# o que é sensível, por categoria (texto já sem acento) — só para dizer o MOTIVO; a regra é negar por padrão
SENSIVEL = [
    (r"\b(compra|compre|comprar|comprei|pague|paga|pagar|pagamento|pix|transfere|transferir|pede|pedir|peca|pedido|encomenda|assina|assinar|carrinho)\b", "comprar/pagar"),
    (r"\b(liga|ligue|ligar|telefona|telefone|chama|chame|disca)\s+(pra|para|pro|pros|pras)\b|\bdrop.?in\b|\bvideochamada\b", "ligar para alguém"),
    (r"\b(mensagem|mensagens|recado|recados|manda um oi|avisa o|avisa a)\b", "mandar mensagem"),
    (r"\b(destranc|destrav|desbloque|desarm|abre[s]? (a |as |o |os )?(porta|portas|portao|portoes|garagem|fechadura)|abrir (a |o )?(porta|portao|garagem)|sobe (o )?portao|levanta (o )?portao)", "abrir a casa"),
    (r"\b(deslig|desativ|deslig)\w* (a |as |o |os )?(alarme|alarmes|camera|cameras|seguranca|cerca)", "desligar a segurança"),
    (r"\brotina\b", "rotina (pode fazer qualquer coisa)"),
]
APARELHOS = r"(luz|luzes|lampada|lampadas|ventilador|tv|televisao|ar|ar condicionado|som|tomada|abajur|luminaria|cafeteira|aquecedor|umidificador|aspirador|robo|cortina|persiana)"
LIVRE = [
    r"^(toca|toque|tocar|coloca|coloque|poe|ponha|reproduz|reproduza)\b",                      # música/rádio/podcast
    r"^(para|pare|pausa|pause|continua|continue|retoma|proxima|pula|volta a musica|repete)\b",   # controle de mídia
    r"^(aumenta|abaixa|diminui|sobe|baixa) (o )?(volume|som)\b|^volume\b",
    rf"^(liga|ligue|desliga|desligue|acende|acenda|apaga|apague) (a |o |as |os )?{APARELHOS}\b",
    r"^(que horas|qual|quanto|quantos|quantas|como esta|como vai|previsao|como sera)\b",
    r"^(coloca|cria|define|poe) (um )?(timer|cronometro)\b|^(me acorda|me lembra)\b",
]
TOCAR_PROIBIDO = r"\b(alexa|compra|compre|comprar|carrinho|pedido|pede|portao|porta|fechadura|alarme|camera|destranc|destrav|mensagem|recado|rotina)\b|[;!?]|\. "
ALEXA_SENSIVEL = SENSIVEL        # compatibilidade de nome


def motivo_alexa(texto: str) -> str | None:
    """None = pode mandar direto. Qualquer outra coisa = passa pelo "sim" do João. NEGA POR PADRÃO: só o que está na
    lista livre (música, mídia, volume, aparelhos comuns, perguntas, timer) sai sem perguntar, e numa frase só."""
    t = re.sub(r"^alexa[, ]+", "", _n(texto))
    if not t:
        return "comando vazio"
    for rx, motivo in SENSIVEL:
        if re.search(rx, t) and not re.match(LIVRE[0], t):
            return motivo
    if re.match(LIVRE[0], t):                             # título de música pode ter "e", "compromisso"…: regra própria
        return "comando embutido no pedido de música" if re.search(TOCAR_PROIBIDO, t) else None
    if re.search(r"[.;!?]|\b(e|depois|entao|tambem)\b\s+\w+", t) and not re.match(LIVRE[4], t):
        return "mais de um pedido numa frase só"
    return None if any(re.match(rx, t) for rx in LIVRE[1:]) else "comando fora da lista livre"


SERVICO_SENSIVEL = {
    ("lock", "unlock"): "destrancar", ("lock", "open"): "abrir a fechadura",
    ("alarm_control_panel", "alarm_disarm"): "desarmar o alarme",
    ("camera", "turn_off"): "desligar a câmera",
}
PROTEGIDO_RX = re.compile(r"(port[aã]o|portao|garag|gate|garage|porta|door|fechadura|lock|alarm|camera|câmera|cerca|seguran|sirene|siren)", re.I)
SEGUROS = {("lock", "lock"), ("cover", "close_cover"), ("alarm_control_panel", "alarm_arm_away"), ("alarm_control_panel", "alarm_arm_home"),
           ("alarm_control_panel", "alarm_arm_night"), ("camera", "turn_on"), ("camera", "snapshot")}
TEXTO_EM_SERVICO = {("alexa_devices", "send_text_command"): "text_command", ("media_player", "play_media"): "media_content_id"}


def motivo_servico(dominio: str, acao: str, entity_id: str, dados: dict | None = None) -> str | None:
    if (dominio, acao) in SERVICO_SENSIVEL:
        return SERVICO_SENSIVEL[(dominio, acao)]
    campo = TEXTO_EM_SERVICO.get((dominio, acao))
    if campo and (dominio != "media_player" or (dados or {}).get("media_content_type") == "custom"):
        m = motivo_alexa(str((dados or {}).get(campo, "")))
        if m:
            return f"comando à Alexa ({m})"
    if dominio.startswith("alexa_media") or dominio == "alexa_devices" and acao not in ("send_sound", "send_info_skill"):
        return f"serviço direto da Alexa ({acao})"
    if (dominio, acao) not in SEGUROS and PROTEGIDO_RX.search(entity_id or ""):
        return f"mexer em {entity_id} (porta/portão/alarme/câmera)"
    return None


PRAZO_S = 900.0                           # um "sim" vale por 15 min (o mesmo prazo do Vigia)
_anotadas: dict[str, float] = {}           # assinatura → quando entrou no lote


def liberado(vigia, nome: str, args: dict, descricao: str, relogio=time.monotonic) -> tuple[bool, str]:
    """(pode seguir?, mensagem para o modelo). Só passa com o "sim" do João para ESTA ação exata (assinatura), dentro
    do prazo. Não usa o "confirmo" armado do Vigia: aquele pode ter sido dado para outra coisa."""
    if vigia is None:
        return False, "ação sensível sem Vigia disponível — não executo"
    if getattr(vigia, "convidado", ""):
        return False, "isso é da casa do João: com visita na linha eu não faço"
    from ..vigia.hooks import Acao, assinatura_de
    a = Acao(nome, f"casa:{descricao}", descricao, assinatura_de(nome, args))
    agora = relogio()
    if a.assinatura in vigia.liberadas:
        vigia.liberadas.pop(a.assinatura)
        quando = _anotadas.pop(a.assinatura, None)
        if quando is not None and agora - quando <= PRAZO_S:
            return True, ""
        # "sim" velho (ou de outra sessão): vale pedir de novo
    if all(x.assinatura != a.assinatura for x in vigia.lote):
        vigia.lote.append(a)
    _anotadas[a.assinatura] = agora
    pergunta = vigia.pedir_lote() or ""
    return False, (f"VIGIA: {descricao} precisa do sim do João — anotado. Siga com o resto e, ao terminar, pergunte UMA vez, "
                   f"exatamente: \"{pergunta}\". Quando ele disser 'sim', chame esta ferramenta de novo com os mesmos argumentos.")
