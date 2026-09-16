"""Raciocínio próprio: forma pensamento (pensador falso), persiste, recall por assunto, rotação de fontes e o loop."""
import asyncio, json
from pathlib import Path
from types import SimpleNamespace
from jaime.brain.vault import Vault
from jaime.mente.pensar import Pensar, Pensamento

def _vault(tmp_path):
    for d in ("01-Estado", "20-Projetos", "40-Diario", "90-Estudo"):
        (tmp_path / d).mkdir()
    (tmp_path / "20-Projetos/Estamparia.md").write_text("# Estamparia\nVídeos do OpenArt prontos; falta processo repetível.\n", encoding="utf-8")
    (tmp_path / "90-Estudo/Problemas.md").write_text("# Problemas\n\n## P-0009 · latência da voz · aberto\n- x\n", encoding="utf-8")
    return Vault(tmp_path)

def _pensador(respostas):
    it = iter(respostas)
    async def fn(prompt, contexto):
        return next(it, "")
    return fn

def test_pensa_persiste_e_recarrega(tmp_path):
    v = _vault(tmp_path)
    p = Pensar(v, pensador=_pensador([json.dumps({"pensamento": "Penso que os vídeos do OpenArt viram um processo se eu catalogar por tema.", "vale_dizer": True, "tema": "Estamparia"})]))
    pen = asyncio.run(p.pensar("Estamparia", "vídeos prontos"))
    assert pen and pen.tema == "Estamparia" and pen.vale_dizer and "catalogar" in pen.texto
    txt = v.read("01-Estado/Pensamentos.md")
    assert "## " in txt and "·dizer" in txt and "catalogar" in txt
    assert "Pensei (Estamparia)" in v.read(f"40-Diario/{__import__('datetime').date.today():%Y-%m-%d}.md")
    p2 = Pensar(v, pensador=None)                               # recarrega do arquivo
    assert len(p2.pensamentos) == 1 and p2.pensamentos[0].vale_dizer and p2.a_dizer()

def test_recall_por_assunto(tmp_path):
    v = _vault(tmp_path)
    p = Pensar(v, pensador=None)
    p.pensamentos = [Pensamento("Estamparia", "Penso em catalogar os vídeos do OpenArt por tema."),
                     Pensamento("BUB", "O build iOS ainda depende de um passo manual."),
                     Pensamento("Oldsen", "O tênis precisa de fotos melhores.")]
    hits = p.sobre("como faço os vídeos da estamparia")
    assert hits and hits[0].tema == "Estamparia"
    assert "OpenArt" in p.recall_para_prompt("vídeos da estamparia")
    assert p.sobre("assunto totalmente diferente xyz") == []

def test_texto_solto_sem_json_ainda_vira_pensamento(tmp_path):
    v = _vault(tmp_path)
    p = Pensar(v, pensador=_pensador(["Notei que o João pula muito entre apps quando está travado."]))
    pen = asyncio.run(p.pensar("o dia de hoje"))
    assert pen and "pula muito" in pen.texto and not pen.vale_dizer

def test_assunto_rotaciona_entre_fontes(tmp_path):
    v = _vault(tmp_path)
    (v.root / "40-Diario" / f"{__import__('datetime').date.today():%Y-%m-%d}.md").write_text("# hoje\n- 10:00 Decisão importante do João sobre vídeos\n", encoding="utf-8")
    p = Pensar(v, pensador=None)
    temas = {p._assunto()[0] for _ in range(8)}
    assert "Estamparia" in temas and ("o dia de hoje" in temas or "um problema em aberto" in temas)

def test_orcamento_bloqueia_e_off_desliga(tmp_path):
    v = _vault(tmp_path)
    p = Pensar(v, pensador=_pensador(["x y z abcde"]), pode_gastar=lambda: False)
    assert asyncio.run(p.pensar("Estamparia")) is None and p.pensamentos == []
    import os
    os.environ["JAIME_PENSAR"] = "off"
    try:
        asyncio.run(asyncio.wait_for(Pensar(v, pensador=None).rodar(lambda: True, intervalo=1), timeout=0.5))   # retorna na hora
    finally:
        os.environ.pop("JAIME_PENSAR", None)
