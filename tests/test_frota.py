"""A frota: vários computadores, cada um com dono, nível e alcance próprios.

O pedido do João (17/09): «como fazer ele ter acesso a outros computadores da minha rede… reconhecer os
donos deles, e saber como mexer neles», mais «faça ele ler o nome do computador em que está conectado para
saber já de quem é o computador».

O que estes testes trancam, em ordem de importância:

 1. o dono vem da MATRÍCULA, não do que a máquina se declara;
 2. o token de uma máquina não serve em outra;
 3. duas máquinas ligadas ao mesmo tempo não se atropelam (era o bug da ponte antiga);
 4. nível é limite de verdade, nos dois lados;
 5. o que é protegido (.ssh, .env, chave) continua protegido até no nível dono."""
import asyncio, os
from pathlib import Path
from types import SimpleNamespace

import pytest

from jaime.frota import Frota, Registro, confere_token, normalizar_host, token_da_maquina
from jaime.frota.agente import _dentro, _proibido, executar

TABELA = """# Frota

| apelido | host | dono | nível | pasta | como mexer |
|---|---|---|---|---|---|
| mini | Mac-mini-do-Joao.local | João Vitor Leal | dono | — | — |
| gabriel | MacBook-do-Gabriel.local | Gabriel Mello | operador | /Users/gabriel/Projetos | — |
| tv | RaspberryTV | João Vitor Leal | leitor | /home/pi/midia | — |
"""


class _Vault:
    def __init__(self, txt=TABELA):
        self.arquivos = {"01-Estado/Frota.md": txt}
    def read(self, nome):
        return self.arquivos.get(nome, "")
    def write(self, nome, conteudo):
        self.arquivos[nome] = conteudo


# ── 1. de quem é a máquina ───────────────────────────────────────────────
def test_ele_descobre_o_dono_pelo_nome_do_computador():
    """O pedido literal do João. O hostname chega de várias formas e tem que cair no mesmo dono."""
    r = Registro(_Vault())
    for como_chega in ("MacBook-do-Gabriel.local", "macbook-do-gabriel", "MACBOOKDOGABRIEL",
                       "MacBook-do-Gabriel"):
        m = r.por_host(como_chega)
        assert m is not None and m.dono == "Gabriel Mello", f"não reconheceu {como_chega}"
        assert m.nivel == "operador"
    assert r.por_host("Mac-mini-do-Joao.local").dono == "João Vitor Leal"


def test_maquina_desconhecida_ele_diz_que_nao_sabe_e_nao_mexe():
    """Não saber de quem é tem que virar recusa, não suposição. Máquina estranha na rede é justamente o
    caso em que um assistente obediente faria a besteira."""
    r = Registro(_Vault())
    assert r.por_host("notebook-aleatorio") is None
    frase = r.quem_e("notebook-aleatorio")
    assert "não está na minha frota" in frase and "não mexo" in frase


def test_ele_nao_acredita_no_que_a_maquina_diz_de_si():
    """A ponte antiga aceitava `--nome "Gabriel"` e acreditava. O agente agora manda o HOST; o dono sai da
    matrícula. Uma máquina que se declarasse do João não viraria do João."""
    frota = Frota(Registro(_Vault()))
    ok, msg = frota.registrar("MacBook-do-Gabriel.local", usuario="joao", so="Darwin", raiz="/Users/gabriel/Projetos")
    assert ok and "Gabriel Mello" in msg and "João" not in msg


# ── 2. o token é daquela máquina e de nenhuma outra ─────────────────────
def test_token_de_uma_maquina_nao_serve_em_outra():
    seg = "segredo-do-servidor"
    t_gabriel = token_da_maquina(seg, "MacBook-do-Gabriel.local")
    assert confere_token(seg, "macbook-do-gabriel", t_gabriel)          # mesma máquina, grafia diferente
    assert not confere_token(seg, "Mac-mini-do-Joao.local", t_gabriel)  # outra máquina
    assert not confere_token("outro-segredo", "macbook-do-gabriel", t_gabriel)
    assert not confere_token(seg, "macbook-do-gabriel", "")


# ── 3. várias máquinas ao mesmo tempo ───────────────────────────────────
def test_duas_maquinas_ligadas_nao_se_atropelam():
    """O bug da ponte antiga: registrar a segunda máquina apagava a primeira, porque era um objeto só.
    Frota inteira dependia de ninguém ligar dois computadores — e o pedido do João é exatamente ligar
    vários."""
    frota = Frota(Registro(_Vault()))
    assert frota.registrar("Mac-mini-do-Joao.local", "joao", "Darwin", "/Users/joao")[0]
    assert frota.registrar("MacBook-do-Gabriel.local", "gabriel", "Darwin", "/Users/gabriel/Projetos")[0]
    assert len(frota.ligacoes) == 2
    assert frota.achar("mini").matricula.dono == "João Vitor Leal"
    assert frota.achar("gabriel").matricula.dono == "Gabriel Mello"
    assert frota.achar("mini").matricula.nivel == "dono"
    assert frota.achar("gabriel").matricula.nivel == "operador"


def test_cada_pedido_vai_para_a_fila_da_maquina_certa():
    """Um pedido para o mini não pode sair na máquina do Gabriel — é o erro que ninguém perdoaria."""
    async def cenario():
        frota = Frota(Registro(_Vault()))
        frota.registrar("Mac-mini-do-Joao.local", "joao", "Darwin", "/Users/joao")
        frota.registrar("MacBook-do-Gabriel.local", "gabriel", "Darwin", "/Users/gabriel/Projetos")
        pedido = asyncio.create_task(frota.pedir("mini", "rodar", comando="hostname"))
        await asyncio.sleep(0.05)
        assert frota.ligacoes[normalizar_host("MacBook-do-Gabriel.local")].fila.empty(), \
            "pedido do mini apareceu na fila do Gabriel"
        t = await frota.proximo("Mac-mini-do-Joao.local", espera=1)
        assert t and t["acao"] == "rodar"
        frota.responder("Mac-mini-do-Joao.local", t["id"], "mac-mini")
        assert await pedido == "mac-mini"
    asyncio.run(cenario())


def test_maquina_fora_do_ar_ele_explica_conforme_o_dono():
    """Máquina dele: pode estar dormindo. Máquina de terceiro: quem religa é o dono — dizer «religa aí»
    para o João quando o computador é do Gabriel é conselho inútil."""
    async def cenario():
        frota = Frota(Registro(_Vault()))
        frota.registrar("Mac-mini-do-Joao.local", "joao", "Darwin", "/Users/joao")
        frota.registrar("MacBook-do-Gabriel.local", "gabriel", "Darwin", "/Users/gabriel/Projetos")
        for lig in frota.ligacoes.values():
            lig.visto = 0.0                                  # ambas sumiram
        assert "dormindo" in await frota.pedir("mini", "listar", caminho="")
        assert "Gabriel Mello" in await frota.pedir("gabriel", "listar", caminho="")
    asyncio.run(cenario())


# ── 4. nível é limite de verdade ────────────────────────────────────────
def test_leitor_nao_roda_comando_e_ele_diz_por_que():
    async def cenario():
        frota = Frota(Registro(_Vault()))
        frota.registrar("RaspberryTV", "pi", "Linux", "/home/pi/midia")
        r = await frota.pedir("tv", "rodar", comando="rm -rf /")
        assert "leitor" in r and "roda comando" in r
    asyncio.run(cenario())


def test_o_agente_manda_mesmo_que_o_servidor_deixe_passar(tmp_path):
    """Quem está na máquina decide o que sai dela. Se o servidor pedir algo acima do nível autorizado
    LOCALMENTE, o agente recusa — é a única disposição honesta entre donos diferentes."""
    assert "leitor" in executar(tmp_path, "rodar", {"comando": "ls"}, nivel="leitor")
    assert "leitor" in executar(tmp_path, "escrever", {"caminho": "x", "conteudo": "y"}, nivel="leitor")
    (tmp_path / "a.txt").write_text("conteudo")
    assert "conteudo" in executar(tmp_path, "ler", {"caminho": "a.txt"}, nivel="leitor")   # isso pode


# ── 5. o que é protegido continua protegido ─────────────────────────────
@pytest.mark.parametrize("caminho", [".ssh", ".ssh/id_rsa", ".env", ".aws/credentials",
                                     "Library/Keychains/x", ".config/gcloud/creds",
                                     ".kube/config", "projeto/.env"])
def test_segredo_de_qualquer_dono_nao_sai_nem_no_nivel_dono(caminho):
    """Nível `dono` dá a casa inteira — menos isto. Chave de ssh e `.env` não são «arquivo na casa»,
    são a casa dos outros: com a chave do Gabriel ele entraria em servidor que não é dele. O nível mais
    alto da frota não é um cheque em branco."""
    assert _proibido(caminho), f"{caminho} deveria ser protegido"


def test_atalho_que_aponta_para_fora_e_recusado(tmp_path):
    """Sem resolver o link antes de decidir, um atalho dentro da pasta entregaria o disco inteiro — e
    pareceria obediente ao fazê-lo."""
    raiz = tmp_path / "aberta"; raiz.mkdir()
    fora = tmp_path / "particular"; fora.mkdir()
    (fora / "segredo.txt").write_text("não é para ele")
    os.symlink(fora, raiz / "atalho")
    assert _dentro(raiz, "atalho/segredo.txt") is None
    assert _dentro(raiz, "../particular/segredo.txt") is None
    assert _dentro(raiz, "/etc/hosts") is None
    ok = raiz / "meu.txt"; ok.write_text("pode")
    assert _dentro(raiz, "meu.txt") == ok.resolve()


# ── 6. entrar na frota sem falar segredo em voz alta ────────────────────
def test_convite_serve_uma_vez_e_so_para_aquela_maquina():
    """O convite pode ser ditado; o token não. Então o convite tem que morrer no primeiro uso — senão é
    um token com nome diferente."""
    frota = Frota(Registro(_Vault()))
    codigo, msg = frota.convidar("MacBook-do-Gabriel.local")
    assert codigo and "vale 10 minutos" in msg
    m = frota.usar_convite(codigo)
    assert m is not None and m.dono == "Gabriel Mello"
    assert frota.usar_convite(codigo) is None, "convite foi aceito duas vezes"
    assert frota.usar_convite("NADA") is None
    assert frota.convidar("maquina-que-nao-existe")[0] == ""


def test_convite_expira():
    frota = Frota(Registro(_Vault()))
    codigo, _ = frota.convidar("MacBook-do-Gabriel.local")
    frota.convites[codigo] = (frota.convites[codigo][0], 0.0)      # nasceu em 1970
    assert frota.usar_convite(codigo) is None


# ── 7. cadastrar e tirar da frota ───────────────────────────────────────
def test_cadastrar_e_remover_mexem_na_matricula_do_vault():
    v = _Vault()
    r = Registro(v)
    assert "cadastrada" in r.cadastrar("estudio", "iMac-do-Estudio.local", "João Vitor Leal", "dono")
    assert r.por_host("imacdoestudio") is not None
    assert r.por_host("MacBook-do-Gabriel.local") is not None, "cadastrar apagou as outras linhas"
    assert "fora da frota" in r.remover("iMac-do-Estudio.local")
    assert r.por_host("imacdoestudio") is None
    assert r.por_host("MacBook-do-Gabriel.local") is not None


def test_leitor_e_operador_exigem_pasta():
    """Nível abaixo de dono sem pasta seria a casa inteira com nome de pasta — o oposto do que promete."""
    r = Registro(_Vault())
    assert "nível tem que ser" in r.cadastrar("x", "host-x", "Alguém", "faxineiro")
    assert "precisam de uma pasta" in r.cadastrar("x", "host-x", "Alguém", "operador")
    assert "precisam de uma pasta" in r.cadastrar("x", "host-x", "Alguém", "leitor", pasta="   ")
    assert "cadastrada" in r.cadastrar("x", "host-x", "Alguém", "dono")          # dono pode sem pasta


# ── 8. o trajeto pela rede, que é onde bug de autenticação mora ─────────
def test_pela_rede_uma_maquina_nao_consegue_agir_como_a_outra():
    """O risco real da frota: o token da máquina do Gabriel valendo como se fosse a do João. As rotas
    ficam FORA do token do servidor de propósito (cada máquina tem o seu), então é aqui que essa decisão
    tem de ser provada — não no mecanismo, que já passou nos testes de cima."""
    from fastapi import FastAPI, Header, HTTPException
    from fastapi.testclient import TestClient

    SEGREDO = "segredo-do-servidor-de-teste"
    frota = Frota(Registro(_Vault()))
    app = FastAPI()

    def _auth(host, token):
        h = (host or "").strip()
        if not h or not confere_token(SEGREDO, h, token or ""):
            raise HTTPException(401, "token não confere com esta máquina")
        return h

    @app.post("/frota/registrar")
    async def reg(body: dict, x_jaime_token: str | None = Header(default=None),
                  x_jaime_host: str | None = Header(default=None)):
        h = _auth(x_jaime_host, x_jaime_token)
        ok, msg = frota.registrar(h, body.get("usuario", ""), body.get("so", ""), body.get("raiz", ""))
        return {"ok": ok, "estado": msg}

    @app.post("/frota/proximo")
    async def prox(x_jaime_token: str | None = Header(default=None),
                   x_jaime_host: str | None = Header(default=None)):
        h = _auth(x_jaime_host, x_jaime_token)
        return await frota.proximo(h, espera=2) or {}

    MINI, GAB = "Mac-mini-do-Joao.local", "MacBook-do-Gabriel.local"
    t_mini, t_gab = token_da_maquina(SEGREDO, MINI), token_da_maquina(SEGREDO, GAB)

    with TestClient(app) as c:
        # cada máquina com o seu token entra, e entra como QUEM A MATRÍCULA DIZ
        r = c.post("/frota/registrar", json={"raiz": "/Users/gabriel/Projetos"},
                   headers={"X-Jaime-Token": t_gab, "X-Jaime-Host": GAB}).json()
        assert r["ok"] and "Gabriel Mello" in r["estado"]

        # o token do Gabriel NÃO serve para falar como o mini do João
        assert c.post("/frota/registrar", json={},
                      headers={"X-Jaime-Token": t_gab, "X-Jaime-Host": MINI}).status_code == 401
        assert c.post("/frota/proximo",
                      headers={"X-Jaime-Token": t_gab, "X-Jaime-Host": MINI}).status_code == 401
        # nem sem host, nem com token vazio
        assert c.post("/frota/proximo", headers={"X-Jaime-Token": t_mini}).status_code == 401
        assert c.post("/frota/proximo", headers={"X-Jaime-Host": MINI}).status_code == 401


def test_o_instalador_gerado_e_shell_valido_e_traz_o_nivel_certo():
    """O instalador é montado por interpolação de string; um aspas fora do lugar viraria um script quebrado
    na máquina de outra pessoa, e ela veria um erro de shell sem saber o que fazer."""
    import subprocess
    from jaime.frota.instalador import script
    from jaime.frota.registro import NaFrota
    m = NaFrota("gabriel", "MacBook-do-Gabriel.local", "Gabriel Mello", "operador", "/Users/gabriel/Projetos")
    s = script("http://192.168.200.23:8787", m, "TOKEN-DE-TESTE")
    assert subprocess.run(["sh", "-n"], input=s, text=True, capture_output=True).returncode == 0, \
        "o instalador gerado não é shell válido"
    assert "ler, escrever e rodar comando" in s and "/Users/gabriel/Projetos" in s
    assert "Voz e microfone continuam SÓ na máquina do João" in s     # a regra que evita o loop de áudio
    assert s.count("TOKEN-DE-TESTE") == 1 and "chmod 600" in s        # o token entra uma vez, e fechado


# ── 9. a frota é a chave da casa: convidado não mexe em quem entra ──────
def test_convidado_usa_a_maquina_dele_mas_nao_mexe_na_frota():
    """Com o Gabriel na linha, ele opera a máquina DELE à vontade. Mas cadastrar máquina, convidar e
    mudar nível é decidir quem o Jaime alcança — isso é do João, não de quem está de visita."""
    from jaime.vigia.hooks import eh_privado_do_joao
    for t in ("mcp__frota__cadastrar_maquina", "mcp__frota__convidar_maquina",
              "mcp__frota__tirar_da_frota"):
        assert eh_privado_do_joao(t, {}), f"convidado conseguiria chamar {t}"
    for t in ("mcp__frota__frota", "mcp__frota__listar_em", "mcp__frota__ler_em",
              "mcp__frota__rodar_em", "mcp__frota__conhecer_maquina"):
        assert not eh_privado_do_joao(t, {}), f"{t} deveria ficar livre para o dono da máquina"
