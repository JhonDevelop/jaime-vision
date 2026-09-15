"""Gravador de processos — "Jaime, grava esse processo" … "para de gravar" … "repete o processo X".

Enquanto grava, registra o que o João faz: app e janela em foco (observador), cliques (posição + captura de tela no
momento), teclas/atalhos e o texto digitado, com pynput. Salva em `~/Jaime/processos/<slug>.json` (passos) e uma nota
legível em `50-Conhecimento/processos/<slug>.md`. `repetir()` reproduz clique a clique com pyautogui, esperando entre
passos; roda como sessão livre do Vigia (o João pediu explicitamente) e "para" interrompe.

Privacidade: a gravação captura o que é digitado — só grava quando o João manda, avisa quando começa e quando termina,
e nunca grava com o campo de senha do macOS/browser em foco não é detectável: por isso ele avisa para não digitar senhas
durante a gravação. Precisa de Acessibilidade para o Terminal/python."""
from __future__ import annotations
import json, os, re, threading, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from ..hud.events import bus
from ..identidade import slug as fazer_slug

PASTA = Path(os.environ.get("JAIME_PROCESSOS", "~/Jaime/processos")).expanduser()
NOTA_DIR = "50-Conhecimento/processos"
GRAVAR_RX = re.compile(r"\b(grava|gravar|registra|registrar|aprende|aprender)\s+(esse|este|o|um)?\s*processo\b(?:\s*(?:chamado|como|de)?\s*[:\-]?\s*(.+))?", re.I)
PARAR_GRAVACAO_RX = re.compile(r"\b(para|pare|parar|chega|termina|terminar|fim)\s+(de\s+)?(gravar|gravação|a gravação|o processo)\b", re.I)
REPETIR_RX = re.compile(r"\b(repete|repetir|executa|executar|roda|rodar|faz|fazer)\s+(o\s+)?processo\s+[:\-]?\s*(.+)$", re.I)

@dataclass
class Passo:
    tipo: str            # app | clique | tecla | texto | espera
    t: float
    app: str = ""
    janela: str = ""
    x: int = 0
    y: int = 0
    botao: str = "left"
    combo: str = ""
    texto: str = ""
    captura: str = ""

@dataclass
class Processo:
    nome: str
    slug: str
    inicio: float
    fim: float = 0.0
    passos: list[Passo] = field(default_factory=list)

    def resumo(self) -> str:
        n = {t: sum(1 for p in self.passos if p.tipo == t) for t in ("app", "clique", "tecla", "texto")}
        return f"{self.nome}: {len(self.passos)} passos ({n['clique']} cliques, {n['tecla']} teclas, {n['texto']} textos, {n['app']} trocas de app) em {self.fim - self.inicio:.0f}s"

def interpretar(texto: str) -> tuple[str, str] | None:
    """('gravar', nome) | ('parar', '') | ('repetir', nome) | None"""
    t = (texto or "").strip().rstrip(".!?")
    if PARAR_GRAVACAO_RX.search(t):
        return "parar", ""
    if (m := REPETIR_RX.search(t)):
        return "repetir", m.group(3).strip()
    if (m := GRAVAR_RX.search(t)):
        return "gravar", (m.group(3) or "").strip() or time.strftime("processo %d-%m %H:%M")
    return None

class Gravador:
    def __init__(self, jaime, observador=None, capturador=None):
        self.jaime, self.observador = jaime, observador
        self.capturador = capturador
        self.processo: Processo | None = None
        self._listeners = []
        self._texto = ""            # teclas comuns acumulam num passo "texto"
        self._ultimo_app = ("", "")
        self._lock = threading.Lock()

    @property
    def gravando(self) -> bool:
        return bool(self.processo and self.processo.fim == 0.0)

    # ── gravação ─────────────────────────────────────
    def iniciar(self, nome: str) -> str:
        if self.gravando:
            return f"Já estou gravando '{self.processo.nome}'."
        self.processo = Processo(nome, fazer_slug(nome)[:40], time.time())
        self._texto = ""; self._ultimo_app = ("", "")
        try:
            from pynput import mouse, keyboard
            ml = mouse.Listener(on_click=self._on_click); kl = keyboard.Listener(on_press=self._on_key)
            ml.start(); kl.start(); self._listeners = [ml, kl]
        except Exception as e:
            self.processo = None
            return f"Não consegui ligar a gravação ({type(e).__name__}) — precisa de Acessibilidade para o Terminal/python."
        threading.Thread(target=self._vigiar_app, daemon=True).start()
        bus.emitir("gravador", estado="gravando", nome=nome)
        self.jaime.vault.diario(f"[gravador] começou: {nome}", "Log")
        return f"Gravando o processo '{nome}'. Faça normalmente; não digite senhas. Diga 'para de gravar' no fim."

    def _flush_texto(self):
        if self._texto.strip():
            self._add(Passo("texto", time.time(), texto=self._texto))
        self._texto = ""

    def _add(self, p: Passo):
        with self._lock:
            if self.gravando:
                app, jan = self._ultimo_app; p.app, p.janela = p.app or app, p.janela or jan
                self.processo.passos.append(p)

    def _on_click(self, x, y, button, pressed):
        if not pressed or not self.gravando:
            return
        self._flush_texto()
        cap = ""
        try:
            if self.capturador:
                cap = str(self.capturador(f"proc-{self.processo.slug}-{len(self.processo.passos):03d}"))
        except Exception:
            pass
        self._add(Passo("clique", time.time(), x=int(x), y=int(y), botao=str(button).split(".")[-1], captura=cap))

    def _on_key(self, key):
        if not self.gravando:
            return
        try:
            ch = key.char
        except AttributeError:
            ch = None
        if ch and ch.isprintable():
            self._texto += ch
        else:
            nome = str(key).replace("Key.", "")
            if nome == "space":
                self._texto += " "
            else:
                self._flush_texto(); self._add(Passo("tecla", time.time(), combo=nome))

    def _vigiar_app(self):
        while self.gravando:
            try:
                atual = tuple(self.observador.atual) if self.observador else ("", "")
                if atual != self._ultimo_app and atual[0]:
                    self._ultimo_app = atual
                    self._add(Passo("app", time.time(), app=atual[0], janela=atual[1]))
            except Exception:
                pass
            time.sleep(1)

    def parar(self) -> str:
        if not self.gravando:
            return "Não estava gravando."
        self._flush_texto()
        self.processo.fim = time.time()
        for l in self._listeners:
            try: l.stop()
            except Exception: pass
        self._listeners = []
        self.salvar(self.processo)
        bus.emitir("gravador", estado="salvo", nome=self.processo.nome, passos=len(self.processo.passos))
        self.jaime.vault.diario(f"[gravador] salvo: {self.processo.resumo()}", "Feito")
        return f"Salvo. {self.processo.resumo()}. Para repetir: 'repete o processo {self.processo.nome}'."

    # ── persistência ─────────────────────────────────
    def salvar(self, p: Processo) -> Path:
        PASTA.mkdir(parents=True, exist_ok=True)
        arq = PASTA / f"{p.slug}.json"
        arq.write_text(json.dumps({**asdict(p), "passos": [asdict(x) for x in p.passos]}, ensure_ascii=False, indent=1), encoding="utf-8")
        linhas = [f"# Processo: {p.nome}", "", f"> Gravado em {time.strftime('%d/%m/%Y %H:%M', time.localtime(p.inicio))}. Arquivo: `{arq}`. Repetir: \"Jaime, repete o processo {p.nome}\".", ""]
        for i, x in enumerate(p.passos, 1):
            if x.tipo == "app": linhas.append(f"{i}. Abrir **{x.app}**" + (f" — {x.janela}" if x.janela else ""))
            elif x.tipo == "clique": linhas.append(f"{i}. Clicar em ({x.x}, {x.y}) em {x.app}" + (f" — captura `{Path(x.captura).name}`" if x.captura else ""))
            elif x.tipo == "tecla": linhas.append(f"{i}. Tecla `{x.combo}`")
            elif x.tipo == "texto": linhas.append(f"{i}. Digitar: `{x.texto[:80]}`")
        self.jaime.vault.write(f"{NOTA_DIR}/{p.slug}.md", "\n".join(linhas) + "\n")
        return arq

    @staticmethod
    def carregar(nome_ou_slug: str) -> Processo | None:
        s = fazer_slug(nome_ou_slug)[:40]
        arq = PASTA / f"{s}.json"
        if not arq.exists():
            cands = [a for a in PASTA.glob("*.json") if s in a.stem or a.stem in s]
            if not cands:
                return None
            arq = cands[0]
        d = json.loads(arq.read_text(encoding="utf-8"))
        passos = [Passo(**x) for x in d.pop("passos", [])]
        return Processo(d["nome"], d["slug"], d["inicio"], d.get("fim", 0.0), passos)

    @staticmethod
    def listar() -> list[str]:
        return sorted(a.stem for a in PASTA.glob("*.json")) if PASTA.exists() else []

    # ── repetição ────────────────────────────────────
    def repetir(self, nome: str, executor=None, deve_parar=lambda: False, esperar=time.sleep) -> str:
        p = self.carregar(nome)
        if not p:
            return f"Não conheço o processo '{nome}'. Tenho: {', '.join(self.listar()) or 'nenhum'}."
        from . import computador
        ex = executor or {
            "app": lambda x: os.system(f"open -a '{x.app}'") if x.app else None,
            "clique": lambda x: computador.clicar(x.x, x.y, botao=x.botao if x.botao in ("left", "right") else "left"),
            "tecla": lambda x: computador.tecla(x.combo.replace("cmd", "cmd").replace("ctrl_l", "ctrl").replace("shift_l", "shift").replace("alt_l", "alt")),
            "texto": lambda x: computador.digitar(x.texto),
        }
        bus.emitir("gravador", estado="repetindo", nome=p.nome, passos=len(p.passos))
        feitos = 0
        for i, x in enumerate(p.passos):
            if deve_parar():
                return f"Parei no passo {i + 1} de {len(p.passos)}."
            if x.tipo in ex:
                ex[x.tipo](x); feitos += 1
            gap = (p.passos[i + 1].t - x.t) if i + 1 < len(p.passos) else 0
            esperar(min(max(gap, 0.3), 3.0))
        self.jaime.vault.diario(f"[gravador] repetido: {p.nome} ({feitos} passos)", "Feito")
        bus.emitir("gravador", estado="concluido", nome=p.nome, passos=feitos)
        return f"Processo '{p.nome}' repetido: {feitos} passos."
