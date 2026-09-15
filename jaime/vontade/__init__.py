"""Sistema de vontades (fase 3, §6) — prioridades com nome, não sentimentos.

- `impulsos.py`: seis impulsos 0–1 (Utilidade, Curiosidade, Maestria, Criação, Ordem, Vínculo) que sobem e descem
  com o que acontece no bus de eventos; persistidos em `01-Estado/Vontades.md`.
- `mente.py`: escolhe a próxima atividade por impulso × janela da rotina × orçamento e registra "quero … porque …".
- `criacoes.py`: noite criativa em `~/Jaime/criacoes/` e a Vitrine (gostei / não gostei).

`ligar(jaime, pode_rodar)` monta tudo com o mínimo de fiação no servidor."""
from __future__ import annotations
import asyncio, os
from dataclasses import dataclass, field
from .impulsos import Impulsos, observar_placar
from .mente import Mente, OrcamentoLivre
from .criacoes import Criacoes

@dataclass
class Vontade:
    impulsos: Impulsos
    mente: Mente
    criacoes: Criacoes
    tasks: list = field(default_factory=list)

    def parar(self) -> None:
        for t in self.tasks:
            t.cancel()

def _orcamento(jaime):
    """Orçamento do Prompt D (jaime/cortex/orcamento.py, `Orcamento(vault, dia_usd)`) se existir; senão tudo liberado.
    O servidor deve preferir injetar a instância do D (app.state.orcamento) para não haver dois contadores."""
    try:
        from ..cortex.orcamento import Orcamento          # type: ignore
        dia = float((os.environ.get("JAIME_ORCAMENTO_DIA_USD") or "0").strip() or 0)
        return Orcamento(jaime.vault.root, dia)
    except Exception:
        return OrcamentoLivre()

def ligar(jaime, pode_rodar=lambda: True, orcamento=None, intervalo: int | None = None, pasta=None) -> Vontade:
    """Cria impulsos + Mente + criações ligados ao `jaime` e sobe as tasks (escuta do bus e ciclo da Mente)."""
    imp = Impulsos(jaime.vault, perguntas=getattr(jaime, "perguntas", None), perfil=getattr(jaime, "perfil", None))
    observar_placar(getattr(jaime, "placar", None))
    imagens = getattr(jaime, "imagens", None)
    cri = Criacoes(jaime.vault, pasta=pasta, imagens=imagens, modelo=getattr(getattr(jaime, "s", None), "model_padrao", "claude-sonnet-5"))
    orc = orcamento or _orcamento(jaime)
    estudo = getattr(jaime, "estudo", None)
    executores = {"criar": cri.noite}
    if estudo:
        executores["estudar"] = estudo.ciclo
        executores["praticar"] = estudo.ciclo
    def organizar():
        from ..brain.saude import gerar_indices
        return gerar_indices(jaime.vault.root)
    executores["organizar"] = organizar
    mente = Mente(imp, jaime.vault, orcamento=orc, executores=executores, pode_criar=cri.pode_criar)
    v = Vontade(imp, mente, cri)
    kw = {"intervalo": intervalo} if intervalo else {}
    v.tasks = [asyncio.create_task(imp.escutar()), asyncio.create_task(mente.rodar(pode_rodar, **kw))]
    imp.emitir()
    return v
