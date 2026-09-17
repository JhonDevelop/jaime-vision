"""Frota — os outros computadores da rede do João que o J.A.I.M.E alcança.

Em uma frase: cada máquina roda um agente que LIGA para cá e pergunta se tem trabalho; o Jaime descobre de
quem a máquina é pelo hostname, confere o nível na matrícula do vault, e atravessa. Nada entra nas outras
máquinas.

    registro.py   a matrícula: hostname -> dono, nível, pasta. E o token derivado de cada máquina.
    frota.py      as ligações vivas, as filas e os convites de entrada.
    servidor.py   as ferramentas que ele chama (frota, de_quem_e_a_maquina, conhecer_maquina, rodar_em…).
    agente.py     o programa que roda NA OUTRA máquina. Quem manda é ele.
    instalar.sh   o instalador de uma linha, servido pelo próprio servidor do João."""
from .frota import Frota, Ligacao, Pedido, CONVITE_S, ESPERA_S, SILENCIO_S
from .registro import (NIVEIS, ACOES, NaFrota, Registro, confere_token, normalizar_host,
                       token_da_maquina)
from .servidor import build_frota_server

__all__ = ["Frota", "Ligacao", "Pedido", "CONVITE_S", "ESPERA_S", "SILENCIO_S",
           "NIVEIS", "ACOES", "NaFrota", "Registro", "confere_token", "normalizar_host",
           "token_da_maquina", "build_frota_server"]
