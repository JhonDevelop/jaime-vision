"""Modelos de bloco (templates) e o uso deles — a parte da interface que o Jaime melhora sozinho, com trava.

- Modelo = receita de bloco com nome ("financas", "agenda", "painel-bub"…). O Jaime pode criar e melhorar modelos,
  mas todo modelo passa pelo CONTRATO antes de ser gravado: renderiza em TODAS as superfícies (cockpit, janela,
  terminal, óculos, visor, falante) sem erro, tem resumo falado e texto não vazios, respeita os limites. Cada versão
  fica guardada; `reverter` volta a anterior. Modelo embutido não é sobrescrito — o Jaime cria uma variante.
- Uso = o que o João faz com os blocos. Aberto pelo Jaime e fechado em menos de 5 s = rejeitado. Os números viram
  sinais da autoevolução (jaime/evolucao.py), para ele parar de abrir o que não serve e melhorar o que é usado.
"""
from __future__ import annotations
import copy, json, time
from pathlib import Path
from .modelo import Bloco, BlocoInvalido, validar
from .superficies import PERFIS, adaptar, linhas_texto, resumo_falado

REJEICAO_S = 5.0

EMBUTIDOS: dict[str, dict] = {
    "maquina": {"tipo": "metricas", "titulo": "Máquina", "fonte": "sistema.maquina", "prioridade": 1},
    "relogio": {"tipo": "texto", "titulo": "Agora", "fonte": "relogio", "prioridade": 0},
    "financas": {"tipo": "metricas", "titulo": "Finanças do mês", "fonte": "financas.resumo", "prioridade": 2},
    "financas-mensal": {"tipo": "grafico", "titulo": "Entradas × saídas", "fonte": "financas.mensal", "prioridade": 1},
    "tarefas": {"tipo": "lista", "titulo": "Tarefas abertas", "fonte": "tarefas.abertas", "prioridade": 2},
    "agenda": {"tipo": "lista", "titulo": "Próximos lembretes", "fonte": "agenda.lembretes", "prioridade": 2},
    "estado": {"tipo": "texto", "titulo": "J.A.I.M.E agora", "fonte": "jaime.estado", "prioridade": 1},
    "placar": {"tipo": "tabela", "titulo": "Placar dos modelos", "fonte": "cortex.placar", "prioridade": 0},
    "espacial": {"tipo": "status", "titulo": "Mãos no ar", "fonte": "espacial.estado", "prioridade": 0},
}
# sinônimos falados → nome do modelo
APELIDOS = {"máquina": "maquina", "computador": "maquina", "sistema": "maquina", "hora": "relogio", "relógio": "relogio",
            "finanças": "financas", "dinheiro": "financas", "saldo": "financas", "gráfico das finanças": "financas-mensal",
            "tarefa": "tarefas", "afazeres": "tarefas", "inbox": "tarefas", "lembretes": "agenda", "compromissos": "agenda",
            "estado": "estado", "status": "estado", "placar": "placar", "modelos": "placar", "mãos": "espacial", "gestos": "espacial"}


def contrato(b: Bloco) -> list[str]:
    """Problemas que impedem o bloco de valer como modelo. Lista vazia = passou."""
    erros = []
    for perfil, caps in PERFIS.items():
        try:
            d = adaptar(b, caps, perfil)
        except Exception as e:
            erros.append(f"{perfil}: quebrou ao adaptar ({type(e).__name__})"); continue
        if caps.visual and not d.get("linhas") and not d.get("conteudo"):
            erros.append(f"{perfil}: nada para mostrar")
        if caps.voz and not (d.get("fala") or "").strip(". "):
            erros.append(f"{perfil}: resumo falado vazio")
        if not caps.html and "conteudo" in d and b.tipo == "html":
            erros.append(f"{perfil}: recebeu html sem ser web")
    try:
        if len(resumo_falado(b)) > 400:
            erros.append("resumo falado longo demais (>400 caracteres)")
        linhas_texto(b, 40, 4)
    except Exception as e:
        erros.append(f"texto: {type(e).__name__}")
    return erros


class Modelos:
    def __init__(self, pasta: Path | None = None, fontes=None):
        self.arquivo = Path(pasta).expanduser() / "modelos.json" if pasta else None
        self.fontes = fontes
        self.proprios: dict[str, list[dict]] = {}          # nome → versões (a última vale)
        if self.arquivo and self.arquivo.exists():
            try:
                self.proprios = json.loads(self.arquivo.read_text(encoding="utf-8")).get("modelos", {})
            except json.JSONDecodeError:
                self.proprios = {}

    def _salvar(self) -> None:
        if self.arquivo:
            self.arquivo.parent.mkdir(parents=True, exist_ok=True)
            self.arquivo.write_text(json.dumps({"v": 1, "modelos": self.proprios}, ensure_ascii=False, indent=1), encoding="utf-8")

    def nomes(self) -> list[str]:
        return sorted(set(EMBUTIDOS) | set(self.proprios))

    def resolver_nome(self, falado: str) -> str | None:
        t = (falado or "").strip().lower()
        t = t.removeprefix("de ").removeprefix("da ").removeprefix("do ").removeprefix("das ").removeprefix("dos ").strip()
        if t in self.proprios or t in EMBUTIDOS:
            return t
        return APELIDOS.get(t) or next((n for n in self.nomes() if n in t or t in n), None)

    def receita(self, nome: str) -> dict:
        if nome in self.proprios:
            return copy.deepcopy(self.proprios[nome][-1]["bloco"])
        if nome in EMBUTIDOS:
            return copy.deepcopy(EMBUTIDOS[nome])
        raise KeyError(nome)

    def instanciar(self, nome: str, **extra) -> dict:
        d = self.receita(nome)
        d.update({k: v for k, v in extra.items() if v is not None})
        d.setdefault("id", nome)
        d["modelo"] = nome
        return d

    def salvar(self, nome: str, bloco: dict, autor: str = "jaime", motivo: str = "") -> tuple[bool, str]:
        """Grava uma versão nova SÓ se passar no contrato. Nome de modelo embutido não é sobrescrito."""
        nome = (nome or "").strip().lower().replace(" ", "-")[:40]
        if not nome:
            return False, "modelo precisa de nome"
        if nome in EMBUTIDOS:
            return False, f"'{nome}' é embutido — crie uma variante (ex.: {nome}-v2)"
        try:
            b = validar({**bloco, "id": bloco.get("id") or nome})
        except BlocoInvalido as e:
            return False, f"inválido: {e}"
        if b.fonte and self.fontes is not None and b.fonte not in self.fontes:
            return False, f"fonte desconhecida: {b.fonte}"
        if not b.fonte and b.privado:
            return False, "modelo estático não pode carregar conteúdo privado (use uma fonte privada)"
        if not b.fonte and linhas_texto(b) == ["(sem dados ainda)"]:
            return False, "modelo estático sem conteúdo (dê conteúdo ou uma fonte viva)"
        erros = contrato(b)
        if erros:
            return False, "não passou no contrato: " + "; ".join(erros[:4])
        versoes = self.proprios.setdefault(nome, [])
        d = b.to_dict()
        for k in ("criado", "atualizado", "versao", "v"):
            d.pop(k, None)
        versoes.append({"bloco": d, "autor": autor, "motivo": motivo[:200], "quando": time.strftime("%Y-%m-%d %H:%M")})
        del versoes[:-10]
        self._salvar()
        return True, f"modelo '{nome}' v{len(versoes)} salvo"

    def reverter(self, nome: str) -> tuple[bool, str]:
        v = self.proprios.get(nome)
        if not v or len(v) < 2:
            return False, "não há versão anterior"
        v.pop(); self._salvar()
        return True, f"'{nome}' voltou para a versão de {v[-1]['quando']}"

    def remover(self, nome: str) -> bool:
        ok = self.proprios.pop(nome, None) is not None
        self._salvar()
        return ok


class Uso:
    """Estatística por chave (modelo › fonte › tipo): aberturas, rejeições rápidas, tempo de vida."""
    def __init__(self, pasta: Path | None = None):
        self.arquivo = Path(pasta).expanduser() / "uso.json" if pasta else None
        self.dados: dict[str, dict] = {}
        if self.arquivo and self.arquivo.exists():
            try:
                self.dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.dados = {}

    @staticmethod
    def chave(b: Bloco) -> str:
        return b.modelo or b.fonte or f"tipo:{b.tipo}"

    def _c(self, b: Bloco) -> dict:
        return self.dados.setdefault(self.chave(b), {"abertos": 0, "rejeitados": 0, "vida_s": 0.0, "pelo_jaime": 0, "fechados": 0})

    def abriu(self, b: Bloco, t: float) -> None:
        c = self._c(b); c["abertos"] += 1
        if not b.criado_por.startswith("joao"):
            c["pelo_jaime"] += 1
        self._gravar()

    def fechou(self, b: Bloco, t: float, motivo: str = "") -> None:
        c = self._c(b); vida = max(0.0, t - b.criado)
        c["fechados"] += 1; c["vida_s"] += vida
        pelo_joao = motivo.startswith("fechado em") or motivo in ("pedido", "voz")
        if pelo_joao and not b.criado_por.startswith("joao") and vida < REJEICAO_S:
            c["rejeitados"] += 1
        self._gravar()

    def _gravar(self) -> None:
        if self.arquivo:
            self.arquivo.parent.mkdir(parents=True, exist_ok=True)
            self.arquivo.write_text(json.dumps(self.dados, ensure_ascii=False), encoding="utf-8")

    def sinais(self, minimo: int = 3) -> str:
        """Linhas para a autoevolução: o que ele abre e o João rejeita; o que o João mais usa."""
        linhas = []
        for k, c in sorted(self.dados.items(), key=lambda kv: -kv[1]["rejeitados"]):
            if c["pelo_jaime"] >= minimo and c["rejeitados"] / max(c["pelo_jaime"], 1) >= 0.5:
                linhas.append(f"- bloco '{k}': o João fechou em <{REJEICAO_S:.0f} s {c['rejeitados']} de {c['pelo_jaime']} vezes que eu abri sozinho")
        usados = sorted(((c["abertos"], k) for k, c in self.dados.items() if c["abertos"] >= minimo), reverse=True)[:3]
        if usados:
            linhas.append("- blocos mais usados: " + ", ".join(f"{k} ({n}×)" for n, k in usados))
        return "\n".join(linhas)
