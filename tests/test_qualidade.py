"""Gate de qualidade da autoevolução: métrica que piora, teste apagado ou área protegida reprovam."""
import json, subprocess, sys
from pathlib import Path
from jaime.qualidade import arquivos_mudados, comparar, medir, medir_em

RAIZ = Path(__file__).resolve().parent.parent
BASE = {"gestos": {"acerto": 1.0, "falsos_h": 0.0, "p95_ms": 0.08, "n": 30}, "blocos": {"contrato_ok": 22, "total": 22}, "voz": {"acerto": 1.0}}


def test_medicao_atual_e_perfeita_e_roda_em_processo_separado():
    m = medir()
    assert m["gestos"]["acerto"] == 1.0 and m["blocos"]["contrato_ok"] == m["blocos"]["total"] and m["voz"]["acerto"] == 1.0
    assert medir_em(RAIZ, sys.executable)["voz"]["acerto"] == 1.0


def test_comparar_aprova_igual_e_reprova_cada_regressao():
    assert comparar(BASE, BASE, 700, 700, ["jaime/blocos/voz.py"]) == (True, [])
    casos = [
        ({**BASE, "gestos": {**BASE["gestos"], "acerto": 0.74}}, 700, [], "acerto caiu"),
        ({**BASE, "gestos": {**BASE["gestos"], "falsos_h": 1452}}, 700, [], "falsas ativações"),
        ({**BASE, "blocos": {"contrato_ok": 21, "total": 22}}, 700, [], "contrato"),
        ({**BASE, "voz": {"acerto": 0.9}}, 700, [], "voz"),
        ({**BASE, "voz": {"erro": "ImportError"}}, 700, [], "quebrou"),
        (BASE, 690, [], "testes coletados caíram"),
        (BASE, 700, ["jaime/vigia/hooks.py"], "só o João"),
        (BASE, 700, [".env"], "só o João"),
        (BASE, 700, ["vault/00-Jaime/Origem.md"], "só o João"),
    ]
    for cand, tc, mud, trecho in casos:
        ok, probs = comparar(BASE, cand, 700, tc, mud)
        assert not ok and any(trecho in p for p in probs), trecho


def test_arquivos_mudados_ve_commit_e_arquivo_solto(tmp_path):
    r = tmp_path / "r"; r.mkdir()
    g = lambda *a: subprocess.run(["git", *a], cwd=r, check=True, capture_output=True)
    g("init", "-q", "-b", "main"); (r / "a.txt").write_text("1"); g("add", "-A")
    g("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "i")
    g("checkout", "-q", "-b", "jaime/x"); (r / "jaime").mkdir(); (r / "jaime" / "vigia").mkdir()
    (r / "jaime" / "vigia" / "hooks.py").write_text("x"); g("add", "-A")
    g("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "m")
    (r / "solto.py").write_text("y")
    assert arquivos_mudados(r) == ["jaime/vigia/hooks.py", "solto.py"]
