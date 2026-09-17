"""A ponte para a máquina do Gabriel.

O servidor roda no Mac do João. Ele não enxerga o disco do Gabriel — nenhum servidor enxerga o disco de
outra máquina, isso não é limitação do Jaime, é como rede funciona. Para o Jaime mexer nos arquivos e no
computador do Gabriel, precisa de algo rodando LÁ.

É o que a ponte é: um programa pequeno (`jaime/ponte/agente.py`) que o Gabriel roda no Mac dele. Ele não
abre porta nenhuma na máquina do Gabriel — quem liga é ele, de dentro para fora, buscando trabalho no
servidor do João. Roteador, firewall e Wi-Fi de café continuam funcionando, e ninguém consegue entrar na
máquina do Gabriel por causa disto.

O Gabriel manda no que a ponte alcança:
- **a raiz**: uma pasta que ele escolhe. Fora dela, a ponte recusa — inclusive `..` e link simbólico que
  aponte para fora.
- **o que pode fazer**: ler, listar e escrever são separados de rodar comando, e rodar vem desligado.
- **desligar**: Ctrl-C. Sem programa rodando, não há acesso. Não fica serviço, não fica nada no boot.

Nada disso é o Jaime sendo tímido: é o que faz o Gabriel poder ligar sem medo, que é o que torna a coisa
realmente utilizável."""
from .servidor import Ponte, build_ponte_server

__all__ = ["Ponte", "build_ponte_server"]
