"""Frases que abrem as cenas do Jarvis sem passar pelo modelo (resposta em milissegundos, frase inteira ancorada):

- "bom dia" (manhã, 1ª vez) / "me dá o briefing"          → briefing (vídeo de 1:22)
- "ativar monitor" / "ativa o monitor"                    → rosto + relatório do treino (vídeo do monitor)
- "cria/abre/mostra um holograma do/da <objeto>"          → holograma 3D controlado pela mão (vídeo do carro)
- "fecha o holograma"                                     → fecha
- "aprende meu rosto" / "esquece meu rosto"               → cadastro do rosto do João (cortesia, nunca chave)
- "aprende o rosto da Ana, minha irmã" / "esquece o rosto da Ana" → outras pessoas, ligadas ao grafo de relações
- "quem é esse?" / "você me reconhece?" / "quais rostos você conhece?" → reconhece e conta quem é
- "modo partículas" / "modo fios" / "orbe de partículas"  → estilo do orbe (vídeo da esfera de partículas)
- "qual sua capacidade máxima?" / "o que você consegue fazer?" → inventário REAL do que está ligado agora
- "como estão os sistemas?"                               → sentinela (sites, servidores e APIs vigiados)
- "quero desenhar" / "modo desenho"                       → prancheta 3D (dedo indicador ou mouse desenham no ar)
- "dá volume ao desenho" / "transforma o desenho em 3D"   → o desenho vira objeto sólido
- "exporta em STL" / "gera o arquivo 3D" / "abre no Blender" → arquivos do holograma como está
- "manda para impressão com 12 cm" / "imprime isso"       → STL de mesa (mm, Z para cima) aberto no fatiador
- "liga o controle pelo olhar"                            → mira pelos olhos
- "liga o controle do computador" / "liga o controle por mão" / "desliga…" → as mãos viram o mouse do Mac inteiro
- "recalibra a mão" / "troca as mãos"                     → calibração dos cantos / canhoto
- "quais as notícias?"                                   → só as notícias (o "bom dia" não traz notícias)
- "me coloca no holograma" / "mostra meus braços" / "tira a câmera do holograma" → câmera e braços dentro da cena
- "captura esse objeto"                                   → congela a câmera como peça de referência
Com holograma aberto (`edicao`): "abre as portas", "aumenta essa peça", "desfaz"… viram edição do holograma.
"""
from __future__ import annotations
import re, unicodedata

MONITOR_RX = re.compile(r"^\s*(jarvis|jaime)?[,\s]*(ativar|ativa|ative|liga|ligar|abre|abrir)\s+(o\s+)?monitor\s*[.!]*\s*$", re.I)
HOLO_RX = re.compile(r"^\s*(jarvis|jaime)?[,\s]*(cria|crie|criar|faz|faca|faça|fazer|abre|abrir|mostra|mostrar|gera|gerar|monta|montar)"
                     r"\s+(pra mim\s+|para mim\s+)?(um|uma|o|a)?\s*holograma\s+(de|do|da|dos|das)\s+(?P<obj>[\w\s\-çãõáéíóúâêô]+?)"
                     r"(\s*,?\s*(pra|para)\s+(que\s+)?eu\s+.*)?\s*[.!?]*\s*$", re.I)
FECHA_HOLO_RX = re.compile(r"^\s*(fecha|fechar|some com|tira)\s+(o\s+)?holograma\s*[.!]*\s*$", re.I)
APRENDE_ROSTO_RX = re.compile(r"^\s*(jaime|jarvis)?[,\s]*(aprende|aprenda|cadastra|cadastre|grava|memoriza)\s+(o\s+)?meu\s+rosto\s*[.!]*\s*$", re.I)
ESQUECE_ROSTO_RX = re.compile(r"^\s*(jaime|jarvis)?[,\s]*(esquece|esqueça|apaga|apague)\s+(o\s+)?meu\s+rosto\s*[.!]*\s*$", re.I)
APRENDE_OUTRO_RX = re.compile(r"^\s*(jaime|jarvis)?[,\s]*(aprende|aprenda|cadastra|cadastre|grava|memoriza)\s+(o\s+)?rosto\s+(do|da|de)\s+"
                              r"(?P<nome>[\wçãõáéíóúâêô]+(?:\s+[\wçãõáéíóúâêô]+)?)"
                              r"(?:\s*,?\s*(?:que\s+é\s+|ele\s+é\s+|ela\s+é\s+)?(?:o\s+|a\s+)?(?:meu|minha)\s+(?P<rel>[\wçãõáéíóúâêô ]+?))?\s*[.!]*\s*$", re.I)
ESQUECE_OUTRO_RX = re.compile(r"^\s*(jaime|jarvis)?[,\s]*(esquece|esqueça|apaga|apague)\s+(o\s+)?rosto\s+(do|da|de)\s+(?P<nome>[\wçãõáéíóúâêô ]+?)\s*[.!]*\s*$", re.I)
QUEM_E_RX = re.compile(r"^\s*(jaime|jarvis)?[,\s]*(quem\s+(é|e|ta|tá|está|esta)\s+(esse|essa|ele|ela|aqui|a[ií]|na\s+c[aâ]mera|na\s+frente)(\s+(aqui|a[ií]|comigo))?|"
                       r"quem\s+sou\s+eu|voc[eê]\s+me\s+reconhece|sabe\s+quem\s+(eu\s+sou|sou\s+eu|[eé]\s+(esse|essa)))\s*[?.!]*\s*$", re.I)
ROSTOS_RX = re.compile(r"^\s*(jaime|jarvis)?[,\s]*(quais|que)\s+rostos\s+(voc[eê]\s+)?(conhece|tem|sabe|guardou)\s*[?.!]*\s*$", re.I)
CAPACIDADES_RX = re.compile(r"^\s*(jarvis|jaime)?[,\s]*(me )?(fala|diga|diz|conta)?\s*(pra|para)?\s*(mim)?[,\s]*(qual|quais)\s+(é|e|são|sao)?\s*(a |as )?(sua|suas)\s+"
                            r"(capacidade|capacidades)( m[aá]xima)?\s*[?.!]*\s*$|^\s*(o que|oque) (voc[eê]|tu) (consegue|sabe|pode) fazer\s*[?.!]*\s*$", re.I)
SISTEMAS_RX = re.compile(r"^\s*(jarvis|jaime)?[,\s]*(como (est[aã]o|t[aã]o)|status d[oa]s?|situa[cç][aã]o d[oa]s?)\s+(os |as )?"
                         r"(sistemas|servidores|sites|apis|servi[cç]os)( cr[ií]ticos)?\s*[?.!]*\s*$", re.I)
J = r"^\s*(jarvis|jaime)?[,\s]*"
DESENHO_RX = re.compile(J + r"((quero|vou|deixa eu|me deixa)\s+desenhar|modo\s+desenho|abre\s+a\s+prancheta|desenhar\s+(um|uma)\s+holograma)(?P<resto>.*)$", re.I)
VOLUME_RX = re.compile(J + r"(d[aá]|coloca|p[õo]e)\s+volume\s+(ao|no|nesse|neste)\s+desenho(?P<resto>.*)$|"
                       r"^\s*(jarvis|jaime)?[,\s]*(transforma|converte|vira|deixa)\s+(o\s+|esse\s+|este\s+)?desenho\s+(em|num|como)\s+(3d|tr[eê]s\s*d|objeto|s[oó]lido)(?P<resto2>.*)$", re.I)
EXPORTA_RX = re.compile(J + r"(?:(exporta|exportar|salva|salvar|gera|gerar|baixa|baixar|me\s+d[aá])\s+(o\s+|esse\s+|um\s+)?(holograma|modelo|objeto|arquivo(\s+3d)?|isso|desenho|3d)"
                        r"(\s+(em|como|no\s+formato|para|pra))?\s*(?P<fmt>stl|obj|glb|gltf|3d)?"
                        r"|(exporta|exportar|salva|salvar|gera|gerar)\s+(em|como|no\s+formato)?\s*(?P<fmt2>stl|obj|glb|gltf))\s*[.!]*\s*$", re.I)
BLENDER_RX = re.compile(J + r"(abre|abrir|manda|mandar|leva|levar|joga|coloca)\s+(o\s+|esse\s+)?(holograma|modelo|objeto|isso|desenho)?\s*(no|pro|para\s+o|pra)\s+"
                        r"(blender|est[uú]dio(\s+3d)?)\s*[.!]*\s*$", re.I)
IMPRIME_RX = re.compile(J + r"(?:(manda|mandar|prepara|preparar|leva|levar|envia|enviar)\s+(o\s+|esse\s+|este\s+)?(holograma|modelo|objeto|isso|desenho)?\s*(para|pra|pro)\s+(a\s+|o\s+)?"
                        r"(impress[aã]o|impressora|fatiador)(\s+3d)?|imprime|imprima|imprimir|imprimi)(\s+(o\s+|esse\s+|isso|este\s+)?(holograma|modelo|objeto|desenho)?)?"
                        r"(\s*(com|de|em|no\s+tamanho\s+de)\s+(?P<n>\d+(?:[.,]\d+)?)\s*(?P<u>mm|mil[ií]metros?|cm|cent[ií]metros?|m|metros?))?\s*[.!]*\s*$", re.I)
DESFAZ_RX = re.compile(J + r"(desfaz|desfazer|desfa[cç]a|volta\s+(como\s+estava|atr[aá]s)|volta\s+o\s+que\s+era)\s*(isso)?\s*[.!]*\s*$", re.I)
OLHAR_RX = re.compile(J + r"(?P<acao>liga|ligar|ativa|ativar|desliga|desligar|desativa|desativar)\s+(o\s+)?(controle\s+(pelo|por)\s+)?(olhar|olho|olhos|rastreamento\s+ocular)\s*[.!]*\s*$", re.I)
MAOS_RX = re.compile(J + r"(?P<acao>liga|ligar|ativa|ativar|desliga|desligar|desativa|desativar)\s+(o\s+)?controle\s+(pela|por|pelas|com\s+a|com\s+as)\s+(m[aã]o|m[aã]os|gestos?)\s*[.!]*\s*$", re.I)
CAIXA_RX = re.compile(J + r"((abre|abra|mostra|mostre|l[eê]|leia|carrega|como\s+est[aá])\s+(a\s+|minha\s+)?caixa\s+de\s+(entrada|e-?mails?)|"
                      r"(abre|mostra|l[eê]|leia|carrega)\s+(os\s+|meus\s+)?e-?mails|tenho\s+(algum\s+)?e-?mails?(\s+novos?)?|chegou\s+(algum\s+)?e-?mail)\s*[?.!]*\s*$", re.I)
MENSAGENS_RX = re.compile(J + r"((abre|mostra|l[eê]|leia|carrega|quais\s+s[aã]o)\s+(as\s+|minhas\s+)?mensagens(\s+(do|no)\s+(whats\s*app|zap|whats))?|"
                          r"(tenho|chegou)\s+(alguma\s+)?mensage(m|ns)(\s+(no|do)\s+(whats\s*app|zap|whats))?|quem\s+(me\s+)?mandou\s+mensagem)\s*[?.!]*\s*$", re.I)
EDITA_RX = re.compile(J + r"(abre|abra|fecha|feche|adiciona|acrescenta|coloca|coloque|p[õo]e|bota|tira|remove|aumenta|aumente|diminui|diminua|deixa|muda|mude|troca|"
                      r"estica|encolhe|alonga|gira|gire|vira|vire|roda|duplica|move|mova|empurra|levanta|abaixa|separa|separe|junta|esconde|mostra|mostre|explode|remonta|"
                      r"reseta|centraliza|inclina|faz|fa[cç]a|transforma|destaca|solta|puxa|isola|isole|foca|foque|enquadra|aproxima|pinta|pinte|colore|sobe|suba|"
                      r"desce|volta|desmonta|oculta|amplia|reduz|dobra|copia|clona|leva|quero\s+ver)\b(?P<resto>.*)$", re.I)
COMPUTADOR_RX = re.compile(J + r"(?P<acao>liga|ligar|ativa|ativar|desliga|desligar|desativa|desativar|para|pare)\s+(o\s+)?(controle|mouse)\s+(do|no|pelo|pela)?\s*"
                           r"(computador|mac|pc|sistema|mouse|m[aã]o|m[aã]os|gestos?)(\s+(pela|pelas|com\s+a|com\s+as)\s+m[aã]os?)?\s*[.!]*\s*$|"
                           r"^\s*(jarvis|jaime)?[,\s]*(?P<acao2>liga|ativa|desliga|desativa)\s+(o\s+)?controle\s+(pela|por|pelas|com\s+a|com\s+as)\s+(m[aã]o|m[aã]os|gestos?)\s*[.!]*\s*$", re.I)
RECALIBRA_RX = re.compile(J + r"(recalibra|recalibrar|calibra|calibrar)\s+(de\s+novo\s+)?(a\s+|as\s+|o\s+)?(m[aã]o|m[aã]os|controle|mouse|cursor)\s*[.!]*\s*$", re.I)
TROCA_MAOS_RX = re.compile(J + r"(troca|trocar|inverte|inverter)\s+(as\s+|a\s+)?m[aã]os?\s*[.!]*\s*$|^\s*(sou|eu\s+sou)\s+canhoto\s*[.!]*\s*$", re.I)
NOTICIAS_RX = re.compile(J + r"((abre|abra|mostra|mostre|monta|monte|l[eê]|leia|carrega|carregue|me\s+d[aá]|me\s+conta|me\s+fala|traz|quero(\s+ver)?)\s+"
                         r"(as\s+|essas\s+|minhas\s+|umas\s+|alguma\s+)?(principais\s+|[uú]ltimas\s+)?not[ií]cias?(\s+(de\s+hoje|do\s+dia|novas|de\s+agora|do\s+mundo))?|"
                         r"(quais\s+(s[aã]o\s+)?(as\s+)?|que\s+|tem\s+)(principais\s+|[uú]ltimas\s+)?not[ií]cias(\s+(de\s+hoje|do\s+dia|novas))?|"
                         r"not[ií]cias\s+(de\s+hoje|do\s+dia)|radar\s+de\s+not[ií]cias|o\s+que\s+(t[aá]|est[aá])\s+acontecendo\s+no\s+mundo)\s*[?.!]*\s*$", re.I)
CAMERA_HOLO_RX = re.compile(J + r"(me\s+(coloca|p[õo]e|bota|mostra)\s+no\s+holograma|(mostra|coloca|p[õo]e|liga)\s+(a\s+)?c[aâ]mera\s+no\s+holograma|"
                            r"(mostra|coloca|p[õo]e)\s+(meu|o\s+meu)\s+(corpo|bra[cç]o|pulso|m[aã]o|rosto|cabe[cç]a|p[eé])\s+no\s+holograma|mostra\s+(os\s+)?meus\s+bra[cç]os)\s*[.!]*\s*$", re.I)
CAMERA_FORA_RX = re.compile(J + r"(tira|desliga|esconde)\s+(a\s+)?c[aâ]mera\s+do\s+holograma|(me\s+)?tira\s+(me\s+)?do\s+holograma|esconde\s+(os\s+)?meus\s+bra[cç]os\s*[.!]*\s*$", re.I)
CAPTURA_RX = re.compile(J + r"(captura|capture|escaneia|escaneie|congela|fotografa|pega)\s+(esse|este|o|a|essa|esta)?\s*(objeto|coisa|c[aâ]mera|imagem|isso|pe[cç]a)?"
                        r"(\s+(para|pro|no)\s+(o\s+)?holograma)?\s*[.!]*\s*$", re.I)
ORBE_RX = re.compile(r"^\s*(modo|orbe( de| em)?|esfera( de)?)\s+(?P<estilo>part[ií]culas|fios|energia)\s*[.!]*\s*$", re.I)


def _n(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn").strip()


def cena(texto: str) -> tuple[str, dict] | None:
    """('monitor'|'holograma'|'fecha_holograma'|'aprende_rosto'|'esquece_rosto'|'orbe', args) ou None."""
    t = (texto or "").strip()
    if MONITOR_RX.match(t):
        return "monitor", {}
    if (m := HOLO_RX.match(t)):
        return "holograma", {"objeto": m.group("obj").strip()}
    if FECHA_HOLO_RX.match(t):
        return "fecha_holograma", {}
    if APRENDE_ROSTO_RX.match(t):
        return "aprende_rosto", {}
    if (m := APRENDE_OUTRO_RX.match(t)):
        return "aprende_rosto", {"nome": m.group("nome").strip(), "relacao": (m.group("rel") or "").strip()}
    if ESQUECE_ROSTO_RX.match(t):
        return "esquece_rosto", {}
    if (m := ESQUECE_OUTRO_RX.match(t)):
        return "esquece_rosto", {"nome": m.group("nome").strip()}
    if QUEM_E_RX.match(t):
        return "quem_e", {}
    if ROSTOS_RX.match(t):
        return "rostos", {}
    if CAPACIDADES_RX.match(t):
        return "capacidades", {}
    if SISTEMAS_RX.match(t):
        return "sistemas", {}
    if (m := ORBE_RX.match(t)):
        e = _n(m.group("estilo"))
        return "orbe", {"estilo": "particulas" if e.startswith("part") else "fios"}
    if (m := DESENHO_RX.match(t)):
        return "desenho", {}
    if (m := VOLUME_RX.match(t)):
        resto = _n(m.group("resto") or m.group("resto2") or "")
        mm = re.search(r"\b(e|eh|é)\s+(um|uma|o|a)\s+(?P<o>[\w\s-]+?)\s*[.!]*$", resto)
        return "volume", {"nome": mm.group("o").strip() if mm else ""}
    if (m := BLENDER_RX.match(t)):
        return "blender", {}
    if (m := IMPRIME_RX.match(t)):
        mm = 100.0
        if m.group("n"):
            n, u = float(m.group("n").replace(",", ".")), _n(m.group("u"))
            mm = n * (10 if u.startswith("c") else 1000 if u in ("m", "metro", "metros") else 1)
        return "imprimir", {"maior_mm": mm}
    if (m := EXPORTA_RX.match(t)):
        f = _n(m.group("fmt") or m.group("fmt2") or "")
        return "exportar", {"formatos": ["glb"] if f in ("glb", "gltf") else [f] if f in ("stl", "obj") else ["stl", "obj", "glb"]}
    if CAIXA_RX.match(t):
        return "caixa", {}
    if MENSAGENS_RX.match(t):
        return "mensagens", {}
    if NOTICIAS_RX.match(t):
        return "noticias", {}
    if (m := OLHAR_RX.match(t)):
        return "olhar", {"ligar": not _n(m.group("acao")).startswith("des")}
    if (m := COMPUTADOR_RX.match(t)) or (m := MAOS_RX.match(t)):
        acao = _n(m.groupdict().get("acao") or m.groupdict().get("acao2") or "")
        return "computador", {"ligar": not (acao.startswith("des") or acao.startswith("par"))}
    if RECALIBRA_RX.match(t):
        return "recalibrar", {}
    if TROCA_MAOS_RX.match(t):
        return "trocar_maos", {}
    if CAMERA_FORA_RX.match(t):
        return "camera_holo", {"ligar": False}
    if (m := CAMERA_HOLO_RX.match(t)):
        return "camera_holo", {"ligar": True, "bracos": bool(re.search(r"bra[cç]o", t, re.I))}
    if CAPTURA_RX.match(t) and re.search(r"objeto|holograma|c[aâ]mera|escane|captura|congela|fotografa", t, re.I):
        return "capturar", {}
    return None


def edicao(texto: str) -> tuple[str, dict] | None:
    """Só vale com holograma aberto: 'desfaz' ou um pedido de alteração ('abre as portas', 'aumenta essa peça')."""
    t = (texto or "").strip()
    if DESFAZ_RX.match(t):
        return "desfazer", {}
    if EDITA_RX.match(t) and len(t) <= 200:
        return "editar", {"pedido": re.sub(r"^\s*(jarvis|jaime)[,\s]*", "", t, flags=re.I)}
    return None
