"""Liga os blocos ao Jaime: fontes do cérebro vivo, voz, cockpit, espaço (mãos) e autoevolução.

Ligado por padrão (`JAIME_BLOCOS=on`): sem superfície conectada e sem bloco aberto, não faz nada além de um tique
por segundo. `JAIME_BLOCOS=off` desliga tudo (rotas respondem 409, sem MCP, sem atalho de voz).
Arquivos em `~/Jaime/blocos/` (layouts, modelos, uso) — fora do vault."""
from __future__ import annotations
import hashlib, hmac, os
from pathlib import Path
from .fontes import padrao as fontes_padrao
from .gerenciador import Gerenciador
from .modelos import Modelos, Uso

PASTA = Path(os.environ.get("JAIME_BLOCOS_PASTA", "~/Jaime/blocos")).expanduser()
ESTADO: dict = {"g": None, "modelos": None, "fontes": None, "jaime": None}


def ligado(env=None) -> bool:
    e = os.environ if env is None else env
    return (e.get("JAIME_BLOCOS", "on") or "on").strip().lower() not in ("off", "0", "false", "nao", "não")


def token_dispositivo(segredo: str, nome: str) -> str:
    """Token de UM dispositivo (óculos, visor, tablet), derivado do segredo do servidor — trocar o JAIME_SERVER_TOKEN
    revoga todos de uma vez. Sem lista de tokens para vazar."""
    return hmac.new((segredo or "").encode(), f"blocos:{(nome or '').strip().lower()}".encode(), hashlib.sha256).hexdigest()[:32]


def montar(jaime=None, pasta: Path | None = None, falar=None, emitir=None, env=None):
    if not ligado(env):
        ESTADO.update(g=None, modelos=None, fontes=None, jaime=None)
        return None
    pasta = Path(pasta) if pasta else PASTA
    fontes = fontes_padrao(jaime)
    modelos = Modelos(pasta, fontes)
    if emitir is None:
        from ..hud.events import bus
        emitir = bus.emitir

    def dono_ok() -> bool:
        if jaime is None:
            return True
        try:
            return bool(jaime.acesso.liberado) and not getattr(jaime.vigia, "convidado", "")
        except Exception:
            return False

    g = Gerenciador(fontes, pasta, dono_ok=dono_ok, emitir=emitir, falar=falar, uso=Uso(pasta))
    ESTADO.update(g=g, modelos=modelos, fontes=fontes, jaime=jaime)
    if jaime is not None:
        try:
            jaime.blocos = g
            jaime.blocos_modelos = modelos
            jaime.blocos_fontes = fontes
            ev = getattr(jaime, "evolucao", None)
            if ev is not None:                       # uso da interface vira sinal da autoevolução
                ev.sinais_extras = list(getattr(ev, "sinais_extras", [])) + [lambda: _sinal_interface(g)]
        except Exception:
            pass
    return g


def _sinal_interface(g) -> str:
    s = g.uso.sinais() if g.uso else ""
    return ("Interface (blocos):\n" + s) if s else ""


def antes_do_turno(jaime, texto: str, contexto: str) -> tuple[str | None, str]:
    """Gancho do orquestrador: comando de bloco resolvido sem modelo, ou contexto com os blocos abertos."""
    from .voz import comando, contexto as ctx_blocos
    g, modelos = ESTADO.get("g"), ESTADO.get("modelos")
    if g is None:
        return None, contexto
    r = _fechar_selecionado(jaime, texto, g)
    if r:
        return r, contexto
    curta = comando(texto, g, modelos)
    if curta is not None:
        return curta, contexto
    if "bloco" in (texto or "").lower() or "layout" in (texto or "").lower():
        linha = ctx_blocos(g)
        contexto = f"{contexto}; {linha}" if contexto else linha
    return None, contexto


def _fechar_selecionado(jaime, texto: str, g) -> str | None:
    """"fecha isso" com a mão apontando para um bloco (expansão espacial ligada)."""
    import re
    from .voz import _n
    t = _n(texto)
    if not re.fullmatch(r"(jaime,? )?(fecha|feche|tira|tire|some com) (isso|esse|essa|este|esta|isso ai|esse ai)", t):
        return None
    voz = getattr(jaime, "espacial_voz", None) if jaime is not None else None
    if voz is None:
        return None
    rec = voz.resolvedor._recentes()
    if not rec or rec[0][0].kind != "bloco":
        return None
    bid = rec[0][0].id.removeprefix("bloco:")
    b = g.blocos.get(bid)
    if not b:
        return None
    g.fechar(bid, motivo="voz")
    return f"Fechei {b.titulo}."


def ligar_espacial(g, servico) -> None:
    """Com a expansão espacial ligada, cada bloco aberto vira um objeto da cena: dá para apontar, pegar, arrastar
    (move o bloco em todas as superfícies) e jogar na lixeira virtual (fecha o bloco)."""
    from ..spatial.core import SpatialObject, Vec3
    core = servico.core
    sessao_ids: set[str] = set()

    def posicao(b, i):
        a = b.ancoragem
        if a.x is not None and a.y is not None:
            return Vec3(a.x, a.y, 0.0)
        return Vec3(0.15 + 0.23 * (i % 4), 0.62 + 0.14 * (i // 4 % 3), 0.0)

    class SessaoCena:
        id = "cena-espacial"; perfil = "cena"; nome = "cena espacial"

        def sincronizar(self, blocos, dono_ok):
            vivos = set()
            for i, b in enumerate(blocos):
                oid = f"bloco:{b.id}"
                vivos.add(oid)
                if b.privado and not dono_ok:
                    continue
                if oid not in core.objects:
                    core.add(SpatialObject(oid, "bloco", posicao(b, i), label=b.titulo, radius=0.05))
                    servico.emitir("espacial", evento="spatial.object", obj_novo=core.objects[oid].to_dict())
            for oid in [o for o in list(core.objects) if o.startswith("bloco:") and o not in vivos]:
                core.remove(oid)
                servico.emitir("espacial", evento="spatial.removed", object_id=oid)
            return 0

    def ao_gesto(ev):
        if ev.kind != "gesture.release" or not (ev.object_id or "").startswith("bloco:"):
            return
        bid = ev.object_id.removeprefix("bloco:")
        obj = core.objects.get(ev.object_id)
        zona = core.objects.get("zona:lixeira")
        if obj and zona and obj.position.distance(zona.position) <= zona.radius * zona.scale:
            g.fechar(bid, motivo="fechado em gesto")          # bloco é só desenho: jogar fora = fechar (com desfazer)
        elif obj and bid in g.blocos:
            g.mover(bid, {"x": round(obj.position.x, 3), "y": round(obj.position.y, 3)})

    g.conectar(SessaoCena())
    servico.ouvintes.append(ao_gesto)
