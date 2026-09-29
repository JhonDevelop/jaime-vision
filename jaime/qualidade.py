"""Qualidade medida — o gate que a autoevolução tem de passar ALÉM do pytest verde.

Teste verde prova que nada quebrou do jeito que alguém pensou em testar. Não prova que ficou melhor, nem que a
mudança não apagou o teste que a pegaria. Por isso o candidato (worktree da proposta) e o baseline (o repositório
atual) rodam o MESMO conjunto de medições, num processo separado cada um, e a proposta só fica "pronta" se:

1. nenhuma métrica piorou: gestos em replay (acerto, falsas ativações/h, latência), contrato de renderização dos
   blocos em todas as superfícies, resolução de "isso"/comandos de voz num conjunto fixo de frases reais;
2. o número de testes coletados não caiu (evolução que apaga teste para passar é reprovada);
3. não mexeu em área que só o João muda: `jaime/vigia/`, `.env`, `vault/00-Jaime/`, `CLAUDE.md`.

`python -m jaime.qualidade medir` imprime as métricas em JSON (é o que o gate chama nos dois lados).
"""
from __future__ import annotations
import json, re, subprocess, sys, time
from pathlib import Path

# a régua não pode ser mexida por quem está sendo medido: qualidade.py e o teste dele também são protegidos
PROTEGIDOS = re.compile(r"^(jaime/vigia/|\.env$|vault/00-Jaime/|CLAUDE\.md$|jaime/qualidade\.py$|tests/test_qualidade\.py$)")

# frases reais (anonimizadas) → o que deve acontecer
FRASES_REFERENCIA = [
    ("abre isso", "ok"), ("Jaime, está aí?", "sem_referencia"), ("isso mesmo", "sem_referencia"),
    ("compara esses dois", "ok"), ("fala da BUB pra mim", "sem_referencia"), ("vira à esquerda na próxima", "sem_referencia"),
    ("resume isso pra mim", "ok"), ("abre a da direita", "ok"),
]
FRASES_BLOCOS = [
    ("abre o bloco da máquina", "Máquina aberto."), ("fecha todos os blocos", "Fechei 1 bloco."),
    ("abre finanças", None), ("abre um bloco comparando a BUB com a Oldsen", None), ("que horas são?", None),
]


def medir() -> dict:
    out: dict = {"quando": time.strftime("%Y-%m-%d %H:%M:%S")}
    # 1. gestos em replay (fase 9 do espacial)
    try:
        from .spatial.experimentos import PADRAO, medir as medir_gestos
        m = medir_gestos(PADRAO, repeticoes=6)
        out["gestos"] = {"acerto": m.accuracy, "falsos_h": m.false_activations_per_hour, "p95_ms": round(m.p95_ms, 4), "n": m.sample_count}
    except Exception as e:
        out["gestos"] = {"erro": f"{type(e).__name__}: {e}"}
    # 2. contrato dos blocos
    try:
        from .blocos.modelo import TIPOS, validar
        from .blocos.modelos import EMBUTIDOS, contrato
        exemplos = {"texto": {"texto": "a"}, "lista": {"itens": ["a"]}, "tabela": {"colunas": ["a"], "linhas": [["1"]]},
                    "metricas": {"itens": [{"rotulo": "a", "valor": "1"}]}, "grafico": {"series": [{"nome": "s", "pontos": [[1, 2]]}]},
                    "grafo": {"nos": [{"id": "a"}, {"id": "b"}], "arestas": [{"de": "a", "para": "b"}]}, "status": {"texto": "ok"},
                    "acoes": {"botoes": [{"rotulo": "a", "intencao": "b"}]}, "imagem": {"src": "/hud/x"},
                    "html": {"html": "<b>a</b>", "alternativo": "a"}, "progresso": {"valor": 0.5}}
        casos = [validar({"tipo": t, "titulo": t, "conteudo": exemplos.get(t, {})}) for t in TIPOS]
        casos += [validar({**d, "conteudo": exemplos.get(d["tipo"], {})}) for d in EMBUTIDOS.values()]
        ok = sum(1 for b in casos if not contrato(b))
        out["blocos"] = {"contrato_ok": ok, "total": len(casos)}
    except Exception as e:
        out["blocos"] = {"erro": f"{type(e).__name__}: {e}"}
    # 3. voz: "isso" e comandos de bloco
    try:
        from .spatial.core import SpatialCore, SpatialObject, Vec3
        from .spatial.referencias import Resolvedor
        c = SpatialCore(relogio=lambda: 100.0)
        for i, n in enumerate(("BUB", "SeventyOne", "GearHead")):
            c.add(SpatialObject(f"p:{n}", "projeto", Vec3(0.2 + 0.2 * i, 0.3, 0), label=n))
        c.relogio = lambda: 90.0; c.select("joao", "p:BUB", 0.97)
        c.relogio = lambda: 95.0; c.select("joao", "p:GearHead", 0.97)
        r = Resolvedor(c, relogio=lambda: 100.0)
        acertos = sum(1 for f, esperado in FRASES_REFERENCIA if r.resolver(f).status == esperado)
        from .blocos.fontes import padrao
        from .blocos.gerenciador import Gerenciador
        from .blocos.modelos import Modelos
        from .blocos.voz import comando
        g = Gerenciador(padrao(None)); m = Modelos(None, g.fontes)
        acertos_b = sum(1 for f, esperado in FRASES_BLOCOS if comando(f, g, m) == esperado)
        out["voz"] = {"acerto": round((acertos + acertos_b) / (len(FRASES_REFERENCIA) + len(FRASES_BLOCOS)), 4)}
    except Exception as e:
        out["voz"] = {"erro": f"{type(e).__name__}: {e}"}
    return out


def _python(repo: Path) -> str:
    venv = Path(repo) / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else sys.executable


def medir_em(pasta: Path, python: str, regua: Path | None = None) -> dict:
    """Mede o código de `pasta` com a RÉGUA (este arquivo) do baseline: o candidato não consegue trocar o medidor."""
    regua = Path(regua or __file__).resolve()
    codigo = ("import json, sys; sys.path.insert(0, '.'); import jaime; "
              f"g = {{'__name__': 'jaime._regua', '__package__': 'jaime'}}; exec(compile(open({str(regua)!r}).read(), 'regua', 'exec'), g); "
              "print(json.dumps(g['medir'](), ensure_ascii=False))")
    r = subprocess.run([python, "-c", codigo], cwd=pasta, capture_output=True, text=True, timeout=600)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"erro": (r.stderr or r.stdout)[-300:]}


def exportar(repo: Path, ref: str, destino: Path) -> Path:
    """Cópia limpa de `ref` (sem .git, sem arquivos soltos) — baseline de verdade, não a pasta de trabalho."""
    destino.mkdir(parents=True, exist_ok=True)
    arq = subprocess.run(["git", "archive", "--format=tar", ref], cwd=repo, capture_output=True, timeout=300, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(destino)], input=arq, check=True, timeout=300)
    return destino


def testes_coletados(pasta: Path, python: str) -> int:
    r = subprocess.run([python, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"], cwd=pasta,
                       capture_output=True, text=True, timeout=600)
    m = re.search(r"(\d+) tests? collected", r.stdout) or re.search(r"(\d+) tests? coletad", r.stdout)
    return int(m.group(1)) if m else 0


def arquivos_mudados(pasta: Path, base: str = "main") -> list[str]:
    r = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"], cwd=pasta, capture_output=True, text=True, timeout=60)
    r2 = subprocess.run(["git", "status", "--porcelain"], cwd=pasta, capture_output=True, text=True, timeout=60)
    nomes = set(r.stdout.split()) | {l[3:].strip() for l in r2.stdout.splitlines() if len(l) > 3}
    lixo = re.compile(r"(__pycache__|\.pyc$|\.pytest_cache)")
    return sorted(n for n in nomes if n and not lixo.search(n))


def comparar(base: dict, cand: dict, testes_base: int, testes_cand: int, mudados: list[str]) -> tuple[bool, list[str]]:
    problemas = []
    protegidos = [m for m in mudados if PROTEGIDOS.search(m)]
    if protegidos:
        problemas.append(f"mexeu em área que só o João muda: {', '.join(protegidos)}")
    if testes_cand < testes_base:
        problemas.append(f"testes coletados caíram de {testes_base} para {testes_cand}")
    for area in ("gestos", "blocos", "voz"):
        if "erro" in cand.get(area, {"erro": "ausente"}) and "erro" not in base.get(area, {"erro": "x"}):
            problemas.append(f"{area}: a medição quebrou no candidato ({cand.get(area, {}).get('erro', 'ausente')[:100]})")
    g0, g1 = base.get("gestos", {}), cand.get("gestos", {})
    if "acerto" in g0 and "acerto" in g1:
        if g1["acerto"] < g0["acerto"]:
            problemas.append(f"gestos: acerto caiu {g0['acerto']:.2f} → {g1['acerto']:.2f}")
        if g1["falsos_h"] > g0["falsos_h"]:
            problemas.append(f"gestos: falsas ativações/h subiram {g0['falsos_h']:.0f} → {g1['falsos_h']:.0f}")
        if g1["p95_ms"] > max(g0["p95_ms"] * 2, g0["p95_ms"] + 0.05):
            problemas.append(f"gestos: p95 por frame {g0['p95_ms']:.3f} → {g1['p95_ms']:.3f} ms")
    b0, b1 = base.get("blocos", {}), cand.get("blocos", {})
    if "contrato_ok" in b0 and "contrato_ok" in b1 and b1["contrato_ok"] - b1["total"] < b0["contrato_ok"] - b0["total"]:
        problemas.append(f"blocos: {b1['total'] - b1['contrato_ok']} bloco(s) falhando no contrato de renderização")
    v0, v1 = base.get("voz", {}), cand.get("voz", {})
    if "acerto" in v0 and "acerto" in v1 and v1["acerto"] < v0["acerto"]:
        problemas.append(f"voz: acerto nas frases de referência caiu {v0['acerto']:.2f} → {v1['acerto']:.2f}")
    return not problemas, problemas


def gate_padrao(repo: Path, base: str = "main"):
    """Gate para `Evolucao(gate=…)`. Baseline = cópia limpa do `main` (de onde o worktree da proposta nasce), em cache
    por commit; candidato = o worktree. Os dois medidos pela régua do repositório atual."""
    import tempfile
    repo = Path(repo)
    cache: dict = {}

    def gate(pasta, proposta) -> tuple[bool, str]:
        py = _python(repo)
        ref = subprocess.run(["git", "rev-parse", base], cwd=repo, capture_output=True, text=True).stdout.strip()
        if ref not in cache:
            with tempfile.TemporaryDirectory(prefix="jaime-baseline-") as tmp:
                limpo = exportar(repo, ref, Path(tmp))
                cache[ref] = (medir_em(limpo, py), testes_coletados(limpo, py))
        b, tb = cache[ref]
        cand, tc = medir_em(Path(pasta), py), testes_coletados(Path(pasta), py)
        ok, problemas = comparar(b, cand, tb, tc, arquivos_mudados(Path(pasta), base))
        linhas = [f"baseline ({base} {ref[:7]}): {json.dumps({k: v for k, v in b.items() if k != 'quando'}, ensure_ascii=False)}",
                  f"candidato: {json.dumps({k: v for k, v in cand.items() if k != 'quando'}, ensure_ascii=False)}",
                  f"testes coletados: {tb} → {tc}"]
        linhas += [f"REPROVADO: {p}" for p in problemas] or ["aprovado: nada piorou"]
        return ok, "\n".join(linhas)
    return gate


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "medir":
        print(json.dumps(medir(), ensure_ascii=False))
    else:
        print(__doc__)
