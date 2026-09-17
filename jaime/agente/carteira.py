"""A carteira de iniciativas — de "tive uma ideia" até "entreguei", sem ninguém mandar.

As peças já existiam soltas: a Mente pensa quando ocioso, as vontades escolhem o que puxar, o harness
persegue objetivo, o estudo abre problema, a evolução propõe melhoria em si mesmo. O que faltava era o fio
que liga tudo — uma coisa onde uma ideia entra e de onde um resultado sai.

O ciclo, e por que cada etapa existe:

    IMAGINAR    pensamento que se repete vira iniciativa. Pensar três vezes no mesmo problema e não fazer
                nada é ruminação, não inteligência.
    PROJETAR    antes de qualquer código, uma especificação: problema, entrada, saída, casos de erro e
                CRITÉRIO DE ACEITE. Sem critério escrito antes, "ficou bom" é opinião de quem fez.
    VALIDAR     um crítico procura buraco na spec — retorno vazio, erro não tratado, requisito ambíguo.
                É a única trava do ciclo, e é de qualidade, não de permissão.
    PRODUZIR    o harness persegue a spec, delegando a mão de obra ao hemisfério esquerdo num worktree.
    TESTAR      o pytest roda POR FORA do agente. Ele não pode declarar sucesso sozinho: se pudesse,
                declararia sempre.
    LANÇAR      reversível por padrão. Projeto do João vira PR; melhoria dele mesmo entra por autoevolução.
    MEDIR       deu certo sobe Criação e Maestria; deu errado abre problema no estudo. É assim que a
                carteira fica melhor com o tempo, em vez de repetir o mesmo erro com assunto diferente.

A carteira mora em `01-Estado/Iniciativas.md`, em Markdown, porque o João tem que poder ler, discordar e
riscar uma linha na mão."""
from __future__ import annotations
import re, time
from dataclasses import dataclass, field
from datetime import date

NOTA = "01-Estado/Iniciativas.md"
ETAPAS = ("imaginada", "projetada", "validada", "produzindo", "testando", "lancada", "medida", "abandonada")
# Quantas vezes um assunto precisa aparecer no pensamento antes de virar iniciativa. Uma vez é ideia solta;
# três é padrão — e padrão é o que merece trabalho.
REPETICOES = 3

LINHA_RX = re.compile(  # o 5º campo é "gasto/orçamento": sem a barra aqui, a carteira voltava VAZIA do disco
    r"^\|\s*([^|]+?)\s*\|\s*(\w+)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([\d./]*)\s*\|", re.M)


@dataclass
class Iniciativa:
    titulo: str
    etapa: str = "imaginada"
    criterio: str = ""                 # como saber que deu certo. Escrito ANTES de começar.
    porque: str = ""                   # de onde veio a ideia; sem isso é capricho
    orcamento_usd: float = 2.0
    gasto_usd: float = 0.0
    spec: str = ""                     # caminho da especificação, quando existir
    resultado: str = ""
    criada: str = field(default_factory=lambda: date.today().isoformat())

    def linha(self) -> str:
        return (f"| {self.titulo[:70]} | {self.etapa} | {self.criterio[:80]} | "
                f"{self.porque[:60]} | {self.gasto_usd:.2f}/{self.orcamento_usd:.2f} |")

    @property
    def viva(self) -> bool:
        return self.etapa not in ("medida", "abandonada")

    @property
    def estourou(self) -> bool:
        return self.gasto_usd > self.orcamento_usd


class Carteira:
    """O que ele decidiu fazer por conta própria, em que pé está e quanto já custou."""

    def __init__(self, vault):
        self.vault = vault
        self.itens: list[Iniciativa] = []
        self._carregar()

    # ── imaginar: pensamento repetido vira iniciativa ────────────────────
    def assunto_recorrente(self, pensamentos: list[str], minimo: int = REPETICOES) -> str:
        """Que assunto voltou pelo menos `minimo` vezes? É esse que merece virar trabalho."""
        # Assunto é substantivo, não verbo: "pensei" aparecia nos três pensamentos e ganhava de "escrow".
        # Corta pelas terminações verbais mais comuns em português, mais uma lista curta do que não diz nada.
        vazias = {"joão", "jaime", "projeto", "coisa", "sobre", "ainda", "mais", "pode", "está", "tudo",
                  "outro", "outra", "hoje", "ontem", "amanhã", "muito", "pouco", "nada", "algum", "nesse"}
        verbo = re.compile(r"(ei|ou|ar|er|ir|ando|endo|indo|ado|ido|ava|iam|mos)$")
        contagem: dict[str, int] = {}
        for p in pensamentos:
            for w in set(re.findall(r"[a-zà-ÿ]{5,}", (p or "").lower())):
                if w not in vazias and not verbo.search(w):
                    contagem[w] = contagem.get(w, 0) + 1
        if not contagem:
            return ""
        assunto, vezes = max(contagem.items(), key=lambda x: x[1])
        return assunto if vezes >= minimo else ""

    def imaginar(self, titulo: str, porque: str, criterio: str = "", orcamento_usd: float = 2.0) -> Iniciativa:
        if (ja := self.achar(titulo)):
            return ja
        i = Iniciativa(titulo.strip()[:120], "imaginada", criterio.strip()[:200], porque.strip()[:200],
                       orcamento_usd)
        self.itens.append(i)
        self._salvar()
        self._diario(f"Iniciativa nova: {i.titulo} — porque {i.porque}")
        return i

    # ── andar pelo ciclo ─────────────────────────────────────────────────
    def avancar(self, titulo: str, etapa: str, resultado: str = "", gasto_usd: float = 0.0) -> str:
        i = self.achar(titulo)
        if i is None:
            return f"não tenho iniciativa «{titulo}»"
        if etapa not in ETAPAS:
            return f"etapa desconhecida; use: {', '.join(ETAPAS)}"
        if etapa in ("produzindo", "testando") and not i.criterio:
            return ("essa iniciativa não tem critério de aceite escrito — sem ele eu não sei dizer se deu "
                    "certo, e vou achar que deu. Escreva o critério antes de produzir.")
        i.gasto_usd += max(0.0, gasto_usd)
        anterior, i.etapa = i.etapa, etapa
        if resultado:
            i.resultado = resultado[:300]
        if i.estourou and i.viva:
            i.etapa = "abandonada"
            i.resultado = f"parei: passei do orçamento (US$ {i.gasto_usd:.2f} de {i.orcamento_usd:.2f})"
            self._salvar(); self._diario(f"Larguei «{i.titulo}»: {i.resultado}")
            return i.resultado
        self._salvar()
        self._diario(f"«{i.titulo}»: {anterior} → {etapa}" + (f" — {resultado[:120]}" if resultado else ""))
        return f"{i.titulo}: {anterior} → {etapa}"

    def achar(self, titulo: str) -> Iniciativa | None:
        alvo = (titulo or "").strip().lower()
        for i in self.itens:
            if i.titulo.lower() == alvo or alvo in i.titulo.lower():
                return i
        return None

    def vivas(self) -> list[Iniciativa]:
        return [i for i in self.itens if i.viva]

    def resumo(self) -> str:
        if not self.itens:
            return "carteira vazia: não tenho nenhuma iniciativa minha em andamento."
        vivas = self.vivas()
        gasto = sum(i.gasto_usd for i in self.itens)
        linhas = [f"{len(vivas)} em andamento de {len(self.itens)} · US$ {gasto:.2f} gastos"]
        linhas += [f"  [{i.etapa}] {i.titulo}" + (f" — {i.resultado[:60]}" if i.resultado else "")
                   for i in vivas[:8]]
        return "\n".join(linhas)

    # ── o vault é a fonte, porque o João tem que poder riscar uma linha ──
    def _carregar(self) -> None:
        try:
            txt = self.vault.read(NOTA) or ""
        except Exception:
            return
        for titulo, etapa, criterio, porque, custo in LINHA_RX.findall(txt):
            if titulo.lower() in ("iniciativa", "---") or etapa not in ETAPAS:
                continue
            gasto, _, orc = (custo or "0/2").partition("/")
            try:
                g, o = float(gasto or 0), float(orc or 2)
            except ValueError:
                g, o = 0.0, 2.0
            self.itens.append(Iniciativa(titulo, etapa, criterio, porque, o, g))

    def _salvar(self) -> None:
        linhas = ["# Iniciativas — o que EU decidi fazer", "",
                  "> Mantido por `jaime/agente/carteira.py`. Cada linha é algo que eu resolvi puxar sozinho,",
                  "> com o critério de sucesso escrito ANTES e o orçamento que me dei. Risque uma linha se",
                  "> discordar: eu releio daqui e paro.", "",
                  "| iniciativa | etapa | critério de aceite | por quê | gasto/orçamento |",
                  "|---|---|---|---|---|"]
        linhas += [i.linha() for i in self.itens]
        linhas += ["", f"- atualizado: {time.strftime('%Y-%m-%d %H:%M')}",
                   f"- etapas: {' → '.join(ETAPAS[:7])}"]
        try:
            self.vault.write(NOTA, "\n".join(linhas) + "\n")
        except Exception:
            pass

    def _diario(self, texto: str) -> None:
        try:
            self.vault.diario(f"[iniciativa] {texto}", "Decisões")
        except Exception:
            pass
