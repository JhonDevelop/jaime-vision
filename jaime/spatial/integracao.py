"""Liga a expansão espacial ao Jaime existente sem criar um segundo bus nem um segundo orquestrador.

`montar(jaime)` é chamado no lifespan do servidor. Com `JAIME_SPATIAL=off` devolve None e NADA é criado:
nenhuma task, nenhuma câmera, nenhum MCP novo — o HUD, a voz e as mãos seguem exatamente como antes."""
from __future__ import annotations
from pathlib import Path
from .config import ConfigEspacial
from .core import SpatialCore
from .simulador import objetos_demo

ESTADO: dict = {"servico": None, "cfg": None, "contexto": None}
PARAMETROS = Path("~/Jaime/espacial/parametros.json").expanduser()
EXPERIMENTOS = Path("~/Jaime/espacial/experimentos.jsonl").expanduser()


def nomes_de_projetos(vault: Path, maximo: int = 6) -> list[str]:
    """Só os NOMES das notas de 20-Projetos (viram objetos na cena); o conteúdo não é lido nem exposto."""
    pasta = Path(vault) / "20-Projetos"
    if not pasta.is_dir():
        return []
    nomes = [p.stem for p in sorted(pasta.glob("*.md")) if p.stem.upper() != "INDEX" and not p.stem.startswith(".")]
    return nomes[:maximo]


def montar(jaime, cfg: ConfigEspacial | None = None, emitir=None):
    from .servico import ServicoEspacial
    cfg = cfg or ConfigEspacial.do_ambiente()
    ESTADO["cfg"] = cfg
    if not cfg.ativo:
        ESTADO.update(servico=None, contexto=None, acoes=None, intencoes=None, telas=None)
        return None
    core = SpatialCore()
    vault = getattr(getattr(jaime, "s", None), "vault", None)
    for o in objetos_demo(nomes_de_projetos(vault) if vault else None):
        core.add(o)

    def dono_ok() -> bool:
        # mão na câmera não prova identidade: quem autoriza é a sessão do dono (palavra-passe) sem visita na linha
        try:
            return bool(jaime.acesso.liberado) and not getattr(jaime.vigia, "convidado", "")
        except Exception:
            return False

    s = ServicoEspacial(cfg, emitir=emitir, core=core, dono_ok=dono_ok)
    # fase 9: limiares promovidos por experimento medido (ou os padrões); rollback em `espacial reverter`
    from .experimentos import Parametros
    from .gestures import PinchMachine
    params = Parametros(PARAMETROS)
    s.pinca = PinchMachine(core, min_confidence=cfg.rastreio_conf_min, **params.valores)
    ESTADO["servico"] = s
    # fase 2: voz contextual. Em sim/replay as seleções são do ator "demo" — a VOZ continua sendo do João autenticado
    from .referencias import ContextoVoz, Resolvedor
    atores = (lambda: ("joao", "demo")) if cfg.modo in ("sim", "replay") else (lambda: ("joao",))
    resolvedor = Resolvedor(core, ttl_s=cfg.ttl_referencia_s, atores=atores, confianca_min=cfg.confianca_min)
    voz = ContextoVoz(s, resolvedor, agendar=_agendar)
    ESTADO["contexto"] = voz
    # fase 3/4: ações no SO (prévia → Vigia → recibo/Undo; dry-run por padrão) e vigia de monitores
    from .acoes import AdaptadorAcoes, executor_do_sistema
    from .intencoes import Intencoes
    from .telas import VigiaTelas
    telas = VigiaTelas(ao_mudar=lambda ev: s.emitir("espacial", **ev))
    acoes = AdaptadorAcoes(core, executor_do_sistema(), dono_ok, vigia=_vigia_de(jaime), dry_run=cfg.dry_run,
                           raizes=_raizes(jaime, cfg), proibidas=_proibidas(jaime), emitir=s.emitir, telas=telas,
                           limiar=cfg.confianca_min, log=Path("~/Jaime/espacial/recibos.jsonl").expanduser())
    intencoes = Intencoes(core, acoes, s.emitir, _agendar)
    s.ouvintes.append(intencoes)
    s.extras.append(lambda: _vigiar_telas(telas))
    ESTADO.update(acoes=acoes, intencoes=intencoes, telas=telas)
    try:
        jaime.espacial = s
        jaime.espacial_voz = voz
        jaime.espacial_acoes = acoes
    except Exception:
        pass
    return s


def _vigia_de(jaime):
    """O MESMO Vigia das ferramentas do modelo (PreToolUse), chamado com o nome da ação espacial."""
    v = getattr(jaime, "vigia", None)
    if v is None or not hasattr(v, "pre_tool_use"):
        return None
    async def checar(nome: str, args: dict) -> dict:
        return await v.pre_tool_use({"tool_name": nome, "tool_input": args}, None, None)
    return checar


def _raizes(jaime, cfg) -> list[Path]:
    if cfg.raizes:
        return [Path(r).expanduser() for r in cfg.raizes]
    ws = getattr(getattr(jaime, "s", None), "workspace", None)
    return [Path(ws)] if ws else []


def _proibidas(jaime) -> list[Path]:
    s = getattr(jaime, "s", None)
    out = [Path("~/.ssh").expanduser()]
    if s is not None:
        if getattr(s, "vault", None):
            out.append(Path(s.vault))
        if getattr(s, "root", None):
            out += [Path(s.root) / ".env", Path(s.root) / "jaime" / "vigia"]
    return out


async def _vigiar_telas(telas, intervalo: float = 2.0):
    import asyncio
    while True:
        await asyncio.sleep(intervalo)
        try:
            await asyncio.to_thread(telas.checar)
        except Exception:
            pass


def _agendar(coro):
    import asyncio
    try:
        return asyncio.get_running_loop().create_task(coro)
    except RuntimeError:          # sem loop (CLI/teste síncrono): roda até o fim
        return asyncio.run(coro)


def servico():
    return ESTADO.get("servico")
