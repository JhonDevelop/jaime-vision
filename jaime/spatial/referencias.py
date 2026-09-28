"""Fase 2 — voz contextual: o que "isso", "esses", "a da esquerda" querem dizer AGORA.

O resolvedor olha as seleções recentes (gesto, HUD ou ferramenta) com TTL e devolve:
- `ok`        → um ou mais objetos, com a linha de contexto que vai ao modelo;
- `ambiguo`   → a pergunta de UMA frase ("Qual deles: BUB ou SeventyOne?"); a resposta seguinte desambigua;
- `nenhum`    → havia dêixis mas nada selecionado dentro do TTL;
- `sem_referencia` → a frase não aponta para nada espacial (o turno segue intocado).

Cuidado com o Vigia: "isso" sozinho, com lote pendente, é APROVAÇÃO ("faz isso", "isso") — o orquestrador só chama
o resolvedor quando não há lote aguardando resposta. E frase curta de concordância ("isso!", "isso mesmo") nunca
vira pergunta de desambiguação.

Nada aqui chama LLM: é regra + estado da cena, em microssegundos, antes do turno."""
from __future__ import annotations
import re, time, unicodedata
from dataclasses import dataclass, field
from typing import Callable
from .core import SpatialCore, SpatialObject


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")).strip()


# casados no texto em minúsculas COM acento: "está" (verbo) não pode virar "esta" (demonstrativo) — "Jaime, está aí?"
SING = r"(?<![\w])(isso|isto|esse|essa|este|esta|aquilo|aquele|aquela)(?![\wáéíóúâêôãõç])"
PLURAL = r"(?<![\w])(esses|essas|estes|estas|aqueles|aquelas|os dois|as duas|ambos|ambas)(?![\wáéíóúâêôãõç])"
LADO = {"esquerda": ("x", min), "direita": ("x", max), "cima": ("y", min), "baixo": ("y", max)}
LADO_RX = r"\b(?:da|a|na|de|do|mais a|mais pra|pra|para a)\s+(esquerda|direita|cima|baixo)\b"
ORDINAL = {"primeir": 0, "segund": 1, "terceir": 2, "ultim": -1}
ACAO_RX = r"\b(abr[ea]|abrir|fech[ae]|mov[ea]|mover|lev[ae]|compar[ae]|mostr[ae]|apag[ae]|jog[ae]|arquiv[ae]|manda|envi[ae]|renomei[ae]|coloc[ae]|poe|junt[ae]|lig[ae]|conect[ae]|analis[ae]|resum[ae]|descrev[ae]|explic[ae])"
CONCORDANCIA = {"isso", "isso mesmo", "isso ai", "e isso", "exato isso", "isso isso", "isso sim", "e isso ai"}
# imperativo/infinitivo de verdade: "para" sozinho é preposição ("um atalho para os gestos") e não desliga nada
DESLIGAR_RX = re.compile(r"\b(desliga|desligue|desligar|pare|parar|encerra|encerre|encerrar)\b.{0,12}\b(o rastreamento|rastreamento|as maos|os gestos|gestos)\b"
                         r"|\bpara de rastrear\b|\bcancela(r)? o gesto\b")


@dataclass
class Resolucao:
    status: str
    objetos: list[SpatialObject] = field(default_factory=list)
    pergunta: str = ""
    motivo: str = ""
    idade_s: float = 0.0

    def contexto(self) -> str:
        """A linha que entra em `[contexto: …]` do turno — IDs, rótulos e idade; nunca conteúdo de arquivo."""
        if self.status == "ok" and self.objetos:
            partes = [f"{o.label or o.id} ({o.kind}, id {o.id}" + (f", recurso {o.resource_ref}" if o.resource_ref else "") + ")"
                      for o in self.objetos]
            alvo = "'isso'" if len(partes) == 1 else "'esses'"
            return (f"espacial (se ele se refere ao que está na tela): {alvo} = {' e '.join(partes)}, "
                    f"selecionado há {self.idade_s:.0f} s ({self.motivo})")
        return ""


class Resolvedor:
    def __init__(self, core: SpatialCore, ttl_s: float = 20.0, janela_ambigua_s: float = 1.5,
                 atores: Callable[[], tuple[str, ...]] = lambda: ("joao",), relogio: Callable[[], float] = time.monotonic,
                 confianca_min: float = 0.85):
        self.core, self.ttl_s, self.janela_ambigua_s = core, ttl_s, janela_ambigua_s
        self.atores, self.relogio, self.confianca_min = atores, relogio, confianca_min
        self.pendente: tuple[list[str], float, str] | None = None  # (candidatos, quando, pedido original) da última pergunta

    # ── classificação da frase ──────────────────────────
    @staticmethod
    def pede_desligar(texto: str) -> bool:
        return bool(DESLIGAR_RX.search(_norm(texto)))

    @staticmethod
    def tem_referencia(texto: str) -> bool:
        a = (texto or "").lower()
        return bool(re.search(SING, a) or re.search(PLURAL, a) or re.search(LADO_RX, _norm(texto)))

    def _recentes(self) -> list[tuple[SpatialObject, float, float]]:
        """(objeto, idade, confiança) das seleções dentro do TTL, mais nova primeiro, sem repetir objeto."""
        agora = self.relogio()
        vistos, out = set(), []
        todas = []
        for ator in self.atores():
            todas += list(self.core.selecoes.get(ator, []))
        for s in sorted(todas, key=lambda s: s.quando, reverse=True):
            idade = agora - s.quando
            if idade > self.ttl_s or s.object_id in vistos or s.object_id not in self.core.objects:
                continue
            vistos.add(s.object_id)
            out.append((self.core.objects[s.object_id], idade, s.confianca))
        return out

    def _por_nome(self, t: str) -> list[SpatialObject]:
        achados = []
        for o in self.core.objects.values():
            rot = _norm(o.label or "")
            if len(rot) >= 3 and re.search(rf"\b{re.escape(rot)}\b", t):
                achados.append(o)
        return achados

    @staticmethod
    def _pergunta(objs: list[SpatialObject]) -> str:
        nomes = [o.label or o.id for o in objs[:3]]
        return "Qual deles: " + (", ".join(nomes[:-1]) + " ou " + nomes[-1] if len(nomes) > 1 else nomes[0]) + "?"

    # ── resolução ──────────────────────────────────────
    def resolver(self, texto: str) -> Resolucao:
        t = _norm(texto)
        if not t or t in CONCORDANCIA:
            return Resolucao("sem_referencia")
        # resposta a uma pergunta de desambiguação feita há pouco
        if self.pendente and self.relogio() - self.pendente[1] <= self.ttl_s:
            cands = [self.core.objects[i] for i in self.pendente[0] if i in self.core.objects]
            # só uma resposta CURTA desambigua; qualquer outra frase encerra a pergunta pendente
            escolhido = self._escolher_entre(t, cands) if len(t.split()) <= 6 else None
            if not escolhido and len(t.split()) > 6:
                self.pendente = None
            if escolhido:
                pedido = self.pendente[2]
                self.pendente = None
                self.core.select("joao", escolhido.id, 1.0, origem="voz")
                return Resolucao("ok", [escolhido], motivo=f"ele respondeu à sua pergunta de desambiguação; o pedido era «{pedido[:80]}» — execute-o")
        a = (texto or "").lower()                        # dêixis com acento; o resto normalizado
        nomeados = self._por_nome(t)
        tem_deixis = bool(re.search(SING, a) or re.search(PLURAL, a) or re.search(LADO_RX, t))
        if not tem_deixis:
            # citar "BUB" numa conversa não é apontar para o objeto BUB da tela: sem dêixis, o turno segue intocado
            return Resolucao("sem_referencia")
        rec = self._recentes()
        plural = bool(re.search(PLURAL, a)) or bool(re.search(r"\bcompar", t))
        lado = re.search(LADO_RX, t)
        acao = bool(re.search(ACAO_RX, t))
        if lado and not acao:
            return Resolucao("sem_referencia")               # "vira à esquerda na rua" não é sobre a tela (resposta a pergunta já tratada acima)
        if lado:
            base = [o for o, _, _ in rec] if len(rec) >= 2 else [o for o in self.core.objects.values() if o.kind != "lixeira"]
            if not base:
                return Resolucao("nenhum", motivo=lado.group(0))
            eixo, f = LADO[lado.group(1)]
            o = f(base, key=lambda o: getattr(o.position, eixo))
            return Resolucao("ok", [o], motivo=f"o mais à {lado.group(1)}" if eixo == "x" else f"o de {lado.group(1)}")
        if nomeados:
            return Resolucao("ok", nomeados, motivo="nomeado na fala")
        if not rec:
            # "isso" em português aponta muito mais para a conversa do que para a tela: sem seleção recente,
            # o turno segue intocado (nada de "pergunte o que é" em toda frase com "isso")
            return Resolucao("nenhum", motivo=(re.search(PLURAL, a) or re.search(SING, a)).group(0))
        if plural:
            if len(rec) < 2:
                return Resolucao("ambiguo", [rec[0][0]], pergunta=f"Só tenho {rec[0][0].label or rec[0][0].id} selecionado. Com qual outro?",
                                 motivo="plural com uma seleção")
            n = 2 if re.search(r"\b(os dois|as duas|ambos|ambas|compar)", t) else min(len(rec), 4)
            return Resolucao("ok", [o for o, _, _ in rec[:n]], motivo="seleções recentes", idade_s=rec[0][1])
        o, idade, conf = rec[0]
        empate = len(rec) > 1 and abs(rec[1][1] - idade) <= self.janela_ambigua_s
        duas_maos = len({v for v in self.core.selected.values() if v}) > 1 and len(rec) > 1 and rec[1][1] <= self.janela_ambigua_s
        if acao and (empate or duas_maos):
            cands = [x for x, _, _ in rec[:3]]
            self.pendente = ([c.id for c in cands], self.relogio(), texto)
            return Resolucao("ambiguo", cands, pergunta=self._pergunta(cands), motivo="duas seleções quase juntas")
        if acao and conf < self.confianca_min:
            self.pendente = ([o.id], self.relogio(), texto)
            return Resolucao("ambiguo", [o], pergunta=f"Você quer dizer {o.label or o.id}?", motivo="seleção com confiança baixa")
        return Resolucao("ok", [o], motivo=f"seleção por gesto" if conf >= self.confianca_min else "seleção fraca", idade_s=idade)

    def _escolher_entre(self, t: str, cands: list[SpatialObject]) -> SpatialObject | None:
        if not cands:
            return None
        por_nome = [o for o in cands if len(_norm(o.label or "")) >= 3 and _norm(o.label or "") in t]
        if len(por_nome) == 1:
            return por_nome[0]
        for chave, i in ORDINAL.items():
            if re.search(rf"\b(o|a)?\s*{chave}[oa]?\b", t):
                return cands[i] if -len(cands) <= i < len(cands) else None
        lado = re.search(LADO_RX, t)
        if lado:
            eixo, f = LADO[lado.group(1)]
            return f(cands, key=lambda o: getattr(o.position, eixo))
        if len(cands) == 1 and re.search(r"\b(sim|isso|esse mesmo|essa mesma|pode|exato|e esse|e essa)\b", t):
            return cands[0]
        return None


class ContextoVoz:
    """A ponte com o orquestrador: `antes_do_turno(texto, contexto)` → (resposta_curta | None, contexto)."""
    def __init__(self, servico, resolvedor: Resolvedor, agendar: Callable | None = None):
        self.servico, self.resolvedor = servico, resolvedor
        self.agendar = agendar
        self.ultimas: list[dict] = []

    def antes_do_turno(self, texto: str, contexto: str = "") -> tuple[str | None, str]:
        if Resolvedor.pede_desligar(texto) and self.servico is not None:
            if self.agendar:
                self.agendar(self.servico.desligar_rastreamento("João pediu por voz"))
            return "Rastreamento de mãos desligado.", contexto
        r = self.resolvedor.resolver(texto)
        self.ultimas = (self.ultimas + [{"texto": texto[:80], "status": r.status, "objetos": [o.id for o in r.objetos]}])[-20:]
        if r.status in ("sem_referencia", "nenhum"):
            return None, contexto
        if self.servico is not None:
            try:
                self.servico.emitir("espacial", evento="voice.reference", status=r.status,
                                    objetos=[o.id for o in r.objetos], pergunta=r.pergunta, motivo=r.motivo)
            except Exception:
                pass
        if r.status == "ambiguo":
            return r.pergunta, contexto
        linha = r.contexto()
        return None, (f"{contexto}; {linha}" if contexto else linha) if linha else contexto
