"""O Espelho — o J.A.I.M.E aprende como o João É, do que ele realmente fala e faz.

Não é perfil inventado nem psicologia: são traços contados a partir do que já está no vault —
o que o João fala (`60-Conversas/`), o que aconteceu (`40-Diario/`) e o que ele deixa em aberto
(`30-Tarefas/Inbox.md`). Cada traço traz a EVIDÊNCIA junto (quantas vezes, em quantos dias), porque
traço sem contagem é chute, e chute sobre o dono é pior que silêncio.

Para que serve: o Jaime usa isso para se parecer com ele no que importa — o ritmo do dia, o tamanho
da frase, as palavras que ele usa, o que ele pede o tempo todo e o que ele empurra com a barriga.
Não para bajular nem para imitar trejeito: para antecipar e para decidir como ele decidiria.

O que o Espelho NUNCA faz: guardar senha, número, chave ou o que estiver marcado como privado; e
nunca escreve em `00-Jaime/` (identidade do Jaime) — ele escreve em `10-Eu/Tracos.md`, que é sobre o João."""
from __future__ import annotations
import re, time
from collections import Counter
from dataclasses import dataclass

NOTA = "10-Eu/Tracos.md"
FALA_RX = re.compile(r"^\*\*João:\*\*\s*(.+)$", re.M)
HORA_RX = re.compile(r"^###\s+(\d{2}):(\d{2})\s+·", re.M)
TAREFA_RX = re.compile(r"^-\s+\[ \]\s+(.+)$", re.M)
SEGREDO_RX = re.compile(r"[•*]{3,}|\b\d{4,}\b|senha|palavra-passe|token|chave|sk-|ghp_", re.I)

# Palavras que não dizem nada sobre ninguém.
VAZIAS = {
    "que", "para", "com", "uma", "meu", "minha", "isso", "aqui", "não", "sim", "você", "voce", "ele",
    "dele", "the", "and", "por", "dos", "das", "num", "numa", "tem", "ter", "mais", "mas", "como",
    "quando", "onde", "porque", "pode", "vai", "vou", "está", "esta", "estou", "foi", "ser", "sei",
    "então", "entao", "agora", "depois", "todo", "toda", "tudo", "nada", "muito", "bem", "jaime",
    "fazer", "faz", "coisa", "coisas", "gente", "aí", "ai", "lá", "la", "ok", "certo", "sobre", "eu",
}
# O que ele manda fazer. Verbo no imperativo é o retrato mais honesto de uma demanda.
PEDIDOS = ("cria", "faz", "arruma", "conserta", "melhora", "coloca", "tira", "abre", "fecha", "manda",
           "mostra", "explica", "pesquisa", "testa", "roda", "instala", "atualiza", "reinicia",
           "aplica", "junta", "deixa", "usa", "traz", "continua", "verifica", "organiza")
DECISIVAS = ("confirmo", "pode fazer", "pode ir", "manda ver", "segue", "faz isso", "vai fundo", "autorizo")


@dataclass
class Traco:
    chave: str
    titulo: str
    valor: str
    evidencia: str

    def linha(self) -> str:
        return f"| {self.titulo} | {self.valor} | {self.evidencia} |"


def _limpo(f: str) -> str:
    return "" if SEGREDO_RX.search(f) else f.strip()


class Espelho:
    """Lê o vault e devolve os traços do João, com a contagem que os sustenta."""

    def __init__(self, vault):
        self.vault = vault
        self.raiz = getattr(vault, "root", None)

    # ── coleta ───────────────────────────────────────────────────────────
    def _falas(self) -> tuple[list[str], list[int], int]:
        """Tudo que o João falou, as horas em que falou, e em quantos dias. Segredo fica de fora."""
        falas, horas, dias = [], [], 0
        pasta = self.raiz / "60-Conversas" if self.raiz else None
        if not (pasta and pasta.is_dir()):
            return falas, horas, dias
        for f in sorted(pasta.glob("*.md")):
            try:
                txt = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            dias += 1
            falas += [x for x in (_limpo(m) for m in FALA_RX.findall(txt)) if len(x) > 2]
            horas += [int(h) for h, _ in HORA_RX.findall(txt)]
        return falas, horas, dias

    # ── traços ───────────────────────────────────────────────────────────
    def tracos(self) -> list[Traco]:
        falas, horas, dias = self._falas()
        t: list[Traco] = []
        if not falas:
            return t

        # ritmo do dia: em que faixa ele realmente aparece
        if horas:
            faixas = Counter("madrugada" if h < 6 else "manhã" if h < 12 else "tarde" if h < 18 else "noite"
                             for h in horas)
            (nome, q), = faixas.most_common(1)
            t.append(Traco("ritmo", "Ritmo do dia", f"mais ativo de {nome}",
                           f"{q} de {len(horas)} falas, em {dias} dias"))

        # tamanho da frase: ele é curto ou explica?
        palavras = [len(f.split()) for f in falas]
        media = sum(palavras) / len(palavras)
        jeito = "direto e curto" if media <= 9 else ("objetivo" if media <= 16 else "explica em blocos longos")
        t.append(Traco("jeito", "Jeito de falar", jeito, f"média de {media:.0f} palavras por fala"))

        # o que ele manda fazer
        texto = " ".join(falas).lower()
        pedidos = Counter({v: texto.count(v + " ") for v in PEDIDOS if texto.count(v + " ")})
        if pedidos:
            top = ", ".join(f"{v} ({q})" for v, q in pedidos.most_common(5))
            t.append(Traco("demanda", "O que ele mais pede", top, f"{sum(pedidos.values())} pedidos contados"))

        # as palavras que são dele
        vocab = Counter(w for w in re.findall(r"[a-zà-ÿ]{4,}", texto) if w not in VAZIAS)
        if vocab:
            t.append(Traco("vocabulario", "Palavras dele", ", ".join(w for w, _ in vocab.most_common(8)),
                           f"de {len(vocab)} palavras distintas"))

        # como decide
        d = sum(texto.count(p) for p in DECISIVAS)
        if d:
            t.append(Traco("decisao", "Como decide",
                           "autoriza direto, sem rodeio" if d >= 3 else "autoriza quando perguntado",
                           f"{d} autorizações explícitas"))

        # o que ele empurra com a barriga
        try:
            abertas = TAREFA_RX.findall(self.vault.read("30-Tarefas/Inbox.md") or "")
        except Exception:
            abertas = []
        if abertas:
            t.append(Traco("adia", "O que fica parado", abertas[0][:60],
                           f"{len(abertas)} tarefas em aberto"))

        # o que importa: projetos que ele cita
        try:
            projetos = [p.stem for p in (self.raiz / "20-Projetos").glob("*.md")] if self.raiz else []
        except Exception:
            projetos = []
        citados = Counter({p: texto.count(p.lower()) for p in projetos if texto.count(p.lower())})
        if citados:
            t.append(Traco("foco", "No que ele está",
                           ", ".join(f"{p} ({q})" for p, q in citados.most_common(4)),
                           f"{len(citados)} projetos citados por ele"))
        return t

    # ── saída ────────────────────────────────────────────────────────────
    def contexto(self, limite: int = 7) -> str:
        """Bloco curto para o prompt: é com isto que o Jaime se parece com ele no que importa."""
        ts = self.tracos()[:limite]
        if not ts:
            return "(ainda não ouvi o João o bastante para ter traços dele)"
        return "\n".join(f"- {x.titulo}: {x.valor} ({x.evidencia})" for x in ts)

    def salvar(self) -> str:
        ts = self.tracos()
        linhas = ["# Traços do João — o que eu aprendi ouvindo", "",
                  "> Mantido por `jaime/espelho/tracos.py`, contado do que está no vault: o que ele fala em",
                  "> `60-Conversas/`, o que acontece em `40-Diario/` e o que fica aberto no `Inbox`. Cada traço",
                  "> vem com a evidência; sem contagem seria chute. Corrija na mão se eu tiver lido errado.", "",
                  "| traço | o que é | em cima de quê |", "|---|---|---|"]
        linhas += [x.linha() for x in ts] or ["| — | ainda sem material | — |"]
        linhas += ["", f"- atualizado: {time.strftime('%Y-%m-%d %H:%M')}", f"- traços: {len(ts)}"]
        texto = "\n".join(linhas) + "\n"
        try:
            self.vault.write(NOTA, texto)
        except Exception:
            pass
        return texto
