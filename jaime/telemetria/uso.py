"""Uso — telemetria local do que o João faz e do que pede ao Jaime.

O que registra (tudo em `vault/.jaime/telemetria.json`, fora do git, nunca no Notion):
1. **Janela ativa** a cada 30 s: app + título. Vem do Observador (`ops/observador.py`), que já sonda o app frontal a
   cada 4 s — aqui só se lê `observador.atual`, sem gastar outro `osascript`. Agrega por hora (`horas["AAAA-MM-DDTHH"][app] = s`)
   e guarda os títulos mais vistos por app.
2. **Pedidos ao Jaime**: cada `conversa` no bus vira um pedido; o evento `cortex` que vem logo depois dá o tipo
   (código · pesquisa · redação · decisão · imagem · voz · rotina).
3. **Temas das perguntas**: agrupamento simples por palavras-chave (TF-IDF caseiro). Se `sentence-transformers` já estiver
   instalado, usa embeddings; nunca instala nada.
4. **Onde o Jaime mais erra**: vem do placar (`cortex/placar.py`) — erros por tipo nos últimos 7 dias.

Interruptores: `JAIME_TELEMETRIA=1|0` e `JAIME_TELEMETRIA_EXCLUIR=1Password,Banco,...` (app que contenha um desses nomes
não é registrado). `resumo_semanal()` escreve `01-Estado/Uso.md`; o scheduler chama isso no "fecha a semana"."""
from __future__ import annotations
import asyncio, json, math, os, re, time, unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from ..hud.events import bus

ARQUIVO_REL = ".jaime/telemetria.json"          # `.jaime/` já está no .gitignore (runtime do Jaime)
USO_REL = "01-Estado/Uso.md"
INTERVALO_S = 30
GUARDAR_DIAS = 35
MAX_PEDIDOS = 3000
MAX_TITULOS_POR_APP = 25
DIAS_RESUMO = 7

def config_env() -> tuple[bool, tuple[str, ...]]:
    """(ligada, apps excluídos) a partir do .env — sem passar pelo Settings para não mexer em config.py."""
    ligada = os.environ.get("JAIME_TELEMETRIA", "1").strip().lower() not in ("0", "off", "false", "nao", "não")
    excluir = tuple(x.strip() for x in os.environ.get("JAIME_TELEMETRIA_EXCLUIR", "").split(",") if x.strip())
    return ligada, excluir

# ── palavras e temas ─────────────────────────────────────────────────────────
STOPWORDS = set("""a o e é de da do das dos em no na nos nas um uma uns umas para pra pro por com sem sob sobre que qual quais
quem quando onde como porque porquê por que se não nao sim ao aos à às até entre isso isto aquilo esse essa este esta aquele aquela
esses essas estes estas ele ela eles elas eu tu você voce vocês nós nos me te se lhe meu minha meus minhas seu sua seus suas
nosso nossa dele dela deles delas já ja ainda também tambem só so mais menos muito muita muitos muitas pouco pouca bem mal
tá ta está esta estão estao ser estar tem têm ter há ha havia foi era são sao vai vou vamos faz fazer feito fiz fez
pode poder posso quer quero queria queira deve devo aqui ali lá la agora hoje ontem amanhã amanha depois antes sempre nunca
então entao mas porém porem ou nem tipo coisa coisas algo tudo nada cada outro outra outros outras mesmo mesma jaime
me dá da ver vê olha olhe faça faca abre abra manda mande cria crie coloca bota deixa deixe favor por favor obrigado valeu
oi olá ola tá bom beleza ok certo tal aí ai né ne qualquer isso aí uma vez dois duas três tres esse aí""".split())
TOKEN_RX = re.compile(r"[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ0-9\-]{2,}")

def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def _raiz(p: str) -> str:
    """Normalização mínima para plural/gênero não separar temas: 'funções'→'função', 'testes'→'teste', 'erros'→'erro'."""
    if p.endswith("ões"): return p[:-3] + "ão"
    if p.endswith("ães"): return p[:-3] + "ão"
    if p.endswith("res") and len(p) > 5: return p[:-2]
    if p.endswith("s") and len(p) > 4 and not p.endswith("ss"): return p[:-1]
    return p

def tokens(texto: str) -> list[str]:
    out = []
    for t in TOKEN_RX.findall((texto or "").lower()):
        if t in STOPWORDS or _sem_acento(t) in STOPWORDS or t.isdigit():
            continue
        out.append(_raiz(t))
    return out

def palavras_chave(textos: list[str], n: int = 4) -> list[list[str]]:
    """Top-n palavras de cada texto. Ao contrário do TF-IDF clássico, palavra que se repete ENTRE pedidos pesa mais —
    é a repetição que faz um tema ("rls", "supabase"); só a que aparece em mais da metade dos pedidos perde peso,
    porque não separa nada. Determinístico (empate → ordem alfabética)."""
    toks = [tokens(t) for t in textos]
    df: Counter = Counter()
    for ts in toks:
        df.update(set(ts))
    N = len(toks)
    out = []
    for ts in toks:
        tf = Counter(ts)
        peso = {w: (1 + math.log(c)) * ((1 + math.log(df[w])) if df[w] <= max(1, N / 2) else 0.5) for w, c in tf.items()}
        out.append([w for w, _ in sorted(peso.items(), key=lambda kv: (-kv[1], kv[0]))[:n]])
    return out

@dataclass
class Tema:
    rotulo: str
    n: int
    exemplos: list[str] = field(default_factory=list)
    palavras: list[str] = field(default_factory=list)

def _agrupar_por_palavras(textos: list[str]) -> list[Tema]:
    kws = palavras_chave(textos)
    grupos: list[dict] = []           # {"palavras": Counter, "itens": [i]}
    for i, kw in enumerate(kws):
        if not kw:
            continue
        precisa = max(1, (len(kw) + 1) // 2)
        melhor, melhor_n = None, 0
        for g in grupos:
            n = sum(1 for w in kw if w in g["palavras"])
            if n >= precisa and n > melhor_n:
                melhor, melhor_n = g, n
        if melhor is None:
            melhor = {"palavras": Counter(), "itens": []}; grupos.append(melhor)
        melhor["palavras"].update(kw); melhor["itens"].append(i)
    temas = []
    for g in grupos:
        top = [w for w, _ in g["palavras"].most_common(2)]
        temas.append(Tema(" · ".join(top), len(g["itens"]), [textos[i][:80] for i in g["itens"][:3]], [w for w, _ in g["palavras"].most_common(6)]))
    return sorted(temas, key=lambda t: (-t.n, t.rotulo))

def _agrupar_por_embeddings(textos: list[str]) -> list[Tema] | None:
    """Só se sentence-transformers JÁ estiver instalado (nunca instala). None = indisponível."""
    try:
        from sentence_transformers import SentenceTransformer   # type: ignore
        import numpy as np
    except Exception:
        return None
    try:
        modelo = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        emb = modelo.encode(textos, normalize_embeddings=True)
    except Exception:
        return None
    grupos: list[dict] = []
    for i, v in enumerate(emb):
        melhor, melhor_s = None, 0.6
        for g in grupos:
            s = float(np.dot(v, g["centro"]) / (np.linalg.norm(g["centro"]) + 1e-9))
            if s > melhor_s:
                melhor, melhor_s = g, s
        if melhor is None:
            grupos.append({"centro": np.array(v, dtype=float), "itens": [i]})
        else:
            melhor["itens"].append(i); melhor["centro"] = melhor["centro"] + v
    kws = palavras_chave(textos)
    temas = []
    for g in grupos:
        c: Counter = Counter()
        for i in g["itens"]:
            c.update(kws[i])
        top = [w for w, _ in c.most_common(2)] or ["(sem palavras)"]
        temas.append(Tema(" · ".join(top), len(g["itens"]), [textos[i][:80] for i in g["itens"][:3]], [w for w, _ in c.most_common(6)]))
    return sorted(temas, key=lambda t: (-t.n, t.rotulo))

def agrupar_temas(textos: list[str], embeddings: bool = True) -> list[Tema]:
    textos = [t for t in textos if t and t.strip()]
    if not textos:
        return []
    if embeddings:
        r = _agrupar_por_embeddings(textos)
        if r is not None:
            return r
    return _agrupar_por_palavras(textos)

# ── a telemetria ─────────────────────────────────────────────────────────────
def _hora_chave(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%dT%H")

def _fmt_h(segundos: float) -> str:
    h, m = divmod(int(segundos // 60), 60)
    return f"{h}h{m:02d}" if h else f"{m} min"

class Telemetria:
    def __init__(self, vault, ligada: bool | None = None, excluir: tuple[str, ...] | None = None, placar=None,
                 agora=time.time, intervalo_s: int = INTERVALO_S):
        """vault: objeto Vault (usa .root) ou Path. agora: relógio injetável (segundos epoch)."""
        self.root = Path(getattr(vault, "root", vault))
        env_ligada, env_excluir = config_env()
        self.ligada = env_ligada if ligada is None else bool(ligada)
        self.excluir = tuple(x.lower() for x in (env_excluir if excluir is None else excluir))
        self.placar = placar
        self.agora, self.intervalo_s = agora, intervalo_s
        self.dados: dict = {"horas": {}, "titulos": {}, "pedidos": []}
        self._carregar()

    # ── persistência ──────────────────────────────────
    def _arquivo(self) -> Path:
        return self.root / ARQUIVO_REL

    def _carregar(self) -> None:
        p = self._arquivo()
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                for k in ("horas", "titulos", "pedidos"):
                    self.dados[k] = d.get(k, self.dados[k])
            except (json.JSONDecodeError, OSError):
                pass

    def salvar(self) -> None:
        self._podar()
        p = self._arquivo()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.dados, ensure_ascii=False), encoding="utf-8")

    def _podar(self) -> None:
        limite = (datetime.fromtimestamp(self.agora()) - timedelta(days=GUARDAR_DIAS)).strftime("%Y-%m-%dT%H")
        self.dados["horas"] = {h: v for h, v in self.dados["horas"].items() if h >= limite}
        self.dados["pedidos"] = self.dados["pedidos"][-MAX_PEDIDOS:]
        for app, ts in self.dados["titulos"].items():
            if len(ts) > MAX_TITULOS_POR_APP:
                self.dados["titulos"][app] = dict(sorted(ts.items(), key=lambda kv: -kv[1])[:MAX_TITULOS_POR_APP])

    # ── janela ativa ──────────────────────────────────
    def excluido(self, app: str) -> bool:
        a = (app or "").lower()
        return any(x in a for x in self.excluir)

    def amostrar(self, app: str, titulo: str = "", agora: float | None = None, segundos: int | None = None) -> bool:
        """Uma amostra da janela ativa. Devolve True se contou."""
        if not self.ligada or not app or self.excluido(app):
            return False
        ts = self.agora() if agora is None else agora
        s = self.intervalo_s if segundos is None else segundos
        h = self.dados["horas"].setdefault(_hora_chave(ts), {})
        h[app] = h.get(app, 0) + s
        if titulo:
            t = self.dados["titulos"].setdefault(app, {})
            t[titulo[:80]] = t.get(titulo[:80], 0) + s
        return True

    # ── pedidos ───────────────────────────────────────
    def registrar_pedido(self, texto: str, tipo: str = "", canal: str = "", agora: float | None = None) -> None:
        if not self.ligada or not (texto or "").strip() or texto.strip() == "•••":
            return
        ts = self.agora() if agora is None else agora
        self.dados["pedidos"].append({"t": datetime.fromtimestamp(ts).isoformat(timespec="seconds"), "tipo": tipo,
                                      "canal": canal, "texto": texto.strip()[:160]})

    def classificar_ultimo(self, tipo: str) -> None:
        """O evento `cortex` chega logo depois do `conversa`: dá o tipo ao último pedido ainda sem tipo."""
        if self.dados["pedidos"] and not self.dados["pedidos"][-1].get("tipo"):
            self.dados["pedidos"][-1]["tipo"] = tipo

    # ── leituras agregadas ────────────────────────────
    def _desde(self, dias: int, agora: float | None = None) -> datetime:
        return datetime.fromtimestamp(self.agora() if agora is None else agora) - timedelta(days=dias)

    def uso_apps(self, dias: int = DIAS_RESUMO, agora: float | None = None) -> list[tuple[str, int]]:
        """[(app, segundos)] no período, do mais usado ao menos."""
        d0 = self._desde(dias, agora).strftime("%Y-%m-%dT%H")
        c: Counter = Counter()
        for h, apps in self.dados["horas"].items():
            if h >= d0:
                c.update(apps)
        return c.most_common()

    def uso_por_hora(self, dias: int = DIAS_RESUMO, agora: float | None = None) -> dict[int, int]:
        """segundos com janela ativa por hora do dia (0–23)."""
        d0 = self._desde(dias, agora).strftime("%Y-%m-%dT%H")
        out: dict[int, int] = defaultdict(int)
        for h, apps in self.dados["horas"].items():
            if h >= d0:
                out[int(h[-2:])] += sum(apps.values())
        return dict(out)

    def titulos(self, app: str, n: int = 3) -> list[tuple[str, int]]:
        return sorted(self.dados["titulos"].get(app, {}).items(), key=lambda kv: -kv[1])[:n]

    def pedidos(self, dias: int = DIAS_RESUMO, agora: float | None = None) -> list[dict]:
        d0 = self._desde(dias, agora).isoformat(timespec="seconds")
        return [p for p in self.dados["pedidos"] if p["t"] >= d0]

    def tipos(self, dias: int = DIAS_RESUMO, agora: float | None = None) -> Counter:
        return Counter(p.get("tipo") or "?" for p in self.pedidos(dias, agora))

    def temas(self, dias: int = DIAS_RESUMO, agora: float | None = None, embeddings: bool = True) -> list[Tema]:
        return agrupar_temas([p["texto"] for p in self.pedidos(dias, agora)], embeddings)

    def erros(self, dias: int = DIAS_RESUMO, agora: float | None = None) -> dict[str, dict]:
        """Do placar: por tipo, {n, erros, taxa, notas} nos últimos `dias` (o loop de estudo fica de fora)."""
        out: dict[str, dict] = {}
        if not self.placar:
            return out
        d0 = self._desde(dias, agora).isoformat(timespec="seconds")
        for l in self.placar.dados.get("log", []):
            if l.get("t", "") < d0 or str(l.get("modelo", "")).startswith("estudo"):
                continue
            c = out.setdefault(l["tipo"], {"n": 0, "erros": 0, "taxa": 0.0, "notas": []})
            c["n"] += 1
            if "erro" in l.get("resultado", ""):
                c["erros"] += 1
                if l.get("nota"):
                    c["notas"].append(l["nota"][:60])
        for c in out.values():
            c["taxa"] = round(c["erros"] / c["n"], 2) if c["n"] else 0.0
        return out

    # ── resumo semanal ────────────────────────────────
    def resumo_semanal(self, agora: float | None = None, dias: int = DIAS_RESUMO) -> str:
        ts = self.agora() if agora is None else agora
        fim = datetime.fromtimestamp(ts); ini = fim - timedelta(days=dias)
        L = ["# Uso — o que o João mais faz e onde eu mais erro", "",
             f"> {ini:%d/%m} a {fim:%d/%m/%Y}, gerado por `jaime/telemetria/uso.py` em {fim:%d/%m %H:%M}. "
             f"Só local — nunca vai ao Notion. Desligar: `JAIME_TELEMETRIA=0`; excluir apps: `JAIME_TELEMETRIA_EXCLUIR`.", ""]
        if not self.ligada:
            L += ["**Telemetria desligada** (`JAIME_TELEMETRIA=0`). Nada foi registrado nesta semana.", ""]
        # o que mais usa
        apps = self.uso_apps(dias, ts)
        total = sum(s for _, s in apps)
        L += ["## O que o João mais usa", ""]
        if apps:
            L += [f"Tempo com janela ativa registrado: **{_fmt_h(total)}**.", "", "| app | tempo | % | títulos mais vistos |", "|---|---|---|---|"]
            for app, s in apps[:8]:
                tit = "; ".join(t for t, _ in self.titulos(app)) or "—"
                L.append(f"| {app} | {_fmt_h(s)} | {100 * s / total:.0f}% | {tit[:90]} |")
            por_hora = self.uso_por_hora(dias, ts)
            if por_hora:
                pico = sorted(por_hora.items(), key=lambda kv: -kv[1])[:3]
                L += ["", "Horas de pico: " + ", ".join(f"{h:02d}h ({_fmt_h(s)})" for h, s in sorted(pico))]
        else:
            L.append("Nada registrado (sem amostras de janela ativa).")
        # o que mais pede
        peds = self.pedidos(dias, ts); tipos = self.tipos(dias, ts)
        L += ["", "## O que mais pede (tipos do Córtex)", ""]
        if peds:
            L += [f"{len(peds)} pedido(s) na semana.", "", "| tipo | pedidos | % |", "|---|---|---|"]
            L += [f"| {t} | {n} | {100 * n / len(peds):.0f}% |" for t, n in tipos.most_common()]
            canais = Counter(p.get("canal") or "?" for p in peds)
            L += ["", "Por canal: " + ", ".join(f"{c} {n}" for c, n in canais.most_common())]
        else:
            L.append("Nenhum pedido registrado.")
        # o que mais pergunta
        L += ["", "## O que mais pergunta (temas)", ""]
        temas = self.temas(dias, ts)
        if temas:
            for t in temas[:8]:
                L.append(f"- **{t.rotulo}** — {t.n}× · ex.: " + " | ".join(f"“{e}”" for e in t.exemplos[:2]))
        else:
            L.append("Sem temas ainda.")
        # onde eu mais erro
        L += ["", "## Onde eu mais erro (placar)", ""]
        erros = self.erros(dias, ts)
        piores = sorted(erros.items(), key=lambda kv: (-kv[1]["erros"], -kv[1]["taxa"]))
        if any(c["erros"] for _, c in piores):
            L += ["| tipo | turnos | erros | taxa de erro | exemplos |", "|---|---|---|---|---|"]
            for tipo, c in piores:
                if c["erros"]:
                    L.append(f"| {tipo} | {c['n']} | {c['erros']} | {c['taxa']:.0%} | {'; '.join(c['notas'][:2])[:90]} |")
        else:
            L.append("Nenhum erro registrado no placar nesta semana.")
        # síntese para o estudo
        L += ["", "## Para o estudo desta semana", ""]
        mais_app = apps[0][0] if apps else "—"
        mais_tipo = tipos.most_common(1)[0][0] if tipos else "—"
        pior = next((t for t, c in piores if c["erros"]), "—")
        L.append(f"Mais tempo em **{mais_app}**; mais pede **{mais_tipo}**; onde mais erro: **{pior}**. "
                 f"As prioridades ficam em `90-Estudo/Prioridades.md` (frequência × taxa de erro × tempo sem estudar).")
        return "\n".join(L) + "\n"

    def escrever_uso(self, agora: float | None = None) -> str:
        p = self.root / USO_REL
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.resumo_semanal(agora), encoding="utf-8")
        return USO_REL

    # ── laços assíncronos (servidor) ──────────────────
    async def rodar(self, observador=None) -> None:
        """A cada 30 s, amostra a janela ativa (do Observador se houver) e ouve o bus por pedidos. Desligada → dorme."""
        if not self.ligada:
            bus.emitir("telemetria", ligada=False); return
        await asyncio.gather(self._amostrar_em_ciclos(observador), self._escutar_bus())

    async def _amostrar_em_ciclos(self, observador=None) -> None:
        n = 0
        while True:
            try:
                if observador is not None:
                    app, jan = observador.atual
                else:
                    from ..ops.observador import app_frontal
                    app, jan = await asyncio.to_thread(app_frontal)
                if self.amostrar(app, jan):
                    n += 1
                    if n % 10 == 0:            # grava a cada 5 min; o resto fica em memória
                        self.salvar()
            except Exception as e:
                bus.emitir("telemetria", erro=f"{type(e).__name__}: {e}"[:120])
            await asyncio.sleep(self.intervalo_s)

    async def _escutar_bus(self) -> None:
        q = bus.assinar()
        try:
            while True:
                evt = await q.get()
                if evt.get("tipo") == "conversa":
                    self.registrar_pedido(evt.get("texto", ""), "", evt.get("canal", ""), evt.get("t"))
                elif evt.get("tipo") == "cortex" and evt.get("tarefa"):
                    self.classificar_ultimo(evt["tarefa"]); self.salvar()
        finally:
            bus.cancelar(q)
