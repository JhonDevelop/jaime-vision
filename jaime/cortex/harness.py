"""O harness do J.A.I.M.E — o laço que persegue um objetivo até conseguir, e corrige o rumo sozinho.

O `jaime/autonomo.py` já planejava e executava, mas parava aí: passo que falhava era marcado "falhou" e a
missão seguia em frente com o plano intacto. Isso não é autonomia, é uma lista de tarefas que roda uma vez.

Um harness de verdade tem quatro coisas que faltavam, e são elas que estão aqui:

    VERIFICAR    depois de agir, conferir contra um critério ESCRITO ANTES. Sem critério, "deu certo"
                 é opinião — e o modelo sempre acha que deu certo.
    CORRIGIR     falhou? tenta de novo, sabendo por que falhou. O que voltou da verificação entra na
                 segunda tentativa; repetir igual é esperar sorte.
    REPLANEJAR   esgotou as tentativas? o problema é o PLANO, não o passo. Troca o caminho que falta,
                 mantendo o que já deu certo.
    DESISTIR     replanejou duas vezes e continua batendo? para e conta. Laço que nunca desiste queima
                 orçamento e cansa o João.

Permissivo de propósito (o João pediu, com todas as letras): ele não pergunta se pode continuar, não pede
aprovação a cada passo e não trava em dúvida — decide e age. O que segura é o Vigia, que é outra camada, e
os limites de ciclo, tempo e dinheiro, que existem para o laço não virar moto-perpétuo.

Tudo é injetável (`planejar`, `agir`, `verificar`, `replanejar`), então o laço é testado sem chamar modelo."""
from __future__ import annotations
import asyncio, os, re, time
from dataclasses import dataclass, field

from ..hud.events import bus

MAX_CICLOS = int(os.environ.get("JAIME_HARNESS_CICLOS", "40"))
MAX_TENTATIVAS = int(os.environ.get("JAIME_HARNESS_TENTATIVAS", "3"))
MAX_REPLANOS = int(os.environ.get("JAIME_HARNESS_REPLANOS", "2"))
LIMITE_HORAS = float(os.environ.get("JAIME_HARNESS_HORAS", "3"))
LIMITE_USD = float(os.environ.get("JAIME_HARNESS_USD", "5"))

PRONTO_RX = re.compile(r"\bPRONTO\b", re.I)
MARCADOR_RX = re.compile(r"^\s*[-*\d.)\s]+")


def ler_passos(texto: str, limite: int = 7) -> list["Passo"]:
    """Lê as linhas `passo | critério` que o modelo devolveu. Linha sem critério não vira passo:
    passo sem critério é passo que nunca fecha, porque não dá para verificar."""
    passos = []
    for linha in (texto or "").splitlines():
        if "|" not in linha:
            continue
        titulo, criterio = linha.split("|", 1)
        titulo = MARCADOR_RX.sub("", titulo).strip()
        criterio = criterio.strip()
        if titulo and criterio:
            passos.append(Passo(titulo[:120], criterio[:200]))
    return passos[:limite]


@dataclass
class Passo:
    titulo: str
    criterio: str = ""                 # como saber que este passo acabou. Escrito ANTES de agir.
    estado: str = "pendente"           # pendente | rodando | ok | falhou | desistido
    tentativas: int = 0
    resultado: str = ""
    porque_falhou: str = ""

    def linha(self) -> str:
        marca = {"ok": "✓", "falhou": "…", "desistido": "✗", "rodando": "▸"}.get(self.estado, "◻")
        return f"{marca} {self.titulo}" + (f" — {self.porque_falhou[:80]}" if self.porque_falhou else "")


@dataclass
class Perseguicao:
    objetivo: str
    passos: list[Passo] = field(default_factory=list)
    estado: str = "planejando"         # planejando | rodando | concluida | desistiu | interrompida
    ciclos: int = 0
    replanos: int = 0
    inicio: float = field(default_factory=time.time)
    custo: float = 0.0
    motivo: str = ""

    @property
    def horas(self) -> float:
        return (time.time() - self.inicio) / 3600

    @property
    def pendente(self) -> Passo | None:
        return next((p for p in self.passos if p.estado in ("pendente", "falhou")), None)

    def resumo(self) -> str:
        ok = sum(1 for p in self.passos if p.estado == "ok")
        return (f"{self.estado}: {ok}/{len(self.passos)} passos, {self.ciclos} ciclos, "
                f"{self.horas:.2f} h" + (f" — {self.motivo}" if self.motivo else ""))


class Harness:
    """Persegue um objetivo: planeja, age, verifica, corrige, replaneja. Para quando cumpre ou quando custa demais."""

    def __init__(self, jaime, *, planejar=None, agir=None, verificar=None, replanejar=None,
                 max_ciclos: int = MAX_CICLOS, max_tentativas: int = MAX_TENTATIVAS,
                 max_replanos: int = MAX_REPLANOS, limite_horas: float = LIMITE_HORAS,
                 limite_usd: float = LIMITE_USD):
        self.jaime = jaime
        self.atual: Perseguicao | None = None
        self._parar = asyncio.Event()
        self.max_ciclos, self.max_tentativas, self.max_replanos = max_ciclos, max_tentativas, max_replanos
        self.limite_horas, self.limite_usd = limite_horas, limite_usd
        self.planejar = planejar or self._planejar_com_modelo
        self.agir = agir or self._agir_com_modelo
        self.verificar = verificar or self._verificar_com_modelo
        self.replanejar = replanejar or self._replanejar_com_modelo

    # ── o laço ───────────────────────────────────────────────────────────
    async def perseguir(self, objetivo: str) -> Perseguicao:
        if self.atual and self.atual.estado in ("planejando", "rodando"):
            raise RuntimeError(f"já estou perseguindo: {self.atual.objetivo[:60]}")
        self._parar.clear()
        p = Perseguicao(objetivo)
        self.atual = p
        self._registrar(p, f"Objetivo: {objetivo}")

        p.passos = await self.planejar(objetivo)
        if not p.passos:
            p.estado, p.motivo = "desistiu", "não consegui quebrar isso em passos"
            self._registrar(p, p.motivo); return p
        p.estado = "rodando"
        self._registrar(p, "Plano: " + " → ".join(x.titulo for x in p.passos))

        while p.estado == "rodando":
            if self._parar.is_set():
                p.estado, p.motivo = "interrompida", "o João mandou parar"; break
            if (passo := p.pendente) is None:
                p.estado = "concluida"; break
            if p.ciclos >= self.max_ciclos:
                p.estado, p.motivo = "desistiu", f"bati o teto de {self.max_ciclos} ciclos"; break
            if p.horas > self.limite_horas:
                p.estado, p.motivo = "desistiu", f"passei de {self.limite_horas} h"; break
            if p.custo > self.limite_usd:
                p.estado, p.motivo = "desistiu", f"passei de US$ {self.limite_usd:.2f}"; break

            p.ciclos += 1
            passo.estado = "rodando"; passo.tentativas += 1
            self._emitir(p, passo)

            # AGIR — a tentativa que já sabe por que a anterior falhou
            try:
                passo.resultado = await self.agir(p, passo) or ""
            except Exception as e:
                passo.resultado = f"(erro ao agir: {type(e).__name__}: {e})"

            # VERIFICAR — contra o critério escrito antes, não contra a opinião do modelo
            try:
                veredito = await self.verificar(p, passo) or ""
            except Exception as e:
                veredito = f"não consegui verificar: {type(e).__name__}"

            if PRONTO_RX.search(veredito):
                passo.estado, passo.porque_falhou = "ok", ""
                self._registrar(p, f"✓ {passo.titulo}")
                continue

            passo.porque_falhou = veredito.strip()[:300]
            passo.estado = "falhou"
            self._registrar(p, f"… {passo.titulo} não fechou: {passo.porque_falhou[:120]}")

            if passo.tentativas < self.max_tentativas:
                continue                                    # CORRIGIR: tenta de novo sabendo o porquê

            # REPLANEJAR — o problema é o caminho, não o passo
            passo.estado = "desistido"
            if p.replanos >= self.max_replanos:
                p.estado, p.motivo = "desistiu", f"replanejei {p.replanos}× e continuo batendo em «{passo.titulo}»"
                break
            p.replanos += 1
            try:
                novos = await self.replanejar(p, passo) or []
            except Exception as e:
                novos = []
                self._registrar(p, f"replanejar falhou: {type(e).__name__}")
            if not novos:
                p.estado, p.motivo = "desistiu", f"sem outro caminho para «{passo.titulo}»"
                break
            feitos = [x for x in p.passos if x.estado == "ok"]
            p.passos = feitos + novos                        # o que deu certo fica; o resto é caminho novo
            self._registrar(p, f"Replanejei ({p.replanos}/{self.max_replanos}): "
                               + " → ".join(x.titulo for x in novos))

        self._relatorio(p)
        return p

    def interromper(self) -> bool:
        if self.atual and self.atual.estado in ("planejando", "rodando"):
            self._parar.set(); return True
        return False

    def como_vai(self) -> str:
        if not self.atual:
            return "não estou perseguindo nada agora."
        p = self.atual
        return f"«{p.objetivo[:70]}» — {p.resumo()}\n" + "\n".join(x.linha() for x in p.passos)

    # ── as quatro etapas, quando ninguém injeta outra coisa ──────────────
    async def _perguntar(self, prompt: str) -> str:
        pedaços = []
        async for t in self.jaime.ask_stream(prompt, canal="harness"):
            pedaços.append(t)
        return "".join(pedaços).strip()

    async def _planejar_com_modelo(self, objetivo: str) -> list[Passo]:
        r = await self._perguntar(
            f"[harness] Quebre este objetivo em 3 a 7 passos concretos, na ordem: «{objetivo}».\n"
            "Um por linha, no formato `passo | critério`. O CRITÉRIO é como saber que o passo acabou, "
            "verificável (arquivo existe, teste passa, página responde, valor bate). Sem preâmbulo, só as linhas.")
        return ler_passos(r, 7)

    async def _agir_com_modelo(self, p: Perseguicao, passo: Passo) -> str:
        antes = "\n".join(f"- {x.titulo}: {x.estado}" for x in p.passos if x.estado == "ok") or "(nada ainda)"
        correcao = (f"\nA tentativa anterior NÃO fechou porque: {passo.porque_falhou}\n"
                    "Faça diferente desta vez; repetir igual é esperar sorte." if passo.porque_falhou else "")
        return await self._perguntar(
            f"[harness] Objetivo: «{p.objetivo}».\nJá feito:\n{antes}\n\n"
            f"AGORA faça, de verdade, com as suas ferramentas: {passo.titulo}\n"
            f"Critério de pronto: {passo.criterio}{correcao}\n"
            "Aja. No fim, diga em uma linha o que você fez e o que observou.")

    async def _verificar_com_modelo(self, p: Perseguicao, passo: Passo) -> str:
        return await self._perguntar(
            f"[harness] Confira, sem se enganar: o passo «{passo.titulo}» atingiu este critério?\n"
            f"Critério: {passo.criterio}\nO que aconteceu: {passo.resultado[:1200]}\n\n"
            "Se atingiu, verifique de verdade (leia o arquivo, rode o teste, abra a página) e responda só PRONTO. "
            "Se não atingiu, responda o que FALTA em uma frase. Não responda PRONTO por educação.")

    async def _replanejar_com_modelo(self, p: Perseguicao, travado: Passo) -> list[Passo]:
        r = await self._perguntar(
            f"[harness] Objetivo: «{p.objetivo}». Empaquei em «{travado.titulo}» depois de "
            f"{travado.tentativas} tentativas. O que impede: {travado.porque_falhou}\n"
            f"Já está feito: {', '.join(x.titulo for x in p.passos if x.estado == 'ok') or 'nada'}\n\n"
            "Proponha OUTRO caminho para o que falta, em 2 a 5 passos `passo | critério`, um por linha. "
            "Não repita o caminho que travou. Se não houver outro caminho honesto, responda só: SEM SAÍDA.")
        if "SEM SAÍDA" in r.upper() or "SEM SAIDA" in r.upper():
            return []
        return ler_passos(r, 5)

    # ── registro ─────────────────────────────────────────────────────────
    def _emitir(self, p: Perseguicao, passo: Passo) -> None:
        bus.emitir("harness", objetivo=p.objetivo[:80], passo=passo.titulo[:80], estado=p.estado,
                   ciclo=p.ciclos, tentativa=passo.tentativas,
                   feitos=sum(1 for x in p.passos if x.estado == "ok"), total=len(p.passos))

    def _registrar(self, p: Perseguicao, texto: str) -> None:
        bus.emitir("harness", objetivo=p.objetivo[:80], msg=texto[:180], estado=p.estado)
        try:
            self.jaime.vault.diario(f"[harness] {texto}", "Log")
        except Exception:
            pass

    def _relatorio(self, p: Perseguicao) -> None:
        linhas = [f"Persegui «{p.objetivo}» — {p.resumo()}"] + [f"  {x.linha()}" for x in p.passos]
        self._registrar(p, "\n".join(linhas)[:900])
