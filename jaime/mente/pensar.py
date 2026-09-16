"""Raciocínio próprio — a Mente contínua do J.A.I.M.E pensa sobre o mundo do João quando ninguém pede nada.

Diferente do estudo (resolve problemas definidos num sandbox) e das vontades (escolhem QUAL atividade fazer): aqui
ele forma um PENSAMENTO genuíno — uma observação, uma conexão, uma ideia, uma preocupação — sobre um assunto do João
(um projeto, uma decisão recente, um padrão de uso, uma pergunta em aberto), registra em `01-Estado/Pensamentos.md` e
no HUD, e CONSULTA o que já pensou antes de responder (tese §3: "antes de responder, checar o que já pensou").

Econômico: modelo rápido (JAIME_PENSAR_MODEL → OpenAI rápido → Haiku), UM pensamento por ciclo, só quando ocioso e
dentro do orçamento; `JAIME_PENSAR=off` desliga. `pensador` é injetável (async prompt,contexto -> texto): testes offline."""
from __future__ import annotations
import asyncio, os, re, time
from dataclasses import dataclass, field
from datetime import datetime
from ..hud.events import bus

ARQUIVO = "01-Estado/Pensamentos.md"
CABECALHO = ("# Pensamentos do J.A.I.M.E\n\n> Raciocínio próprio: o que ele pensa sobre o mundo do João quando está "
             "ocioso. Ele relê isto antes de responder. Modelo rápido, um por ciclo; JAIME_PENSAR=off desliga.\n\n")
INTERVALO_S = 12 * 60
MAX_PENSAMENTOS = 200
ABRE = ("Penso que", "Notei que", "Reparei que", "Me ocorreu que", "Uma ideia:", "Vale lembrar que", "Fico com a impressão de que")

SISTEMA = ("Você é o J.A.I.M.E, robô assistente autônomo do João (Franca/SP), pensando sozinho — não está respondendo a "
           "ninguém. Forme UM pensamento próprio, curto e honesto, sobre o assunto dado: uma observação real, uma conexão "
           "entre coisas dele, uma ideia de melhoria ou uma preocupação. Nada genérico, nada de bajulação, nada inventado "
           "sobre pessoas. Se não houver o que pensar de útil, diga isso. Devolva SÓ um JSON: "
           '{"pensamento": "1-2 frases", "vale_dizer": true|false (se vale trazer ao João sem ele perguntar), "tema": "1-3 palavras"}.')

@dataclass
class Pensamento:
    tema: str
    texto: str
    gatilho: str = ""
    quando: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    vale_dizer: bool = False

    def linha(self) -> str:
        marca = " ·dizer" if self.vale_dizer else ""
        return f"## {self.quando} · {self.tema}{marca}\n{self.texto}\n"

def _palavras(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-zà-ú0-9]{3,}", (s or "").lower())}

def _pensador_padrao(s):
    """Modelo rápido: OpenAI rápido se houver chave, senão Haiku pela Anthropic."""
    modelo = os.environ.get("JAIME_PENSAR_MODEL", "")
    if getattr(s, "openai_key", ""):
        from ..cortex.provedores.openai import ProvedorOpenAI
        p = ProvedorOpenAI(s.openai_key, modelo or getattr(s, "openai_model_rapido", "gpt-5.6-luna"))
    else:
        from ..cortex.provedores.anthropic import ProvedorAnthropic
        p = ProvedorAnthropic(modelo or getattr(s, "model_rotina", "claude-haiku-4-5-20251001"), str(getattr(s, "root", ".")))
    async def fn(prompt: str, contexto: str) -> str:
        r = await p.responder(prompt, contexto)
        return r.texto if r.ok else ""
    return fn

class Pensar:
    def __init__(self, vault, pensador=None, s=None, pode_gastar=lambda: True):
        self.vault, self.s, self.pode_gastar = vault, s, pode_gastar
        self.pensador = pensador or (_pensador_padrao(s) if s is not None else None)
        self.pensamentos: list[Pensamento] = self._carregar()
        self.ocupado = False
        self._giro = 0

    # ── persistência ───────────────────────────────────
    def _carregar(self) -> list[Pensamento]:
        try:
            txt = self.vault.read(ARQUIVO)
        except Exception:
            return []
        out = []
        for bloco in re.split(r"^## ", txt or "", flags=re.M)[1:]:
            cab, _, corpo = bloco.partition("\n")
            m = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d)\s*·\s*(.+?)(\s·dizer)?\s*$", cab.strip())
            if m and corpo.strip():
                out.append(Pensamento(m.group(2).strip(), corpo.strip(), quando=m.group(1), vale_dizer=bool(m.group(3))))
        return out

    def _salvar(self) -> None:
        self.pensamentos = self.pensamentos[-MAX_PENSAMENTOS:]
        try:
            self.vault.write(ARQUIVO, CABECALHO + "\n".join(p.linha() for p in reversed(self.pensamentos)))
        except Exception:
            pass

    # ── de onde pensar ─────────────────────────────────
    def _assunto(self) -> tuple[str, str]:
        """(tema, trecho) rotativo entre projetos, decisões recentes, uso e problemas em aberto."""
        fontes = [self._proj, self._diario, self._uso, self._problemas]
        for i in range(len(fontes)):
            self._giro = (self._giro + 1) % len(fontes)
            r = fontes[self._giro]()
            if r:
                return r
        return ("o João", "o que sei dele no vault")

    def _proj(self):
        try:
            import glob
            base = self.vault.path("20-Projetos")
            arqs = [p for p in sorted(glob.glob(str(base / "*.md"))) if "INDEX" not in p]
            if not arqs:
                return None
            alvo = arqs[self._giro % len(arqs)]
            nome = os.path.basename(alvo)[:-3]
            corpo = self.vault.read(f"20-Projetos/{nome}.md")[:1200]
            return (nome, corpo)
        except Exception:
            return None

    def _diario(self):
        try:
            hoje = datetime.now().strftime("%Y-%m-%d")
            txt = self.vault.read(f"40-Diario/{hoje}.md")
            linhas = [l[2:] for l in txt.splitlines() if l.startswith("- ") and not l.count("Notificação") and not l.count("iniciado")]
            if linhas:
                return ("o dia de hoje", "\n".join(linhas[-12:]))
        except Exception:
            pass
        return None

    def _uso(self):
        try:
            txt = self.vault.read("01-Estado/Uso.md").strip()
            return ("o que o João mais faz", txt[:1000]) if txt else None
        except Exception:
            return None

    def _problemas(self):
        try:
            txt = self.vault.read("90-Estudo/Problemas.md")
            abertos = [b.split("\n")[0] for b in re.split(r"^## ", txt or "", flags=re.M)[1:] if "resolvido" not in b.split("\n")[0]]
            return ("um problema em aberto", "\n".join(abertos[:6])) if abertos else None
        except Exception:
            return None

    # ── pensar ─────────────────────────────────────────
    async def pensar(self, tema: str | None = None, trecho: str | None = None) -> Pensamento | None:
        if not self.pensador or not self.pode_gastar():
            return None
        if tema is None:
            tema, trecho = self._assunto()
        bus.emitir("pensamento", pensando=True, tema=tema)
        prompt = f"Assunto: {tema}.\nO que sei sobre isso agora:\n{(trecho or '(pouco)')[:1500]}\n\nSeu pensamento (JSON)."
        try:
            saida = await self.pensador(prompt, SISTEMA)
        except Exception as e:
            bus.emitir("pensamento", pensando=False, erro=f"{type(e).__name__}: {e}"[:120]); return None
        p = self._parse(saida, tema)
        if not p:
            bus.emitir("pensamento", pensando=False); return None
        self.pensamentos.append(p); self._salvar()
        bus.emitir("pensamento", pensando=False, tema=p.tema, texto=p.texto, vale_dizer=p.vale_dizer)
        try:
            self.vault.diario(f"Pensei ({p.tema}): {p.texto[:180]}", "Log")
        except Exception:
            pass
        return p

    def _parse(self, saida: str, tema: str) -> Pensamento | None:
        import json
        m = re.search(r"\{.*\}", saida or "", re.S)
        if m:
            try:
                d = json.loads(m.group(0))
                t = str(d.get("pensamento", "")).strip()
                if len(t) >= 8:
                    return Pensamento(str(d.get("tema") or tema)[:40], t[:400], gatilho="ciclo", vale_dizer=bool(d.get("vale_dizer")))
            except Exception:
                pass
        t = re.sub(r"\s+", " ", (saida or "").strip())
        return Pensamento(tema[:40], t[:400], gatilho="ciclo") if len(t) >= 8 else None

    # ── recall (antes de responder) ────────────────────
    def sobre(self, assunto: str, n: int = 3) -> list[Pensamento]:
        alvo = _palavras(assunto)
        if not alvo:
            return []
        marcados = []
        for p in self.pensamentos:
            score = len(alvo & _palavras(p.tema + " " + p.texto))
            if score:
                marcados.append((score, p))
        marcados.sort(key=lambda x: (-x[0], x[1].quando))
        return [p for _, p in marcados[:n]]

    def recall_para_prompt(self, assunto: str, n: int = 2) -> str:
        hits = self.sobre(assunto, n)
        return " | ".join(f"({p.quando}) {p.texto}" for p in hits)

    def a_dizer(self) -> list[Pensamento]:
        return [p for p in self.pensamentos if p.vale_dizer]

    def resumo(self, n: int = 5) -> str:
        return "\n".join(f"- {p.quando} · {p.tema}: {p.texto}" for p in self.pensamentos[-n:]) or "Ainda não pensei nada registrado."

    # ── loop ───────────────────────────────────────────
    async def rodar(self, pode_rodar=lambda: True, intervalo: int | None = None) -> None:
        if os.environ.get("JAIME_PENSAR", "on").lower() == "off":
            return
        intervalo = intervalo or int(os.environ.get("JAIME_PENSAR_INTERVALO_S", INTERVALO_S))
        bus.emitir("pensamento", pensando=False, ligado=True, total=len(self.pensamentos))
        while True:
            await asyncio.sleep(intervalo)
            try:
                if pode_rodar() and not self.ocupado:
                    self.ocupado = True
                    try:
                        await self.pensar()
                    finally:
                        self.ocupado = False
            except asyncio.CancelledError:
                return
            except Exception as e:
                bus.emitir("pensamento", pensando=False, erro=f"ciclo: {type(e).__name__}: {e}"[:120])
