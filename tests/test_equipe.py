"""Filhos do J.A.I.M.E: descoberta do Maestri (env), CLI falso (executor injetável), criar/delegar/checar/dispensar,
papel gerado com as regras, relatórios pela nota compartilhada e persistência em 01-Estado/Equipe.md."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
import pytest
from jaime.brain.vault import Vault
from jaime.equipe.maestri import Maestri, descobrir_socket, descobrir_terminal
from jaime.equipe import filhos as fl

class _CLI:
    """Executor falso: registra as chamadas e devolve saídas plausíveis."""
    def __init__(self):
        self.chamadas = []; self.notas = {}; self.recrutados = []; self.papeis = {}
    def __call__(self, args, timeout):
        self.chamadas.append(args); cmd = args[0]
        if cmd == "list": return 0, "You:\n  - name: \"Cerebro Principal J.A.I.M.E\", maestro: true\nConnected agents:\n" + "".join(f"  - name: \"{n}\"\n" for n in self.recrutados)
        if cmd == "preset": return 0, "Available agent presets:\n  - \"Claude Code\"\n  - \"Codex\"\n  - \"Shell\""
        if cmd == "role" and args[1] == "create":
            if args[2] in self.papeis: return 1, "role already exists"
            self.papeis[args[2]] = args[3]; return 0, f'Created role "{args[2]}"'
        if cmd == "role" and args[1] == "write": self.papeis[args[2]] = args[3]; return 0, "ok"
        if cmd == "recruit": self.recrutados.append(args[1]); return 0, f'Recruited "{args[1]}".'
        if cmd == "dismiss": self.recrutados.remove(args[1]); return 0, "dismissed"
        if cmd == "connect": return 0, "Connected"
        if cmd == "ask": return 0, ("ok" if "--raw" in args else f"resposta de {args[1]}")
        if cmd == "check": return 0, "\n".join(f"linha {i}" for i in range(40))
        if cmd == "note":
            sub, nome = args[1], args[2] if args[2] != "--name" else args[3]
            if sub == "create": self.notas[nome] = args[-1]; return 0, f'Created note "{nome}"'
            if nome not in self.notas: return 1, "note not found"
            if sub == "read": return 0, "\n".join(f"{i+1}\t{l}" for i, l in enumerate(self.notas[nome].splitlines()))
            if sub == "write": self.notas[nome] = args[3]; return 0, "ok"
            if sub == "edit": self.notas[nome] = self.notas[nome].replace(args[3], args[4], 1); return 0, "ok"
        return 1, f"comando desconhecido: {args}"

def _maestri(cli):
    m = Maestri(executor=cli); m.socket = "/tmp/x.sock"; m.terminal_id = "T1"; return m

@pytest.fixture
def jaime(tmp_path):
    for d in ("01-Estado", "40-Diario"):
        (tmp_path / d).mkdir()
    v = Vault(tmp_path)
    return SimpleNamespace(vault=v, s=SimpleNamespace(workspace=tmp_path / "projetos"))

def test_descoberta_por_env(monkeypatch):
    monkeypatch.setenv("JAIME_MAESTRI_SOCKET", "/tmp/m.sock"); monkeypatch.setenv("JAIME_MAESTRI_TERMINAL_ID", "ABC")
    assert descobrir_socket() == "/tmp/m.sock" and descobrir_terminal()[0] == "ABC"
    m = Maestri(executor=lambda a, t: (0, "")); assert m.disponivel

def test_indisponivel_nao_trava(monkeypatch, tmp_path):
    monkeypatch.delenv("JAIME_MAESTRI_SOCKET", raising=False); monkeypatch.delenv("MAESTRI_SOCKET", raising=False)
    monkeypatch.delenv("JAIME_MAESTRI_TERMINAL_ID", raising=False); monkeypatch.delenv("MAESTRI_TERMINAL_ID", raising=False)
    monkeypatch.setenv("TMPDIR", str(tmp_path)); monkeypatch.setenv("HOME", str(tmp_path))
    m = Maestri(executor=lambda a, t: (0, ""), cli="/nao/existe")
    assert not m.disponivel
    with pytest.raises(RuntimeError):
        m.listar()

def test_criar_delegar_checar_dispensar_e_persistir(jaime, tmp_path, monkeypatch):
    monkeypatch.setattr(fl, "LABORATORIOS", tmp_path / "filhos"); monkeypatch.setattr(fl, "MAX_FILHOS", 2)
    cli = _CLI(); eq = fl.Equipe(jaime, tmp_path, maestri=_maestri(cli))
    f = eq.criar("Faísca", "descobrir como ler o chat.db do iPhone", tipo="pesquisa", preset="codex")
    assert f.preset == "Codex" and f.tipo == "pesquisa" and Path(f.pasta).is_dir() and cli.recrutados == ["Faísca"]
    papel = cli.papeis["Filho: Faísca"]
    assert "pesquisador" in papel and "Nunca git push" in papel and str(f.pasta) in papel and "equipe-relatorios" in papel
    assert "equipe-relatorios" in cli.notas                                       # nota criada e conectada
    assert eq.delegar("Faísca", "comece pela documentação da Apple", esperar_s=5) == "resposta de Faísca"
    assert eq.filhos["Faísca"].tarefas == 1
    assert "linha 39" in eq.checar("Faísca")
    with pytest.raises(RuntimeError):
        eq.criar("Faísca", "de novo")                                             # nome repetido
    g = eq.criar("Bigorna", "MVP de catálogo", tipo="mvp", preset="claude")
    assert g.pasta.endswith("projetos/bigorna")
    with pytest.raises(RuntimeError):
        eq.criar("Terceiro", "x", tipo="operacao")                               # limite de vivos
    # relatório chega pela nota
    cli.notas["equipe-relatorios"] = cli.notas["equipe-relatorios"].replace("## fim", "## Faísca · 14:10\nPronto: chat.db lê com sqlite ro; ver relatorio.md\n\n## fim")
    novos = eq.ler_relatorios()
    assert novos == [("Faísca", "Pronto: chat.db lê com sqlite ro; ver relatorio.md")] and eq.ler_relatorios() == []
    assert eq.filhos["Faísca"].ultimo_relatorio.startswith("Pronto")
    assert "dispensado" in eq.dispensar("Faísca", "terminou") and cli.recrutados == ["Bigorna"]
    eq2 = fl.Equipe(jaime, tmp_path, maestri=_maestri(cli))                     # recarrega do vault
    assert set(eq2.filhos) == {"Faísca", "Bigorna"} and eq2.filhos["Faísca"].estado == "dispensado" and eq2.filhos["Bigorna"].estado == "vivo"
    assert "Filho criado: Faísca" in jaime.vault.read(f"40-Diario/{__import__('datetime').date.today():%Y-%m-%d}.md")

def test_vigiar_relatorios_ignora_o_antigo_e_fala_o_novo(jaime, tmp_path, monkeypatch):
    monkeypatch.setattr(fl, "LABORATORIOS", tmp_path / "filhos")
    cli = _CLI(); eq = fl.Equipe(jaime, tmp_path, maestri=_maestri(cli))
    eq.criar("Faísca", "x", tipo="pesquisa")
    cli.notas["equipe-relatorios"] = cli.notas["equipe-relatorios"].replace("## fim", "## Faísca · 13:00\nantigo\n\n## fim")
    falas = []
    async def rodar():
        t = asyncio.create_task(eq.vigiar_relatorios(intervalo_s=0.05, falar=falas.append))
        await asyncio.sleep(0.08)
        cli.notas["equipe-relatorios"] = cli.notas["equipe-relatorios"].replace("## fim", "## Faísca · 13:05\nPronto: terminei a leitura\n\n## fim")
        await asyncio.sleep(0.15); t.cancel()
    asyncio.run(rodar())
    assert falas == ["Faísca relatou: Pronto: terminei a leitura"]
    assert "Relatório de Faísca: Pronto" in jaime.vault.read(f"40-Diario/{__import__('datetime').date.today():%Y-%m-%d}.md")
