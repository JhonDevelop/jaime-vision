"""Reconhecimento do rosto do João — cortesia e contexto, NUNCA chave.

A tela (face-api no navegador, nesta máquina) extrai um descritor de 128 números do rosto na câmera e manda ao
servidor local; a comparação acontece aqui, contra o que o João cadastrou ("Jaime, aprende meu rosto"). Os
descritores ficam só em `~/Jaime/identidade/rosto.json` (0600) e nunca voltam para a página.

O que o rosto faz: "Identidade confirmada, bem-vindo" e libera o relatório de saúde do "ativar monitor".
O que ele NÃO faz: destrancar o cérebro (isso é a palavra-passe), aprovar ação do Vigia, dar privilégio a gesto.
Foto é fácil de imitar; por isso o rosto só decide cortesia.
"""
from __future__ import annotations
import json, math, os, time
from pathlib import Path

ARQ = Path(os.environ.get("JAIME_ROSTO_ARQ", "~/Jaime/identidade/rosto.json")).expanduser()
LIMIAR = float(os.environ.get("JAIME_ROSTO_LIMIAR", "0.5"))    # distância euclidiana do face-api (0.6 é o padrão frouxo deles)
MAX_AMOSTRAS = 12


def _valido(d) -> bool:
    return isinstance(d, (list, tuple)) and len(d) == 128 and all(isinstance(x, (int, float)) and math.isfinite(x) for x in d)


def distancia(a, b) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


class Rostos:
    def __init__(self, arq: Path | None = None, limiar: float = LIMIAR):
        self.arq, self.limiar = Path(arq or ARQ), limiar

    def amostras(self) -> list[list[float]]:
        try:
            return [d for d in json.loads(self.arq.read_text(encoding="utf-8")).get("amostras", []) if _valido(d)]
        except Exception:
            return []

    @property
    def cadastrado(self) -> bool:
        return bool(self.amostras())

    def cadastrar(self, descritores: list) -> int:
        novos = [list(map(float, d)) for d in descritores if _valido(d)]
        if not novos:
            raise ValueError("nenhum descritor válido (esperado 128 números)")
        todas = (self.amostras() + novos)[-MAX_AMOSTRAS:]
        self.arq.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.arq.parent, 0o700)
        except OSError:
            pass
        self.arq.write_text(json.dumps({"atualizado": time.time(), "amostras": todas}), encoding="utf-8")
        os.chmod(self.arq, 0o600)
        return len(todas)

    def esquecer(self) -> None:
        try:
            self.arq.unlink()
        except FileNotFoundError:
            pass

    def verificar(self, descritor) -> dict:
        """{'status': 'confirmado'|'desconhecido'|'sem_cadastro'|'invalido', 'distancia': float|None}"""
        if not _valido(descritor):
            return {"status": "invalido", "distancia": None}
        amostras = self.amostras()
        if not amostras:
            return {"status": "sem_cadastro", "distancia": None}
        d = min(distancia(descritor, a) for a in amostras)
        return {"status": "confirmado" if d <= self.limiar else "desconhecido", "distancia": round(d, 3)}
