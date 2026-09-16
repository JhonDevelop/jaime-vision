"""Antecipador — enquanto o João ainda fala, já se sabe o que ele quer (docs/FASE-3-TEMPO-REAL.md §2.1).

Duas camadas, porque nenhum modelo em nuvem responde em 300 ms (medido 15/09: gpt-4.1-nano ~0,7 s, luna ~4 s):
1. **Heurística local, imediata** (pontuação, conjunção solta, hesitação, tamanho): decide `frase_fechou` para o
   detector de fim de turno e uma completude aproximada. Custa microssegundos.
2. **Modelo rápido, em segundo plano**: disparado a cada ~500 ms de texto novo, sem bloquear; quando responde (se o
   texto não mudou de rumo) refina intenção/completude, traz o `rascunho` da 1ª frase e chama `on_modelo(a)` —
   é aí que o TTS pré-sintetiza. Se chegar tarde demais, não faz mal: o turno segue pela heurística.
`modelo_fn` é injetável: `async (texto) -> dict`. `avaliar(texto, esperar=True)` espera o modelo (testes)."""
from __future__ import annotations
import asyncio, json, re, time
from dataclasses import dataclass, field, replace

INTERVALO_S = 0.5           # não chama o modelo mais que isto
MINIMO_CHARS = 6            # menos que isto não vale antecipar
ESPECULAR_A_PARTIR = 0.8    # completude mínima para pré-sintetizar o rascunho
TIMEOUT_S = 4.0             # o modelo roda em segundo plano; acima disto desiste

# fala que termina assim está claramente no meio: "…e também", "abre o Finder e", "eu queria que"
INACABADA_RX = re.compile(r"\b(e|ou|mas|que|também|tambem|aí|ai|então|entao|tipo|com|para|pra|pro|de|do|da|dos|das|no|na|nos|nas|em|se|porque|"
                          r"depois|antes|quando|onde|como|o|a|os|as|um|uma|meu|minha|meus|minhas|seu|sua|esse|essa|isso|aquele|aquela|é|eh|"
                          # verbos e preposições que pedem complemento: "eu preciso", "você sabe sobre o", "me manda" (cortes de 15/09 14:20–14:22)
                          r"preciso|precisa|quero|queria|gostaria|vou|vai|pode|podia|poderia|consegue|conseguiria|sabe|sobre|tem|tenho|"
                          r"faz|fazer|ver|abrir|abre|manda|mandar|me|te|nos|lhe|você|voce|deixa|só|so|mais|muito|bem|tá|ta)\s*[,…]?\s*$", re.I)
# frases completas que TERMINAM numa palavra da lista acima ("está aí?"): não são inacabadas
COMPLETA_RX = re.compile(r"\b(?:t[aá]|est[aá])\s+a[íi]\s*[?.!…]*$", re.I)
HESITACAO_RX = re.compile(r"\b(é+|hum+|ãh+|ah+|tipo|então|assim|né)\b[,…\s]*$", re.I)

SISTEMA = ("Você é o antecipador do Jaime, assistente pessoal do João. Recebe a transcrição PARCIAL do que o João está "
           "dizendo agora (ele ainda pode estar falando) e devolve SÓ um JSON com: intencao (5 palavras), completude "
           "(0 a 1: quanto do pedido já dá para entender), ambigua (true se há mais de uma leitura razoável), acao_prevista "
           "(o que o Jaime vai fazer, curto), rascunho (a PRIMEIRA frase da resposta do Jaime em português do Brasil, "
           "curta, direta, sem saudação — vazio se completude < 0.8), frase_fechou (true se a frase parece terminada; "
           "false se termina em conjunção, hesitação ou claramente vai continuar). Nada além do JSON.")

@dataclass
class Antecipacao:
    texto: str                      # transcrição que foi avaliada
    intencao: str = ""
    completude: float = 0.0
    ambigua: bool = True
    acao_prevista: str = ""
    rascunho: str = ""
    frase_fechou: bool = False
    origem: str = "heuristica"      # heuristica | modelo
    t: float = field(default_factory=time.time)
    latencia_s: float = 0.0

    @property
    def especulavel(self) -> bool:
        return self.completude >= ESPECULAR_A_PARTIR and not self.ambigua and bool(self.rascunho.strip())

def _norm(s: str) -> list[str]:
    return re.findall(r"[a-zà-ú0-9]+", (s or "").lower())

# Rascunhos LOCAIS para os pedidos mais comuns (Mente, 15/09): o modelo em nuvem leva 3,7–5,4 s por parecer — mais
# que o turno inteiro — e por isso o cache da 1ª frase nunca existia (0/10 na medição). Uma frase curta e certa,
# sintetizada enquanto o João ainda fala, é o que faz a resposta sair em ~150 ms. O modelo continua a partir dela.
VOCATIVO_RX = re.compile(r"^\s*(?:ô|o|oi|ei|hey|olá|ola|e aí|alô|fala)?\s*jaime\b[,\s]*", re.I)
_ART = r"(?:o|a|os|as|um|uma)?"
RASCUNHOS: list[tuple[re.Pattern, "callable"]] = [
    (re.compile(rf"^(?:abre|abra|abrir)\s+(?P<art>{_ART})\s*(?P<alvo>[\wÀ-ÿ][\wÀ-ÿ .'-]{{1,40}}?)\s*(?:pra mim|para mim|por favor|aí|ai)?[.!?…]*$", re.I),
     lambda m: ("abrir " + m.group("alvo").strip(), f"Abrindo {(m.group('art') + ' ') if m.group('art') else ''}{m.group('alvo').strip()}.")),
    (re.compile(r"\b(?:quem|o que|que|alguém|alguem)\b.*\b(?:mandou|me mandou|mensagem|mensagens|escreveu)\b", re.I),
     lambda m: ("ver mensagens", "Deixa eu ver as mensagens.")),
    (re.compile(r"\b(?:manda|mande|envia|envie|responde|responda)\b.*?\b(?:mensagem|zap|whatsapp|e-mail|email)?\b.*?\b(?:pro|pra|para|ao|à)\s+(?P<pessoa>[A-Za-zÀ-ÿ][\wÀ-ÿ-]{1,24})", re.I),
     lambda m: ("mensagem para " + m.group("pessoa"), f"Preparando a mensagem para {m.group('pessoa').capitalize()}.")),
    (re.compile(r"\b(?:previs[aã]o do tempo|clima|vai chover|temperatura|tempo (?:hoje|amanhã|amanha))\b", re.I),
     lambda m: ("clima", "Deixa eu ver o tempo.")),
    (re.compile(r"\b(?:cria|crie|criar|anota|anote|adiciona|adicione)\s+(?:uma\s+)?tarefa\b", re.I),
     lambda m: ("criar tarefa", "Criando a tarefa.")),
    (re.compile(r"\bresumo\s+do\s+dia\b|\bcomo\s+(?:est[aá]|t[aá])\s+o\s+dia\b", re.I),
     lambda m: ("resumo do dia", "Vou resumir o dia.")),
    (re.compile(r"\b(?:quanto\s+(?:est[aá]|t[aá])\s+o\s+d[oó]lar|cota[cç][aã]o\s+do\s+d[oó]lar|d[oó]lar\s+hoje)\b", re.I),
     lambda m: ("cotação do dólar", "Deixa eu ver a cotação.")),
    (re.compile(r"\bme\s+lembra\b|\blembrete\b", re.I),
     lambda m: ("lembrete", "Anotando o lembrete.")),
    (re.compile(r"^\s*(?:t[aá]|est[aá])\s+a[íi]\s*[?.!…]*$", re.I),
     lambda m: ("presença", "Estou aqui, senhor.")),
    (re.compile(r"\b(?:minha\s+)?agenda\b|\bcompromissos?\b", re.I),
     lambda m: ("agenda", "Deixa eu ver a agenda.")),
]

def rascunho_local(texto: str) -> tuple[str, str]:
    """(acao_prevista, rascunho) para um pedido comum, ou ("", "") — sem modelo, em microssegundos."""
    t = VOCATIVO_RX.sub("", (texto or "").strip())
    for rx, fazer in RASCUNHOS:
        if (m := rx.search(t)):
            acao, r = fazer(m)
            return acao, r
    return "", ""

def heuristico(texto: str) -> dict:
    """Sem modelo: completude pelo tamanho e pela pontuação; fechou se não termina em conjunção/hesitação."""
    t = (texto or "").strip()
    palavras = _norm(t)
    if not palavras:
        return {"intencao": "", "completude": 0.0, "ambigua": True, "acao_prevista": "", "rascunho": "", "frase_fechou": False}
    inacabada = (bool(INACABADA_RX.search(t)) and not COMPLETA_RX.search(t)) or bool(HESITACAO_RX.search(t))
    pontuada = t[-1] in ".!?…"
    completude = min(1.0, 0.25 + 0.12 * len(palavras)) if not inacabada else min(0.5, 0.08 * len(palavras))
    if pontuada:
        completude = max(completude, 0.85)
    # "fechou" (fim de turno em 450 ms) só com pontuação final ou pedido reconhecido; 3+ palavras soltas NÃO bastam —
    # "…parabéns mas eu preciso" fechava em 450 ms e cortava o João (15/09 14:20). Sem parecer, o detector espera 700 ms.
    acao, rascunho = rascunho_local(t) if not inacabada else ("", "")
    fechou = (not inacabada) and (pontuada or bool(rascunho))
    if rascunho:
        completude = max(completude, ESPECULAR_A_PARTIR)         # pedido reconhecido: dá para especular a 1ª frase
    return {"intencao": " ".join(palavras[:5]), "completude": round(completude, 2), "ambigua": len(palavras) < 3 and not rascunho,
            "acao_prevista": acao, "rascunho": rascunho, "frase_fechou": fechou}

def bate(antecipado: str, final: str, minimo: float = 0.6) -> bool:
    """A intenção antecipada ainda vale para a transcrição final? Jaccard de palavras + o final não pode ter
    crescido para outra direção (mais de 60% de palavras novas)."""
    a, b = set(_norm(antecipado)), set(_norm(final))
    if not a or not b:
        return False
    inter = len(a & b)
    jaccard = inter / len(a | b)
    novas = len(b - a) / max(1, len(b))
    return jaccard >= minimo and novas <= 0.6

def modelo_openai(client, modelo: str):
    """Fábrica: devolve `async (texto) -> dict` usando a Responses API (saída curta, JSON)."""
    async def fn(texto: str) -> dict:
        r = await client.responses.create(model=modelo, max_output_tokens=160,
                                          input=[{"role": "system", "content": SISTEMA},
                                                 {"role": "user", "content": f"Transcrição parcial: «{texto}»"}])
        saida = (getattr(r, "output_text", "") or "").strip()
        m = re.search(r"\{.*\}", saida, re.S)
        return json.loads(m.group(0)) if m else {}
    return fn

class Antecipador:
    def __init__(self, modelo_fn=None, intervalo_s: float = INTERVALO_S, timeout_s: float = TIMEOUT_S, on_modelo=None):
        self.modelo_fn = modelo_fn          # None = só heurística
        self.intervalo_s, self.timeout_s = intervalo_s, timeout_s
        self.on_modelo = on_modelo          # callback(a) quando o modelo refina uma antecipação
        self.ultima: Antecipacao | None = None
        self._ultimo_texto = ""
        self._ultima_chamada = 0.0
        self._em_curso: asyncio.Task | None = None
        self.chamadas = 0
        self.erros = 0

    def limpar(self) -> None:
        self.ultima = None; self._ultimo_texto = ""; self._ultima_chamada = 0.0
        if self._em_curso and not self._em_curso.done():
            self._em_curso.cancel()
        self._em_curso = None

    def pode_avaliar(self, texto: str, agora: float | None = None) -> bool:
        agora = time.time() if agora is None else agora
        t = (texto or "").strip()
        return len(t) >= MINIMO_CHARS and t != self._ultimo_texto

    def _pode_chamar_modelo(self, agora: float) -> bool:
        return bool(self.modelo_fn) and (self._em_curso is None or self._em_curso.done()) and agora - self._ultima_chamada >= self.intervalo_s

    async def avaliar(self, texto: str, agora: float | None = None, esperar: bool = False) -> Antecipacao | None:
        """Heurística já; modelo em segundo plano (ou esperado, se `esperar`). Devolve a antecipação vigente."""
        agora = time.time() if agora is None else agora
        if not self.pode_avaliar(texto, agora):
            return self.ultima
        self._ultimo_texto = texto.strip()
        base = heuristico(texto)
        a = Antecipacao(texto=texto.strip(), **{k: base[k] for k in ("intencao", "completude", "ambigua", "acao_prevista", "rascunho", "frase_fechou")})
        self.ultima = a
        if self._pode_chamar_modelo(agora):
            self._ultima_chamada = agora
            self._em_curso = asyncio.create_task(self._refinar(texto.strip(), a))
            if esperar:
                try:
                    await self._em_curso
                except (asyncio.CancelledError, Exception):
                    pass
        return self.ultima

    async def _refinar(self, texto: str, base: Antecipacao) -> None:
        inicio = time.time(); self.chamadas += 1
        try:
            d = await asyncio.wait_for(self.modelo_fn(texto), self.timeout_s)
        except asyncio.CancelledError:
            return
        except Exception:
            self.erros += 1; return
        if not isinstance(d, dict) or not d:
            self.erros += 1; return
        # o texto seguiu outro rumo enquanto o modelo pensava? então o parecer não vale
        if not self._ultimo_texto.startswith(texto) and not bate(texto, self._ultimo_texto):
            return
        # o parecer vale para o texto ATUAL (o modelo viu um prefixo dele): assim `confere()` compara com o final certo
        # O rascunho LOCAL (pedido reconhecido) prevalece: o modelo devolvia rascunho vazio/completude 0,5 para
        # "abre o Finder" e apagava o da heurística — era isso o 0/10 do `voz latencia` com esperar=True (Vigília, 18:04).
        rascunho_modelo = str(d.get("rascunho", ""))[:240].strip()
        try:
            completude_modelo = max(0.0, min(1.0, float(d.get("completude", 0.0))))
        except (TypeError, ValueError):
            completude_modelo = 0.0
        modelo_especula = bool(rascunho_modelo) and completude_modelo >= ESPECULAR_A_PARTIR and not bool(d.get("ambigua", False))
        # o modelo só substitui o rascunho local se o parecer dele também for especulável (o nano devolvia um rascunho
        # com completude 0,2 e derrubava o local — Vigília 23:44: 0/10 no benchmark mesmo com o M-13)
        local = bool(base.rascunho) and base.origem == "heuristica" and not modelo_especula
        a = replace(base, texto=self._ultimo_texto, origem="modelo", latencia_s=time.time() - inicio,
                    intencao=str(d.get("intencao", base.intencao))[:80],
                    completude=max(base.completude if local else 0.0, min(1.0, float(d.get("completude", base.completude)))),
                    ambigua=False if local else bool(d.get("ambigua", base.ambigua)),
                    acao_prevista=(base.acao_prevista if local else "") or str(d.get("acao_prevista", ""))[:120],
                    rascunho=base.rascunho if local else rascunho_modelo,
                    # o modelo decide se fechou, mas conjunção solta no fim é veto local (barato e certeiro)
                    frase_fechou=bool(d.get("frase_fechou", base.frase_fechou)) and not INACABADA_RX.search(self._ultimo_texto))
        self.ultima = a
        if self.on_modelo:
            try:
                r = self.on_modelo(a)
                if asyncio.iscoroutine(r):
                    await r
            except Exception:
                pass
        # o texto cresceu enquanto o modelo pensava: já pede o parecer do texto novo
        if self._ultimo_texto != texto and self.modelo_fn:
            self._ultima_chamada = time.time()
            self._em_curso = asyncio.create_task(self._refinar(self._ultimo_texto, a))

    async def esperar_modelo(self) -> Antecipacao | None:
        if self._em_curso and not self._em_curso.done():
            try:
                await self._em_curso
            except (asyncio.CancelledError, Exception):
                pass
        return self.ultima

    def confere(self, texto_final: str) -> Antecipacao | None:
        """Ao fim do turno: a última antecipação especulável ainda bate com o texto final? Devolve-a, ou None."""
        a = self.ultima
        if a and a.especulavel and bate(a.texto, texto_final):
            return a
        return None
