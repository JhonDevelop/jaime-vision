"""Liga a expansão espacial ao Jaime existente sem criar um segundo bus nem um segundo orquestrador.

`montar(jaime)` é chamado no lifespan do servidor. Com `JAIME_SPATIAL=off` devolve None e NADA é criado:
nenhuma task, nenhuma câmera, nenhum MCP novo — o HUD, a voz e as mãos seguem exatamente como antes."""
from __future__ import annotations
from pathlib import Path
from .config import ConfigEspacial
from .core import SpatialCore
from .simulador import objetos_demo

ESTADO: dict = {"servico": None, "cfg": None, "contexto": None}


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
        ESTADO["servico"] = None
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
    ESTADO["servico"] = s
    try:
        jaime.espacial = s
    except Exception:
        pass
    return s


def servico():
    return ESTADO.get("servico")
