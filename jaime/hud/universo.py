"""O universo do J.A.I.M.E — o mapa dos mundos que ele realmente tem, não uma ficção.

Cada "mundo" é um sistema vivo dele (mente, vontade, estudo, memória, equipe, feitoria, vigilância,
cuidado, serviço, mãos, consultoria, conexões) e cada "corpo" em órbita é uma coisa real lida agora:
um pensamento que ele teve, um impulso com o nível de hoje, um problema que ele abriu sozinho, um filho
que ele criou no Maestri, uma criação da noite, uma classe de ação que ele já ganhou o direito de fazer
sem perguntar. O `nivel` de cada mundo (0..1) é o quanto ele está aceso agora — é o que faz a órbita
girar mais rápido e o mundo brilhar mais no cockpit.

Nada aqui pode derrubar o servidor: todo mundo é montado dentro de um try, e o que falhar vira um mundo
apagado com o motivo, em vez de um erro."""
from __future__ import annotations
import re, json, time
from pathlib import Path
from datetime import datetime

BARRA_RX = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([0-9.]+)\s*\|", re.M)
PENSAMENTO_RX = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+·\s+([^·\n]+)", re.M)
PROBLEMA_RX = re.compile(r"^##\s+(P-\d+)\s+·\s+(.+?)\s+·\s+(\w+)", re.M)
FILHO_RX = re.compile(r"^##\s+([^\n]+)\n((?:- .*\n)+)", re.M)
TAREFA_RX = re.compile(r"^-\s+\[ \]\s+(.+)$", re.M)


def _ler(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _recente(quando: str, horas: float = 24.0) -> bool:
    """Aconteceu nas últimas `horas`? Usado para medir o quanto um mundo está aceso agora."""
    for f in ("%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d"):
        try:
            return (time.time() - datetime.strptime(quando.strip(), f).timestamp()) < horas * 3600
        except ValueError:
            continue
    return False


def montar(vault, jaime=None) -> dict:
    raiz = Path(vault.root)
    repo = raiz.parent
    mundos: list[dict] = []

    def mundo(mid, nome, cor, resumo, corpos, nivel, ordem, tipo="sistema"):
        mundos.append({"id": mid, "nome": nome, "cor": cor, "resumo": resumo, "tipo": tipo,
                       "corpos": corpos[:14], "total": len(corpos), "nivel": round(max(0.05, min(1.0, nivel)), 2),
                       "ordem": ordem})

    def tentar(fn, mid, nome, cor, ordem):
        try:
            fn()
        except Exception as e:
            mundo(mid, nome, cor, f"apagado: {type(e).__name__}", [], 0.05, ordem)

    # ── 1. MENTE: raciocínio próprio. Cada pensamento é uma estrela. ──────────
    def _mente():
        txt = _ler(raiz / "01-Estado/Pensamentos.md")
        ps = PENSAMENTO_RX.findall(txt)
        corpos = [{"nome": t.strip().replace("·dizer", "").strip(), "detalhe": f"{d} {h}",
                   "peso": 1.0 if _recente(f"{d} {h}", 6) else 0.5} for d, h, t in ps[:14]]
        hoje = sum(1 for d, h, _ in ps if _recente(f"{d} {h}", 24))
        mundo("mente", "Mente", "#7d5cff", f"{len(ps)} pensamentos · {hoje} nas últimas 24 h",
              corpos, hoje / 8, 1)

    # ── 2. VONTADE: os impulsos com o nível de agora. É o que ele QUER. ──────
    def _vontade():
        txt = _ler(raiz / "01-Estado/Vontades.md")
        imp = [(n, float(v)) for n, v in BARRA_RX.findall(txt) if n.lower() not in ("impulso", "---")]
        corpos = [{"nome": n, "detalhe": f"nível {v:.2f}", "peso": v} for n, v in imp]
        alto = max([v for _, v in imp], default=0.0)
        topo = max(imp, key=lambda x: x[1])[0] if imp else "—"
        mundo("vontade", "Vontade", "#ffb347", f"{len(imp)} impulsos · o mais alto agora é {topo}",
              corpos, alto, 2)

    # ── 3. ESTUDO: o que ele não entendeu e foi atrás por conta própria. ─────
    def _estudo():
        txt = _ler(raiz / "90-Estudo/Problemas.md")
        ps = PROBLEMA_RX.findall(txt)
        abertos = [p for p in ps if p[2] != "resolvido"]
        corpos = [{"nome": t[:54], "detalhe": f"{i} · {e}", "peso": 1.0 if e != "resolvido" else 0.4}
                  for i, t, e in ps[:14]]
        mundo("estudo", "Estudo", "#5fe0c0", f"{len(abertos)} em aberto de {len(ps)} que ele mesmo abriu",
              corpos, len(abertos) / 5, 3)

    # ── 4. MEMÓRIA: o vault inteiro, pasta a pasta. ──────────────────────────
    def _memoria():
        corpos, total = [], 0
        for d in sorted(raiz.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            n = len(list(d.rglob("*.md")))
            total += n
            if n:
                corpos.append({"nome": d.name, "detalhe": f"{n} notas", "peso": min(1.0, n / 30)})
        corpos.sort(key=lambda c: -c["peso"])
        mundo("memoria", "Memória", "#3a86ff", f"{total} notas em {len(corpos)} pastas", corpos, 0.6, 4)

    # ── 5. EQUIPE: os filhos que ele criou sozinho no Maestri. ───────────────
    def _equipe():
        txt = _ler(raiz / "01-Estado/Equipe.md")
        corpos, vivos = [], 0
        for nome, bloco in FILHO_RX.findall(txt):
            estado = (re.search(r"estado:\s*(\w+)", bloco) or [None, "?"])[1]
            missao = (re.search(r"missão:\s*(.+)", bloco) or [None, ""])[1]
            if estado == "vivo":
                vivos += 1
            corpos.append({"nome": nome.strip(), "detalhe": f"{estado} · {missao[:70]}",
                           "peso": 1.0 if estado == "vivo" else 0.35})
        mundo("equipe", "Equipe", "#ff5c72", f"{vivos} filhos vivos de {len(corpos)} que ele criou",
              corpos, vivos / 3, 5)

    # ── 6. FEITORIA: o que ele fez por vontade própria, sem ninguém pedir. ───
    def _feitoria():
        pasta = Path.home() / "Jaime" / "criacoes"
        corpos = []
        for f in sorted(pasta.glob("*.md"), reverse=True)[:14] if pasta.is_dir() else []:
            corpos.append({"nome": f.stem[14:].replace("-", " ") or f.stem,
                           "detalhe": f.stem[:13].replace("-", " às "), "peso": 0.8})
        try:
            vit = json.loads(_ler(pasta / "vitrine.json") or "[]")
            n_vit = len(vit) if isinstance(vit, list) else len(vit.get("itens", []))
        except Exception:
            n_vit = 0
        mundo("feitoria", "Feitoria", "#ff5cc8", f"{len(corpos)} criações da noite · {n_vit} na vitrine",
              corpos, min(1.0, len(corpos) / 4), 6)

    # ── 7. VIGILÂNCIA: o Vigia e a confiança que ele foi ganhando. ───────────
    def _vigilancia():
        txt = _ler(raiz / "01-Estado/Confianca.md")
        linhas = [l for l in txt.splitlines() if l.startswith("|") and "classe" not in l and "---" not in l]
        corpos = []
        for l in linhas:
            c = [x.strip() for x in l.strip("|").split("|")]
            if len(c) >= 3 and c[0]:
                corpos.append({"nome": c[0], "detalhe": f"{c[1]} aprovações · livre: {c[2]}",
                               "peso": 1.0 if c[2] == "sim" else 0.5})
        lote = len(getattr(getattr(jaime, "vigia", None), "lote", []) or [])
        livres = sum(1 for c in corpos if "livre: sim" in c["detalhe"])
        mundo("vigilancia", "Vigilância", "#49e6a0",
              f"{livres} ações já livres · {lote} esperando o seu confirmo", corpos, 0.4 + lote * 0.2, 7)

    # ── 8. CUIDADO: humor, momento e o vínculo com o João. ───────────────────
    def _cuidado():
        corpos = []
        for atr, rot in (("humor", "humor"), ("momento", "momento"), ("vinculo", "vínculo")):
            o = getattr(jaime, atr, None)
            v = ""
            for m in ("rotulo", "texto", "contexto", "atual"):
                f = getattr(o, m, None)
                try:
                    v = (f() if callable(f) else f) or ""
                except Exception:
                    v = ""
                if v:
                    break
            if v:
                corpos.append({"nome": rot, "detalhe": str(v)[:90], "peso": 0.9})
        txt = _ler(raiz / "01-Estado/Vinculo.md")
        mundo("cuidado", "Cuidado", "#b98cff", "como ele lê o seu momento e cuida do vínculo",
              corpos or [{"nome": "vínculo", "detalhe": txt.strip().splitlines()[0][:80] if txt else "—", "peso": .6}],
              0.5, 8)

    # ── 9. SERVIÇO: as demandas de verdade — tarefas, lembretes, rotinas. ────
    def _servico():
        tarefas = TAREFA_RX.findall(_ler(raiz / "30-Tarefas/Inbox.md"))
        lembretes = [l for l in _ler(raiz / "30-Tarefas/Lembretes.md").splitlines() if l.startswith("- ")]
        corpos = [{"nome": t[:56], "detalhe": "tarefa aberta", "peso": 0.9} for t in tarefas[:10]]
        corpos += [{"nome": l[2:58], "detalhe": "lembrete", "peso": 0.7} for l in lembretes[:4]]
        mundo("servico", "Serviço", "#ff9f6b", f"{len(tarefas)} tarefas abertas · {len(lembretes)} lembretes",
              corpos, min(1.0, len(tarefas) / 6), 9)

    # ── 10. MÃOS: as ferramentas com que ele age no mundo. ───────────────────
    def _maos():
        fams: dict[str, int] = {}
        for py in (repo / "jaime").rglob("*.py"):
            src = _ler(py)
            m = re.search(r'create_sdk_mcp_server\(\s*name="([a-z_]+)"', src)
            if m:
                fams[m.group(1)] = fams.get(m.group(1), 0) + len(re.findall(r'@tool\("([a-z_]+)"', src))
        corpos = [{"nome": f"@{k}", "detalhe": f"{v} ferramentas", "peso": min(1.0, v / 8)}
                  for k, v in sorted(fams.items(), key=lambda x: -x[1])]
        mundo("maos", "Mãos", "#38e1ff", f"{len(fams)} famílias · {sum(fams.values())} ferramentas",
              corpos, 0.7, 10)

    # ── 11. CONSULTORIA: os especialistas a quem ele pode recorrer. ──────────
    def _consultoria():
        ags = sorted((repo / ".claude" / "agents").glob("*.md"))
        maesters = [a for a in ags if a.stem.startswith("maester-")]
        skills = [d for d in (repo / ".claude" / "skills").iterdir() if d.is_dir()]
        corpos = [{"nome": a.stem, "detalhe": "maester da casa", "peso": 1.0} for a in maesters]
        corpos += [{"nome": f"acervo", "detalhe": f"{len(ags)-len(maesters)-1} especialistas", "peso": 0.6}]
        mundo("consultoria", "Consultoria", "#9aa7ff",
              f"{len(maesters)} maesters · {len(ags)-len(maesters)-1} especialistas · {len(skills)} skills",
              corpos, 0.5, 11)

    # ── 12. CONEXÕES: as janelas dele para fora desta máquina. ───────────────
    def _conexoes():
        corpos = []
        for atr, rot in (("spotify", "Spotify"), ("google", "Google"), ("notion", "Notion"),
                         ("meta", "WhatsApp"), ("casa", "Casa"), ("visao", "Visão")):
            o = getattr(jaime, atr, None)
            if o is None:
                continue
            on = bool(getattr(o, "conectado", getattr(o, "ativo", getattr(o, "ligado", False))))
            corpos.append({"nome": rot, "detalhe": "ligado" if on else "desligado", "peso": 1.0 if on else 0.25})
        ligados = sum(1 for c in corpos if c["detalhe"] == "ligado")
        mundo("conexoes", "Conexões", "#ffd08a", f"{ligados} de {len(corpos)} ligadas", corpos,
              ligados / max(1, len(corpos)), 12)

    for fn, mid, nome, cor, ordem in (
        (_mente, "mente", "Mente", "#7d5cff", 1), (_vontade, "vontade", "Vontade", "#ffb347", 2),
        (_estudo, "estudo", "Estudo", "#5fe0c0", 3), (_memoria, "memoria", "Memória", "#3a86ff", 4),
        (_equipe, "equipe", "Equipe", "#ff5c72", 5), (_feitoria, "feitoria", "Feitoria", "#ff5cc8", 6),
        (_vigilancia, "vigilancia", "Vigilância", "#49e6a0", 7), (_cuidado, "cuidado", "Cuidado", "#b98cff", 8),
        (_servico, "servico", "Serviço", "#ff9f6b", 9), (_maos, "maos", "Mãos", "#38e1ff", 10),
        (_consultoria, "consultoria", "Consultoria", "#9aa7ff", 11),
        (_conexoes, "conexoes", "Conexões", "#ffd08a", 12)):
        tentar(fn, mid, nome, cor, ordem)

    mundos.sort(key=lambda m: m["ordem"])
    nucleo = {"nome": "J.A.I.M.E", "fase": "", "modelo": getattr(jaime, "modelo_atual", "") or "",
              "acesso": bool(getattr(getattr(jaime, "acesso", None), "liberado", False))}
    try:
        est = _ler(raiz / "01-Estado/Estado.md")
        m = re.search(r"^##\s*Fase\s*\n+\s*(?:-\s*)?(.+)$", est, re.M)
        nucleo["fase"] = (m.group(1).strip() if m else "")[:70]
    except Exception:
        pass
    return {"nucleo": nucleo, "mundos": mundos,
            "total_corpos": sum(m["total"] for m in mundos), "gerado": time.time()}
