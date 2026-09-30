"""Briefing do "bom dia" — o vídeo de 1:22, de verdade.

O João diz "bom dia" (de manhã, a primeira vez no dia) ou "me dá o briefing". O Jaime:
1. fala na hora que revisou o que ficou de ontem ("Sem desvios relevantes" ou o desvio que achou) — enquanto isso
   já está coletando, em paralelo, clima, agenda, e-mails, notícias e saúde (o card "BRIEFING MATINAL" acende
   cada etapa quando ela chega);
2. monta um roteiro de segmentos — cada um com a FRASE falada e o CARD que aparece no orbe no momento em que a
   voz começa aquela frase (a tela casa o texto do evento `voz` com o segmento);
3. fecha com uma linha de foco; os cards terminam enfileirados sob o orbe.

Eventos no barramento: `briefing` com fase inicio | etapa | roteiro | segmento | fim. A tela `/hud/jarvis` desenha.
Tudo que falhar some do roteiro sem derrubar o resto (sem Google conectado não há card de e-mail, e ele diz).
"""
from __future__ import annotations
import asyncio, json, os, re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Awaitable, Callable

from ..hud.events import bus

ETAPAS = ["AGENDA", "E-MAILS", "NOTÍCIAS", "CLIMA", "PRIORIDADES"]
PEDIDO_RX = re.compile(r"^\s*(bom dia|bom-dia)\s*[,!.]*\s*(jaime|jarvis|senhor)?\s*[,!.]*\s*$", re.I)
PEDIDO_EXPLICITO_RX = re.compile(r"\b(me d[aá] o briefing|faz(er)? o briefing|briefing (do dia|matinal|da manh[aã])|"
                                 r"resumo da manh[aã]|o que eu preciso saber hoje)\b", re.I)
CODIGO_SOL = {0: "Céu limpo", 1: "Possibilidade de sol", 2: "Parcialmente nublado", 3: "Nublado", 61: "Chuva fraca",
              63: "Chuva", 65: "Chuva forte", 80: "Pancadas de chuva", 95: "Trovoada"}


def _br(x, casas: int = 1) -> str:
    if x is None:
        return "?"
    s = f"{float(x):.{casas}f}"
    s = s.rstrip("0").rstrip(".") if "." in s else s
    return s.replace(".", ",")


@dataclass
class Segmento:
    id: str
    fala: str
    card: dict = field(default_factory=dict)

    def dados(self) -> dict:
        return asdict(self)


def quer_briefing(texto: str, agora: datetime | None = None, ja_deu_hoje: bool = False) -> bool:
    """'bom dia' puro, de manhã, na primeira vez do dia → briefing; pedido explícito → sempre."""
    if PEDIDO_EXPLICITO_RX.search(texto or ""):
        return True
    agora = agora or datetime.now()
    return bool(PEDIDO_RX.match(texto or "")) and 5 <= agora.hour < 12 and not ja_deu_hoje


class Briefing:
    def __init__(self, *, clima=None, agenda=None, emails=None, noticias=None, saude=None, desvios=None, foco=None,
                 resumir: Callable[[str, str], Awaitable[str]] | None = None, cidade: str = "", emitir=None,
                 timeout: float = 12.0):
        self.fontes = {"clima": clima, "agenda": agenda, "emails": emails, "noticias": noticias, "saude": saude}
        self.desvios, self.foco, self.resumir = desvios, foco, resumir
        self.cidade = cidade or os.environ.get("JAIME_CIDADE", "Franca")
        self.emitir = emitir or bus.emitir
        self.timeout = timeout
        self.ultimo_dia = ""
        self.ultimo: list[dict] = []

    # ── coleta ───────────────────────────────────────────
    async def _uma(self, nome: str) -> tuple[str, Any]:
        fn = self.fontes.get(nome)
        if fn is None:
            return nome, None
        try:
            r = fn()
            if asyncio.iscoroutine(r):
                r = await asyncio.wait_for(r, self.timeout)
            return nome, r
        except Exception as e:
            return nome, {"erro": f"{type(e).__name__}"}

    async def coletar(self) -> dict:
        """Coleta tudo em paralelo; a ordem em que as etapas ficaram prontas vai em dados['_ordem'] (a tela acende assim)."""
        etapa_de = {"agenda": "AGENDA", "emails": "E-MAILS", "noticias": "NOTÍCIAS", "clima": "CLIMA", "saude": "PRIORIDADES"}
        dados: dict = {"_ordem": []}
        for fut in asyncio.as_completed([self._uma(n) for n in self.fontes]):
            nome, r = await fut
            dados[nome] = r
            dados["_ordem"].append((etapa_de[nome], bool(r) and not (isinstance(r, dict) and r.get("erro"))))
        return dados

    # ── roteiro ──────────────────────────────────────────
    def seg_desvios(self, desvios: list[str]) -> Segmento:
        if desvios:
            fala = f"Revisei o que ficou de ontem. {'Há um ponto' if len(desvios) == 1 else f'Há {len(desvios)} pontos'} de atenção: {desvios[0]}."
            card = {"tipo": "status", "rotulo": "CONTINUIDADE · ONTEM", "titulo": "Pede sua atenção", "texto": "; ".join(desvios[:3]), "alerta": True}
        else:
            fala = "Revisei o que já está consolidado desde ontem. Sem desvios relevantes. Nada exige interromper sua manhã antes do briefing."
            card = {"tipo": "status", "rotulo": "CONTINUIDADE · ONTEM", "titulo": "Sem desvios relevantes",
                    "texto": "Nada exige interromper sua manhã antes do briefing", "chips": ["AGENDA", "E-MAILS", "SISTEMAS", "CASA"]}
        return Segmento("desvios", fala, card)

    def seg_clima(self, d: dict | None) -> Segmento | None:
        if not d or d.get("erro"):
            return None
        cur, dia = d.get("current", {}), d.get("daily", {})
        mx = (dia.get("temperature_2m_max") or [None])[0]; mn = (dia.get("temperature_2m_min") or [None])[0]
        chuva = (dia.get("precipitation_probability_max") or [None])[0]
        t = cur.get("temperature_2m")
        if mx is None or mn is None:
            return None
        fala = f"Em {self.cidade}, a temperatura mínima será de {_br(mn)} graus e a máxima de {_br(mx)}"
        fala += f", com chance de chuva de {chuva:.0f}%." if chuva is not None else "."
        card = {"tipo": "clima", "rotulo": f"{self.cidade.upper()} · CLIMA", "titulo": self.cidade, "temp": _br(t),
                "condicao": CODIGO_SOL.get(int(cur.get("weather_code", -1)), "Tempo instável"),
                "min": _br(mn), "max": _br(mx), "chuva": f"{chuva:.0f}%" if chuva is not None else "—"}
        return Segmento("clima", fala, card)

    def seg_agenda(self, itens) -> Segmento | None:
        if itens is None or (isinstance(itens, dict) and itens.get("erro")):
            return None
        itens = list(itens or [])
        if not itens:
            return Segmento("agenda", "Sua agenda está livre hoje.",
                            {"tipo": "agenda", "rotulo": "AGENDA · HOJE", "titulo": "Agenda livre", "vazio": "Nenhum compromisso registrado",
                             "sub": "Seu dia está livre de compromissos agendados."})
        prim = itens[0]
        hora = str(prim.get("hora") or "")[:5] or str(prim.get("inicio", ""))[11:16]
        fala = (f"Você tem {len(itens)} compromisso{'s' if len(itens) > 1 else ''} hoje; o primeiro às {hora}: {prim.get('titulo', '')}."
                if hora else f"Você tem {len(itens)} compromissos hoje.")
        return Segmento("agenda", fala, {"tipo": "agenda", "rotulo": "AGENDA · HOJE", "titulo": f"{len(itens)} compromisso{'s' if len(itens) > 1 else ''}",
                                          "itens": [{"hora": str(i.get("hora") or str(i.get("inicio", ""))[11:16]), "titulo": i.get("titulo", "")} for i in itens[:5]]})

    async def seg_emails(self, lista) -> Segmento | None:
        if lista is None or (isinstance(lista, dict) and lista.get("erro")):
            return None
        lista = list(lista or [])
        total = len(lista)
        acoes = await self._acoes_de_email(lista)
        if total == 0:
            return Segmento("emails", "Sua caixa de entrada está em dia.",
                            {"tipo": "emails", "rotulo": "COMUNICAÇÕES · E-MAIL", "titulo": "Caixa em dia", "total": 0, "agir": 0, "itens": []})
        fala = f"Há {total} e-mails na caixa, dos quais {_extenso(len(acoes))} merece{'m' if len(acoes) != 1 else ''} atenção."
        if acoes:
            fala += f" O principal: {acoes[0]['acao']}"
            if len(acoes) > 1:
                fala += f" Também: {acoes[1]['acao']}"
        card = {"tipo": "emails", "rotulo": "COMUNICAÇÕES · E-MAIL", "titulo": "Pedem sua atenção", "total": total, "agir": len(acoes),
                "itens": [{"de": a["de"].upper()[:28], "acao": a["acao"]} for a in acoes[:4]]}
        return Segmento("emails", fala, card)

    async def _acoes_de_email(self, lista: list[dict]) -> list[dict]:
        candidatos = [e for e in lista if not re.search(r"no-?reply|newsletter|notifica|marketing", e.get("de", ""), re.I)] or lista
        base = [{"de": _nome(e.get("de", "")), "acao": (e.get("assunto") or "").strip().rstrip(".") + "."} for e in candidatos[:5]]
        if not self.resumir or not candidatos:
            return base
        texto = "\n".join(f"- DE: {e.get('de','')} | ASSUNTO: {e.get('assunto','')} | TRECHO: {e.get('resumo','')[:220]}" for e in candidatos[:12])
        prompt = ("Destes e-mails de hoje, quais pedem uma AÇÃO do João? Responda SÓ um JSON: lista de objetos "
                  "{\"de\": nome curto do remetente, \"acao\": uma frase em português dizendo o que fazer e até quando}. "
                  "No máximo 5, do mais urgente ao menos. Ignore promoções e avisos automáticos sem ação.")
        try:
            r = await asyncio.wait_for(self.resumir(prompt, texto), self.timeout)
            m = re.search(r"\[.*\]", r or "", re.S)
            itens = json.loads(m.group(0)) if m else []
            out = [{"de": str(i.get("de", ""))[:40], "acao": str(i.get("acao", "")).strip()} for i in itens if i.get("acao")]
            return out[:5]
        except Exception:
            return base

    def seg_noticias(self, lista) -> list[Segmento]:
        if not lista or (isinstance(lista, dict) and lista.get("erro")):
            return []
        out = []
        for i, n in enumerate(lista):
            d = n.dados() if hasattr(n, "dados") else dict(n)
            abertura = "Na política" if d["tema"].lower().startswith("pol") else f"Nas notícias {'sobre' if ' ' in d['tema'] else 'de'} {d['tema']}"
            fala = f"{abertura}, {d['titulo'].rstrip('.')}." + (f" A informação é do {d['fonte']}." if d.get("fonte") else "")
            out.append(Segmento(f"noticia{i}", fala, {"tipo": "noticia", "rotulo": "RADAR · NOTÍCIAS", "titulo": d["tema"],
                                                      "manchete": d["titulo"], "imagem": d.get("imagem", ""), "fonte": d.get("fonte", ""),
                                                      "link": d.get("link", "")}))
        return out

    def seg_saude(self, r) -> Segmento | None:
        if r is None or isinstance(r, dict):
            return None
        obs = list(getattr(r, "observacoes", []) or [])
        n = len(obs)
        fala = (f"Tenho {_extenso(n, True)} observaç{'ões' if n != 1 else 'ão'} sobre seus dados de saúde." if n
                else "Seus dados de saúde não trouxeram nada fora do normal.")
        return Segmento("saude", fala, {"tipo": "saude", "rotulo": "SAÚDE · DADOS", "titulo": "Observações disponíveis" if n else "Tudo dentro do normal",
                                         "total": n, "itens": obs[:4]})

    def seg_foco(self, foco: str | None) -> Segmento:
        fala = f"Hoje, mantenha o foco em {foco}." if foco else "Hoje, mantenha o foco no essencial."
        return Segmento("foco", fala, {"tipo": "foco", "rotulo": "PRIORIDADES · HOJE", "titulo": fala})

    async def montar(self, dados: dict, foco: str | None = None) -> list[Segmento]:
        segs: list[Segmento | None] = [self.seg_clima(dados.get("clima")), self.seg_agenda(dados.get("agenda")),
                                       await self.seg_emails(dados.get("emails"))]
        segs += self.seg_noticias(dados.get("noticias"))
        segs += [self.seg_saude(dados.get("saude")), self.seg_foco(foco)]
        return [s for s in segs if s is not None]

    # ── execução ─────────────────────────────────────────
    async def rodar(self, cps: float = 14.5, pausa_etapa: float = 0.6):
        """Gerador assíncrono das frases (o canal de voz fala cada uma; a tela casa com o card).

        Ordem do vídeo: 1) "sem desvios" enquanto a coleta já corre; 2) terminada essa fala, o card BRIEFING MATINAL
        acende as etapas e "Atualizando o radar de notícias..."; 3) os segmentos. O TTS consome o gerador sem esperar
        o áudio acabar, por isso a pausa do passo 2 é calculada pelo tempo estimado da 1ª fala (`cps` letras/s)."""
        loop = asyncio.get_event_loop()
        self.ultimo_dia = datetime.now().strftime("%Y-%m-%d")
        coleta = asyncio.ensure_future(self.coletar())
        desvios = []
        if self.desvios:
            try:
                r = self.desvios()
                desvios = list((await r) if asyncio.iscoroutine(r) else r or [])
            except Exception:
                desvios = []
        s0 = self.seg_desvios(desvios)
        self.emitir("briefing", fase="segmento", **s0.dados())
        t0 = loop.time()
        yield s0.fala
        dados = await coleta
        falta = len(s0.fala) / cps - (loop.time() - t0)
        if falta > 0:
            await asyncio.sleep(falta)
        self.emitir("briefing", fase="inicio", etapas=ETAPAS, titulo="BRIEFING MATINAL",
                    texto="Convertendo os sinais do dia em um resumo falado e objetivo.")
        for etapa, ok in dados.pop("_ordem", []):
            await asyncio.sleep(pausa_etapa)
            self.emitir("briefing", fase="etapa", etapa=etapa, ok=ok)
            if etapa == "NOTÍCIAS":
                self.emitir("briefing", fase="radar", texto="Atualizando o radar de notícias...")
        await asyncio.sleep(pausa_etapa * 3)
        foco = None
        if self.foco:
            try:
                foco = self.foco()
            except Exception:
                foco = None
        segs = await self.montar(dados, foco)
        self.ultimo = [s0.dados()] + [s.dados() for s in segs]
        self.emitir("briefing", fase="roteiro", segmentos=self.ultimo)
        for s in segs:
            self.emitir("briefing", fase="segmento", **s.dados())
            yield s.fala
        self.emitir("briefing", fase="fim")


def _nome(de: str) -> str:
    m = re.match(r'\s*"?([^"<]+?)"?\s*<', de or "")
    return (m.group(1) if m else (de or "").split("@")[0]).strip()


def _extenso(n: int, feminino: bool = False) -> str:
    if not 0 <= n <= 10:
        return str(n)
    if feminino and n in (0, 1, 2):
        return ("nenhuma", "uma", "duas")[n]
    return ["nenhum", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez"][n]


def do_jaime(jaime) -> Briefing:
    """As fontes reais: Open-Meteo, Google (se conectado), RSS, saúde do webhook, pendências do Estado."""
    from ..agenda import clima as cl
    from . import noticias, saude
    lat = float(os.environ.get("JAIME_LAT", cl.LAT)); lon = float(os.environ.get("JAIME_LON", cl.LON))
    g = getattr(jaime, "google", None)
    conectado = bool(g is not None and getattr(g, "conectado", False))

    async def agenda():
        return await asyncio.to_thread(g.agenda_dia) if conectado else None

    async def emails():
        return await asyncio.to_thread(g.email_buscar, "newer_than:1d in:inbox -category:promotions -category:social", 30) if conectado else None

    def desvios():
        out = []
        ouvido = getattr(jaime, "ouvido", None)
        if ouvido is not None and getattr(ouvido, "erro", ""):
            out.append("o microfone está com erro")
        h = getattr(jaime, "hermes", None)
        if h is not None and getattr(h, "pendentes", None):
            out.append(f"o Hermes espera sua aprovação em {len(h.pendentes)} comando(s)")
        return out

    def foco():
        try:
            txt = jaime.vault.read("30-Tarefas/Inbox.md") or ""
            m = re.search(r"^- \[ \] (.+?)(?:\s+@\S+|\s+⏳.*)?$", txt, re.M)
            return m.group(1).strip()[:80] if m else None
        except Exception:
            return None

    resumir = None
    try:
        from ..mente.pensar import _pensador_padrao
        resumir = _pensador_padrao(jaime.s)
    except Exception:
        pass
    return Briefing(clima=lambda: cl.buscar(lat, lon), agenda=agenda, emails=emails, noticias=noticias.destaques,
                    saude=saude.carregar, desvios=desvios, foco=foco, resumir=resumir)
