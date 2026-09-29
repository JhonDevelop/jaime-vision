"""Casa: a Alexa como mãos e boca do Jaime (via Home Assistant), o lote do Vigia para o sensível e presença BLE."""
import asyncio, json
import httpx
import pytest
from jaime.casa.alexa import Alexa
from jaime.casa.bluetooth import Conhecido, Presenca, conhecidos_do_ambiente, vigiar
from jaime.casa.homeassistant import Casa
from jaime.casa.seguranca import motivo_alexa, motivo_servico
from jaime.vigia.hooks import Vigia

ESTADOS = [
    {"entity_id": "media_player.echo_sala", "state": "idle", "attributes": {"friendly_name": "Echo da Sala"}},
    {"entity_id": "media_player.echo_quarto", "state": "idle", "attributes": {"friendly_name": "Echo do Quarto"}},
    {"entity_id": "light.escritorio", "state": "on", "attributes": {"friendly_name": "Luz do Escritório"}},
    {"entity_id": "lock.porta_frente", "state": "locked", "attributes": {"friendly_name": "Porta da Frente"}},
    {"entity_id": "cover.portao_garagem", "state": "closed", "attributes": {"friendly_name": "Portão da Garagem"}},
]


def ha(backend="oficial", chamadas=None):
    chamadas = chamadas if chamadas is not None else []

    def handler(req: httpx.Request):
        p = req.url.path
        if p == "/api/services":
            doms = [{"domain": "light", "services": {"turn_on": {}}}, {"domain": "media_player", "services": {"play_media": {}}}]
            if backend == "oficial":
                doms += [{"domain": "alexa_devices", "services": {"send_text_command": {}, "send_sound": {}}},
                         {"domain": "notify", "services": {"send_message": {}}}]
            elif backend == "amp":
                doms += [{"domain": "notify", "services": {"alexa_media": {}, "alexa_media_echo_sala": {}}}]
            return httpx.Response(200, json=doms)
        if p == "/api/states":
            return httpx.Response(200, json=ESTADOS)
        if p == "/api/template":
            t = json.loads(req.content)["template"]
            if "integration_entities" in t:
                ents = ["media_player.echo_sala", "media_player.echo_quarto"]
                if backend == "oficial":
                    ents += ["notify.echo_sala_speak", "notify.echo_sala_announce", "notify.echo_quarto_speak", "notify.echo_quarto_announce"]
                return httpx.Response(200, text=json.dumps(ents))
            if "device_id" in t:
                return httpx.Response(200, text="dev-sala" if "sala" in t else "dev-quarto")
        if p.startswith("/api/services/"):
            chamadas.append((p.removeprefix("/api/services/"), json.loads(req.content)))
            return httpx.Response(200, json=[])
        return httpx.Response(404)
    return Casa("http://ha:8123", "tok", http=httpx.AsyncClient(transport=httpx.MockTransport(handler))), chamadas


def run(c):
    return asyncio.run(c)


def test_oficial_fala_anuncia_e_manda_comando_por_texto():
    casa, ch = ha("oficial")
    a = Alexa(casa, padrao="sala")
    assert run(a.detectar()) == "oficial" and {e.device_id for e in a.echos} == {"dev-sala", "dev-quarto"}
    assert run(a.falar("A build terminou.")) == "falei em Echo da Sala"
    assert ch[-1] == ("notify/send_message", {"entity_id": "notify.echo_sala_speak", "message": "A build terminou."})
    run(a.falar("Jantar pronto", "todos", "announce"))
    assert [c[1]["entity_id"] for c in ch[-2:]] == ["notify.echo_sala_announce", "notify.echo_quarto_announce"]
    assert "Quarto" in run(a.comando("Alexa, liga o ventilador", "quarto"))
    assert ch[-1] == ("alexa_devices/send_text_command", {"device_id": "dev-quarto", "text_command": "liga o ventilador"})
    run(a.tocar("rock dos anos 80", "sala", "Spotify"))
    assert ch[-1][1]["text_command"] == "toca rock dos anos 80 no Spotify"
    run(a.volume(150, "sala")); assert ch[-1] == ("media_player/volume_set", {"entity_id": "media_player.echo_sala", "volume_level": 1.0})
    run(a.som("amzn_sfx_doorbell_chime_01", "sala")); assert ch[-1][0] == "alexa_devices/send_sound"


def test_alexa_media_player_usa_notify_e_play_media_custom():
    casa, ch = ha("amp")
    a = Alexa(casa)
    assert run(a.detectar()) == "amp"
    run(a.falar("oi", "quarto", "announce"))
    assert ch[-1] == ("notify/alexa_media", {"message": "oi", "target": ["media_player.echo_quarto"], "data": {"type": "announce", "method": "all"}})
    run(a.comando("toca Legião Urbana", "sala"))
    assert ch[-1] == ("media_player/play_media", {"entity_id": "media_player.echo_sala", "media_content_type": "custom",
                                                   "media_content_id": "toca Legião Urbana"})
    assert "oficial" in run(a.som("x"))


def test_sem_integracao_ou_lugar_inexistente_explica():
    casa, ch = ha("nenhum")
    a = Alexa(casa)
    assert "Alexa Devices" in run(a.falar("oi")) and ch == []
    casa, ch = ha("oficial")
    a = Alexa(casa)
    assert "Tenho: Echo da Sala, Echo do Quarto" in run(a.falar("oi", "piscina"))


def test_o_que_e_sensivel():
    for t in ("compra pilhas", "Alexa, peça uma pizza", "liga para a minha mãe", "faz um drop in na sala", "manda uma mensagem pro Rafael",
              "destranca a porta da frente", "abre o portão", "desarma o alarme", "desliga a câmera da garagem"):
        assert motivo_alexa(t), t
    for t in ("toca Coldplay", "liga o ventilador", "apaga a luz da sala", "que horas são", "abre a cortina"):
        assert motivo_alexa(t) is None, t
    assert motivo_servico("lock", "unlock", "lock.porta_frente") and motivo_servico("alarm_control_panel", "alarm_disarm", "x")
    assert motivo_servico("cover", "open_cover", "cover.portao_garagem") and not motivo_servico("cover", "open_cover", "cover.cortina_sala")
    assert motivo_servico("light", "turn_on", "light.x") is None


def _ferramentas(casa, vigia, alexa):
    from jaime.casa import tools as mod
    orig = mod.create_sdk_mcp_server
    mod.create_sdk_mcp_server = lambda name, version, tools: {t.name: t.handler for t in tools}
    try:
        return mod.build_casa_server(casa, "0", vigia=vigia, alexa=alexa)
    finally:
        mod.create_sdk_mcp_server = orig


def txt(r):
    return r["content"][0]["text"]


def test_comando_sensivel_vai_para_o_lote_do_vigia_e_so_sai_com_o_sim():
    casa, ch = ha("oficial")
    v = Vigia()
    h = _ferramentas(casa, v, Alexa(casa, "sala"))
    r = txt(run(h["alexa_comando"]({"texto": "compra pilhas AA", "lugar": "sala"})))
    assert "VIGIA" in r and ch == [] and v.lote and "compra pilhas AA" in v.pedir_lote()
    assert "liga o ventilador" in txt(run(h["alexa_comando"]({"texto": "liga o ventilador", "lugar": "sala"})))   # livre
    v.liberar_lote()
    run(h["alexa_comando"]({"texto": "compra pilhas AA", "lugar": "sala"}))
    assert ch[-1][1]["text_command"] == "compra pilhas AA"
    ch.clear()
    run(h["alexa_comando"]({"texto": "compra pilhas AA", "lugar": "sala"}))            # o sim valeu UMA vez
    assert ch == []


def test_destrancar_pelo_ha_tambem_passa_pelo_vigia_e_visita_nao_faz():
    casa, ch = ha("oficial")
    v = Vigia()
    h = _ferramentas(casa, v, Alexa(casa))
    args = {"dominio": "lock", "acao": "unlock", "entity_id": "lock.porta_frente", "dados": ""}
    assert "VIGIA" in txt(run(h["casa_servico"](args))) and ch == []
    v.armar()                                                                         # o João disse "confirmo"
    run(h["casa_servico"](args)); assert ch[-1][0] == "lock/unlock"
    run(h["casa_servico"]({"dominio": "light", "acao": "turn_on", "entity_id": "light.escritorio", "dados": ""}))
    assert ch[-1][0] == "light/turn_on"
    v.convidado = "Gabriel"; v.armar()
    assert "visita" in txt(run(h["casa_servico"](args)))
    assert "visita" in txt(run(h["alexa_comando"]({"texto": "abre o portão", "lugar": ""})))


def test_presenca_com_histerese_e_ausencia():
    t = [0.0]
    p = Presenca([Conhecido("celular do João", nome="iPhone de João")], relogio=lambda: t[0], ausencia_s=300)
    assert p.atualizar([("iPhone de João", "AA", -85)]) == []                    # fraco demais para "chegou"
    ev = p.atualizar([("iPhone de João", "AA", -60), ("Fone de estranho", "BB", -40)])
    assert ev == [{"presenca": "chegou", "quem": "joao", "aparelho": "celular do João", "rssi": -60}] and p.em_casa()
    t[0] = 200; assert p.atualizar([("iPhone de João", "AA", -86)]) == []           # fraco, mas dentro da histerese: continua
    t[0] = 450; assert p.atualizar([]) == []                                       # 250 s desde o último: ainda em casa
    t[0] = 600; assert p.atualizar([])[0]["presenca"] == "saiu" and not p.em_casa()


def test_conhecidos_do_ambiente_e_vigia_sem_bleak():
    cs = conhecidos_do_ambiente({"JAIME_BT_CONHECIDOS": "celular=iPhone de João;relógio=AA:BB:CC:DD:EE:FF"})
    assert cs[0].nome == "iPhone de João" and cs[1].endereco == "AA:BB:CC:DD:EE:FF"
    ev = []
    async def scanner():
        raise ImportError("bleak")
    run(vigiar(Presenca(cs), lambda tipo, **d: ev.append(d), scanner=scanner))
    assert ev[0]["presenca"] == "indisponivel"
    ev.clear()
    rodadas = []
    async def scanner2():
        rodadas.append(1)
        if len(rodadas) > 1:
            raise asyncio.CancelledError
        return [("iPhone de João", "x", -50)]
    chegadas = []
    with pytest.raises(asyncio.CancelledError):
        run(vigiar(Presenca(cs), lambda tipo, **d: ev.append(d), ao_chegar=chegadas.append, intervalo=0, scanner=scanner2))
    assert ev[0]["presenca"] == "chegou" and chegadas


def test_blocos_da_casa(monkeypatch):
    from types import SimpleNamespace
    from jaime.blocos.fontes import padrao
    estados = ESTADOS + [{"entity_id": "binary_sensor.porta", "state": "on", "attributes": {"device_class": "door"}},
                         {"entity_id": "sensor.sala_temp", "state": "24.5", "attributes": {"unit_of_measurement": "°C", "friendly_name": "Sala"}}]
    monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(json=lambda: estados))
    j = SimpleNamespace(casa=SimpleNamespace(ativa=True, url="http://ha", token="t"), presenca=Presenca([Conhecido("celular", "iPhone")]))
    f = padrao(j)
    tipo, c = f.ler("casa.resumo")
    assert tipo == "metricas" and c["itens"][0]["valor"] == "1" and c["itens"][1]["estado"] == "atencao" and c["itens"][2]["valor"] == "24.5"
    assert f.get("casa.resumo").privada and "ninguém" in f.ler("casa.presenca")[1]["texto"]
