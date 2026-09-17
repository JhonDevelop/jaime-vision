"""O acervo — o J.A.I.M.E alcança qualquer especialista sem carregar todos a cada turno.

O problema, medido: a `description` de cada agente e de cada skill entra no contexto em TODO turno. Com 708
agentes e 293 skills isso dava ~65 mil tokens fixos por turno — o maior peso do primeiro token lento, que é
o que faz ele dizer "deixa eu ver, peraí" antes de responder qualquer coisa.

A saída não é jogar capacidade fora, é parar de carregar tudo:

    CARREGADOS    os maesters da casa e um punhado de generalistas. É o que entra no contexto e é o que ele
                  pode invocar como subagente direto. Teto em `JAIME_AGENTES_MAX`.
    O ACERVO      todo o resto, no disco, fora do contexto. `buscar` acha pelo assunto e `consultar` traz o
                  texto inteiro do especialista, para ele aplicar o conhecimento ali mesmo, naquele turno.

Ou seja: nada some. O que muda é que o especialista de Kubernetes deixa de custar tokens em toda conversa
sobre o almoço, e passa a ser chamado quando o assunto é Kubernetes."""
from .busca import Acervo, build_acervo_server

__all__ = ["Acervo", "build_acervo_server"]
