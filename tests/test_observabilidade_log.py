"""O log precisa mostrar o que o Jaime respondeu (uma linha por turno) e não repetir o mesmo erro do Notion a cada evento."""
import asyncio
from types import SimpleNamespace

def test_ask_stream_deixa_uma_linha_com_a_resposta(capsys):
    from jaime.orchestrator.jaime import Jaime
    j = Jaime.__new__(Jaime); j.acesso = SimpleNamespace(liberado=True)
    async def inner(texto, canal, contexto):
        for t in ["Primeiro,  a estamparia.\n", "Depois o BUB."]:
            yield t
    j._ask_stream = inner
    async def rodar():
        return [t async for t in j.ask_stream("plano da semana", canal="voice")]
    assert asyncio.run(rodar()) == ["Primeiro,  a estamparia.\n", "Depois o BUB."]     # o fluxo passa intacto
    assert capsys.readouterr().out.strip() == "🔈 jaime › Primeiro, a estamparia. Depois o BUB."

def test_ask_stream_marca_tranca_e_trunca_mesmo_se_o_fluxo_for_cortado(capsys):
    from jaime.orchestrator.jaime import Jaime
    j = Jaime.__new__(Jaime); j.acesso = SimpleNamespace(liberado=False)
    async def inner(texto, canal, contexto):
        yield "x" * 200; yield "nunca lido"
    j._ask_stream = inner
    async def rodar():
        gen = j.ask_stream("1234")
        await gen.__anext__(); await gen.aclose()       # barge-in: o consumidor fecha o gerador no meio
    asyncio.run(rodar())
    out = capsys.readouterr().out.strip()
    assert out.startswith("🔈 jaime 🔒 › " + "x" * 160) and out.endswith("…") and "nunca lido" not in out

def test_notion_nao_repete_o_mesmo_erro(capsys, monkeypatch):
    from jaime.brain import notion_sync as ns
    n = ns.NotionSync.__new__(ns.NotionSync); n._erros = {}
    async def falha(): raise RuntimeError("404 Not Found")
    async def ok(): pass
    n.sincronizar_estado = falha; n.sincronizar_diario = ok; n.sincronizar_tarefas = ok
    n.sincronizar_estado.__name__ = "sincronizar_estado"
    import time as _t
    relogio = [1000.0]; monkeypatch.setattr(_t, "time", lambda: relogio[0])
    for _ in range(10): asyncio.run(n.tudo())
    linhas = capsys.readouterr().out.strip().splitlines()
    assert linhas == ["[notion] sincronizar_estado: 404 Not Found", "[notion] sincronizar_estado: mesmo erro 3× (mostro de novo em 1 h)"]
    relogio[0] += 3601; asyncio.run(n.tudo())
    assert capsys.readouterr().out.strip() == "[notion] sincronizar_estado: mesmo erro 11× (mostro de novo em 1 h)"
    async def outra(): raise RuntimeError("401")
    outra.__name__ = "sincronizar_estado"; n.sincronizar_estado = outra; asyncio.run(n.tudo())
    assert capsys.readouterr().out.strip() == "[notion] sincronizar_estado: 401"     # erro diferente aparece na hora
    n.sincronizar_estado = ok; ok.__name__ = "sincronizar_estado"; asyncio.run(n.tudo())
    assert "sincronizar_estado" not in n._erros                                         # voltou a funcionar: zera
