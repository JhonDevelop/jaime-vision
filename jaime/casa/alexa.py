"""Alexa como mãos e boca do J.A.I.M.E dentro de casa — ele manda, ela executa.

O Jaime continua sendo o cérebro (entende, decide, confere, lembra). A Alexa vira um periférico: os Echos são
alto-falantes espalhados pela casa, e tudo que ela sabe fazer por voz (tocar música no Amazon Music/Spotify,
ligar coisas que só existem no app Alexa, rotinas, timers, volume) ele manda por texto, como se falasse com ela.

Caminho: Home Assistant ↔ Alexa. Dois backends, detectados sozinhos:
- `alexa_devices` — integração OFICIAL do Home Assistant (core): entidades notify `…_speak` e `…_announce`,
  ações `alexa_devices.send_text_command` (texto dito como voz) e `alexa_devices.send_sound`.
  Exige conta Amazon com 2FA por app autenticador. https://www.home-assistant.io/integrations/alexa_devices/
- `alexa_media` — Alexa Media Player (HACS, não oficial): `notify.alexa_media` (tts/announce) e
  `media_player.play_media` com `media_content_type: custom` para comandos de texto.
Os dois usam a API não oficial da Amazon: podem quebrar quando a Amazon muda algo. O domínio da conta precisa ser
o do Brasil (amazon.com.br) para os Echos daqui aparecerem.

O que é sensível ("compra…", "liga para…", "destranca…") passa pelo lote do Vigia (seguranca.py) antes de sair.
"""
from __future__ import annotations
import json, re, unicodedata
from dataclasses import dataclass, field


def _n(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


@dataclass
class Echo:
    entity_id: str                      # media_player.echo_sala
    nome: str
    device_id: str = ""                 # do registro de dispositivos do HA (backend oficial)
    notify_speak: str = ""              # notify.echo_sala_speak (oficial)
    notify_announce: str = ""
    extras: dict = field(default_factory=dict)


class Alexa:
    def __init__(self, casa, padrao: str = ""):
        self.casa = casa
        self.padrao = padrao                 # onde falar quando o pedido não diz (JAIME_ALEXA_PADRAO: "sala")
        self.backend: str | None = None      # "oficial" | "amp" | "" (nenhum)
        self.echos: list[Echo] = []

    # ── descoberta ─────────────────────────────────────
    async def detectar(self, forcar: bool = False) -> str:
        if self.backend is not None and not forcar:
            return self.backend
        dom = await self.casa.dominios_de_servico()
        if "alexa_devices" in dom:
            self.backend = "oficial"
        elif "alexa_media" in dom or "alexa_media" in (await self.casa.servicos_do_dominio("notify")):
            self.backend = "amp"
        else:
            self.backend = ""
        self.echos = await self._echos() if self.backend else []
        return self.backend

    async def _echos(self) -> list[Echo]:
        integ = "alexa_devices" if self.backend == "oficial" else "alexa_media"
        bruto = await self.casa.template("{{ integration_entities('%s') | tojson }}" % integ)
        try:
            ents = json.loads(bruto or "[]")
        except json.JSONDecodeError:
            ents = []
        estados = {e["id"]: e for e in await self.casa.estados()}
        players = [e for e in ents if e.startswith("media_player.")]
        notifies = [e for e in ents if e.startswith("notify.")]
        out = []
        for p in players:
            base = p.split(".", 1)[1]
            eco = Echo(p, estados.get(p, {}).get("nome", base))
            if self.backend == "oficial":
                eco.device_id = (await self.casa.template("{{ device_id('%s') }}" % p) or "").strip()
                mesmos = [n for n in notifies if n.split(".", 1)[1].startswith(base)]
                eco.notify_speak = next((n for n in mesmos if n.endswith("_speak")), "")
                eco.notify_announce = next((n for n in mesmos if n.endswith("_announce")), "")
            out.append(eco)
        return out

    def onde(self, lugar: str = "") -> list[Echo]:
        """'sala' → o Echo da sala; 'todos'/'casa toda' → todos; vazio → o padrão (ou o primeiro)."""
        if not self.echos:
            return []
        l = _n(lugar or self.padrao)
        if l in ("todos", "casa toda", "casa inteira", "todo lugar", "tudo"):
            return list(self.echos)
        if not l:
            return self.echos[:1]
        toks = [t for t in re.findall(r"\w+", l) if len(t) > 2 and t not in ("echo", "alexa", "dot", "show", "na", "no", "da", "do")]
        pont = sorted(((sum(t in _n(f"{e.nome} {e.entity_id}") for t in toks), e) for e in self.echos), key=lambda x: -x[0])
        return [pont[0][1]] if pont and pont[0][0] > 0 else []

    # ── ações ──────────────────────────────────────────
    async def falar(self, texto: str, lugar: str = "", modo: str = "speak") -> str:
        """Ela fala (speak) ou anuncia com o sininho (announce). É a voz da Alexa, não a do Jaime."""
        await self.detectar()
        alvo = self.onde(lugar)
        if not alvo:
            return self._sem_echo(lugar)
        texto = texto.strip()[:500]
        for e in alvo:
            if self.backend == "oficial":
                ent = e.notify_announce if modo == "announce" and e.notify_announce else e.notify_speak
                if not ent:
                    return f"o Echo {e.nome} não tem entidade de fala no HA"
                await self.casa._req("POST", "services/notify/send_message", {"entity_id": ent, "message": texto})
            else:
                await self.casa._req("POST", "services/notify/alexa_media",
                                     {"message": texto, "target": [e.entity_id], "data": {"type": "announce" if modo == "announce" else "tts",
                                                                                         **({"method": "all"} if modo == "announce" else {})}})
        return f"{'anunciei' if modo == 'announce' else 'falei'} em {', '.join(e.nome for e in alvo)}"

    async def comando(self, texto: str, lugar: str = "") -> str:
        """Qualquer coisa que se fala para a Alexa, mandada como texto. O filtro de sensível fica na ferramenta."""
        await self.detectar()
        alvo = self.onde(lugar)
        if not alvo:
            return self._sem_echo(lugar)
        e = alvo[0]
        texto = re.sub(r"^\s*alexa[,!]?\s*", "", texto.strip(), flags=re.I)[:300]
        if self.backend == "oficial":
            if not e.device_id:
                return f"não achei o device_id do {e.nome} no HA"
            await self.casa._req("POST", "services/alexa_devices/send_text_command", {"device_id": e.device_id, "text_command": texto})
        else:
            await self.casa._req("POST", "services/media_player/play_media",
                                 {"entity_id": e.entity_id, "media_content_type": "custom", "media_content_id": texto})
        return f"pedi à Alexa ({e.nome}): «{texto}»"

    async def tocar(self, o_que: str, lugar: str = "", servico: str = "") -> str:
        s = f" no {servico}" if servico else ""
        return await self.comando(f"toca {o_que}{s}", lugar)

    async def parar(self, lugar: str = "") -> str:
        return await self.comando("para", lugar)

    async def volume(self, nivel: int, lugar: str = "") -> str:
        await self.detectar()
        alvo = self.onde(lugar)
        if not alvo:
            return self._sem_echo(lugar)
        v = max(0, min(100, int(nivel))) / 100
        for e in alvo:
            await self.casa._req("POST", "services/media_player/volume_set", {"entity_id": e.entity_id, "volume_level": v})
        return f"volume {int(v * 100)}% em {', '.join(e.nome for e in alvo)}"

    async def som(self, som: str, lugar: str = "") -> str:
        await self.detectar()
        if self.backend != "oficial":
            return "sons prontos só pela integração oficial Alexa Devices"
        alvo = self.onde(lugar)
        if not alvo:
            return self._sem_echo(lugar)
        await self.casa._req("POST", "services/alexa_devices/send_sound", {"device_id": alvo[0].device_id, "sound": som})
        return f"som {som} no {alvo[0].nome}"

    def _sem_echo(self, lugar: str) -> str:
        if not self.backend:
            return ("nenhuma integração Alexa no Home Assistant — instale 'Alexa Devices' (oficial) ou 'Alexa Media Player' "
                    "(HACS) e reinicie; docs/CASA.md")
        return f"não achei Echo em '{lugar}'. Tenho: {', '.join(e.nome for e in self.echos) or 'nenhum'}"

    def estado(self) -> dict:
        return {"backend": self.backend, "echos": [{"id": e.entity_id, "nome": e.nome} for e in self.echos], "padrao": self.padrao}
