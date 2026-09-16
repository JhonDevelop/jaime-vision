"""Grafo dos agentes do J.A.I.M.E — TODAS as peças reais dele num grafo só, denso como o ATSMATRIX, sem inventar.

"Agente" aqui é cada coisa que trabalha ou que ele sabe: o orquestrador, os maesters, cada família de ferramentas
e cada ferramenta, os loops contínuos, os nós do Maestri, e o cérebro inteiro do vault (notas, cada linha do diário,
conhecimento, problemas de estudo, pensamentos), além dos artistas do Spotify. Junta tudo, clusteriza por tipo e liga
por relações reais ([[links]], menções a projeto, ferramenta→família, tudo→orquestrador). Passa fácil de 500 nós reais."""
from __future__ import annotations
import re, glob, os
from pathlib import Path

MENCAO_RX = re.compile(r"\[\[([^\]|#]+)")
LINHA_DIARIO_RX = re.compile(r"^-\s+(?:\d{1,2}:\d{2}\s+)?(.+)$")

def montar(vault, jaime=None) -> dict:
    raiz = vault.root
    nos: list[dict] = []
    arestas: list[list] = []
    ids = set()
    def add(nid, nome, cluster, kb=0.3, extra=None):
        if nid in ids:
            return nid
        ids.add(nid); nos.append({"id": nid, "nome": nome[:60], "pasta": cluster, "kb": kb, **(extra or {})}); return nid
    def liga(a, b):
        if a in ids and b in ids and a != b:
            arestas.append([a, b])

    # ── hub central: o orquestrador ──
    HUB = add("agente:orquestrador", "J.A.I.M.E (orquestrador)", "núcleo", 3.0, {"nucleo": True})

    # ── vault: notas + [[links]] ──
    idx = {}
    for p in sorted(raiz.rglob("*.md")):
        if ".obsidian" in p.parts or "templates" in p.parts:
            continue
        rel = str(p.relative_to(raiz)); pasta = rel.split("/")[0]
        idx[p.stem] = rel; idx[rel] = rel
        add(rel, p.stem, pasta, round(p.stat().st_size / 1024, 1))
    for nid in list(ids):
        if nid.endswith(".md"):
            try:
                txt = (raiz / nid).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for alvo in set(MENCAO_RX.findall(txt)):
                dest = idx.get(alvo.strip()) or idx.get(alvo.strip().split("/")[-1])
                liga(nid, dest)

    projetos = [p.stem for p in (raiz / "20-Projetos").glob("*.md")] if (raiz / "20-Projetos").is_dir() else []

    # ── diário: cada linha é um evento-nó (é o grosso da densidade, tudo real) ──
    for f in sorted(glob.glob(str(raiz / "40-Diario" / "*.md"))):
        dia = Path(f).stem; dia_id = f"40-Diario/{dia}.md"
        try:
            linhas = Path(f).read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for i, l in enumerate(linhas):
            m = LINHA_DIARIO_RX.match(l.strip())
            if not m or len(m.group(1)) < 5:
                continue
            texto = m.group(1)
            nid = f"diario:{dia}:{i}"
            add(nid, texto, "diário", 0.15)
            liga(nid, dia_id)
            for proj in projetos:                      # liga a linha ao projeto que ela cita
                if proj.lower() in texto.lower():
                    liga(nid, f"20-Projetos/{proj}.md")

    # ── capacidades: maesters, servidores e ferramentas MCP, loops (os "agentes-worker") ──
    if jaime is not None:
        base = getattr(jaime, "s", None)
        raiz_repo = Path(getattr(base, "root", ".")) if base else Path(".")
    else:
        raiz_repo = raiz.parent
    for f in sorted(glob.glob(str(raiz_repo / ".claude" / "agents" / "*.md"))):
        nome = Path(f).stem
        add(f"maester:{nome}", nome, "maesters", 1.2); liga(f"maester:{nome}", HUB)
    for py in glob.glob(str(raiz_repo / "jaime" / "**" / "*.py"), recursive=True):
        try:
            src = Path(py).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        m = re.search(r'create_sdk_mcp_server\(\s*name="([a-z_]+)"', src)
        fam = m.group(1) if m else None
        if fam:
            fid = add(f"mcp:{fam}", f"@{fam}", "ferramentas", 1.0); liga(fid, HUB)
            for tnome in re.findall(r'@tool\("([a-z_]+)"', src):
                tid = add(f"tool:{fam}:{tnome}", tnome, "ferramentas", 0.3); liga(tid, fid)
    for loop in ("pensar", "estudo", "vontade", "observador", "notificações", "agenda", "telemetria", "equipe"):
        add(f"loop:{loop}", loop, "loops", 0.8); liga(f"loop:{loop}", HUB)

    # ── equipe no Maestri (nós vivos) ──
    try:
        for f in getattr(jaime.equipe, "vivos", []):
            add(f"equipe:{f.nome}", f.nome, "equipe", 1.5); liga(f"equipe:{f.nome}", HUB)
    except Exception:
        pass

    # ── música: artistas do gosto ──
    try:
        if jaime is not None and jaime.spotify.conectado:
            for a in jaime.spotify.top("artists"):
                add(f"artista:{a}", a, "música", 0.6); liga(f"artista:{a}", "loop:vontade" if "loop:vontade" in ids else HUB)
    except Exception:
        pass

    clusters = {}
    for n in nos:
        clusters[n["pasta"]] = clusters.get(n["pasta"], 0) + 1
    return {"nos": nos, "arestas": arestas, "total": len(nos), "total_arestas": len(arestas),
            "clusters": sorted(([c, q] for c, q in clusters.items()), key=lambda x: -x[1])}
