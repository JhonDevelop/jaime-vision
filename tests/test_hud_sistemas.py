"""fase 3 — HUD: /hud/sistemas monta a fotografia dos subsistemas sem depender de nenhum módulo real."""
from datetime import datetime
from types import SimpleNamespace as NS
from jaime.hud.sistemas import montar

class _Acao:
    def __init__(self, d, c): self.descricao, self.classe = d, c

def test_montar_com_tudo_vazio():
    r = montar(NS(), None, None, None)
    assert r["vigia"] == {"lote": [], "armado": False, "executando_lote": False}
    assert r["fila"]["itens"] == [] and r["equipe"] == [] and r["pendentes"] == []
    assert r["estudo"]["abertos"] == 0 and r["orcamento"] is None and r["vontades"] is None
    assert r["mente"] == {"total": 0, "ocupado": False, "a_dizer": 0, "ultimo": None}
    assert r["rotina"]["janela"] in ("noite", "atento", "ocioso")

def test_montar_com_lote_fila_filhos_e_estudo():
    fila = NS(dados=lambda: [{"id": 1, "resumo": "abre o Finder", "estado": "interrompida"}],
              atual=None, aguardando=NS(id=1), plano_de_retomada=lambda d: ("perguntar", "Continuo o que eu dizia sobre abre o Finder?"))
    ouvido = NS(fila=fila, ativo=True, ocupado=False, erro=None, barge_in="fone", antecipador=object(), fluxo=NS(nome="deepgram"),
                latencias=NS(mediana=lambda: 0.64))
    jaime = NS(vigia=NS(lote=[_Acao("enviar o e-mail para o Rafael", "email"), _Acao("mover a pasta X", "arquivo")], _armado_ate=0.0, lote_executado=False),
               equipe=NS(filhos={"maester-dev": NS(nome="maester-dev", tipo="terminal", estado="vivo", preset="dev", tarefas=2, ultimo_relatorio="pronto")}),
               estudo=NS(problemas=NS(abertos=lambda: [NS(titulo="Whisper em GPU")]), ocupado=True, pode_estudar=lambda: (False, "modo atento"), ultimo_ciclo=0.0),
               autonomo=NS(missao=NS(estado="pausada", objetivo="organizar downloads")),
               evolucao=NS(propostas=lambda: [NS(estado="pronta", titulo="cache do vault")]),
               aguardando_nome=False, humor=NS(dados=lambda: {"rotulo": "leve"}), estado=NS(secao=lambda s: "1) testar\n2) commitar"),
               pensar=NS(pensamentos=[NS(tema="BUB", texto="o build quebra sempre no pod install", quando="2026-09-16 09:00", vale_dizer=True)], ocupado=False))
    state = NS(atencao=NS(ultima_fala=datetime(2026, 9, 15, 10, 0).timestamp() - 60),
               orcamento=NS(estado=lambda: {"total": 1.2, "teto": 5.0, "fatias": {}}, ativo=True, resumo=lambda: "US$ 1.20 de 5.00"),
               vontade=NS(impulsos=NS(dados=lambda: {"niveis": {"utilidade": 1.0}}), mente=NS(ultima=NS(dados=lambda: {"pensamento": "quero estudar porque..."}))))
    r = montar(jaime, ouvido, state, NS(voz_modo="duplex"), agora=datetime(2026, 9, 15, 10, 0))
    assert [a["descricao"] for a in r["vigia"]["lote"]] == ["enviar o e-mail para o Rafael", "mover a pasta X"]
    assert r["fila"]["aguardando"] == 1 and "Continuo" in r["fila"]["pergunta"]
    assert r["equipe"][0]["nome"] == "maester-dev" and r["equipe"][0]["estado"] == "vivo"
    assert r["estudo"] == {"abertos": 1, "ocupado": True, "pode": False, "motivo": "modo atento", "ultimo_ciclo": 0.0, "titulos": ["Whisper em GPU"]}
    assert r["rotina"]["janela"] == "atento" and r["rotina"]["min_sem_fala"] == 1
    assert r["orcamento"]["ativo"] and r["orcamento"]["resumo"].startswith("US$")
    assert r["vontades"]["escolha"]["pensamento"].startswith("quero")
    assert r["ouvido"]["latencia_mediana_ms"] == 640 and r["ouvido"]["stt"] == "deepgram" and r["ouvido"]["modo"] == "duplex"
    tipos = [p["tipo"] for p in r["pendentes"]]
    assert tipos == ["vigia", "fila", "autonomo", "evolucao"]
    assert r["pendentes"][0]["texto"].startswith("Você deseja que eu enviar o e-mail")
    assert r["proximos"].startswith("1) testar")
    assert r["mente"] == {"total": 1, "ocupado": False, "a_dizer": 1, "ultimo": {"tema": "BUB", "texto": "o build quebra sempre no pod install", "quando": "2026-09-16 09:00", "vale_dizer": True}}
