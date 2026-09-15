"""Prioridades de estudo — `90-Estudo/Prioridades.md` (fase 3, §4).

    prioridade = frequência × taxa de erro × tempo desde o último estudo

- **frequência**: quanto o assunto aparece nos pedidos do João nos últimos 7 dias (telemetria):
  `1 + pedidos relacionados (palavra-chave em comum com o título/contexto) + 0,2 × pedidos do mesmo tipo do Córtex`.
- **taxa de erro**: erros ÷ turnos daquele tipo no placar nos últimos 7 dias, suavizada (Laplace: (erros+1)/(n+2)),
  para um tipo sem histórico valer 0,5 e não zerar tudo.
- **tempo desde o último estudo**: dias desde a última tentativa (ou desde a abertura), +1, teto de 30 —
  um problema esquecido sobe sozinho; um estudado hoje vale 1.

Recalculado no "fecha o dia" (gancho do scheduler) e no "fecha a semana". `Problemas.proximo()` lê este arquivo
e escolhe o problema aberto de maior prioridade; sem arquivo, cai na heurística antiga (menos tentativas, mais antigo)."""
from __future__ import annotations
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from ..cortex.roteador import classificar
from ..estudo.problemas import ARQUIVO_PRIORIDADES, Problemas, Problema
from .uso import tokens

TENTATIVA_DATA_RX = re.compile(r"^- (\d{4}-\d{2}-\d{2})")
DIAS = 7
TETO_DIAS = 30

@dataclass
class Prioridade:
    id: str
    titulo: str
    valor: float
    frequencia: float
    taxa_erro: float
    dias_sem_estudar: int
    tipo: str
    relacionados: int

def ultimo_estudo(p: Problema) -> date:
    datas = [m.group(1) for t in p.tentativas if (m := TENTATIVA_DATA_RX.match(t))]
    if datas:
        try:
            return date.fromisoformat(max(datas))
        except ValueError:
            pass
    return p.aberto_em

def tipo_do_problema(p: Problema, tipos_relacionados: list[str]) -> str:
    """Tipo do Córtex para o problema. Título sem pista (o classificador cai em 'voz'/'redação' por falta de sinal)
    herda o tipo mais comum dos pedidos relacionados; falha de ferramenta/teste sem pedido relacionado é código."""
    tipo, conf = classificar(f"{p.titulo} {p.contexto}")
    if conf > 0.5:
        return tipo
    c = Counter(t for t in tipos_relacionados if t)
    if c:
        return c.most_common(1)[0][0]
    if p.origem in ("ferramenta_falhou", "teste_quebrou"):
        return "código"
    return tipo

def taxa_erro_por_tipo(placar_log: list[dict], desde: datetime) -> dict[str, float]:
    """(erros+1)/(n+2) por tipo nos registros do placar a partir de `desde` (ignora o próprio loop de estudo)."""
    d0 = desde.isoformat(timespec="seconds")
    n: dict[str, int] = {}; e: dict[str, int] = {}
    for l in placar_log or []:
        if l.get("t", "") < d0 or str(l.get("modelo", "")).startswith("estudo"):
            continue
        t = l.get("tipo", "?"); n[t] = n.get(t, 0) + 1
        if "erro" in l.get("resultado", ""):
            e[t] = e.get(t, 0) + 1
    return {t: (e.get(t, 0) + 1) / (n[t] + 2) for t in n}

def calcular(problemas: list[Problema], pedidos: list[dict], placar_log: list[dict], agora: datetime) -> list[Prioridade]:
    hoje = agora.date()
    taxas = taxa_erro_por_tipo(placar_log, agora.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=DIAS))
    peds_tokens = [set(tokens(p.get("texto", ""))) for p in pedidos]
    peds_tipos = [p.get("tipo") or "" for p in pedidos]
    out = []
    for p in problemas:
        chaves = set(tokens(f"{p.titulo} {p.contexto}"))
        relacionados = sum(1 for t in peds_tokens if chaves & t)
        tipo = tipo_do_problema(p, [pt for pt, t in zip(peds_tipos, peds_tokens) if chaves & t])
        mesmo_tipo = sum(1 for t in peds_tipos if t == tipo)
        freq = round(1 + relacionados + 0.2 * mesmo_tipo, 2)
        taxa = round(taxas.get(tipo, 0.5), 2)
        dias = max(0, (hoje - ultimo_estudo(p)).days)
        tempo = min(TETO_DIAS, 1 + dias)
        out.append(Prioridade(p.id, p.titulo, round(freq * taxa * tempo, 2), freq, taxa, dias, tipo, relacionados))
    return sorted(out, key=lambda x: (-x.valor, len(x.id), x.id))

def formatar(prioridades: list[Prioridade], agora: datetime, n_pedidos: int = 0) -> str:
    L = ["# Prioridades de estudo", "",
         f"> Recalculado em {agora:%d/%m/%Y %H:%M} por `jaime/telemetria/prioridades.py` no fecha-dia. "
         f"prioridade = frequência × taxa de erro × (1 + dias sem estudar, teto {TETO_DIAS}). "
         f"Frequência = 1 + pedidos relacionados + 0,2 × pedidos do mesmo tipo ({n_pedidos} pedidos nos últimos {DIAS} dias). "
         "`Problemas.proximo()` escolhe o aberto de maior prioridade.", "",
         "| id | problema | prioridade | frequência | taxa de erro | dias sem estudar | tipo | pedidos relacionados |",
         "|---|---|---|---|---|---|---|---|"]
    L += [f"| {p.id} | {p.titulo.replace('|', '/')} | {p.valor:.2f} | {p.frequencia:.2f} | {p.taxa_erro:.2f} | {p.dias_sem_estudar} | {p.tipo} | {p.relacionados} |"
          for p in prioridades] or ["| — | (nenhum problema em aberto) | 0 | 0 | 0 | 0 | — | 0 |"]
    return "\n".join(L) + "\n"

def recalcular(vault, telemetria=None, placar=None, agora: datetime | None = None) -> list[Prioridade]:
    """Lê problemas abertos, pedidos (telemetria) e placar; escreve `90-Estudo/Prioridades.md`. Devolve a lista."""
    agora = agora or datetime.now()
    abertos = Problemas(vault).abertos()
    pedidos = telemetria.pedidos(DIAS, agora.timestamp()) if telemetria is not None else []
    log = placar.dados.get("log", []) if placar is not None else []
    prios = calcular(abertos, pedidos, log, agora)
    vault.write(ARQUIVO_PRIORIDADES, formatar(prios, agora, len(pedidos)))
    return prios
