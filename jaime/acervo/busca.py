"""Busca no acervo: achar o especialista certo e trazer o que ele sabe, sem carregar todo mundo.

A busca é por palavra, com pontuação simples e explicável: acerto no nome vale mais que acerto na descrição,
e termo que aparece em muitos agentes vale menos que termo raro (é a ideia do TF-IDF, sem a matemática
pesada — aqui é uma lista de arquivos, não um mecanismo de busca).

Nada de embedding: o acervo tem centenas de itens, não milhões, e busca por palavra em português resolve.
Embedding aqui custaria dependência, tempo de boot e dinheiro para ganhar quase nada."""
from __future__ import annotations
import math, re
from difflib import SequenceMatcher
from dataclasses import dataclass, field
from pathlib import Path

from claude_agent_sdk import tool, create_sdk_mcp_server

VAZIAS = {"para", "com", "uma", "que", "the", "and", "use", "when", "this", "agent", "used", "using",
          "usar", "quando", "sobre", "dos", "das", "por", "você", "voce", "proactively", "expert",
          "specialist", "specializing", "skill", "should", "user", "asks", "help", "task", "tasks"}
LIMITE_CORPO = 14000

# O João fala português; o acervo veio em inglês. Sem esta ponte, "lgpd", "animação" e "banco de dados"
# não achavam nada — e a busca que não acha é pior que não ter busca, porque ele conclui que não sabe fazer.
SINONIMOS = {
    "lgpd": ["gdpr", "privacy", "compliance", "data"], "privacidade": ["privacy", "gdpr", "compliance"],
    "animacao": ["animation", "motion", "animate"], "animação": ["animation", "motion", "animate"],
    "banco": ["database", "sql"], "dados": ["data", "database"], "consulta": ["query"],
    "seguranca": ["security"], "segurança": ["security"], "teste": ["test", "testing", "qa"],
    "testes": ["test", "testing"], "implantar": ["deploy", "deployment"], "implantação": ["deploy"],
    "desempenho": ["performance"], "lentidao": ["performance", "slow"], "lentidão": ["performance", "slow"],
    "lento": ["slow", "performance"], "lenta": ["slow", "performance"],
    "otimizar": ["optimize", "performance"], "rapido": ["fast", "performance"],
    "interface": ["frontend", "ui", "design"], "tela": ["ui", "frontend", "screen"],
    "design": ["design", "ui", "visual"], "bonito": ["design", "visual", "polish"],
    "bonita": ["design", "visual", "polish"], "video": ["video", "remotion"], "vídeo": ["video"],
    "imagem": ["image", "visual"], "texto": ["content", "writing", "copy"],
    "escrever": ["writing", "content", "copy"], "pesquisa": ["research", "search"],
    "pesquisar": ["research", "search"], "arquitetura": ["architecture", "architect"],
    "documentacao": ["documentation", "docs"], "documentação": ["documentation", "docs"],
    "erro": ["error", "bug", "debug"], "falha": ["error", "failure", "debug"],
    "depurar": ["debug", "debugger"], "nuvem": ["cloud"], "rede": ["network"],
    "pagamento": ["payment", "stripe", "billing"], "planilha": ["spreadsheet", "excel", "xlsx"],
    "movel": ["mobile"], "móvel": ["mobile"], "celular": ["mobile", "ios", "android"],
    "acessibilidade": ["accessibility", "wcag", "a11y"], "juridico": ["legal"], "jurídico": ["legal"],
    "contrato": ["contract", "legal"], "produto": ["product"], "negocio": ["business"],
    "negócio": ["business"], "marketing": ["marketing", "seo", "growth"],
}


def _expandir(palavras: list[str]) -> list[str]:
    """Junta o termo em português com os equivalentes em inglês do acervo."""
    saida = list(palavras)
    for w in palavras:
        saida.extend(SINONIMOS.get(w, ()))
    return saida


def _palavras(texto: str) -> list[str]:
    return [p for p in re.findall(r"[0-9a-zà-ÿ]{3,}", (texto or "").lower()) if p not in VAZIAS]


@dataclass
class Item:
    nome: str
    tipo: str                  # agente | skill
    descricao: str
    caminho: Path
    carregado: bool            # está no contexto de todo turno, ou só no acervo?


@dataclass
class Acervo:
    """Índice de tudo que o Jaime sabe fazer — o que está carregado e o que está guardado."""
    repo: Path
    itens: list[Item] = field(default_factory=list)
    _idf: dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        self.reindexar()

    # ── índice ───────────────────────────────────────────────────────────
    def _ler_descricao(self, p: Path) -> str:
        try:
            cab = p.read_text(encoding="utf-8", errors="ignore")[:1200]
        except OSError:
            return ""
        m = re.search(r"^description:\s*(.*)$", cab, re.M)
        return re.sub(r'^"|"$', "", (m.group(1) if m else "")).strip()

    def reindexar(self) -> int:
        self.itens = []
        for pasta, carregado in ((self.repo / ".claude/agents", True),
                                 (self.repo / ".claude/acervo/agents", False)):
            if pasta.is_dir():
                for p in sorted(pasta.glob("*.md")):
                    if p.stem in ("README", "LICENSE"):
                        continue
                    self.itens.append(Item(p.stem, "agente", self._ler_descricao(p), p, carregado))
        sk = self.repo / ".claude/skills"
        if sk.is_dir():
            for d in sorted(sk.iterdir()):
                if d.is_dir() and (d / "SKILL.md").is_file():
                    self.itens.append(Item(d.name, "skill", self._ler_descricao(d / "SKILL.md"),
                                           d / "SKILL.md", True))
        # termo que está em todo mundo não distingue ninguém
        doc = {}
        for it in self.itens:
            for w in set(_palavras(it.nome + " " + it.descricao)):
                doc[w] = doc.get(w, 0) + 1
        n = max(1, len(self.itens))
        self._idf = {w: math.log(1 + n / c) for w, c in doc.items()}
        return len(self.itens)

    # ── busca ────────────────────────────────────────────────────────────
    def buscar(self, termo: str, limite: int = 8) -> list[tuple[Item, float]]:
        alvos = _expandir(_palavras(termo))
        if not alvos:
            return []
        achados = []
        for it in self.itens:
            nome = set(_palavras(it.nome))
            desc = set(_palavras(it.descricao))
            pontos = 0.0
            for w in alvos:
                peso = self._idf.get(w, 1.0)
                if w in nome:
                    pontos += 3.0 * peso
                # parecido nos dois sentidos: "kubernets" digitado tem que achar "kubernetes",
                # e "postgres" tem que achar "postgresql". Só um lado não basta.
                elif any(len(w) >= 4 and len(x) >= 4 and (w in x or x in w) for x in nome):
                    pontos += 1.5 * peso
                # letra trocada ou faltando ("kubernets" → "kubernetes") não é substring de nada:
                # aqui só a semelhança resolve, e é o caso mais comum de quem digita com pressa.
                elif any(len(w) >= 5 and SequenceMatcher(None, w, x).ratio() >= 0.82 for x in nome):
                    pontos += 1.2 * peso
                if w in desc:
                    pontos += 1.0 * peso
            if pontos:
                achados.append((it, round(pontos, 2)))
        achados.sort(key=lambda x: -x[1])
        return achados[:limite]

    def consultar(self, nome: str) -> str:
        alvo = (nome or "").strip().lower()
        for it in self.itens:
            if it.nome.lower() == alvo:
                try:
                    txt = it.caminho.read_text(encoding="utf-8", errors="ignore")
                except OSError as e:
                    return f"não consegui ler: {type(e).__name__}"
                return txt[:LIMITE_CORPO] + (" …(cortei)" if len(txt) > LIMITE_CORPO else "")
        perto = self.buscar(nome, 3)
        return (f"não tenho «{nome}». Mais perto: " + ", ".join(i.nome for i, _ in perto)) if perto \
            else f"não tenho «{nome}» e não achei nada parecido."

    def resumo(self) -> str:
        """Quantos ele REALMENTE carrega por turno, não quantos arquivos existem — a diferença é o ponto."""
        import os
        ag = [i for i in self.itens if i.tipo == "agente"]
        teto = int(os.environ.get("JAIME_AGENTES_MAX", "40") or 0)
        carregados = min(teto, len(ag)) if teto > 0 else len(ag)
        return (f"{len(ag)} agentes no total, {carregados} carregados neste turno e "
                f"{len(ag) - carregados} alcançáveis por busca; {sum(1 for i in self.itens if i.tipo == 'skill')} skills.")


def build_acervo_server(acervo: Acervo):
    @tool("buscar", "ACHA o especialista certo para um assunto, entre todos os agentes e skills que você tem — "
                    "inclusive os que não estão carregados neste turno. Use quando o assunto for específico e "
                    "você quiser saber se já existe alguém seu para isso (Kubernetes, LGPD, Remotion, "
                    "otimizar Postgres). Devolve nome, tipo e do que trata.", {"assunto": str})
    async def buscar(args):
        termo = (args.get("assunto") or "").strip()
        if not termo:
            return _txt("faltou dizer o assunto")
        achados = acervo.buscar(termo)
        if not achados:
            return _txt(f"não achei nada sobre «{termo}» no meu acervo.")
        linhas = [f"- {i.nome} ({i.tipo}{'' if i.carregado else ', no acervo'}): {i.descricao[:130]}"
                  for i, _ in achados]
        return _txt(f"sobre «{termo}»:\n" + "\n".join(linhas)
                    + "\n\nPara usar o conhecimento de um deles agora, chame consultar com o nome.")

    @tool("consultar", "TRAZ o texto inteiro de um agente ou skill do acervo, para você aplicar o que ele sabe "
                       "AGORA, neste turno, sem precisar invocá-lo como subagente. Use depois de buscar, quando "
                       "o especialista não está carregado.", {"nome": str})
    async def consultar(args):
        return _txt(acervo.consultar(args.get("nome") or ""))

    @tool("capacidades", "O que você sabe fazer, em números: quantos agentes estão carregados neste turno, "
                         "quantos estão guardados no acervo e quantas skills você tem.", {})
    async def capacidades(args):
        return _txt(acervo.resumo())

    return create_sdk_mcp_server(name="acervo", version="1.0.0", tools=[buscar, consultar, capacidades])


def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}
