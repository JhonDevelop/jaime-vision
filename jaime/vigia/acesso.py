"""Palavra-passe — falada ou digitada. Sem ela, o cérebro fica fechado e o Jaime só pede a senha.

A senha nunca fica em texto puro no código: compara-se o SHA-256. Padrão inicial (12341234) está
hasheado no .env.example — troque em JAIME_PASSPHRASE_HASH com `python -m jaime senha`."""
from __future__ import annotations
import hashlib, re, time

PALAVRAS = {"zero": "0", "um": "1", "uma": "1", "hum": "1", "dois": "2", "duas": "2", "três": "3", "tres": "3",
            "quatro": "4", "cinco": "5", "seis": "6", "meia": "6", "sete": "7", "oito": "8", "nove": "9"}

def normalizar(texto: str) -> str:
    """'um dois três quatro, 1234' → '12341234'. Aceita dígitos, números por extenso e mistura."""
    t = texto.lower()
    for palavra, digito in sorted(PALAVRAS.items(), key=lambda kv: -len(kv[0])):
        t = re.sub(rf"\b{palavra}\b", digito, t)
    return re.sub(r"\D", "", t)

def hash_senha(senha: str) -> str:
    return hashlib.sha256(normalizar(senha).encode()).hexdigest()

class Acesso:
    def __init__(self, hash_hex: str, timeout_min: int = 30):
        self._hash = hash_hex.lower()
        self._timeout = timeout_min * 60
        self._ate = 0.0

    @property
    def liberado(self) -> bool:
        return time.time() < self._ate

    def tentar(self, texto: str) -> bool:
        digitos = normalizar(texto)
        if len(digitos) >= 4 and hashlib.sha256(digitos.encode()).hexdigest() == self._hash:
            self._ate = time.time() + self._timeout
            return True
        return False

    def confere(self, texto: str) -> bool:
        """É a palavra-passe? Sem liberar nada (para saber que alguém que NÃO é o dono tentou)."""
        digitos = normalizar(texto)
        return len(digitos) >= 4 and hashlib.sha256(digitos.encode()).hexdigest() == self._hash

    def tocar(self) -> None:
        if self.liberado:
            self._ate = time.time() + self._timeout

    def trancar(self) -> None:
        self._ate = 0.0

PEDIDOS_DE_TRANCA = {"tranca", "trancar", "bloqueia", "bloquear", "fecha o cérebro", "modo seguro"}
def quer_trancar(texto: str) -> bool:
    return texto.strip().lower().rstrip(".!") in PEDIDOS_DE_TRANCA
