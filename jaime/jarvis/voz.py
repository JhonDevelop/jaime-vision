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
- "liga o controle pelo olhar" / "liga o controle por mão" → mira pelos olhos / cursor pela mão na tela toda
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
EDITA_RX = re.compile(J + r"(abre|abra|fecha|feche|adiciona|acrescenta|coloca|coloque|p[õo]e|bota|tira|remove|aumenta|aumente|diminui|diminua|deixa|muda|mude|troca|"
                      r"estica|encolhe|alonga|gira|gire|vira|vire|roda|duplica|move|mova|empurra|levanta|abaixa|separa|junta|esconde|mostra|explode|remonta|"
                      r"reseta|centraliza|inclina|faz|fa[cç]a|transforma)\b(?P<resto>.+)$", re.I)
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
    if (m := OLHAR_RX.match(t)):
        return "olhar", {"ligar": not _n(m.group("acao")).startswith("des")}
    if (m := MAOS_RX.match(t)):
        return "maos", {"ligar": not _n(m.group("acao")).startswith("des")}
    return None


def edicao(texto: str) -> tuple[str, dict] | None:
    """Só vale com holograma aberto: 'desfaz' ou um pedido de alteração ('abre as portas', 'aumenta essa peça')."""
    t = (texto or "").strip()
    if DESFAZ_RX.match(t):
        return "desfazer", {}
    if EDITA_RX.match(t) and len(t) <= 200:
        return "editar", {"pedido": re.sub(r"^\s*(jarvis|jaime)[,\s]*", "", t, flags=re.I)}
    return None
