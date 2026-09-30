"""Liga as cenas do Jarvis ao orquestrador: uma frase reconhecida vira um gerador de falas (voz) + eventos (tela).

`JAIME_JARVIS=off` desliga tudo; `JAIME_BRIEFING_BOM_DIA=off` faz o "bom dia" voltar a ser só cumprimento
(o "me dá o briefing" continua funcionando).
"""
from __future__ import annotations
import asyncio, os, time
from datetime import datetime
from ..hud.events import bus
from . import holograma as holo
from . import tela
from .briefing import Briefing, do_jaime, quer_briefing
from .monitor import Monitor
from .rosto import DONO, Rostos, ident
from .estudio import Estudio
from .voz import cena, edicao


def ligado(env=None) -> bool:
    e = os.environ if env is None else env
    return (e.get("JAIME_JARVIS", "on") or "on").strip().lower() not in ("0", "off", "false", "nao", "não")


class Jarvis:
    def __init__(self, briefing: Briefing, monitor: Monitor, rostos: Rostos, emitir=None, env=None,
                 modelo_holo=None, sentinela=None, capacidades=None, garantir_tela=None, relacoes=None, espera_rosto: float = 10.0, mensagens=None, convidado=None):
        self.briefing, self.monitor, self.rostos = briefing, monitor, rostos
        self.modelo_holo, self.sentinela, self.capacidades = modelo_holo, sentinela, capacidades
        self.garantir_tela = garantir_tela or (lambda: None)
        self.emitir = emitir or bus.emitir
        e = os.environ if env is None else env
        self.bom_dia = (e.get("JAIME_BRIEFING_BOM_DIA", "on") or "on").strip().lower() not in ("0", "off", "false")
        self.cadastrando: dict | None = None   # {"pessoa", "nome", "dono", "relacao"} depois do "aprende o rosto de…"
        self.relacoes = relacoes                # grafo de relações (memórias de cada pessoa) — pode ser None
        self.presente: dict | None = None       # quem a câmera reconheceu por último {pessoa, nome, relacao, dono, quando}
        self.espera_rosto = espera_rosto
        self.mensagens = mensagens              # () -> [{"app", "de", "texto", "hora"}] (notificações do WhatsApp e cia.)
        self.convidado = convidado or (lambda: "")  # quem está na linha, se não for o João (voz reconhecida / remoto)
        self._espera_quem: asyncio.Future | None = None
        self.estudio = Estudio(self.emitir)
        self.abrir_blender = None               # injetável (teste); padrão: malha3d.abrir_no_blender
        self.abrir_fatiador = None              # injetável (teste); padrão: malha3d.abrir_no_fatiador

    def gerador(self, texto: str, agora: datetime | None = None):
        """Um gerador assíncrono de frases se a fala abre uma cena; senão None (o turno segue normal)."""
        agora = agora or datetime.now()
        hoje = agora.strftime("%Y-%m-%d")
        if quer_briefing(texto, agora, ja_deu_hoje=self.briefing.ultimo_dia == hoje or not self.bom_dia):
            self.garantir_tela()
            return self._falas(self.briefing.rodar())
        c = cena(texto)
        if c is None and self.estudio.aberto:
            c = edicao(texto)                    # holograma aberto: "abre as portas", "aumenta essa peça", "desfaz"
        if c is None:
            return None
        nome, args = c
        if nome == "monitor":
            self.garantir_tela()                          # "ativar monitor" acorda o monitor e abre o painel
            return self._falas(self.monitor.rodar())
        if nome == "holograma":
            self.garantir_tela()
            return self._falas(self._holograma(args["objeto"]))
        if nome == "capacidades":
            return self._uma(self.capacidades() if callable(self.capacidades) else CAPACIDADES_PADRAO)
        if nome == "sistemas":
            return self._falas(self._sistemas())
        if nome == "fecha_holograma":
            self.emitir("holograma", acao="fechar"); self.estudio.fechar()
            return self._uma("Holograma fechado.")
        if nome in ("caixa", "mensagens") and self._visita():
            return self._uma("Tem mais alguém aqui; e-mail e mensagens do senhor eu mostro quando estivermos só nós.")
        if nome == "caixa":
            self.garantir_tela()
            return self._falas(self._caixa())
        if nome == "mensagens":
            self.garantir_tela()
            return self._falas(self._mensagens())
        if nome == "desenho":
            self.garantir_tela()
            self.estudio.abrir("desenho")
            self.emitir("holograma", acao="desenho", titulo="DESENHO")
            return self._uma("Prancheta aberta. Desenhe com o dedo indicador ou com o mouse; gire com a mão aberta para "
                             "desenhar em outro plano. Quando terminar, diga: dá volume ao desenho, ou exporta em STL.")
        if nome == "volume":
            return self._falas(self._volume(args.get("nome", "")))
        if nome == "editar":
            return self._falas(self._editar(args["pedido"]))
        if nome == "desfazer":
            return self._uma(self.estudio.desfazer())
        if nome == "imprimir":
            if not self.estudio.aberto and not self.estudio.spec:
                return self._uma("Não tem holograma aberto para imprimir. Peça um holograma ou diga: quero desenhar.")
            return self._falas(self._imprimir(args.get("maior_mm", 100.0)))
        if nome in ("exportar", "blender"):
            if not self.estudio.aberto and not self.estudio.spec:
                return self._uma("Não tem holograma aberto. Peça um holograma ou diga: quero desenhar.")
            return self._falas(self._exportar(args.get("formatos") or ["glb"], blender=nome == "blender"))
        if nome in ("olhar", "maos"):
            self.garantir_tela()
            self.emitir("sentidos", **{nome: args["ligar"]})
            if nome == "olhar":
                return self._uma("Controle pelo olhar ligado. Olhe para o centro da tela por um segundo para eu calibrar."
                                 if args["ligar"] else "Controle pelo olhar desligado.")
            return self._uma("Controle por mão ligado: o indicador é o cursor, a pinça clica, a mão aberta parada fecha o que estiver aberto."
                             if args["ligar"] else "Controle por mão desligado.")
        if nome == "aprende_rosto":
            return self._uma(self._aprender(args.get("nome", ""), args.get("relacao", "")))
        if nome == "esquece_rosto":
            return self._uma(self._esquecer(args.get("nome", "")))
        if nome == "rostos":
            return self._uma(self._lista_rostos())
        if nome == "quem_e":
            self.garantir_tela()
            return self._falas(self._quem_e())
        if nome == "orbe":
            self.emitir("orbe", estilo=args["estilo"])
            return self._uma("Feito." if args["estilo"] == "fios" else "Modo partículas.")
        return None

    # ── rostos de várias pessoas ─────────────────────
    def _aprender(self, nome: str, relacao: str) -> str:
        nome = (nome or "").strip()
        if not nome or ident(nome) == DONO:
            self.cadastrando = {"pessoa": DONO, "nome": "João", "dono": True, "relacao": ""}
            self.emitir("rosto", acao="cadastrar", amostras=5, nome="")
            return "Olhe para a câmera por uns segundos; vou aprender o seu rosto. Ele serve para eu te reconhecer, não para destrancar nada."
        self.cadastrando = {"pessoa": ident(nome), "nome": nome, "dono": False, "relacao": relacao}
        self.emitir("rosto", acao="cadastrar", amostras=5, nome=nome)
        return (f"Peça para {nome} olhar para a câmera por uns segundos. Só guardo o rosto com o consentimento da pessoa; "
                "serve para eu reconhecer, nunca para liberar nada.")

    def cadastrado(self, n: int) -> str:
        """A rota chama depois de gravar as amostras: liga a pessoa ao grafo de relações e devolve a frase."""
        c = self.cadastrando or {"pessoa": DONO, "nome": "João", "dono": True, "relacao": ""}
        self.cadastrando = None
        if c["dono"]:
            return "Aprendi o seu rosto."
        self._ligar_no_grafo(c["nome"], c["relacao"])
        return f"Aprendi o rosto de {c['nome']}." + (f" Anotei que é {_art(c['relacao'])} {c['relacao']}." if c["relacao"] else "")

    def _grafo(self):
        """O grafo do Jaime; se a conexão SQLite for de outra thread, abre uma nova no mesmo arquivo."""
        r = self.relacoes() if callable(self.relacoes) else self.relacoes
        if r is None:
            return None
        try:
            r._con.execute("SELECT 1")
            return r
        except Exception:
            from ..relacoes.grafo import Relacoes
            return Relacoes(r.caminho)

    def _ligar_no_grafo(self, nome: str, relacao: str) -> None:
        g = self._grafo()
        if g is None:
            return
        try:
            g.lembrar_pessoa(nome, evidencia="rosto cadastrado no Jarvis")
            tipo = tipo_relacao(relacao)
            if tipo:
                g.ligar(nome, "João", tipo, detalhe=relacao, evidencia="o João disse ao cadastrar o rosto")
            elif relacao:
                g.fato(nome, "relação com o João", relacao, evidencia="o João disse ao cadastrar o rosto")
        except Exception:
            pass

    def _esquecer(self, nome: str) -> str:
        nome = (nome or "").strip()
        if not nome or ident(nome) == DONO:
            self.rostos.esquecer(DONO)
            return "Pronto, esqueci o seu rosto."
        if self.rostos.esquecer(ident(nome)):
            if self.presente and self.presente.get("pessoa") == ident(nome):
                self.presente = None
            return f"Pronto, esqueci o rosto de {nome}. O que sei dessa pessoa continua nas relações; se quiser apagar, é só pedir."
        return f"Não tenho o rosto de {nome} guardado."

    def _lista_rostos(self) -> str:
        ps = [p for p in self.rostos.pessoas() if p["amostras"]]
        if not ps:
            return "Ainda não aprendi nenhum rosto. Diga: aprende meu rosto."
        nomes = ["o senhor" if p["dono"] else (f"{p['nome']}, {_art(p['relacao'])} {p['relacao']}" if p["relacao"] else p["nome"])
                 for p in sorted(ps, key=lambda p: not p["dono"])]
        lista = nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]
        return f"Conheço {len(ps)} rosto{'s' if len(ps) > 1 else ''}: {lista}."

    def receber_rosto(self, res: dict) -> None:
        """Resultado da câmera: vai ao monitor, a quem perguntou "quem é esse?" e marca quem está presente."""
        self.monitor.receber_rosto(res)
        if self._espera_quem is not None and not self._espera_quem.done():
            self._espera_quem.set_result(res)
        if res.get("status") in ("confirmado", "conhecido"):
            self.presente = {"pessoa": res.get("pessoa"), "nome": res.get("nome"), "relacao": res.get("relacao", ""),
                             "dono": res.get("status") == "confirmado", "quando": time.time()}

    def presente_agora(self, janela_s: float = 600.0) -> dict | None:
        p = self.presente
        return p if p and time.time() - p["quando"] <= janela_s else None

    def contexto_presente(self) -> str:
        """Uma linha para o modelo: quem a câmera viu (se não for o João) e o que o grafo já sabe dessa pessoa."""
        p = self.presente_agora()
        if not p or p["dono"]:
            return ""
        linha = f"na câmera agora: {p['nome']}" + (f" ({p['relacao']} do João)" if p["relacao"] else "")
        g = self._grafo()
        try:
            txt = g.texto_sobre(g.sobre(p["nome"])) if g is not None else ""
        except Exception:
            txt = ""
        return linha + (f"; memórias: {txt[:300]}" if txt else "") + "; é visita: nada privado do João em voz alta"

    async def _quem_e(self):
        self._espera_quem = asyncio.get_event_loop().create_future()
        self.emitir("rosto", acao="identificar")
        try:
            res = await asyncio.wait_for(asyncio.shield(self._espera_quem), self.espera_rosto)
        except asyncio.TimeoutError:
            res = {"status": "sem_rosto"}
        finally:
            self._espera_quem = None
        st = res.get("status")
        if st == "confirmado":
            yield "É o senhor, João."; return
        if st == "conhecido":
            nome, rel = res.get("nome") or "visita", res.get("relacao", "")
            yield f"É {nome}" + (f", {_art(rel)} {rel}." if rel else ".")
            g = self._grafo()
            try:
                d = g.sobre(nome) if g is not None else None
            except Exception:
                d = None
            if d:
                itens = [f"{f['chave']}: {f['valor']}" for f in d["fatos"] if f["chave"] != "relação com o João"][:2]
                itens += [f"{r['relacao']} de {r['com']}" + (f" ({r['detalhe']})" if r["detalhe"] else "")
                          for r in d["relacoes"] if r["com"] != "João"][:2]
                if itens:
                    yield "O que eu sei: " + "; ".join(itens) + "."
            return
        yield {"desconhecido": "Não conheço esse rosto. Se quiser, diga: aprende o rosto do fulano.",
               "sem_cadastro": "Ainda não aprendi nenhum rosto.",
               "sem_camera": "Não consegui abrir a câmera."}.get(st, "Não vi ninguém na câmera.")

    def _visita(self) -> bool:
        try:
            if self.convidado():
                return True
        except Exception:
            pass
        p = self.presente_agora(120)
        return bool(p and not p["dono"])

    async def _caixa(self):
        _, lista = await self.briefing._uma("emails")
        if lista is None or (isinstance(lista, dict) and lista.get("erro")):
            yield "Não consegui abrir o seu e-mail agora. Confira se o Google está conectado."; return
        yield "Abrindo a caixa de entrada."
        seg = await self.briefing.seg_emails(lista)
        self.emitir("cartao", card={**seg.card, "rotulo": "CAIXA DE ENTRADA · GMAIL"})
        yield seg.fala

    async def _mensagens(self):
        try:
            lista = (self.mensagens() if callable(self.mensagens) else []) or []
        except Exception:
            lista = []
        if not lista:
            yield "Nenhuma mensagem nova desde que liguei. Eu leio o WhatsApp pelas notificações do computador."; return
        de = []
        for m in reversed(lista):
            if m["de"] not in de:
                de.append(m["de"])
        itens = [{"de": m["de"].upper()[:28], "acao": m["texto"][:120] or "(mídia)"} for m in list(reversed(lista))[:5]]
        self.emitir("cartao", card={"tipo": "emails", "rotulo": "MENSAGENS · WHATSAPP", "titulo": "Recebidas", "total": len(lista),
                                     "agir": len(de), "itens": itens})
        nomes = de[0] if len(de) == 1 else ", ".join(de[:3][:-1]) + " e " + de[:3][-1]
        yield f"{len(lista)} mensage{'m' if len(lista) == 1 else 'ns'} de {nomes}. A última: {lista[-1]['texto'][:140] or 'uma mídia'}."

    async def _editar(self, pedido: str):
        yield await self.estudio.editar(pedido, self.modelo_holo)

    async def _volume(self, nome: str):
        if not self.estudio.tracos:
            yield "Ainda não vi nenhum traço. Diga: quero desenhar."; return
        yield "Dando volume ao desenho."
        r = await self.estudio.volume(self.modelo_holo, nome)
        if r is None:
            yield "Não consegui transformar esse desenho em objeto. Tente traços mais fechados, ou diga o que é."; return
        self.estudio.abrir(r["titulo"], r["pecas"])
        self.emitir("holograma", acao="abrir", **r)
        yield f"Pronto: {r['titulo']} em três dimensões. Pode pegar as peças com a mão ou pedir alterações."

    async def _exportar(self, formatos: list[str], blender: bool = False):
        from . import malha3d
        fmts = sorted(set(formatos) | ({"glb"} if blender else set()))
        malhas = await self.estudio.malhas()
        if not malhas:
            yield "A tela do holograma não respondeu e não tenho a descrição das peças para exportar."; return
        arquivos = await asyncio.to_thread(malha3d.exportar, self.estudio.titulo or "holograma", malhas, fmts)
        self.emitir("holograma", acao="exportado", arquivos=arquivos)
        nomes = ", ".join(os.path.basename(p) for p in arquivos.values())
        yield f"Salvei {nomes} na pasta Jaime, hologramas, exportados."
        if blender:
            abrir = self.abrir_blender or malha3d.abrir_no_blender
            r = await asyncio.to_thread(abrir, arquivos["glb"])
            yield "Abrindo no Blender." if r.get("ok") else f"Não consegui abrir no Blender: {r.get('erro', '')[:120]}"

    async def _imprimir(self, maior_mm: float):
        from . import malha3d
        malhas = await self.estudio.malhas()
        if not malhas:
            yield "A tela do holograma não respondeu e não tenho a descrição das peças."; return
        mesa = malha3d.para_impressao(malhas, maior_mm)
        titulo = f"{self.estudio.titulo or 'holograma'} {int(round(maior_mm))}mm"
        arq = (await asyncio.to_thread(malha3d.exportar, titulo, mesa, ["stl"], malha3d.EXPORTADOS / "impressao"))["stl"]
        self.emitir("holograma", acao="exportado", arquivos={"stl": arq})
        cm = maior_mm / 10
        yield f"Arquivo de impressão pronto, com {cm:g} centímetros na maior medida, apoiado na mesa."
        abrir = self.abrir_fatiador or malha3d.abrir_no_fatiador
        r = await asyncio.to_thread(abrir, arq)
        yield (f"Abri no {r['fatiador']}; confira suportes e material e aperte imprimir quando quiser." if r.get("ok")
               else "Não achei fatiador instalado; o STL está na pasta Jaime, hologramas, exportados, impressão.")

    async def _holograma(self, objeto: str):
        """Catálogo ou arquivo .glb: na hora. Qualquer outro objeto: o modelo descreve as peças (uns segundos)."""
        r = holo.resolver(objeto)
        if not r["exato"] and self.modelo_holo is not None:
            self.emitir("holograma", acao="montando", titulo=objeto)
            yield f"Montando o holograma de {objeto}."
            try:
                r = await holo.gerar(objeto, self.modelo_holo)
            except Exception:
                r = {**r, "falhou": True}
        self.estudio.abrir(r.get("titulo") or objeto, r.get("pecas"))
        self.emitir("holograma", acao="abrir", **r)
        yield holo.fala(r)

    async def _sistemas(self):
        s = self.sentinela
        if s is None:
            yield "A sentinela está desligada."; return
        if s.alvos and all(a.ok is None for a in s.alvos):
            await s.rodada()
        self.emitir("sentinela", estado=s.estado(), mostrar=True)
        yield s.resumo_falado()

    async def _falas(self, gen):
        async for frase in gen:
            bus.emitir("fala", texto=frase)
            yield frase.rstrip() + " "
        bus.emitir("fala_fim")

    async def _uma(self, frase: str):
        bus.emitir("fala", texto=frase); bus.emitir("fala_fim")
        yield frase


PARENTESCO = {"pai", "mãe", "mae", "irmão", "irmao", "irmã", "irma", "filho", "filha", "tio", "tia", "primo", "prima", "avô", "avo",
              "avó", "neto", "neta", "sobrinho", "sobrinha", "cunhado", "cunhada", "sogro", "sogra", "genro", "nora", "esposa",
              "marido", "namorada", "namorado", "noiva", "noivo", "padrasto", "madrasta", "enteado", "enteada"}
FEMININO = {"mãe", "mae", "avó", "avo"}


def tipo_relacao(relacao: str) -> str:
    """'irmã' → parentesco, 'sócio' → sociedade, 'amiga' → amizade; o resto vira fato solto ('' aqui)."""
    r = (relacao or "").strip().lower()
    if not r:
        return ""
    base = r.split()[-1]
    if base in PARENTESCO:
        return "parentesco"
    if base.startswith("sóci") or base.startswith("soci"):
        return "sociedade"
    if base.startswith("amig") or base in ("parceiro", "parceira", "colega"):
        return "amizade"
    return ""


def _art(relacao: str) -> str:
    base = (relacao or "").strip().lower().split()[-1] if relacao and relacao.strip() else ""
    return "sua" if base.endswith(("a", "ã")) or base in FEMININO else "seu"


CAPACIDADES_PADRAO = ("Eu analiso dados em tempo real, vigio sistemas críticos, entendo linguagem natural e coordeno várias "
                      "tarefas ao mesmo tempo. Em termos práticos: sou uma central de automação e inteligência operacional.")


def capacidades_de(jaime) -> str:
    """O inventário REAL (o que está ligado agora), no tom do vídeo — nada de prometer o que não está conectado."""
    partes = ["analiso dados em tempo real", "entendo e respondo em linguagem natural, por voz ou texto"]
    s = getattr(jaime, "sentinela", None)
    if s is not None and s.alvos:
        partes.append(f"vigio {len(s.alvos)} sistema{'s' if len(s.alvos) > 1 else ''} crítico{'s' if len(s.alvos) > 1 else ''} e aviso se algum cair")
    try:
        filhos = len(jaime.equipe.vivos()) if hasattr(jaime.equipe, "vivos") else 0
    except Exception:
        filhos = 0
    partes.append("coordeno várias tarefas ao mesmo tempo" + (f", com {filhos} agentes trabalhando para mim agora" if filhos else ""))
    if getattr(getattr(jaime, "google", None), "conectado", False):
        partes.append("leio e organizo seu e-mail e sua agenda")
    if getattr(getattr(jaime, "casa", None), "ativa", False):
        partes.append("comando a casa e a Alexa")
    h = getattr(jaime, "hermes", None)
    if h is not None and h.disponivel:
        partes.append("delego trabalho pesado ao Hermes")
    cer = getattr(jaime, "cerebros", None)
    if cer is not None:
        partes.append("penso junto com outros cérebros, o Codex e o Gemini, quando o trabalho pede")
    if getattr(jaime, "jarvis", None) is not None:
        partes.append("crio hologramas 3D de qualquer objeto, que o senhor manipula com as mãos, e mando para o Blender ou para a impressora 3D")
    partes += ["escrevo e corrijo código", "gero relatórios estratégicos a partir do seu vault",
               "e melhoro os meus próprios processos com base nos padrões que observo"]
    return ("Hoje eu " + ", ".join(partes[:-1]) + " " + partes[-1] + ". A maioria dos sistemas só responde a comandos, senhor; "
            "eu acompanho o contexto e ajo antes de precisar. Em termos práticos: sou uma central de automação e inteligência operacional.")


def montar(jaime, env=None) -> Jarvis | None:
    if not ligado(env):
        return None
    rostos = Rostos()
    modelo_holo = None
    try:
        from ..mente.pensar import _pensador_padrao
        modelo_holo = _pensador_padrao(jaime.s)
    except Exception:
        pass
    return Jarvis(do_jaime(jaime), Monitor(rostos), rostos, env=env, modelo_holo=modelo_holo,
                  sentinela=getattr(jaime, "sentinela", None), capacidades=lambda: capacidades_de(jaime),
                  garantir_tela=lambda: tela.garantir(env=env), relacoes=lambda: getattr(jaime, "relacoes", None),
                  mensagens=lambda: mensagens_de(jaime), convidado=lambda: getattr(getattr(jaime, "vigia", None), "convidado", ""))


def mensagens_de(jaime, apps=("WhatsApp", "Mensagens", "Telegram")) -> list[dict]:
    """Últimas mensagens vistas nas notificações do computador (jaime/ops/notificacoes.py)."""
    import time as _t
    n = getattr(jaime, "notificacoes", None)
    return [{"app": x.nome_app, "de": x.remetente, "texto": x.texto, "hora": _t.strftime("%H:%M", _t.localtime(x.quando))}
            for x in (getattr(n, "vistas", None) or []) if x.nome_app in apps][-20:]
