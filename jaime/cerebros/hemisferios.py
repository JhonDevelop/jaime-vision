"""Os três cérebros do J.A.I.M.E — um córtex central e dois hemisférios que trabalham em paralelo.

    CENTRAL (Claude)    decide, conversa com o João, orquestra, escreve no vault. É o único que fala.
    ESQUERDO (Codex)    a técnica: código, execução, teste, refatoração, mão de obra repetitiva.
    DIREITO (Gemini)    o evolutivo: pesquisa longa, alternativas, crítica do próprio trabalho, criação.

Não é metáfora: cada hemisfério é um terminal de verdade no Maestri (`jaime/equipe`), com preset,
pasta e papel próprios, criado sob demanda e reaproveitado enquanto estiver vivo. O central não é um
terminal — é o próprio processo do Jaime.

O roteamento aprende. Cada entrega volta com "deu certo?" e vira linha em `01-Estado/Cerebros.md`;
quando um hemisfério erra seguido num tipo de trabalho, o peso dele naquele tipo cai e o outro passa
a ser escolhido. É por isso que a tabela fica no vault em Markdown: o João lê e corrige na mão."""
from __future__ import annotations
import re, time
from dataclasses import dataclass, field

NOTA = "01-Estado/Cerebros.md"
PISO, TETO = 0.15, 1.0          # peso de um hemisfério num tipo de trabalho
PREMIO, MULTA = 0.08, 0.16      # acertar sobe pouco; errar desce o dobro (confiança custa a voltar)

@dataclass(frozen=True)
class Hemisferio:
    id: str
    nome: str
    preset: str                  # preset do Maestri: claude | codex | antigravity | opencode | shell
    funcao: str                  # o que ele faz, em uma frase
    tipos: tuple[str, ...]       # os tipos de trabalho que são a casa dele
    cor: str

CENTRAL = Hemisferio("central", "Central", "claude",
                     "decide, conversa com o João, orquestra os outros dois e escreve no vault",
                     ("decisao", "conversa", "orquestracao", "vault", "resposta"), "#38e1ff")
ESQUERDO = Hemisferio("esquerdo", "Esquerdo", "codex",
                      "a técnica: escreve código, executa, testa, refatora e faz a mão de obra repetitiva",
                      ("codigo", "execucao", "teste", "refatoracao", "operacao", "build"), "#7d5cff")
DIREITO = Hemisferio("direito", "Direito", "antigravity",
                     "o evolutivo: pesquisa longa, levanta alternativas, critica o trabalho pronto e cria",
                     ("pesquisa", "alternativa", "critica", "criacao", "evolucao", "estudo"), "#ffb347")
HEMISFERIOS = (CENTRAL, ESQUERDO, DIREITO)
POR_ID = {h.id: h for h in HEMISFERIOS}

# Palavras que revelam o tipo de trabalho num pedido em português. Só o que é inequívoco:
# na dúvida o Central fica com o pedido, porque é ele quem fala com o João.
PISTAS: dict[str, tuple[str, ...]] = {
    "codigo": ("implementa", "programa", "escreve o código", "corrige o bug", "refatora", "migra", "script"),
    "teste": ("testa", "teste", "pytest", "cobertura", "valida o código"),
    "execucao": ("roda", "executa", "instala", "compila", "build", "deploy"),
    "operacao": ("renomeia", "organiza os arquivos", "converte", "em lote", "repetitiv"),
    "pesquisa": ("pesquisa", "investiga", "levanta", "compara", "descobre", "busca na internet"),
    "alternativa": ("alternativa", "outra forma", "outro jeito", "e se", "opções"),
    "critica": ("revisa", "critica", "avalia", "o que está errado", "revisão"),
    "criacao": ("cria", "inventa", "desenha", "propõe", "imagina"),
    "evolucao": ("melhora você", "se melhora", "evolui", "aprimora a si"),
    "estudo": ("estuda", "aprende sobre", "entende"),
}

LINHA_RX = re.compile(r"^\|\s*([a-z]+)\s*\|\s*([a-z_]+)\s*\|\s*([0-9.]+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|", re.M)


def tipo_do_pedido(texto: str) -> str:
    """Que tipo de trabalho é este pedido? 'decisao' quando não dá para afirmar outra coisa."""
    t = (texto or "").lower()
    achados = [(tipo, min(t.find(p) for p in ps if p in t))
               for tipo, ps in PISTAS.items() if any(p in t for p in ps)]
    return min(achados, key=lambda x: x[1])[0] if achados else "decisao"


@dataclass
class Cerebros:
    """Escolhe o hemisfério para cada trabalho, acorda o terminal dele no Maestri e aprende com o resultado."""
    vault: object
    equipe: object | None = None
    pesos: dict[tuple[str, str], float] = field(default_factory=dict)   # (hemisfério, tipo) → peso
    acertos: dict[tuple[str, str], int] = field(default_factory=dict)
    erros: dict[tuple[str, str], int] = field(default_factory=dict)

    def __post_init__(self):
        self._carregar()

    # ── escolha ──────────────────────────────────────────────────────────
    def peso(self, h: str, tipo: str) -> float:
        base = 1.0 if tipo in POR_ID[h].tipos else 0.25
        return round(min(TETO, max(PISO, self.pesos.get((h, tipo), base))), 3)

    def escolher(self, pedido_ou_tipo: str) -> Hemisferio:
        """O hemisfério de maior peso para este trabalho. Empate fica com o Central: ele é quem fala."""
        tipo = pedido_ou_tipo if pedido_ou_tipo in {t for h in HEMISFERIOS for t in h.tipos} else tipo_do_pedido(pedido_ou_tipo)
        melhor = max(HEMISFERIOS, key=lambda h: (self.peso(h.id, tipo), h.id == "central"))
        return melhor

    def por_que(self, pedido: str) -> str:
        tipo = tipo_do_pedido(pedido)
        h = self.escolher(tipo)
        return f"{h.nome} ({h.preset}) — trabalho de {tipo}, peso {self.peso(h.id, tipo):.2f}"

    # ── aprendizado: acertou sobe, errou desce o dobro ───────────────────
    def registrar(self, hemisferio: str, tipo: str, ok: bool) -> float:
        if hemisferio not in POR_ID:
            return 0.0
        k = (hemisferio, tipo)
        atual = self.pesos.get(k, self.peso(hemisferio, tipo))
        novo = min(TETO, atual + PREMIO) if ok else max(PISO, atual - MULTA)
        self.pesos[k] = novo
        (self.acertos if ok else self.erros)[k] = (self.acertos if ok else self.erros).get(k, 0) + 1
        self._salvar()
        return round(novo, 3)

    # ── acordar o terminal do hemisfério no Maestri ──────────────────────
    def nome_do_filho(self, h: Hemisferio) -> str:
        return f"cerebro-{h.id}"

    def acordar(self, hemisferio: str, missao: str = "") -> str:
        """Garante um terminal vivo para o hemisfério. O Central não tem terminal: é o próprio Jaime."""
        h = POR_ID.get(hemisferio)
        if h is None:
            return f"hemisfério desconhecido: {hemisferio}"
        if h.id == "central":
            return "O Central sou eu; não preciso acordar ninguém."
        if self.equipe is None:
            return "Maestri indisponível: sem equipe para acordar o hemisfério."
        nome = self.nome_do_filho(h)
        try:
            if any(getattr(f, "nome", "") == nome for f in getattr(self.equipe, "vivos", [])):
                return f"{h.nome} já está acordado."
            tipo = "codigo" if h.id == "esquerdo" else "pesquisa"
            self.equipe.criar(nome=nome, missao=missao or h.funcao, tipo=tipo, preset=h.preset,
                              papel_extra=f"Você é o hemisfério {h.nome} do J.A.I.M.E: {h.funcao}. "
                                          f"Quem fala com o João é o Central; você entrega a ele.")
            return f"{h.nome} acordado ({h.preset})."
        except Exception as e:
            return f"não consegui acordar o {h.nome}: {type(e).__name__}: {e}"

    def delegar(self, hemisferio: str, tarefa: str) -> str:
        h = POR_ID.get(hemisferio)
        if h is None or h.id == "central":
            return "O Central resolve sozinho; não delego para mim mesmo."
        if self.equipe is None:
            return "Maestri indisponível."
        self.acordar(h.id, tarefa)
        try:
            return str(self.equipe.delegar(self.nome_do_filho(h), tarefa))
        except Exception as e:
            self.registrar(h.id, tipo_do_pedido(tarefa), ok=False)
            return f"o {h.nome} não respondeu: {type(e).__name__}"

    # ── estado, para o prompt e para o universo ──────────────────────────
    def vivos(self) -> set[str]:
        nomes = {getattr(f, "nome", "") for f in getattr(self.equipe, "vivos", [])} if self.equipe else set()
        return {h.id for h in HEMISFERIOS if h.id == "central" or self.nome_do_filho(h) in nomes}

    def estado(self) -> list[dict]:
        acordados = self.vivos()
        saida = []
        for h in HEMISFERIOS:
            tipos = {t: self.peso(h.id, t) for t in h.tipos}
            a = sum(v for (hh, _), v in self.acertos.items() if hh == h.id)
            e = sum(v for (hh, _), v in self.erros.items() if hh == h.id)
            saida.append({"id": h.id, "nome": h.nome, "preset": h.preset, "funcao": h.funcao, "cor": h.cor,
                          "acordado": h.id in acordados, "acertos": a, "erros": e,
                          "forte_em": max(tipos, key=tipos.get) if tipos else "", "tipos": tipos})
        return saida

    def resumo(self) -> str:
        return " · ".join(f"{d['nome']}({d['preset']}){'' if d['acordado'] else ' dormindo'}" for d in self.estado())

    # ── persistência: Markdown, porque o João tem que poder corrigir na mão ──
    def _carregar(self) -> None:
        try:
            txt = self.vault.read(NOTA) or ""
        except Exception:
            return
        for h, tipo, peso, a, e in LINHA_RX.findall(txt):
            if h in POR_ID:
                self.pesos[(h, tipo)] = float(peso)
                self.acertos[(h, tipo)] = int(a); self.erros[(h, tipo)] = int(e)

    def _salvar(self) -> None:
        linhas = ["# Cérebros — os três hemisférios do J.A.I.M.E", "",
                  "> Mantido por `jaime/cerebros/hemisferios.py`. O peso sobe quando o hemisfério entrega bem",
                  "> aquele tipo de trabalho e cai o dobro quando erra. Corrija na mão se discordar: eu releio daqui.", ""]
        for h in HEMISFERIOS:
            linhas += [f"## {h.nome} · {h.preset}", f"> {h.funcao}", "",
                       "| hemisfério | tipo | peso | acertos | erros |", "|---|---|---|---|---|"]
            tipos = sorted({t for (hh, t) in self.pesos if hh == h.id} | set(h.tipos))
            for t in tipos:
                k = (h.id, t)
                linhas.append(f"| {h.id} | {t} | {self.peso(h.id, t):.2f} | "
                              f"{self.acertos.get(k, 0)} | {self.erros.get(k, 0)} |")
            linhas.append("")
        linhas.append(f"- atualizado: {time.strftime('%Y-%m-%d %H:%M')}")
        try:
            self.vault.write(NOTA, "\n".join(linhas) + "\n")
        except Exception:
            pass
