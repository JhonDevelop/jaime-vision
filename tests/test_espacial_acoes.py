"""Fase 3 — ações no SO só por prévia → política → Vigia → recibo/Undo. A suíte nunca toca o SO de verdade."""
import asyncio, os
from pathlib import Path
from types import SimpleNamespace
import pytest
from jaime.spatial.acoes import ActionProposal, AdaptadorAcoes, PREVIA_TTL_S
from jaime.spatial.core import SpatialCore, SpatialEvent, SpatialObject, Vec3
from jaime.spatial.intencoes import Intencoes
from jaime.spatial.telas import Display, VigiaTelas
from jaime.vigia.hooks import Vigia


class Relogio:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t


class FakeSO:
    def __init__(self, move_de_verdade=True):
        self.chamadas = []; self.janelas = {"Finder": [100, 100, 800, 600]}; self.move_de_verdade = move_de_verdade
        self.lixo = {}
    def abrir(self, c): self.chamadas.append(("abrir", c))
    def janela(self, app, titulo=""):
        return tuple(self.janelas[app]) if app in self.janelas else None
    def mover_janela(self, app, titulo, x, y):
        self.chamadas.append(("mover", app, x, y))
        if self.move_de_verdade:
            self.janelas[app][0], self.janelas[app][1] = x, y
    def lixeira(self, c):
        destino = c + ".lixo"; os.replace(c, destino); self.lixo[c] = destino; self.chamadas.append(("lixeira", c)); return destino
    def restaurar(self, na, dest):
        os.replace(na, dest); self.chamadas.append(("restaurar", dest))


def _montar(tmp_path, dry_run=True, dono=True, vigia=None, telas=None, so=None):
    raiz = tmp_path / "projetos"; (raiz / "bub").mkdir(parents=True)
    (raiz / "bub" / "rascunho.txt").write_text("x")
    vault = tmp_path / "vault"; (vault / "00-Jaime").mkdir(parents=True); (vault / "00-Jaime" / "Origem.md").write_text("id")
    c = SpatialCore()
    c.add(SpatialObject("projeto:bub", "pasta", Vec3(0.2, 0.3, 0), label="BUB", resource_ref=str(raiz / "bub")))
    c.add(SpatialObject("arq:rascunho", "arquivo", Vec3(0.4, 0.3, 0), label="rascunho", resource_ref=str(raiz / "bub" / "rascunho.txt")))
    c.add(SpatialObject("ideia", "nota", Vec3(0.6, 0.3, 0), label="ideia"))
    c.add(SpatialObject("zona:lixeira", "lixeira", Vec3(0.9, 0.85, 0), label="lixeira", radius=0.07))
    ev = []
    rel = Relogio()
    so = so or FakeSO()
    a = AdaptadorAcoes(c, so, lambda: dono, vigia=vigia, dry_run=dry_run, raizes=[raiz], proibidas=[vault],
                       emitir=lambda tipo, **d: ev.append(d), telas=telas, relogio=rel)
    return a, c, so, ev, rel, raiz, vault


def run(coro):
    return asyncio.run(coro)


def test_abrir_em_dry_run_gera_previa_e_recibo_sem_tocar_o_so(tmp_path):
    a, c, so, ev, *_ = _montar(tmp_path)
    p = ActionProposal("open", "projeto:bub", "joao", 0.95, "gesto")
    pv = run(a.propor(p))
    assert pv.status == "allow" and pv.efeitos[0].startswith("[dry-run]")
    r = run(a.executar(p.id))
    assert r.dry_run and not r.executado and so.chamadas == []
    assert [e["evento"] for e in ev] == ["action.preview", "action.receipt"]


def test_abrir_de_verdade_usa_o_caminho_canonico_e_e_idempotente(tmp_path):
    a, c, so, ev, rel, raiz, _ = _montar(tmp_path, dry_run=False)
    p = ActionProposal("open", "projeto:bub", "joao", 0.95)
    run(a.propor(p))
    r1 = run(a.executar(p.id)); r2 = run(a.executar(p.id))
    assert r1 is r2 and r1.executado and so.chamadas == [("abrir", str((raiz / "bub").resolve()))]
    assert a.duplicados_bloqueados == 1


@pytest.mark.parametrize("ator,dono,conf,motivo", [
    ("desconhecido", True, 0.99, "owner"), ("joao", False, 0.99, "owner"), ("joao", True, 0.6, "low confidence")])
def test_sem_dono_ou_com_confianca_baixa_nega(tmp_path, ator, dono, conf, motivo):
    a, *_ = _montar(tmp_path, dono=dono)
    pv = run(a.propor(ActionProposal("open", "projeto:bub", ator, conf)))
    assert pv.status == "deny" and motivo in pv.motivo


def test_recurso_fora_do_escopo_com_ponto_ponto_symlink_ou_vault_e_negado(tmp_path):
    a, c, so, ev, rel, raiz, vault = _montar(tmp_path)
    fora = tmp_path / "fora"; fora.mkdir()
    (raiz / "atalho").symlink_to(fora)
    casos = {"fora": str(fora), "pontoponto": str(raiz / "bub" / ".." / ".." / "fora"), "symlink": str(raiz / "atalho"),
             "inexistente": str(raiz / "nao-existe"), "vault": str(vault / "00-Jaime")}
    for nome, ref in casos.items():
        c.add(SpatialObject(f"x:{nome}", "pasta", Vec3(0.5, 0.5, 0), label=nome, resource_ref=ref))
        pv = run(a.propor(ActionProposal("open", f"x:{nome}", "joao", 0.99)))
        assert pv.status == "deny", nome
    pv = run(a.propor(ActionProposal("open", "ideia", "joao", 0.99)))
    assert pv.status == "deny" and "virtual" in pv.motivo


def test_lixeira_exige_confirmacao_explicita_e_tem_undo(tmp_path):
    a, c, so, ev, rel, raiz, _ = _montar(tmp_path, dry_run=False)
    arq = raiz / "bub" / "rascunho.txt"
    p = ActionProposal("move_to_trash", "arq:rascunho", "joao", 0.99, "gesto")
    pv = run(a.propor(p))
    assert pv.status == "review" and "Lixeira" in pv.efeitos[0] and pv.undo
    r = run(a.executar(p.id))                              # só o gesto: não basta
    assert not r.executado and arq.exists() and so.chamadas == []
    r = run(a.executar(p.id, confirmado=True))
    assert r.executado and not arq.exists()
    ok, msg = run(a.desfazer(r.id))
    assert ok and arq.exists() and so.chamadas[-1] == ("restaurar", str(arq.resolve()))


def test_apagar_definitivo_publicar_enviar_nunca(tmp_path):
    a, *_ = _montar(tmp_path, dry_run=False)
    for v in ("delete_forever", "publish", "send", "install"):
        p = ActionProposal(v, "arq:rascunho", "joao", 1.0, "voz")
        assert run(a.propor(p)).status == "deny"
        assert not run(a.executar(p.id, confirmado=True)).executado


def test_mover_janela_observa_o_so_e_desfaz(tmp_path):
    a, c, so, ev, *_ = _montar(tmp_path, dry_run=False)
    p = ActionProposal("move_window", "projeto:bub", "joao", 0.99, "voz", {"app": "Finder", "x": 1500, "y": 40})
    assert run(a.propor(p)).status == "allow"
    r = run(a.executar(p.id))
    assert r.executado and so.janelas["Finder"][:2] == [1500, 40] and r.undo_dados == {"app": "Finder", "titulo": "", "x": 100, "y": 100}
    assert run(a.desfazer(r.id))[0] and so.janelas["Finder"][:2] == [100, 100]


def test_mover_janela_que_o_so_ignorou_vira_erro_no_recibo(tmp_path):
    a, *_ = _montar(tmp_path, dry_run=False, so=FakeSO(move_de_verdade=False))
    p = ActionProposal("move_window", "projeto:bub", "joao", 0.99, "voz", {"app": "Finder", "x": 1500, "y": 40})
    run(a.propor(p))
    r = run(a.executar(p.id))
    assert not r.executado and "não moveu" in r.erro


def test_hotplug_suspende_mover_janela_ate_validar(tmp_path):
    layout = [[Display("a", "embutido", 0, 0, 1440, 900, 2.0, principal=True)]]
    vt = VigiaTelas(backend=lambda: layout[0])
    a, *_ = _montar(tmp_path, dry_run=False, telas=vt)
    p = ActionProposal("move_window", "projeto:bub", "joao", 0.99, "voz", {"app": "Finder", "x": 10, "y": 10})
    assert run(a.propor(p)).status == "allow"
    layout[0] = layout[0] + [Display("b", "externo 1", 1440, 0, 2560, 1440, 1.0)]
    assert vt.checar()["entrou"] == ["b"]
    r = run(a.executar(p.id))
    assert not r.executado and "mudou" in r.erro                       # a prévia era do layout antigo
    p2 = ActionProposal("move_window", "projeto:bub", "joao", 0.99, "voz", {"app": "Finder", "x": 10, "y": 10})
    assert run(a.propor(p2)).status == "deny"
    vt.validar()
    p3 = ActionProposal("move_window", "projeto:bub", "joao", 0.99, "voz", {"app": "Finder", "x": 10, "y": 10})
    run(a.propor(p3)); assert run(a.executar(p3.id)).executado


def test_previa_vencida_e_cerebro_trancado_entre_previa_e_execucao(tmp_path):
    a, c, so, ev, rel, *_ = _montar(tmp_path, dry_run=False)
    p = ActionProposal("open", "projeto:bub", "joao", 0.95)
    run(a.propor(p)); rel.t += PREVIA_TTL_S + 1
    assert "vencida" in run(a.executar(p.id)).erro
    estado = {"dono": True}
    a.dono_ok = lambda: estado["dono"]
    p2 = ActionProposal("open", "projeto:bub", "joao", 0.95)
    run(a.propor(p2)); estado["dono"] = False
    assert not run(a.executar(p2.id)).executado and so.chamadas == []


def test_o_vigia_real_decide_e_convidado_na_linha_nao_executa(tmp_path):
    v = Vigia()
    async def vigia(nome, args):
        return await v.pre_tool_use({"tool_name": nome, "tool_input": args}, None, None)
    a, c, so, ev, *_ = _montar(tmp_path, dry_run=False, vigia=vigia)
    p = ActionProposal("open", "projeto:bub", "joao", 0.95)
    run(a.propor(p)); assert run(a.executar(p.id)).executado     # abrir é livre no Vigia
    # a ferramenta da Lixeira se chama `apagar`: o Vigia existente segura até o "sim" do João
    d = run(v.pre_tool_use({"tool_name": "mcp__espacial__apagar", "tool_input": {"alvo": "rascunho", "caminho": "/x"}}, None, None))
    assert d["hookSpecificOutput"]["permissionDecision"] == "deny" and v.lote
    assert "apagar /x" in v.pedir_lote()
    v.liberar_lote()
    assert run(v.pre_tool_use({"tool_name": "mcp__espacial__apagar", "tool_input": {"alvo": "rascunho", "caminho": "/x"}}, None, None)) == {}


def test_vigia_negando_nao_executa(tmp_path):
    async def nega(nome, args):
        return {"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "teste"}}
    a, c, so, *_ = _montar(tmp_path, dry_run=False, vigia=nega)
    p = ActionProposal("open", "projeto:bub", "joao", 0.95)
    run(a.propor(p))
    r = run(a.executar(p.id))
    assert not r.executado and "Vigia" in r.erro and so.chamadas == []


# ── gestos → intenções ──────────────────────────────────────────────────────
def _intencoes(tmp_path, **kw):
    a, c, so, ev, rel, raiz, _ = _montar(tmp_path, **kw)
    tarefas = []
    i = Intencoes(c, a, lambda tipo, **d: ev.append(d), agendar=lambda coro: tarefas.append(coro))
    def drenar():
        while tarefas:
            run(tarefas.pop(0))
    return i, a, c, so, ev, drenar


def test_duplo_clique_em_pasta_propoe_abrir_e_clique_simples_so_seleciona(tmp_path):
    i, a, c, so, ev, drenar = _intencoes(tmp_path, dry_run=False)
    i(SpatialEvent("gesture.click", "projeto:bub", "joao", 10.0, 0.95))
    drenar(); assert so.chamadas == []
    i(SpatialEvent("gesture.click", "projeto:bub", "joao", 10.4, 0.95))
    drenar(); assert so.chamadas and so.chamadas[0][0] == "abrir"


def test_jogar_na_lixeira_virtual_some_da_cena_com_undo(tmp_path):
    i, a, c, so, ev, drenar = _intencoes(tmp_path)
    c.move("ideia", Vec3(0.9, 0.84, 0))
    i(SpatialEvent("gesture.release", "ideia", "joao", 1.0, 0.95))
    assert "ideia" not in c.objects
    token = next(e["desfazer"] for e in ev if e.get("evento") == "spatial.removed")
    assert i.desfazer_descarte(token) and "ideia" in c.objects


def test_jogar_arquivo_real_na_lixeira_so_gera_previa_em_revisao(tmp_path):
    i, a, c, so, ev, drenar = _intencoes(tmp_path, dry_run=False)
    c.move("arq:rascunho", Vec3(0.9, 0.85, 0))
    i(SpatialEvent("gesture.release", "arq:rascunho", "joao", 1.0, 0.99))
    drenar()
    assert so.chamadas == [] and "arq:rascunho" in c.objects
    prev = [e for e in ev if e.get("evento") == "action.preview"]
    assert prev and prev[-1]["status"] == "review"


def test_mcp_espacial_estado_criar_propor_executar_e_desfazer(tmp_path):
    import json
    from jaime.spatial.config import ConfigEspacial
    from jaime.spatial.referencias import ContextoVoz, Resolvedor
    from jaime.spatial.servico import ServicoEspacial
    from jaime.spatial.tools import build_espacial_server
    a, c, so, ev, rel, raiz, _ = _montar(tmp_path, dry_run=False)
    s = ServicoEspacial(ConfigEspacial(modo="camera"), emitir=lambda *x, **k: None, core=c, dono_ok=lambda: True)
    voz = ContextoVoz(s, Resolvedor(c))
    assert build_espacial_server(s, a, voz)                 # monta com o SDK de verdade
    # e os handlers são chamados direto (sem cliente/CLI do Claude)
    from jaime.spatial import tools as mod
    handlers = {}
    orig = mod.create_sdk_mcp_server
    mod.create_sdk_mcp_server = lambda name, version, tools: {t.name: t.handler for t in tools}
    try:
        handlers = build_espacial_server(s, a, voz)
    finally:
        mod.create_sdk_mcp_server = orig
    txt = lambda r: r["content"][0]["text"]
    assert set(handlers) == {"estado", "selecionar", "criar_objeto", "propor_acao", "executar", "apagar", "desfazer"}
    assert "projeto:bub" in txt(run(handlers["estado"]({})))
    assert "selecionado" in txt(run(handlers["selecionar"]({"alvo": "BUB"})))
    pv = json.loads(txt(run(handlers["propor_acao"]({"verbo": "open", "alvo": "isso", "args_json": ""}))))
    assert pv["status"] == "allow" and pv["alvo_id"] == "projeto:bub"
    r = json.loads(txt(run(handlers["executar"]({"proposta_id": pv["proposta_id"]}))))
    assert r["executado"] and so.chamadas[-1][0] == "abrir"
    pv = json.loads(txt(run(handlers["propor_acao"]({"verbo": "move_to_trash", "alvo": "rascunho"}))))
    assert pv["status"] == "review" and "apagar" in pv["proximo_passo"]
    r = json.loads(txt(run(handlers["apagar"]({"proposta_id": pv["proposta_id"], "caminho": pv["recurso"]}))))
    assert r["executado"] and not (raiz / "bub" / "rascunho.txt").exists()
    assert json.loads(txt(run(handlers["desfazer"]({"recibo_id": r["id"]}))))["ok"]
    assert (raiz / "bub" / "rascunho.txt").exists()
    assert "criado" in txt(run(handlers["criar_objeto"]({"label": "API", "kind": "backend", "x": 0.3, "y": 0.6})))


def test_mover_janela_para_o_monitor_da_direita_calcula_o_destino(tmp_path):
    esq = Display("a", "embutido", 0, 0, 1440, 900, 2.0, principal=True, embutido=True)
    dir_ = Display("b", "externo 1", 1440, 0, 2560, 1440, 1.0)
    vt = VigiaTelas(backend=lambda: [esq, dir_])
    a, c, so, *_ = _montar(tmp_path, dry_run=False, telas=vt)
    p = ActionProposal("move_window", "projeto:bub", "joao", 0.99, "voz", {"app": "Finder", "monitor": "direita"})
    pv = run(a.propor(p))
    assert pv.status == "allow" and p.args["monitor_id"] == "b" and dir_.contem(p.args["x"], p.args["y"])
    assert run(a.executar(p.id)).executado and dir_.contem(*so.janelas["Finder"][:2])
    p2 = ActionProposal("move_window", "projeto:bub", "joao", 0.99, "voz", {"app": "Finder", "monitor": "cima"})
    assert run(a.propor(p2)).status == "deny"


# ── achados da revisão de integração ────────────────────────────────────────
def test_abrir_programa_ou_script_e_revisao_nunca_duplo_clique_direto(tmp_path):
    a, c, so, ev, rel, raiz, _ = _montar(tmp_path, dry_run=False)
    for nome in ("instalar.command", "Calc.app", "setup.exe", "atalho.lnk"):
        alvo = raiz / "bub" / nome
        alvo.mkdir() if nome.endswith(".app") else alvo.write_text("x")
        c.add(SpatialObject(f"x:{nome}", "arquivo", Vec3(0.5, 0.5, 0), label=nome, resource_ref=str(alvo)))
        p = ActionProposal("open", f"x:{nome}", "joao", 0.99, "gesto")
        pv = run(a.propor(p))
        assert pv.status == "review" and "executar" in pv.motivo, nome
        assert not run(a.executar(p.id)).executado
    script = raiz / "bub" / "roda"; script.write_text("#!/bin/sh\n"); script.chmod(0o755)
    c.add(SpatialObject("x:roda", "arquivo", Vec3(0.5, 0.5, 0), resource_ref=str(script)))
    assert run(a.propor(ActionProposal("open", "x:roda", "joao", 0.99))).status == "review"
    assert so.chamadas == []


def test_dois_confirmares_ao_mesmo_tempo_executam_uma_vez(tmp_path):
    async def vigia_lento(nome, args):
        await asyncio.sleep(0.05); return {}
    a, c, so, *_ = _montar(tmp_path, dry_run=False, vigia=vigia_lento)
    p = ActionProposal("open", "projeto:bub", "joao", 0.95)
    run(a.propor(p))
    async def dois():
        return await asyncio.gather(a.executar(p.id), a.executar(p.id))
    r1, r2 = run(dois())
    assert [x for x in so.chamadas if x[0] == "abrir"] == [so.chamadas[0]] and len(so.chamadas) == 1
    assert {r1.erro, r2.erro} == {"", "já em execução"} and a.duplicados_bloqueados == 1


def test_vault_com_outra_caixa_continua_protegido(tmp_path):
    raiz = tmp_path / "ws"; (raiz / "vault" / "40-Diario").mkdir(parents=True)
    (raiz / "vault" / "40-Diario" / "hoje.md").write_text("privado")
    c = SpatialCore()
    a = AdaptadorAcoes(c, FakeSO(), lambda: True, dry_run=False, raizes=[raiz], proibidas=[raiz / "vault"])
    ref = str(raiz / "VAULT" / "40-Diario" / "hoje.md")      # APFS/NTFS abrem o mesmo arquivo
    caminho, motivo = a.recurso(str(raiz / "vault" / "40-Diario" / "hoje.md"))
    assert caminho is None and "protegido" in motivo
    from jaime.spatial.acoes import _dentro
    assert _dentro(Path(str((raiz / "vault").resolve()).upper() + "/x"), (raiz / "vault").resolve(), True)


def test_apagar_so_executa_o_caminho_da_previa(tmp_path):
    import json
    from jaime.spatial.config import ConfigEspacial
    from jaime.spatial.referencias import ContextoVoz, Resolvedor
    from jaime.spatial.servico import ServicoEspacial
    from jaime.spatial import tools as mod
    a, c, so, ev, rel, raiz, _ = _montar(tmp_path, dry_run=False)
    s = ServicoEspacial(ConfigEspacial(modo="camera"), emitir=lambda *x, **k: None, core=c, dono_ok=lambda: True)
    orig = mod.create_sdk_mcp_server
    mod.create_sdk_mcp_server = lambda name, version, tools: {t.name: t.handler for t in tools}
    try:
        h = mod.build_espacial_server(s, a, ContextoVoz(s, Resolvedor(c)))
    finally:
        mod.create_sdk_mcp_server = orig
    txt = lambda r: r["content"][0]["text"]
    pv = json.loads(txt(run(h["propor_acao"]({"verbo": "move_to_trash", "alvo": "rascunho", "args_json": ""}))))
    assert pv["status"] == "review" and "apagar" in pv["proximo_passo"]
    # o Vigia perguntou por OUTRO caminho: nada acontece
    assert "não confere" in txt(run(h["apagar"]({"proposta_id": pv["proposta_id"], "caminho": str(raiz / "outro.txt")})))
    assert (raiz / "bub" / "rascunho.txt").exists()
    # prévia de abrir não vira Lixeira
    po = json.loads(txt(run(h["propor_acao"]({"verbo": "open", "alvo": "BUB", "args_json": ""}))))
    assert "não é uma ida à Lixeira" in txt(run(h["apagar"]({"proposta_id": po["proposta_id"], "caminho": po["recurso"]})))
    r = json.loads(txt(run(h["apagar"]({"proposta_id": pv["proposta_id"], "caminho": pv["recurso"]}))))
    assert r["executado"] and not (raiz / "bub" / "rascunho.txt").exists()


def test_rotas_que_mudam_estado_recusam_outra_maquina_e_outro_site(tmp_path):
    from jaime.spatial import rotas
    from fastapi import HTTPException
    req = lambda host, origem="": SimpleNamespace(client=SimpleNamespace(host=host), headers={"origin": origem} if origem else {},
                                                  url=SimpleNamespace(hostname="127.0.0.1"))
    with pytest.raises(HTTPException):
        rotas._so_local(req("192.168.0.20"))
    with pytest.raises(HTTPException):
        rotas._so_local(req("127.0.0.1", "https://site-malicioso.com"))
    with pytest.raises(HTTPException):
        rotas._so_local(req("127.0.0.1", "null"))                  # iframe sandbox de qualquer site
    with pytest.raises(HTTPException):
        rotas._so_local(req("127.0.0.1", "http://evil.com:8787"))  # DNS rebinding
    rotas._so_local(req("127.0.0.1", "http://127.0.0.1:8787"))
    rotas._so_local(req("127.0.0.1"))
