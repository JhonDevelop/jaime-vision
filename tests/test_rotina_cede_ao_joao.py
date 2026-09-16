"""Utilidade sempre ganha se há demanda: uma rotina que segura o orquestrador cede a vez quando o João fala
(Vigília 16/09 07:56: 4 turnos esperaram 66–122 s pelo briefing)."""
import asyncio, time
from types import SimpleNamespace
from datetime import datetime, timedelta

def _jaime():
    from jaime.orchestrator.jaime import Jaime
    j = Jaime.__new__(Jaime)
    j._lock = asyncio.Lock(); j._ordem_em_curso = ""; j._rotina_cedida = ""
    j.acesso = SimpleNamespace(liberado=True)
    j.linhas = []; j.vault = SimpleNamespace(diario=lambda t, s="Log": j.linhas.append(t))
    j.reagendadas = []; j.agenda = SimpleNamespace(reagendar=lambda o, minutos=10: j.reagendadas.append((o, minutos)))
    j.interrompido = asyncio.Event()
    async def interrupt(): j.interrompido.set()
    j._client = SimpleNamespace(interrupt=interrupt)
    async def _ask_stream(texto, canal, contexto):
        async with j._lock:
            j._ordem_em_curso = texto if canal == "rotina" else ""
            if canal == "rotina":
                yield "Briefing: "
                try:
                    await asyncio.wait_for(j.interrompido.wait(), 5)     # o modelo "pensa" até ser interrompido
                    yield "(interrompido)"
                except asyncio.TimeoutError:
                    yield "clima, agenda, tarefas."
            else:
                yield f"resposta a «{texto}»"
    j._ask_stream = _ask_stream
    return j

def test_demanda_do_joao_interrompe_a_rotina_e_a_reagenda():
    async def rodar():
        j = _jaime()
        async def rotina():
            return "".join([t async for t in j.ask_stream("briefing", canal="rotina")])
        tarefa = asyncio.create_task(rotina())
        await asyncio.sleep(0.05)                                    # a rotina pegou o orquestrador
        assert j._lock.locked() and j._ordem_em_curso == "briefing"
        t0 = time.time()
        resposta = "".join([t async for t in j.ask_stream("me ajuda com a minha rotina", canal="voice")])
        assert resposta == "resposta a «me ajuda com a minha rotina»" and time.time() - t0 < 2.0   # não esperou o briefing
        assert j.interrompido.is_set() and j.reagendadas == [("briefing", 10)] and j._rotina_cedida == "briefing"
        assert any(l.startswith("Rotina «briefing» interrompida") for l in j.linhas)
        assert (await tarefa).endswith("(interrompido)") and j._ordem_em_curso == ""
    asyncio.run(rodar())

def test_sem_rotina_em_curso_nao_interrompe_nada():
    async def rodar():
        j = _jaime()
        r = "".join([t async for t in j.ask_stream("que horas são", canal="voice")])
        assert r.startswith("resposta") and not j.interrompido.is_set() and j.reagendadas == []
    asyncio.run(rodar())
