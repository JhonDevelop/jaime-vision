"""Córtex — decide quem pensa.

`classificar(texto, contexto)` → (tipo, confiança). Tipos: código · pesquisa · redação · decisão · imagem · voz · rotina.
Heurística por palavras-chave, sem chamar modelo: custa zero e roda antes de cada turno. Errou? O placar
corrige com o tempo — o que importa é a política de escolha, não a classificação perfeita.

`escolher(tipo)` → (modelo, motivo). Candidatos por tipo vêm do .env; vence o de maior taxa de acerto no
placar para aquele tipo (suavizada, para candidatos novos não saírem com 0%), com JAIME_CORTEX_EXPLORACAO
de chance de testar outro — sem isso o placar nunca aprenderia sobre o segundo modelo."""
from __future__ import annotations
import random, re
from dataclasses import dataclass
from .placar import Placar

TIPOS = ("código", "pesquisa", "redação", "decisão", "imagem", "voz", "rotina")

PISTAS = {
    "código":   r"\b(c[oó]digo|bug|fun[cç][aã]o|classe|deploy|git|commit|branch|teste[s]?|reposit[oó]rio|compila|build|erro no|stack ?trace|api|endpoint|script|python|javascript|typescript|refator|implementa|programa|sdk|servidor|docker|npm|pip|pytest)\b",
    "pesquisa": r"\b(pesquis|procur|o que [eé]|quem [eé]|quando foi|como funciona|descobr|compara(?:r)? pre[cç]os|not[ií]cia|busca na web|google|wikipedia|fonte|refer[eê]ncia|estuda)\w*",
    "redação":  r"\b(escrev|redig|reda[cç][aã]o|e-?mail|mensagem|texto|post|legenda|roteiro|resum|resume|carta|proposta comercial|descri[cç][aã]o|tradu[zç])\w*",
    "decisão":  r"\b(decid|devo|vale a pena|qual [eé] melhor|pensa bem|compara|pr[oó]s e contras|o que voc[eê] acha|recomenda|escolhe|prefere|estrat[eé]gi)\w*",
    "imagem":   r"\b(imagem|foto|logo|logotipo|thumbnail|desenh|ilustra|arte|banner|capa|gera uma imagem|vetor)\w*",
    "rotina":   r"\b(briefing|que horas|hora [eé]|clima|tempo hoje|lembr|agenda|tarefa|anota|registra|inbox|lembrete|fecha o dia|fecha a semana|di[aá]rio|estado)\w*",
}
# quanto cada pista pesa: sinais fortes decidem sozinhos
PESOS = {"código": 1.0, "pesquisa": 0.9, "redação": 0.8, "decisão": 1.0, "imagem": 1.1, "rotina": 0.9}

CORRECAO_RX = re.compile(r"\b(errado|errou|n[aã]o era isso|n[aã]o [eé] isso|refaz|refaça|de novo|n[aã]o foi isso|tá errado|est[aá] errado|não era assim)\b", re.I)

@dataclass
class Escolha:
    tipo: str
    confianca: float
    modelo: str
    motivo: str
    exploracao: bool = False

def eh_correcao(texto: str) -> bool:
    """'errado', 'não era isso', 'refaz', 'de novo' → o turno anterior foi um erro do modelo anterior."""
    return bool(CORRECAO_RX.search(texto or ""))

def classificar(texto: str, contexto: str = "", canal: str = "cli") -> tuple[str, float]:
    t = (texto or "").lower()
    pontos = {}
    for tipo, rx in PISTAS.items():
        n = len(re.findall(rx, t))
        if n:
            pontos[tipo] = n * PESOS[tipo]
    if not pontos:
        # sem pista nenhuma: conversa curta por voz é "voz"; texto longo sem pista é redação
        if canal == "voice" or len(t.split()) <= 8:
            return "voz", 0.5
        return "redação", 0.3
    tipo, p = max(pontos.items(), key=lambda kv: kv[1])
    total = sum(pontos.values())
    conf = min(0.95, 0.5 + 0.45 * (p / total)) if total else 0.5
    if len(pontos) == 1:
        conf = min(0.95, conf + 0.1)
    return tipo, round(conf, 2)

class Roteador:
    def __init__(self, modelos: dict, placar: Placar, exploracao: float = 0.10, rng: random.Random | None = None):
        """modelos: {"decisao": ..., "codigo": ..., "padrao": ..., "rotina": ...} vindos do .env."""
        self.m = modelos
        self.placar = placar
        self.exploracao = exploracao
        self.rng = rng or random.Random()

    def candidatos(self, tipo: str) -> list[str]:
        m = self.m
        ordem = {
            "código":   [m["codigo"], m["padrao"]],
            "pesquisa": [m["padrao"], m["codigo"]],
            "redação":  [m["padrao"], m["codigo"]],
            "decisão":  [m["decisao"], m["codigo"]],
            "imagem":   [m["padrao"]],                 # OpenAI entra na etapa 3
            "voz":      [m["padrao"], m["rotina"]],
            "rotina":   [m["rotina"], m["padrao"]],
        }
        vistos = []
        for x in ordem.get(tipo, [m["padrao"]]):
            if x and x not in vistos:
                vistos.append(x)
        return vistos

    def escolher(self, tipo: str) -> tuple[str, str, bool]:
        """(modelo, motivo, foi_exploracao)"""
        cands = self.candidatos(tipo)
        if len(cands) > 1 and self.rng.random() < self.exploracao:
            m = self.rng.choice(cands)
            return m, f"exploração ({int(self.exploracao * 100)}%): testando {m} em '{tipo}'", True
        melhor, taxa_melhor = cands[0], -1.0
        for c in cands:
            taxa = self.placar.taxa(c, tipo)
            if taxa > taxa_melhor + 1e-9:
                melhor, taxa_melhor = c, taxa
        n = self.placar.amostras(melhor, tipo)
        motivo = (f"melhor taxa no placar para '{tipo}': {taxa_melhor:.0%} em {n} tarefa(s)" if n
                  else f"padrão para '{tipo}' (placar ainda vazio)")
        return melhor, motivo, False

    def decidir(self, texto: str, contexto: str = "", canal: str = "cli") -> Escolha:
        tipo, conf = classificar(texto, contexto, canal)
        modelo, motivo, expl = self.escolher(tipo)
        return Escolha(tipo, conf, modelo, motivo, expl)

    def explicar(self, texto: str, canal: str = "cli") -> str:
        e = self.decidir(texto, canal=canal)
        linhas = [f"tarefa:    {texto}", f"tipo:      {e.tipo} (confiança {e.confianca:.0%})",
                  f"modelo:    {e.modelo}", f"porquê:    {e.motivo}", "candidatos:"]
        for c in self.candidatos(e.tipo):
            linhas.append(f"  - {c}: {self.placar.linha(c, e.tipo)}")
        return "\n".join(linhas)
