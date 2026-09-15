"""Juiz — segunda opinião com arbitragem.

Para tarefa do tipo *decisão*, ou quando o João diz "pensa bem" / "compara": os dois provedores respondem em
paralelo e um terceiro modelo (Fable 5.1, `JAIME_MODEL_DECISAO`) escolhe A, B ou mescla, com UMA frase de
justificativa — que vai para o diário e para o painel Raciocínio do HUD. Custa o dobro; só quando vale.

Se um provedor falhar (sem crédito, sem chave), o juiz devolve a resposta do outro sem arbitrar."""
from __future__ import annotations
import asyncio, json, re
from dataclasses import dataclass, field
from .provedores.base import Resposta

PEDE_JUIZ_RX = re.compile(r"\b(pensa bem|pense bem|compara|compare|segunda opini[aã]o|duas opini[oõ]es)\b", re.I)

def pede_juiz(texto: str, tipo: str = "") -> bool:
    return tipo == "decisão" or bool(PEDE_JUIZ_RX.search(texto or ""))

@dataclass
class Veredito:
    texto: str
    escolha: str            # "A" | "B" | "mescla" | "unica"
    justificativa: str
    respostas: list = field(default_factory=list)
    custo: float = 0.0
    latencia: float = 0.0

PROMPT_JUIZ = """Você é o juiz. O João perguntou:

<pergunta>{pergunta}</pergunta>

Duas respostas independentes:

<A provedor="{pa}" modelo="{ma}">{a}</A>

<B provedor="{pb}" modelo="{mb}">{b}</B>

Escolha a melhor (A ou B) ou mescle as duas numa resposta melhor que ambas. Critérios: correção, utilidade prática
para o João, concisão. Responda SOMENTE um JSON com as chaves: "escolha" ("A", "B" ou "mescla"),
"justificativa" (UMA frase, em português) e "resposta" (o texto final para o João, sem markdown)."""

def _extrair_json(txt: str) -> dict | None:
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None

class Juiz:
    def __init__(self, a, b, arbitro):
        """a, b, arbitro: objetos com `.nome`, `.modelo` e `async responder(prompt, contexto, ferramentas)`."""
        self.a, self.b, self.arbitro = a, b, arbitro

    async def julgar(self, pergunta: str, contexto: str = "") -> Veredito:
        ra, rb = await asyncio.gather(self.a.responder(pergunta, contexto), self.b.responder(pergunta, contexto))
        respostas = [ra, rb]
        custo = ra.custo + rb.custo; lat = max(ra.latencia, rb.latencia)
        vivas = [r for r in respostas if r.ok]
        if len(vivas) < 2:
            unica = vivas[0] if vivas else None
            texto = unica.texto if unica else "Nenhum dos provedores respondeu."
            falhou = [f"{r.provedor}: {r.erro or 'vazio'}" for r in respostas if not r.ok]
            return Veredito(texto, "unica", f"só {unica.provedor} respondeu ({'; '.join(falhou)})" if unica else "; ".join(falhou),
                            respostas, custo, lat)
        prompt = PROMPT_JUIZ.format(pergunta=pergunta, pa=ra.provedor, ma=ra.modelo, a=ra.texto[:6000],
                                    pb=rb.provedor, mb=rb.modelo, b=rb.texto[:6000])
        rj = await self.arbitro.responder(prompt, "Você é um juiz criterioso e direto. Responda só JSON.")
        custo += rj.custo; lat += rj.latencia
        dados = _extrair_json(rj.texto) if rj.ok else None
        if not dados or not str(dados.get("resposta", "")).strip():
            # o árbitro falhou: fica com A (Anthropic) e registra o porquê
            return Veredito(ra.texto, "A", f"árbitro não respondeu ({rj.erro or 'sem JSON'}); fiquei com {ra.provedor}", respostas, custo, lat)
        escolha = str(dados.get("escolha", "mescla")).strip().upper()
        escolha = escolha if escolha in ("A", "B") else "mescla"
        return Veredito(str(dados["resposta"]).strip(), escolha, str(dados.get("justificativa", "")).strip()[:200], respostas, custo, lat)
