"""fase 3 — HUD: fotografia dos subsistemas do Jaime para o painel "Sistemas" (docs/HUD-VIVO.md, camada 3).

Tudo que não tem evento contínuo no bus e o HUD precisa mostrar de uma vez: lote do Vigia esperando "sim", fila de
demandas, filhos no Maestri, estudo, janela da rotina, orçamento do dia, vontades, humor e o que depende do João.
Só leitura, e defensiva: qualquer módulo ausente vira `None`/lista vazia — o HUD nunca quebra por falta de um pedaço."""
from __future__ import annotations
import time
from datetime import datetime

def _tenta(fn, padrao=None):
    try:
        return fn()
    except Exception:
        return padrao

def _vigia(jaime) -> dict:
    v = getattr(jaime, "vigia", None)
    lote = [{"descricao": getattr(a, "descricao", str(a)), "classe": getattr(a, "classe", "")} for a in (getattr(v, "lote", None) or [])]
    armado = float(getattr(v, "_armado_ate", 0.0) or 0.0) > time.time()
    return {"lote": lote, "armado": armado, "executando_lote": bool(getattr(v, "lote_executado", False))}

def _fila(ouvido) -> dict:
    f = getattr(ouvido, "fila", None)
    if f is None:
        return {"itens": [], "atual": None, "aguardando": None}
    return {"itens": _tenta(f.dados, []), "atual": getattr(getattr(f, "atual", None), "id", None),
            "aguardando": getattr(getattr(f, "aguardando", None), "id", None),
            "pergunta": _tenta(lambda: f.plano_de_retomada(f.aguardando)[1] if f.aguardando else "", "")}

def _equipe(jaime) -> list[dict]:
    eq = getattr(jaime, "equipe", None)
    filhos = getattr(eq, "filhos", None) or {}
    return [{"nome": f.nome, "tipo": getattr(f, "tipo", ""), "estado": getattr(f, "estado", ""), "preset": getattr(f, "preset", ""),
             "tarefas": getattr(f, "tarefas", 0), "ultimo": (getattr(f, "ultimo_relatorio", "") or "")[:120]} for f in filhos.values()]

def _estudo(jaime) -> dict:
    e = getattr(jaime, "estudo", None)
    if e is None:
        return {"abertos": 0, "ocupado": False, "pode": False, "motivo": "sem cérebro de estudo"}
    abertos = _tenta(lambda: e.problemas.abertos(), [])
    pode, motivo = _tenta(lambda: e.pode_estudar(), (False, ""))
    return {"abertos": len(abertos), "ocupado": bool(getattr(e, "ocupado", False)), "pode": bool(pode), "motivo": motivo,
            "ultimo_ciclo": float(getattr(e, "ultimo_ciclo", 0.0) or 0.0),
            "titulos": [getattr(p, "titulo", "")[:60] for p in abertos[:3]]}

def _rotina(state, agora: datetime | None = None) -> dict:
    agora = agora or datetime.now()
    atencao = getattr(state, "atencao", None)
    ultima = float(getattr(atencao, "ultima_fala", 0.0) or 0.0)
    try:
        from ..vontade.mente import janela
        jan = janela(agora, ultima)
    except Exception:
        h = agora.hour
        jan = "noite" if (h >= 21 or h < 6) else ("atento" if 8 <= h < 18 and ultima and agora.timestamp() - ultima < 900 else "ocioso")
    return {"janela": jan, "ultima_fala": ultima,
            "min_sem_fala": round((agora.timestamp() - ultima) / 60) if ultima else None}

def _orcamento(state) -> dict | None:
    o = getattr(state, "orcamento", None)
    if o is None:
        return None
    est = _tenta(o.estado)
    if not est:
        return None
    est["ativo"] = bool(getattr(o, "ativo", False))
    est["resumo"] = _tenta(o.resumo, "")
    return est

def _vontades(state) -> dict | None:
    v = getattr(state, "vontade", None)
    if v is None:
        return None
    dados = _tenta(lambda: v.impulsos.dados(), {}) or {}
    ultima = getattr(getattr(v, "mente", None), "ultima", None)
    dados["escolha"] = _tenta(ultima.dados) if ultima is not None else None
    return dados

def _pendentes(jaime, ouvido, fila: dict, vigia: dict) -> list[dict]:
    """O que só anda com uma palavra do João. Cada item: {tipo, texto, resposta}."""
    p: list[dict] = []
    if vigia["lote"]:
        p.append({"tipo": "vigia", "texto": "Você deseja que eu " + (", ".join(a["descricao"] for a in vigia["lote"]))[:160] + "?", "resposta": "sim / não"})
    if fila.get("aguardando"):
        p.append({"tipo": "fila", "texto": fila.get("pergunta") or "Continuo o que eu dizia?", "resposta": "sim / deixa"})
    m = getattr(getattr(jaime, "autonomo", None), "missao", None)
    if m is not None and getattr(m, "estado", "") == "pausada":
        p.append({"tipo": "autonomo", "texto": f"objetivo pausado pelo Vigia: {getattr(m, 'objetivo', '')[:80]}", "resposta": "confirmo"})
    for prop in _tenta(lambda: jaime.evolucao.propostas(), []) or []:
        if getattr(prop, "estado", "") == "pronta":
            p.append({"tipo": "evolucao", "texto": f"melhoria pronta: {getattr(prop, 'titulo', '')[:80]}", "resposta": "confirmo"})
    if getattr(jaime, "aguardando_nome", False):
        p.append({"tipo": "identidade", "texto": f"nome proposto: {getattr(getattr(jaime, 'identidade', None), 'nome', '')}", "resposta": "confirmo"})
    return p

def montar(jaime, ouvido=None, state=None, settings=None, agora: datetime | None = None) -> dict:
    vigia = _vigia(jaime)
    fila = _fila(ouvido)
    lat = getattr(ouvido, "latencias", None)
    return {
        "t": time.time(),
        "vigia": vigia,
        "fila": fila,
        "equipe": _equipe(jaime),
        "estudo": _estudo(jaime),
        "rotina": _rotina(state, agora),
        "orcamento": _orcamento(state),
        "vontades": _vontades(state),
        "humor": _tenta(lambda: jaime.humor.dados()),
        "ouvido": {"modo": getattr(settings, "voz_modo", None), "ativo": bool(getattr(ouvido, "ativo", False)),
                   "ocupado": bool(getattr(ouvido, "ocupado", False)), "erro": getattr(ouvido, "erro", None),
                   "barge_in": getattr(ouvido, "barge_in", None), "antecipador": getattr(ouvido, "antecipador", None) is not None,
                   "stt": getattr(getattr(ouvido, "fluxo", None), "nome", None),
                   "latencia_mediana_ms": (round(v * 1000) if (v := _tenta(lambda: lat.mediana())) is not None else None)},
        "pendentes": _pendentes(jaime, ouvido, fila, vigia),
        "proximos": _tenta(lambda: jaime.estado.secao("Próximos passos"), "") or "",
    }
