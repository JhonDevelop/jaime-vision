"""Relações — o grafo de conhecimento temporal do Jaime (pessoas, animais, lugares, projetos, organizações).

Arquivo markdown não guarda bem "a Ana é irmã do Gabriel, que é sócio do João, e o cachorro dela chama Thor".
Isso é um grafo. E é temporal porque fato muda: quem troca de emprego não vira contradição — o fato velho
ganha data de fim e fica no histórico, o novo passa a valer. Cada fato traz a evidência de onde saiu."""
from .grafo import Relacoes, No
from .tools import build_relacoes_server

__all__ = ["Relacoes", "No", "build_relacoes_server"]
