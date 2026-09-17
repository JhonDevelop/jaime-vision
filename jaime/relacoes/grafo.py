"""O grafo de relações — o problema que resolve: `10-Eu/Pessoas.md` é uma lista plana, uma linha por pessoa.

Isso funciona enquanto nada muda. Mas o Gabriel pode trocar de cargo, o Diego pode abrir uma empresa nova, o
João pode ficar sem falar com alguém por meses e voltar a falar — e uma linha só de markdown ou apaga o fato
velho (perde história) ou empilha contradições (o Jaime não sabe qual vale hoje). Este módulo guarda ISSO como
um grafo temporal em SQLite (`~/Jaime/relacoes.db`, `sqlite3` da biblioteca padrão — sem dependência nova):
nós (pessoa, animal, lugar, projeto, organização) e arestas datadas entre eles (parentesco, amizade, sociedade,
dono-de, trabalha-em, mora-em), cada uma com `desde`, `ate` (nulo = ainda vale) e `evidencia` (de onde saiu,
quantas vezes apareceu). Fatos soltos sobre um nó (cargo, onde mora, o que ganha) seguem a mesma régua numa
tabela separada, porque nem tudo é uma relação entre dois nós.

A regra que sustenta tudo: FATO QUE MUDA NÃO VIRA CONTRADIÇÃO. Quando um fato novo substitui um velho (o Gabriel
trocou de cargo), o velho recebe `ate` e continua no histórico — `esquecer` (apagar de verdade) só roda quando
alguém pede explicitamente ("apaga isso, foi engano"), nunca como efeito colateral de uma atualização.

Nunca guarda senha, número de documento, chave ou cartão — filtrado na entrada, com a mesma régua do Espelho
(`jaime/espelho/tracos.py`): se o texto bate com o padrão de segredo, o campo vira vazio e nada é gravado ali."""
from __future__ import annotations
import os, re, sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

CAMINHO_PADRAO = "~/Jaime/relacoes.db"
TIPOS_NO = ("pessoa", "animal", "lugar", "projeto", "organizacao")
RELACOES = ("parentesco", "amizade", "sociedade", "dono-de", "trabalha-em", "mora-em")

# Mesma ideia de tracos.SEGREDO_RX, adaptada: aqui não filtramos fala solta, filtramos CAMPOS que vão virar fato
# permanente num banco — por isso o gatilho de dígitos exige uma sequência longa (documento/cartão/conta), não
# qualquer número de 4 dígitos (senão um salário de "2500" ou um CEP nunca poderiam ser guardados).
SEGREDO_RX = re.compile(
    r"senha|palavra-passe|password|\btoken\b|chave\s*(?:de\s*)?api|api\s*-?\s*key|\bsk-|\bghp_|\bcvv\b|"
    r"cart[aã]o(?:\s*de\s*cr[eé]dito)?|\bcpf\b|\bcnpj\b|\brg\b\s*[:\-]?\s*\d|\d[\d.\-\s]{9,}\d",
    re.I,
)
ARTIGOS_RX = re.compile(r"^(o|a|os|as|meu|minha|meus|minhas|um|uma)\s+", re.I)


def _seguro(texto: str) -> str:
    """Devolve o texto, ou vazio se bater com o padrão de segredo — nunca lança erro, só filtra."""
    t = (texto or "").strip()
    return "" if SEGREDO_RX.search(t) else t


def _lista_apelidos(apelidos) -> list[str]:
    if not apelidos:
        return []
    if isinstance(apelidos, str):
        apelidos = apelidos.split(",")
    vistos, out = set(), []
    for a in apelidos:
        a = (a or "").strip()
        if a and a.lower() not in vistos:
            vistos.add(a.lower()); out.append(a)
    return out


@dataclass
class No:
    id: int
    nome: str
    tipo: str
    apelidos: list[str] = field(default_factory=list)


class Relacoes:
    """Uma instância = uma conexão com o `relacoes.db`. Seguro reabrir: schema é `CREATE ... IF NOT EXISTS`."""

    def __init__(self, caminho: str | Path | None = None):
        self.caminho = Path(caminho or os.environ.get("JAIME_RELACOES_DB", CAMINHO_PADRAO)).expanduser()
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(self.caminho)
        self._con.execute("PRAGMA foreign_keys = ON")
        self._migrar()

    def _migrar(self) -> None:
        self._con.executescript("""
            CREATE TABLE IF NOT EXISTS nos(
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                nome     TEXT NOT NULL,
                tipo     TEXT NOT NULL,
                apelidos TEXT NOT NULL DEFAULT '',
                criado   TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS arestas(
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                origem    INTEGER NOT NULL REFERENCES nos(id),
                destino   INTEGER NOT NULL REFERENCES nos(id),
                relacao   TEXT NOT NULL,
                detalhe   TEXT NOT NULL DEFAULT '',
                desde     TEXT,
                ate       TEXT,
                evidencia TEXT NOT NULL DEFAULT '',
                vezes     INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS fatos(
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                no        INTEGER NOT NULL REFERENCES nos(id),
                chave     TEXT NOT NULL,
                valor     TEXT NOT NULL,
                desde     TEXT,
                ate       TEXT,
                evidencia TEXT NOT NULL DEFAULT '',
                vezes     INTEGER NOT NULL DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_arestas_origem ON arestas(origem);
            CREATE INDEX IF NOT EXISTS idx_arestas_destino ON arestas(destino);
            CREATE INDEX IF NOT EXISTS idx_fatos_no ON fatos(no);
        """)
        self._con.commit()

    def fechar(self) -> None:
        self._con.close()

    # ── nós ──────────────────────────────────────────────────────────────
    def _no_por_id(self, id_no: int) -> No | None:
        row = self._con.execute("SELECT id, nome, tipo, apelidos FROM nos WHERE id = ?", (id_no,)).fetchone()
        if not row:
            return None
        return No(row[0], row[1], row[2], _lista_apelidos(row[3]))

    def _achar_no(self, nome_ou_apelido: str) -> No | None:
        """Match exato de nome ou apelido, sem artigo ('o Rafael' → 'rafael'). `quem_e` faz o match difuso."""
        alvo = ARTIGOS_RX.sub("", (nome_ou_apelido or "").strip()).strip().lower()
        if not alvo:
            return None
        for row in self._con.execute("SELECT id, nome, tipo, apelidos FROM nos"):
            nomes = [row[1].lower()] + [a.lower() for a in _lista_apelidos(row[3])]
            if alvo in nomes:
                return No(row[0], row[1], row[2], _lista_apelidos(row[3]))
        return None

    def _resolver_ou_criar(self, nome: str, tipo: str = "pessoa") -> int:
        no = self._achar_no(nome)
        return no.id if no else self.lembrar_pessoa(nome, tipo)

    def lembrar_pessoa(self, nome: str, tipo: str = "pessoa", apelidos=None, evidencia: str = "",
                        desde: str | None = None) -> int:
        """Cria o nó, ou funde nele se já existir (por nome ou apelido) — nunca duplica a mesma pessoa.

        `tipo` serve para qualquer um dos cinco (pessoa, animal, lugar, projeto, organizacao); o nome do
        método ficou `lembrar_pessoa` porque é o caso mais comum, não porque só sirva para gente."""
        nome = (nome or "").strip()
        if not nome:
            raise ValueError("nome vazio")
        if tipo not in TIPOS_NO:
            tipo = "pessoa"
        novos_apelidos = _lista_apelidos(apelidos)
        existente = self._achar_no(nome)
        if existente:
            fundidos = _lista_apelidos(existente.apelidos + novos_apelidos +
                                       ([nome] if nome.lower() != existente.nome.lower() else []))
            self._con.execute("UPDATE nos SET apelidos = ? WHERE id = ?", (",".join(fundidos), existente.id))
            self._con.commit()
            return existente.id
        id_no = self._con.execute(
            "INSERT INTO nos(nome, tipo, apelidos, criado) VALUES (?, ?, ?, ?)",
            (nome, tipo, ",".join(novos_apelidos), datetime.now().isoformat(timespec="seconds")),
        ).lastrowid
        self._con.commit()
        return id_no

    # ── arestas (relação entre dois nós) ───────────────────────────────────
    def ligar(self, a: str, b: str, relacao: str, detalhe: str = "", desde: str | None = None,
              evidencia: str = "", tipo_a: str = "pessoa", tipo_b: str = "pessoa") -> int:
        """Liga `a` a `b` por `relacao` (parentesco, amizade, sociedade, dono-de, trabalha-em, mora-em).

        Se já existe uma aresta ABERTA (`ate` nulo) com o mesmo par e relação:
          - mesmo `detalhe` de novo → só soma evidência (não duplica linha);
          - `detalhe` diferente (trocou de emprego, por exemplo) → fecha a antiga em `desde` da nova e abre
            uma aresta nova. A antiga fica no histórico; nada é apagado."""
        detalhe, evidencia = _seguro(detalhe), _seguro(evidencia)
        id_a = self._resolver_ou_criar(a, tipo_a)
        id_b = self._resolver_ou_criar(b, tipo_b)
        quando = desde or date.today().isoformat()
        existente = self._con.execute(
            "SELECT id, detalhe, evidencia, vezes FROM arestas WHERE origem=? AND destino=? AND relacao=? AND ate IS NULL",
            (id_a, id_b, relacao),
        ).fetchone()
        if existente:
            eid, detalhe_atual, ev_atual, vezes = existente
            if (detalhe or "") == (detalhe_atual or ""):
                nova_ev = _somar_evidencia(ev_atual, evidencia)
                self._con.execute("UPDATE arestas SET vezes = ?, evidencia = ? WHERE id = ?", (vezes + 1, nova_ev, eid))
                self._con.commit()
                return eid
            self._con.execute("UPDATE arestas SET ate = ? WHERE id = ?", (quando, eid))
        novo_id = self._con.execute(
            "INSERT INTO arestas(origem, destino, relacao, detalhe, desde, ate, evidencia, vezes) "
            "VALUES (?, ?, ?, ?, ?, NULL, ?, 1)",
            (id_a, id_b, relacao, detalhe, quando, evidencia),
        ).lastrowid
        self._con.commit()
        return novo_id

    # ── fatos soltos (atributo de um nó só) ─────────────────────────────────
    def fato(self, nome: str, chave: str, valor: str, desde: str | None = None, evidencia: str = "",
              tipo: str = "pessoa") -> int:
        """Mesma regra da aresta, mas para um atributo de um nó só (cargo, onde mora, o que ganha).
        Devolve 0 sem gravar nada se `valor` bater com o padrão de segredo."""
        valor_limpo = _seguro(valor)
        if not valor_limpo:
            return 0
        evidencia = _seguro(evidencia)
        id_no = self._resolver_ou_criar(nome, tipo)
        quando = desde or date.today().isoformat()
        existente = self._con.execute(
            "SELECT id, valor, evidencia, vezes FROM fatos WHERE no=? AND chave=? AND ate IS NULL",
            (id_no, chave),
        ).fetchone()
        if existente:
            fid, valor_atual, ev_atual, vezes = existente
            if valor_limpo == valor_atual:
                nova_ev = _somar_evidencia(ev_atual, evidencia)
                self._con.execute("UPDATE fatos SET vezes = ?, evidencia = ? WHERE id = ?", (vezes + 1, nova_ev, fid))
                self._con.commit()
                return fid
            self._con.execute("UPDATE fatos SET ate = ? WHERE id = ?", (quando, fid))
        novo_id = self._con.execute(
            "INSERT INTO fatos(no, chave, valor, desde, ate, evidencia, vezes) VALUES (?, ?, ?, ?, NULL, ?, 1)",
            (id_no, chave, valor_limpo, quando, evidencia),
        ).lastrowid
        self._con.commit()
        return novo_id

    # ── leitura ──────────────────────────────────────────────────────────
    def quem_e(self, apelido: str) -> dict | None:
        """Resolve 'o Rafael', 'meu sócio' etc. para o nó certo. Match exato de apelido/nome vence; senão,
        prefixo; senão, substring — sempre no nó com mais evidência quando há empate."""
        alvo = ARTIGOS_RX.sub("", (apelido or "").strip()).strip().lower()
        if not alvo:
            return None
        melhor: tuple[int, int, int] | None = None   # (score, evidencia_total, id) — maior vence
        melhor_id = None
        for row in self._con.execute("SELECT id, nome, tipo, apelidos FROM nos"):
            nomes = [row[1].lower()] + [a.lower() for a in _lista_apelidos(row[3])]
            score = 0
            for n in nomes:
                if n == alvo:
                    score = max(score, 3)
                elif n.startswith(alvo) or alvo.startswith(n):
                    score = max(score, 2)
                elif alvo in n:
                    score = max(score, 1)
            if score == 0:
                continue
            evid = self._con.execute(
                "SELECT COALESCE(SUM(vezes),0) FROM arestas WHERE origem=? OR destino=?", (row[0], row[0])
            ).fetchone()[0]
            chave = (score, evid, row[0])
            if melhor is None or chave > melhor:
                melhor, melhor_id = chave, row[0]
        return self.sobre_id(melhor_id) if melhor_id else None

    def sobre(self, nome: str) -> dict | None:
        """Quem é: o nó, as relações e fatos que valem hoje, e o histórico do que já valeu."""
        no = self._achar_no(nome)
        return self.sobre_id(no.id) if no else None

    def sobre_id(self, id_no: int) -> dict | None:
        no = self._no_por_id(id_no)
        if not no:
            return None
        vigentes, historico = [], []
        for eid, relacao, detalhe, desde, ate, evidencia, vezes, outro_nome, outro_tipo, direcao in self._con.execute(
            """
            SELECT a.id, a.relacao, a.detalhe, a.desde, a.ate, a.evidencia, a.vezes, n.nome, n.tipo, 'saida'
              FROM arestas a JOIN nos n ON n.id = a.destino WHERE a.origem = ?
            UNION ALL
            SELECT a.id, a.relacao, a.detalhe, a.desde, a.ate, a.evidencia, a.vezes, n.nome, n.tipo, 'entrada'
              FROM arestas a JOIN nos n ON n.id = a.origem WHERE a.destino = ? AND a.origem != a.destino
            """,
            (id_no, id_no),
        ):
            item = {"relacao": relacao, "detalhe": detalhe, "com": outro_nome, "tipo_com": outro_tipo,
                    "direcao": direcao, "desde": desde, "ate": ate, "evidencia": evidencia, "vezes": vezes}
            (vigentes if ate is None else historico).append(item)
        fatos_vigentes, fatos_historico = [], []
        for chave, valor, desde, ate, evidencia, vezes in self._con.execute(
            "SELECT chave, valor, desde, ate, evidencia, vezes FROM fatos WHERE no = ?", (id_no,)
        ):
            item = {"chave": chave, "valor": valor, "desde": desde, "ate": ate, "evidencia": evidencia, "vezes": vezes}
            (fatos_vigentes if ate is None else fatos_historico).append(item)
        return {"id": no.id, "nome": no.nome, "tipo": no.tipo, "apelidos": no.apelidos,
                "relacoes": vigentes, "relacoes_historico": historico,
                "fatos": fatos_vigentes, "fatos_historico": fatos_historico}

    def texto_sobre(self, d: dict | None) -> str:
        """Frase curta pra devolver ao modelo/voz a partir do dict de `sobre`/`quem_e`."""
        if not d:
            return ""
        partes = [f"{d['nome']} ({d['tipo']})" + (f", também chamado de {', '.join(d['apelidos'])}" if d["apelidos"] else "") + "."]
        for r in d["relacoes"]:
            partes.append(f"{r['relacao']} de {r['com']}" if r["direcao"] == "saida" else f"{r['com']} {r['relacao']} de {d['nome']}")
        for f in d["fatos"]:
            partes.append(f"{f['chave']}: {f['valor']}")
        if d["relacoes_historico"] or d["fatos_historico"]:
            partes.append(f"(histórico: {len(d['relacoes_historico'])} relação(ões) e {len(d['fatos_historico'])} fato(s) que já valeram e mudaram)")
        return " ".join(partes)

    # ── esquecer (apagar de verdade — pedido explícito, não é "fato mudou") ─
    def esquecer(self, nome: str, relacao: str | None = None, com: str | None = None, chave: str | None = None) -> int:
        no = self._achar_no(nome)
        if not no:
            return 0
        id_no = no.id
        if chave:
            n = self._con.execute("DELETE FROM fatos WHERE no = ? AND chave = ?", (id_no, chave)).rowcount
        elif relacao or com:
            id_com = None
            if com:
                outro = self._achar_no(com)
                id_com = outro.id if outro else None
            q = "DELETE FROM arestas WHERE (origem = ? OR destino = ?)"
            params: list = [id_no, id_no]
            if relacao:
                q += " AND relacao = ?"; params.append(relacao)
            if id_com is not None:
                q += " AND (origem = ? OR destino = ?)"; params += [id_com, id_com]
            n = self._con.execute(q, params).rowcount
        else:
            n = self._con.execute("DELETE FROM arestas WHERE origem = ? OR destino = ?", (id_no, id_no)).rowcount
            n += self._con.execute("DELETE FROM fatos WHERE no = ?", (id_no,)).rowcount
            n += self._con.execute("DELETE FROM nos WHERE id = ?", (id_no,)).rowcount
        self._con.commit()
        return n


def _somar_evidencia(atual: str, nova: str) -> str:
    if not nova:
        return atual
    partes = [p.strip() for p in (atual or "").split(";") if p.strip()]
    if nova not in partes:
        partes.append(nova)
    return "; ".join(partes[-6:])
