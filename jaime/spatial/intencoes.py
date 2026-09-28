"""Gestos → intenções (fase 3). Ouvinte do serviço: recebe os eventos já decididos pela máquina de gestos.

- clique = só seleção (virtual). DUPLO clique num objeto com arquivo = propor "abrir" (prévia → recibo).
- soltar um objeto sobre a zona da lixeira:
    · objeto virtual → some da cena, com Undo (é só desenho);
    · objeto com arquivo real → PRÉVIA de "mover para a Lixeira" em revisão: nada acontece sem confirmação
      explícita (botão no HUD ou "sim" ao Vigia pela voz). Apagar definitivo não existe como gesto.
- "amassar" (mão fechada sobre o objeto) fica para quando o rastreador real estiver calibrado; o arremesso
  aqui é o arrastar-e-soltar na zona, que já é medido e reversível."""
from __future__ import annotations
from typing import Callable
from uuid import uuid4
from .acoes import ActionProposal, AdaptadorAcoes
from .core import SpatialCore, SpatialEvent, SpatialObject

DUPLO_S = 0.6


class Intencoes:
    def __init__(self, core: SpatialCore, acoes: AdaptadorAcoes | None, emitir: Callable[..., None],
                 agendar: Callable, zona_lixeira: str = "zona:lixeira"):
        self.core, self.acoes, self.emitir, self.agendar, self.zona = core, acoes, emitir, agendar, zona_lixeira
        self._ultimo_clique: dict[str, tuple[str, float]] = {}
        self.descartados: dict[str, SpatialObject] = {}

    def __call__(self, ev: SpatialEvent) -> None:
        if ev.kind == "gesture.click" and ev.object_id:
            ant = self._ultimo_clique.get(ev.actor)
            self._ultimo_clique[ev.actor] = (ev.object_id, ev.timestamp)
            if ant and ant[0] == ev.object_id and ev.timestamp - ant[1] <= DUPLO_S:
                self._ultimo_clique.pop(ev.actor, None)
                obj = self.core.objects.get(ev.object_id)
                if obj and obj.resource_ref and self.acoes:
                    self.agendar(self._abrir(ActionProposal("open", obj.id, ev.actor, ev.confidence, "gesto", id=ev.id)))
        elif ev.kind == "gesture.release" and ev.object_id:
            self._talvez_lixeira(ev)

    async def _abrir(self, p: ActionProposal) -> None:
        pv = await self.acoes.propor(p)
        if pv.status == "allow":                 # reversível e liberado: a prévia já apareceu, o recibo diz o que houve
            await self.acoes.executar(p.id)

    def _talvez_lixeira(self, ev: SpatialEvent) -> None:
        zona = self.core.objects.get(self.zona)
        obj = self.core.objects.get(ev.object_id or "")
        if not zona or not obj or obj.id == zona.id:
            return
        if obj.position.distance(zona.position) > zona.radius * zona.scale:
            return
        if obj.resource_ref:
            if self.acoes:
                self.agendar(self.acoes.propor(ActionProposal("move_to_trash", obj.id, ev.actor, ev.confidence, "gesto", id=ev.id)))
            return
        token = uuid4().hex[:10]
        self.descartados[token] = self.core.remove(obj.id)
        self.emitir("espacial", evento="spatial.removed", object_id=obj.id, desfazer=token,
                    resumo=f"{obj.label or obj.id} descartado (só na cena)")

    def desfazer_descarte(self, token: str) -> bool:
        obj = self.descartados.pop(token, None)
        if not obj:
            return False
        from .core import Vec3
        obj.position = Vec3(0.5, 0.5, 0.0)
        self.core.add(obj)
        self.emitir("espacial", evento="spatial.object", obj_novo=obj.to_dict())
        return True
