"""Antecipador — enquanto o João ainda fala, um modelo rápido já diz o que ele quer (docs/FASE-3-TEMPO-REAL.md §2.1).

A cada ~500 ms de transcrição nova devolve: intenção, completude (0–1), ambígua?, ação prevista, um rascunho de
primeira frase e se a frase fechou (critério semântico do fim de turno). Se completude ≥ 0.8 e não é ambígua, o
rascunho vai para o TTS antes de o João terminar; ao fim do turno, `bate()` decide se o áudio em cache ainda serve.

Modelo: OpenAI rápido (JAIME_ANTECIPADOR_MODEL, padrão gpt-5.6-luna) quando há OPENAI_API_KEY; senão a heurística
local (pontuação, conjunções soltas, tamanho) — sem rede, sem custo, e é o que os testes usam.
`modelo_fn` é injetável: `async (texto) -> dict`."""
from __future__ import annotations
import asyncio, json, re, time
from dataclasses import dataclass, field

INTERVALO_S = 0.5           # não chama o modelo mais que isto
MINIMO_CHARS = 6            # menos que isto não vale antecipar
ESPECULAR_A_PARTIR = 0.8    # completude mínima para pré-sintetizar o rascunho
TIMEOUT_S = 0.8             # resposta do modelo tem de ser rápida; senão fica a heurística

# fala que termina assim está claramente no meio: "…e também", "abre o Finder e", "eu queria que"
INACABADA_RX = re.compile(r"\b(e|ou|mas|que|também|tambem|aí|ai|então|entao|tipo|com|para|pra|de|do|da|no|na|em|se|porque|"
                          r"depois|antes|quando|onde|como|o|a|os|as|um|uma|meu|minha|esse|essa|isso|aquele|aquela|é|eh)\s*[,…]?\s*$", re.I)
HESITACAO_RX = re.compile(r"\b(é+|hum+|ãh+|ah+|tipo|então|assim|né)\b[,…\s]*$", re.I)
PERGUNTA_RX = re.compile(r"\b(o que|qual|quanto|quando|onde|como|por que|porque|quem|será|tem como|dá pra|da pra|pode)\b", re.I)

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

def heuristico(texto: str) -> dict:
    """Sem modelo: completude pelo tamanho e pela pontuação; fechou se não termina em conjunção/hesitação."""
    t = (texto or "").strip()
    palavras = _norm(t)
    if not palavras:
        return {"intencao": "", "completude": 0.0, "ambigua": True, "acao_prevista": "", "rascunho": "", "frase_fechou": False}
    inacabada = bool(INACABADA_RX.search(t)) or bool(HESITACAO_RX.search(t))
    pontuada = t[-1] in ".!?…"
    completude = min(1.0, 0.25 + 0.12 * len(palavras)) if not inacabada else min(0.5, 0.08 * len(palavras))
    if pontuada:
        completude = max(completude, 0.85)
    return {"intencao": " ".join(palavras[:5]), "completude": round(completude, 2), "ambigua": len(palavras) < 3,
            "acao_prevista": "", "rascunho": "", "frase_fechou": (not inacabada) and (pontuada or len(palavras) >= 3)}

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
    def __init__(self, modelo_fn=None, intervalo_s: float = INTERVALO_S, timeout_s: float = TIMEOUT_S):
        self.modelo_fn = modelo_fn          # None = só heurística
        self.intervalo_s, self.timeout_s = intervalo_s, timeout_s
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
        return len(t) >= MINIMO_CHARS and t != self._ultimo_texto and agora - self._ultima_chamada >= self.intervalo_s

    async def avaliar(self, texto: str, agora: float | None = None) -> Antecipacao | None:
        """Avalia a transcrição parcial (respeitando o intervalo). Heurística sempre; modelo por cima quando há."""
        agora = time.time() if agora is None else agora
        if not self.pode_avaliar(texto, agora):
            return self.ultima
        self._ultimo_texto = texto.strip(); self._ultima_chamada = agora
        base = heuristico(texto)
        a = Antecipacao(texto=texto.strip(), **{k: base[k] for k in ("intencao", "completude", "ambigua", "acao_prevista", "rascunho", "frase_fechou")})
        if self.modelo_fn:
            inicio = time.time()
            try:
                self.chamadas += 1
                d = await asyncio.wait_for(self.modelo_fn(texto), self.timeout_s)
                if isinstance(d, dict) and d:
                    a.intencao = str(d.get("intencao", a.intencao))[:80]
                    a.completude = max(0.0, min(1.0, float(d.get("completude", a.completude))))
                    a.ambigua = bool(d.get("ambigua", a.ambigua))
                    a.acao_prevista = str(d.get("acao_prevista", ""))[:120]
                    a.rascunho = str(d.get("rascunho", ""))[:240]
                    # o modelo decide se fechou, mas conjunção solta no fim é veto local (barato e certeiro)
                    a.frase_fechou = bool(d.get("frase_fechou", a.frase_fechou)) and not INACABADA_RX.search(texto.strip())
                    a.origem = "modelo"
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self.erros += 1
            except Exception:
                self.erros += 1
            a.latencia_s = time.time() - inicio
        self.ultima = a
        return a

    def confere(self, texto_final: str) -> Antecipacao | None:
        """Ao fim do turno: a última antecipação especulável ainda bate com o texto final? Devolve-a, ou None."""
        a = self.ultima
        if a and a.especulavel and bate(a.texto, texto_final):
            return a
        return None
