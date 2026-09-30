"""Rostos das pessoas da vida do João — cortesia e contexto, NUNCA chave.

Cada pessoa tem um identificador (`joao`, `ana`, `gabriel`…), um nome, se é o dono, a relação com o João ("irmã",
"sócio") e até 12 amostras do rosto. A tela (face-api no navegador, nesta máquina) extrai um descritor de 128
números; a comparação acontece aqui. Tudo fica em `~/Jaime/identidade/rosto.json` (0600) e nunca volta para a página.

O que o rosto faz: "Identidade confirmada, bem-vindo, senhor", "É a Ana, sua irmã", e libera o relatório de saúde
do "ativar monitor" só para o dono. As memórias de cada pessoa moram no grafo de relações (`~/Jaime/relacoes.db`),
ligadas pelo nome — o rosto é só a forma de reconhecer quem está ali.
O que ele NÃO faz: destrancar o cérebro (isso é a palavra-passe), aprovar ação do Vigia, dar privilégio a ninguém.
Foto é fácil de imitar. Cadastrar o rosto de outra pessoa é com o consentimento dela — o Jaime lembra isso ao João.
"""
from __future__ import annotations
import json, math, os, re, time, unicodedata
from pathlib import Path

ARQ = Path(os.environ.get("JAIME_ROSTO_ARQ", "~/Jaime/identidade/rosto.json")).expanduser()
LIMIAR = float(os.environ.get("JAIME_ROSTO_LIMIAR", "0.5"))    # distância euclidiana do face-api (0.6 é o padrão frouxo deles)
MAX_AMOSTRAS = 12
DONO = "joao"


def _valido(d) -> bool:
    return isinstance(d, (list, tuple)) and len(d) == 128 and all(isinstance(x, (int, float)) and math.isfinite(x) for x in d)


def distancia(a, b) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def ident(nome: str) -> str:
    t = unicodedata.normalize("NFD", (nome or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40]


class Rostos:
    def __init__(self, arq: Path | None = None, limiar: float = LIMIAR):
        self.arq, self.limiar = Path(arq or ARQ), limiar

    # ── armazenamento ────────────────────────────────
    def _ler(self) -> dict:
        try:
            d = json.loads(self.arq.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if "pessoas" in d:
            return d["pessoas"]
        if d.get("amostras"):                      # formato antigo: só o João
            return {DONO: {"nome": "João", "dono": True, "relacao": "", "amostras": d["amostras"]}}
        return {}

    def _gravar(self, pessoas: dict) -> None:
        self.arq.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.arq.parent, 0o700)
        except OSError:
            pass
        self.arq.write_text(json.dumps({"atualizado": time.time(), "pessoas": pessoas}, ensure_ascii=False), encoding="utf-8")
        os.chmod(self.arq, 0o600)

    def pessoas(self) -> list[dict]:
        return [{"id": k, "nome": v.get("nome", k), "dono": bool(v.get("dono")), "relacao": v.get("relacao", ""),
                 "amostras": len([a for a in v.get("amostras", []) if _valido(a)])} for k, v in self._ler().items()]

    def amostras(self, pessoa: str = DONO) -> list[list[float]]:
        return [a for a in self._ler().get(pessoa, {}).get("amostras", []) if _valido(a)]

    @property
    def cadastrado(self) -> bool:
        return any(p["amostras"] for p in self.pessoas())

    @property
    def dono_cadastrado(self) -> bool:
        return any(p["amostras"] and p["dono"] for p in self.pessoas())

    def cadastrar(self, descritores: list, pessoa: str = DONO, nome: str = "João", dono: bool | None = None, relacao: str = "") -> int:
        novos = [list(map(float, d)) for d in descritores if _valido(d)]
        if not novos:
            raise ValueError("nenhum descritor válido (esperado 128 números)")
        pessoa = ident(pessoa) or DONO
        dados = self._ler()
        atual = dados.get(pessoa, {})
        dono = (pessoa == DONO) if dono is None else dono
        dados[pessoa] = {"nome": nome or atual.get("nome", pessoa), "dono": dono, "relacao": relacao or atual.get("relacao", ""),
                         "amostras": ([a for a in atual.get("amostras", []) if _valido(a)] + novos)[-MAX_AMOSTRAS:]}
        self._gravar(dados)
        return len(dados[pessoa]["amostras"])

    def esquecer(self, pessoa: str | None = None) -> bool:
        """Sem argumento: esquece TODOS (compatível com o "esquece meu rosto" antigo quando só havia o João)."""
        if pessoa is None:
            try:
                self.arq.unlink()
            except FileNotFoundError:
                pass
            return True
        dados = self._ler()
        if dados.pop(ident(pessoa), None) is None:
            return False
        self._gravar(dados)
        return True

    # ── reconhecimento ───────────────────────────────
    def verificar(self, descritor) -> dict:
        """{'status': 'confirmado'(dono) | 'conhecido'(outra pessoa) | 'desconhecido' | 'sem_cadastro' | 'invalido',
            'pessoa': id | None, 'nome': str | None, 'relacao': str, 'distancia': float | None}"""
        vazio = {"pessoa": None, "nome": None, "relacao": "", "distancia": None}
        if not _valido(descritor):
            return {"status": "invalido", **vazio}
        dados = self._ler()
        melhor = None
        for pid, p in dados.items():
            for a in p.get("amostras", []):
                if _valido(a):
                    d = distancia(descritor, a)
                    if melhor is None or d < melhor[0]:
                        melhor = (d, pid, p)
        if melhor is None:
            return {"status": "sem_cadastro", **vazio}
        d, pid, p = melhor
        if d > self.limiar:
            return {"status": "desconhecido", **vazio, "distancia": round(d, 3)}
        return {"status": "confirmado" if p.get("dono") else "conhecido", "pessoa": pid, "nome": p.get("nome", pid),
                "relacao": p.get("relacao", ""), "distancia": round(d, 3)}
