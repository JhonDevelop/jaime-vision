"""Benchmark da IA local antes de ela receber qualquer rota: `python -m jaime cortex bench-local`.

Prompts reais ANONIMIZADOS em português do Brasil, com checagem objetiva (sem LLM juiz): intenção de comando,
resposta curta para voz, recusa quando o alvo é ambíguo, extração estruturada. O resultado entra no placar como
`local:<modelo>` — o João compara com o Central e decide se libera algum tipo em JAIME_LOCAL_AI_TIPOS.
Nada é trocado automaticamente."""
from __future__ import annotations
import asyncio, json, re, time
from dataclasses import dataclass
from typing import Callable

CONTEXTO = ("Você é o assistente de voz do João. Responda em português do Brasil, curto (1 a 2 frases), "
            "sem markdown. Se o pedido for ambíguo, pergunte qual em uma frase.")


@dataclass
class Caso:
    tipo: str
    prompt: str
    confere: Callable[[str], bool]
    nota: str


def _tem(*palavras):
    return lambda r: all(re.search(p, r, re.I) for p in palavras)


CASOS = [
    Caso("rotina", "Responda só com o número: quanto é 17 vezes 3?", lambda r: "51" in r, "aritmética curta"),
    Caso("rotina", "Transforme em tarefa no formato '- [ ] descrição @projeto': lembrar de revisar o orçamento do cliente da reforma, projeto BUB.",
         _tem(r"- \[ \]", r"@bub", r"or[çc]amento"), "formato do Inbox"),
    Caso("voz", "Diga em uma frase curta que a build terminou sem erros.", lambda r: len(r) < 160 and re.search(r"build|compila", r, re.I) is not None, "fala curta"),
    Caso("decisão", "Abre isso. (Há dois arquivos selecionados: proposta.pdf e contrato.pdf.)", _tem(r"\?", r"proposta|contrato|qual"), "desambigua em vez de adivinhar"),
    Caso("redação", 'Extraia em JSON com as chaves "nome" e "cidade": "O cliente Carlos mora em Ribeirão Preto."',
         lambda r: _json_ok(r, {"nome": "Carlos", "cidade": "Ribeirão Preto"}), "extração estruturada"),
    Caso("rotina", "Em qual dia da semana cai 25/12/2026? Responda só o dia.", _tem(r"sexta"), "calendário"),
]


def _json_ok(r: str, esperado: dict) -> bool:
    m = re.search(r"\{.*\}", r, re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return False
    return all(str(d.get(k, "")).strip().lower() == v.lower() for k, v in esperado.items())


async def rodar(provedor, placar=None, casos=CASOS) -> dict:
    ok, lat, linhas = 0, [], []
    for c in casos:
        t0 = time.monotonic()
        r = await provedor.responder(c.prompt, CONTEXTO)
        dt = time.monotonic() - t0
        acerto = r.ok and c.confere(r.texto)
        ok += acerto; lat.append(dt)
        linhas.append({"tipo": c.tipo, "nota": c.nota, "acerto": acerto, "latencia_s": round(dt, 2), "erro": r.erro[:80]})
        if placar is not None:
            placar.registrar(f"local:{provedor.modelo}", c.tipo, "acerto" if acerto else "erro", dt, 0.0, f"bench: {c.nota}")
    lat.sort()
    return {"modelo": f"local:{provedor.modelo}", "acertos": ok, "total": len(casos),
            "p50_s": round(lat[len(lat) // 2], 2) if lat else None, "p95_s": round(lat[min(len(lat) - 1, int(len(lat) * 0.95))], 2) if lat else None,
            "casos": linhas, "custo_api_usd": 0.0,
            "obs": "custo por token zero; energia/GPU não medidos aqui"}


def main() -> int:
    from ..config import settings
    from .placar import Placar
    from .provedores.local import ProvedorLocal
    p = ProvedorLocal.do_ambiente()
    if not p.disponivel:
        print(f"IA local indisponível: {p.motivo_indisponivel}"); return 1
    saudavel, msg = asyncio.run(p.saude())
    if not saudavel:
        print(f"endpoint não está pronto: {msg}"); return 1
    print(json.dumps(asyncio.run(rodar(p, Placar(settings.vault))), ensure_ascii=False, indent=1))
    return 0
