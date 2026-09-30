"""Cliente de JANELAS NATIVAS dos blocos — cada bloco é uma janela do sistema (Tk), sem navegador.

`python -m jaime blocos janela [ws://127.0.0.1:8787/blocos/ws]`

Janelas sem moldura, sempre na frente, semi-transparentes, arrastáveis; × fecha, ◉ lê em voz. Funciona no
macOS, no Windows e no Linux (Tk vem com o Python oficial e com o do uv). Métricas em número grande, gráfico
desenhado no Canvas, o resto em texto — o mesmo bloco que o cockpit mostra, adaptado pelo servidor ao perfil `janela`.

A lógica de layout (`geometria`, `pintar_metricas`…) é separada do Tk para ser testável sem tela."""
from __future__ import annotations
import json, queue, threading

FUNDO, TEXTO, APAGADO, CIANO = "#0a111d", "#dfe9f5", "#7f93ab", "#38e1ff"
TRILHO = {0: "#3a5068", 1: "#38e1ff", 2: "#ffb347", 3: "#ff5c72"}
ESTADO = {"ok": "#49e6a0", "atencao": "#ffb347", "ruim": "#ff5c72"}
LARGURA = 360


def geometria(indice: int, bloco: dict, tela_w: int, tela_h: int) -> tuple[int, int]:
    """Posição da janela: a ancoragem do bloco (fração da tela) ou uma coluna à direita, de cima para baixo."""
    a = bloco.get("ancoragem") or {}
    if a.get("x") is not None and a.get("y") is not None:
        return int(a["x"] * tela_w), int(a["y"] * tela_h)
    col, lin = divmod(indice, 4)
    return max(0, tela_w - (LARGURA + 24) * (col + 1)), 60 + lin * 190


def barras(series: list[dict], w: int, h: int) -> list[tuple[float, float, float, float, int]]:
    """Retângulos (x0, y0, x1, y1, série) de um gráfico de barras — geometria pura, sem Tk."""
    pts = [p["y"] for s in series for p in s.get("pontos", [])]
    if not pts:
        return []
    lo, hi = min(0.0, *pts), max(pts)
    hi = hi if hi > lo else lo + 1
    n = max(len(s.get("pontos", [])) for s in series)
    larg = w / max(n, 1) / max(len(series), 1) * 0.8
    y = lambda v: h - (v - lo) / (hi - lo) * h
    out = []
    for k, s in enumerate(series):
        for i, p in enumerate(s.get("pontos", [])):
            x0 = i * w / n + k * larg
            out.append((x0, min(y(p["y"]), y(0)), x0 + larg, max(y(p["y"]), y(0)), k))
    return out


class Janelas:
    def __init__(self, url: str):
        import tkinter as tk
        self.tk = tk
        self.url = url
        self.raiz = tk.Tk(); self.raiz.withdraw()
        self.janelas: dict[str, object] = {}
        self.fila: queue.Queue = queue.Queue()
        self.ws = None

    # ── rede (thread) ──────────────────────────────
    def _rede(self):
        from websockets.sync.client import connect
        try:
            with connect(self.url, additional_headers={"Origin": "http://127.0.0.1"}) as ws:
                self.ws = ws
                ws.send(json.dumps({"op": "ola", "perfil": "janela", "nome": "janelas nativas",
                                    "capacidades": {"largura": self.raiz.winfo_screenwidth(), "altura": self.raiz.winfo_screenheight()}}))
                for bruto in ws:
                    self.fila.put(json.loads(bruto))
        except Exception as e:
            self.fila.put({"op": "erro", "msg": str(e)[:120]})

    def enviar(self, m: dict):
        try:
            self.ws and self.ws.send(json.dumps(m))
        except Exception:
            pass

    # ── Tk (thread principal) ──────────────────────
    def _drenar(self):
        while not self.fila.empty():
            m = self.fila.get_nowait()
            if m.get("op") in ("abrir", "atualizar"):
                self.desenhar(m["bloco"])
            elif m.get("op") == "fechar":
                j = self.janelas.pop(m.get("id"), None)
                if j:
                    j.destroy()
        self.raiz.after(60, self._drenar)

    def desenhar(self, b: dict):
        tk = self.tk
        j = self.janelas.get(b["id"])
        if j is None:
            j = tk.Toplevel(self.raiz, bg=FUNDO)
            j.overrideredirect(True)
            try:
                j.attributes("-topmost", True); j.attributes("-alpha", 0.93)
            except tk.TclError:
                pass
            x, y = geometria(len(self.janelas), b, j.winfo_screenwidth(), j.winfo_screenheight())
            j.geometry(f"{LARGURA}x10+{x}+{y}")
            self.janelas[b["id"]] = j
        for w in j.winfo_children():
            w.destroy()
        cor = TRILHO.get(b.get("prioridade", 1), CIANO)
        tk.Frame(j, bg=cor, width=2).pack(side="left", fill="y")
        caixa = tk.Frame(j, bg=FUNDO); caixa.pack(side="left", fill="both", expand=True, padx=(10, 8), pady=8)
        cab = tk.Frame(caixa, bg=FUNDO); cab.pack(fill="x")
        tk.Label(cab, text=b.get("titulo", ""), bg=FUNDO, fg=TEXTO, font=("Helvetica", 13, "bold"), anchor="w").pack(side="left")
        tk.Button(cab, text="×", command=lambda: self.enviar({"op": "fechar", "id": b["id"]}), bg=FUNDO, fg=APAGADO,
                  relief="flat", bd=0, highlightthickness=0, activebackground=FUNDO).pack(side="right")
        tk.Button(cab, text="ler", command=lambda: self.enviar({"op": "ler", "id": b["id"]}), bg=FUNDO, fg=APAGADO,
                  relief="flat", bd=0, highlightthickness=0, activebackground=FUNDO).pack(side="right")
        c = b.get("conteudo")
        if b.get("tipo") == "metricas" and c:
            linha = tk.Frame(caixa, bg=FUNDO); linha.pack(fill="x", pady=(6, 0))
            for m in c.get("itens", []):
                f = tk.Frame(linha, bg=FUNDO, highlightthickness=0); f.pack(side="left", padx=(0, 16))
                tk.Label(f, text=f"{m['valor']}{m.get('unidade', '')}", bg=FUNDO, fg=ESTADO.get(m.get("estado"), TEXTO),
                         font=("Helvetica", 20)).pack(anchor="w")
                tk.Label(f, text=m["rotulo"], bg=FUNDO, fg=APAGADO, font=("Helvetica", 10)).pack(anchor="w")
        elif b.get("tipo") == "grafico" and c:
            cv = tk.Canvas(caixa, width=LARGURA - 30, height=110, bg=FUNDO, highlightthickness=0); cv.pack(pady=(6, 0))
            cores = [CIANO, "#ffb347", "#7d5cff"]
            for x0, y0, x1, y1, k in barras(c.get("series", []), LARGURA - 30, 104):
                cv.create_rectangle(x0, y0 + 3, x1, y1 + 3, fill=cores[k % 3], width=0)
        elif b.get("tipo") == "acoes" and c:
            if c.get("texto"):
                tk.Label(caixa, text=c["texto"], bg=FUNDO, fg=TEXTO, font=("Helvetica", 11), anchor="w").pack(fill="x", pady=(6, 4))
            linha = tk.Frame(caixa, bg=FUNDO); linha.pack(fill="x")
            for bt in c.get("botoes", []):
                tk.Button(linha, text=bt["rotulo"], command=lambda i=bt["intencao"]: self.enviar({"op": "acao", "id": b["id"], "intencao": i}),
                          bg=FUNDO, fg=TEXTO, relief="solid", bd=1, highlightthickness=0, padx=10, pady=3).pack(side="left", padx=(0, 6))
        else:
            tk.Label(caixa, text="\n".join(b.get("linhas") or []), bg=FUNDO, fg=TEXTO, justify="left", anchor="w",
                     font=("Helvetica", 11), wraplength=LARGURA - 30).pack(fill="x", pady=(6, 0))
        j.update_idletasks()
        j.geometry(f"{LARGURA}x{j.winfo_reqheight()}")
        self._arrastavel(j, cab, b["id"])

    def _arrastavel(self, j, alca, bid):
        estado = {}
        def pega(e): estado.update(dx=e.x_root - j.winfo_x(), dy=e.y_root - j.winfo_y())
        def move(e): j.geometry(f"+{e.x_root - estado['dx']}+{e.y_root - estado['dy']}")
        def solta(e):
            self.enviar({"op": "mover", "id": bid, "ancoragem": {"x": round(j.winfo_x() / j.winfo_screenwidth(), 3),
                                                                  "y": round(j.winfo_y() / j.winfo_screenheight(), 3)}})
        for w in (alca, *alca.winfo_children()):
            if isinstance(w, self.tk.Label):
                w.bind("<ButtonPress-1>", pega); w.bind("<B1-Motion>", move); w.bind("<ButtonRelease-1>", solta)
        alca.bind("<ButtonPress-1>", pega); alca.bind("<B1-Motion>", move); alca.bind("<ButtonRelease-1>", solta)

    def rodar(self):
        threading.Thread(target=self._rede, daemon=True).start()
        self.raiz.after(60, self._drenar)
        self.raiz.mainloop()


def rodar(url: str = "ws://127.0.0.1:8787/blocos/ws") -> int:
    try:
        import tkinter  # noqa: F401
    except ImportError:
        print("Tk indisponível neste Python (no Linux: apt install python3-tk; o Python do uv já traz)."); return 1
    Janelas(url).rodar()
    return 0
