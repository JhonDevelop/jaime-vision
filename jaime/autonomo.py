"""Modo autônomo — `objetivo(texto, limite_horas)`: o Córtex decompõe em etapas com critério de aceite; cada etapa
roda como turno do Jaime com checkpoint (diário + HUD); um bloqueio do Vigia pausa e o "confirmo" retoma; no fim,
relatório em 40-Diario e proposta de próximos passos.

Limites (.env): horas, custo em dólares, ferramentas permitidas. `executor` e `planejador` são injetáveis — os testes
usam funções offline. Nunca roda em paralelo com outro objetivo."""
from __future__ import annotations
import asyncio, json, re, time
from dataclasses import dataclass, field
from .hud.events import bus

PROMPT_PLANO = """Decomponha o objetivo abaixo em 3 a 8 etapas concretas e ordenadas, cada uma com um critério de aceite verificável.
Objetivo: {objetivo}
Limites: {horas} h, US$ {custo}, ferramentas {ferramentas}.
Responda SOMENTE um JSON: {{"etapas": [{{"titulo": "...", "aceite": "..."}}, ...]}}"""

PROMPT_ETAPA = """[modo autônomo · etapa {n}/{total} do objetivo "{objetivo}"]
Etapa: {titulo}
Critério de aceite: {aceite}
Contexto das etapas anteriores: {anteriores}
Execute a etapa com as ferramentas permitidas ({ferramentas}). Ao terminar, responda em até 3 frases: o que fez,
se o critério de aceite foi atingido (SIM/NÃO) e o que ficou pendente. Se uma ação for bloqueada pelo Vigia, pare e diga
exatamente qual foi (o João dirá "confirmo")."""

@dataclass
class Etapa:
    titulo: str
    aceite: str
    estado: str = "pendente"     # pendente | ok | falhou | pausada
    resultado: str = ""
    inicio: float = 0.0
    fim: float = 0.0

@dataclass
class Missao:
    objetivo: str
    limite_horas: float
    limite_custo: float
    etapas: list[Etapa] = field(default_factory=list)
    inicio: float = field(default_factory=time.time)
    custo: float = 0.0
    atual: int = 0
    estado: str = "planejando"   # planejando | rodando | pausada | concluida | interrompida

    @property
    def horas(self) -> float:
        return (time.time() - self.inicio) / 3600

    def resumo(self) -> str:
        ok = sum(e.estado == "ok" for e in self.etapas)
        return f"{self.estado} · {ok}/{len(self.etapas)} etapas · {self.horas:.2f} h · US$ {self.custo:.2f}"

def _extrair_json(txt: str) -> dict | None:
    m = re.search(r"\{.*\}", txt or "", re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None

class Autonomo:
    def __init__(self, jaime, horas: float, custo_usd: float, ferramentas: str, planejador=None, executor=None):
        self.jaime = jaime
        self.limite_horas, self.limite_custo, self.ferramentas = horas, custo_usd, ferramentas
        self.planejador = planejador or self._planejar_com_modelo
        self.executor = executor or self._executar_com_modelo
        self.missao: Missao | None = None
        self._retomar = asyncio.Event()

    # ── padrão: pelo próprio Jaime ───────────────────
    async def _planejar_com_modelo(self, m: Missao) -> list[Etapa]:
        txt = await self.jaime.ask(PROMPT_PLANO.format(objetivo=m.objetivo, horas=m.limite_horas, custo=m.limite_custo, ferramentas=self.ferramentas), canal="autonomo")
        dados = _extrair_json(txt) or {}
        return [Etapa(str(e.get("titulo", "")), str(e.get("aceite", ""))) for e in dados.get("etapas", []) if e.get("titulo")]

    async def _executar_com_modelo(self, m: Missao, i: int) -> str:
        e = m.etapas[i]
        anteriores = "; ".join(f"{x.titulo}: {x.resultado[:80]}" for x in m.etapas[:i] if x.resultado) or "nenhuma"
        antes = getattr(self.jaime, "_custo_sessao", 0.0)
        txt = await self.jaime.ask(PROMPT_ETAPA.format(n=i + 1, total=len(m.etapas), objetivo=m.objetivo, titulo=e.titulo,
                                                       aceite=e.aceite, anteriores=anteriores, ferramentas=self.ferramentas), canal="autonomo")
        m.custo += max(0.0, getattr(self.jaime, "_custo_sessao", 0.0) - antes)
        return txt

    # ── ciclo ─────────────────────────────────────────
    def confirmar(self) -> bool:
        """O 'confirmo' do João retoma uma missão pausada pelo Vigia."""
        if self.missao and self.missao.estado == "pausada":
            self._retomar.set(); return True
        return False

    def interromper(self) -> bool:
        if self.missao and self.missao.estado in ("rodando", "pausada", "planejando"):
            self.missao.estado = "interrompida"; self._retomar.set(); return True
        return False

    async def objetivo(self, texto: str, limite_horas: float | None = None) -> Missao:
        if self.missao and self.missao.estado in ("rodando", "pausada", "planejando"):
            raise RuntimeError(f"já há um objetivo em andamento: {self.missao.objetivo[:60]}")
        m = Missao(texto, limite_horas or self.limite_horas, self.limite_custo)
        self.missao = m
        self._checkpoint(m, f"Objetivo iniciado: {texto}")
        m.etapas = await self.planejador(m)
        if not m.etapas:
            m.estado = "interrompida"; self._checkpoint(m, "Não consegui decompor o objetivo em etapas."); return m
        m.estado = "rodando"
        self._checkpoint(m, "Plano: " + " → ".join(e.titulo for e in m.etapas))
        for i, e in enumerate(m.etapas):
            if m.estado == "interrompida":
                break
            if m.horas > m.limite_horas or m.custo > m.limite_custo:
                m.estado = "interrompida"; self._checkpoint(m, f"Limite atingido ({m.horas:.2f} h, US$ {m.custo:.2f})."); break
            m.atual = i; e.estado = "rodando"; e.inicio = time.time()
            bus.emitir("autonomo", objetivo=m.objetivo[:80], etapa=i + 1, total=len(m.etapas), titulo=e.titulo, estado=m.estado)
            resultado = await self.executor(m, i)
            e.resultado = resultado or ""; e.fim = time.time()
            bloqueado = bool(getattr(self.jaime, "vigia", None) and getattr(self.jaime.vigia, "ultima_bloqueada", None)) and "vigia" in e.resultado.lower()
            if bloqueado:
                m.estado = "pausada"; e.estado = "pausada"
                self._checkpoint(m, f"Etapa {i + 1} pausada pelo Vigia: {self.jaime.vigia.ultima_bloqueada}. Aguardando 'confirmo'.")
                bus.emitir("autonomo", objetivo=m.objetivo[:80], etapa=i + 1, total=len(m.etapas), titulo=e.titulo, estado="pausada")
                self._retomar.clear(); await self._retomar.wait()
                if m.estado == "interrompida":
                    break
                m.estado = "rodando"; self.jaime.vigia.ultima_bloqueada = None
                e.resultado = await self.executor(m, i) or e.resultado
            e.estado = "ok" if re.search(r"\bSIM\b", e.resultado) or "aceite: sim" in e.resultado.lower() else "falhou"
            self._checkpoint(m, f"Etapa {i + 1}/{len(m.etapas)} {e.estado}: {e.titulo} — {e.resultado[:160]}")
        if m.estado == "rodando":
            m.estado = "concluida"
        self._relatorio(m)
        return m

    # ── registro ─────────────────────────────────────
    def _checkpoint(self, m: Missao, texto: str) -> None:
        self.jaime.vault.diario(f"[autônomo] {texto}", "Log")
        bus.emitir("autonomo", objetivo=m.objetivo[:80], msg=texto[:160], estado=m.estado)

    def _relatorio(self, m: Missao) -> None:
        linhas = [f"Relatório do objetivo \"{m.objetivo}\": {m.resumo()}"]
        for i, e in enumerate(m.etapas, 1):
            linhas.append(f"  {i}. [{e.estado}] {e.titulo} — {e.resultado[:120]}")
        pend = [e.titulo for e in m.etapas if e.estado != "ok"]
        linhas.append("Próximos passos: " + ("; ".join(pend) if pend else "nenhum — objetivo concluído."))
        self.jaime.vault.diario("\n".join(linhas), "Feito" if m.estado == "concluida" else "Pendente")
        bus.emitir("fala", texto=f"Objetivo {m.estado}: {sum(e.estado == 'ok' for e in m.etapas)} de {len(m.etapas)} etapas em {m.horas * 60:.0f} minutos."); bus.emitir("fala_fim")
