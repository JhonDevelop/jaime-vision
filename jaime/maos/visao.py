"""Visão contínua — jogos e apps por visão: ver a tela em loop, decidir, agir, com limites e kill switch.

`Sessao(objetivo)`: a cada passo captura a tela, pede ao Jaime UMA ação em JSON ({"acao": "clicar"|"tecla"|"digitar"|"esperar"|"parar",
...}) olhando a imagem, executa (pyautogui), registra. Limites: máximo de passos e intervalo mínimo (.env); "para"/"chega"/"pare"
do João encerram na hora (kill switch em `Jaime._porta`). O João inicia a sessão explicitamente ("Jaime, joga…"), por isso
o Vigia libera as ações de tela ENQUANTO a sessão estiver ativa — fora dela, cada clique volta a exigir "confirmo".
`decisor` e `executor` são injetáveis (testes offline)."""
from __future__ import annotations
import asyncio, json, re, time
from dataclasses import dataclass, field
from ..hud.events import bus
from . import computador

PROMPT = """[visão contínua · passo {n}/{max} · objetivo: {objetivo}]
A captura da tela está em {captura} — leia com Read e olhe. Tamanho lógico da tela: {w}x{h}.
Últimas ações: {historico}
Responda SOMENTE um JSON com UMA ação: {{"acao": "clicar", "x": int, "y": int}} | {{"acao": "tecla", "combo": "space"}} |
{{"acao": "digitar", "texto": "..."}} | {{"acao": "esperar", "segundos": 1}} | {{"acao": "parar", "motivo": "..."}}
Pare quando o objetivo estiver cumprido ou se algo parecer errado/perigoso."""

PARAR_RX = re.compile(r"^\s*(para|pare|parar|chega|stop|cancela|cancelar)[!.\s]*$", re.I)

def quer_parar(texto: str) -> bool:
    return bool(PARAR_RX.match(texto or ""))

@dataclass
class Sessao:
    objetivo: str
    max_passos: int = 60
    intervalo_s: float = 2.0
    passos: list[dict] = field(default_factory=list)
    ativa: bool = False
    inicio: float = field(default_factory=time.time)
    fim_motivo: str = ""

def extrair_acao(txt: str) -> dict:
    m = re.search(r"\{.*\}", txt or "", re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        d = {}
    return d if d.get("acao") in ("clicar", "tecla", "digitar", "esperar", "parar") else {"acao": "parar", "motivo": "resposta sem ação válida"}

def executar_acao(a: dict) -> str:
    if a["acao"] == "clicar":
        return computador.clicar(int(a["x"]), int(a["y"]), duplo=bool(a.get("duplo")))
    if a["acao"] == "tecla":
        return computador.tecla(str(a.get("combo", "space")))
    if a["acao"] == "digitar":
        return computador.digitar(str(a.get("texto", "")))
    if a["acao"] == "esperar":
        time.sleep(min(float(a.get("segundos", 1)), 10)); return "esperei"
    return "parar"

class Visao:
    def __init__(self, jaime, max_passos: int = 60, intervalo_s: float = 2.0, decisor=None, executor=None, capturador=None):
        self.jaime, self.max_passos, self.intervalo_s = jaime, max_passos, intervalo_s
        self.decisor = decisor or self._decidir_com_modelo
        self.executor = executor or executar_acao
        self.capturador = capturador or (lambda: computador.capturar("visao"))
        self.sessao: Sessao | None = None

    @property
    def ativa(self) -> bool:
        return bool(self.sessao and self.sessao.ativa)

    def parar(self, motivo: str = "o João mandou parar") -> bool:
        if self.ativa:
            self.sessao.ativa = False; self.sessao.fim_motivo = motivo; return True
        return False

    async def _decidir_com_modelo(self, s: Sessao, captura, n: int) -> dict:
        try:
            w, h = computador.tamanho()
        except Exception:
            w, h = 0, 0
        hist = "; ".join(f"{p['acao']}" + (f"({p.get('x')},{p.get('y')})" if p.get("x") is not None else "") for p in s.passos[-5:]) or "nenhuma"
        txt = await self.jaime.ask(PROMPT.format(n=n, max=s.max_passos, objetivo=s.objetivo, captura=captura, w=w, h=h, historico=hist), canal="visao")
        return extrair_acao(txt)

    async def rodar(self, objetivo: str, max_passos: int | None = None) -> Sessao:
        if self.ativa:
            raise RuntimeError("já há uma sessão de visão ativa; diga 'para' primeiro")
        s = Sessao(objetivo, max_passos or self.max_passos, self.intervalo_s, ativa=True)
        self.sessao = s
        self.jaime.vault.diario(f"[visão] sessão iniciada: {objetivo}", "Log")
        bus.emitir("visao", objetivo=objetivo[:80], passo=0, max=s.max_passos, estado="ativa")
        try:
            for n in range(1, s.max_passos + 1):
                if not s.ativa:
                    break
                captura = await asyncio.to_thread(self.capturador)
                a = await self.decisor(s, captura, n)
                if not s.ativa:            # o João mandou parar enquanto o modelo pensava
                    break
                resultado = await asyncio.to_thread(self.executor, a) if a["acao"] != "parar" else "parar"
                s.passos.append({**a, "resultado": resultado, "t": time.time()})
                bus.emitir("visao", objetivo=objetivo[:80], passo=n, max=s.max_passos, acao=a.get("acao"), estado="ativa")
                if a["acao"] == "parar":
                    s.fim_motivo = str(a.get("motivo", "objetivo cumprido")); break
                await asyncio.sleep(s.intervalo_s)
            else:
                s.fim_motivo = f"limite de {s.max_passos} passos"
        finally:
            s.ativa = False
        self.jaime.vault.diario(f"[visão] sessão encerrada ({len(s.passos)} passos): {s.fim_motivo}", "Log")
        bus.emitir("visao", objetivo=objetivo[:80], passo=len(s.passos), max=s.max_passos, estado="encerrada", motivo=s.fim_motivo)
        return s
