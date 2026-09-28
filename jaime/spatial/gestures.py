"""Máquina de estados dos gestos de pinça; limiares relativos à largura da palma.

Estados por mão (`ator:mão`): idle → candidate (pinça fechando, espera o dwell) → held (agarrado) → idle (+cooldown).
- Histerese: fecha abaixo de `close_ratio`, só abre acima de `open_ratio` — sem isso o tremor na fronteira gera
  dezenas de pega-solta por segundo.
- Dwell: a pinça precisa durar `dwell_s` para virar grab; fechar e abrir antes disso é ruído, não clique.
- Clique = grab curto e parado (solta em até `click_max_s`, movendo menos que `click_max_move`).
- Cooldown depois de soltar: o dedo que reabre devagar não vira um segundo grab.
- Perda de rastreamento com algo agarrado: `spatial.tracking_lost` + `gesture.cancel` — nunca um "release" fingido.
- Duas mãos do mesmo ator agarrando o mesmo objeto: `gesture.scale` (proporcional e limitado).

O efeito dos gestos aqui é SÓ virtual (posição/escala do objeto no HUD). Nada disto toca o SO."""
from __future__ import annotations
from dataclasses import dataclass
from .core import SpatialCore, SpatialEvent, Vec3

ESCALA_MIN, ESCALA_MAX = 0.3, 4.0


@dataclass(frozen=True)
class HandSample:
    actor: str
    thumb: Vec3
    index: Vec3
    palm_width: float
    timestamp: float
    confidence: float
    target_id: str | None = None
    hand: str = "right"
    cursor: Vec3 | None = None        # onde a mão aponta no HUD; sem ele, a ponta do indicador

    @property
    def pos(self) -> Vec3:
        return self.cursor or self.index


class PinchMachine:
    def __init__(self, core: SpatialCore, close_ratio: float = .28, open_ratio: float = .42, dwell_s: float = .09,
                 click_max_s: float = .35, click_max_move: float = .03, cooldown_s: float = .2,
                 min_confidence: float = .65, move_objects: bool = True):
        if not close_ratio < open_ratio:
            raise ValueError("histerese exige close_ratio < open_ratio")
        self.core, self.close_ratio, self.open_ratio, self.dwell_s = core, close_ratio, open_ratio, dwell_s
        self.click_max_s, self.click_max_move, self.cooldown_s = click_max_s, click_max_move, cooldown_s
        self.min_confidence, self.move_objects = min_confidence, move_objects
        self.state: dict[str, str] = {}
        self.started: dict[str, float] = {}
        self.target: dict[str, str | None] = {}
        self.grab_pos: dict[str, Vec3] = {}
        self.orig_pos: dict[str, Vec3] = {}                       # onde o objeto estava no grab (o cancel devolve)
        self.last_pos: dict[str, Vec3] = {}
        self.hover: dict[str, str | None] = {}
        self.cooldown_until: dict[str, float] = {}
        self._escala_base: dict[str, tuple[float, float]] = {}   # ator → (distância inicial entre mãos, escala inicial)

    @staticmethod
    def _key(actor: str, hand: str) -> str:
        return f"{actor}:{hand}"

    def held(self, actor: str | None = None) -> dict[str, str | None]:
        """Mãos que estão segurando algo agora (chave → alvo)."""
        return {k: self.target.get(k) for k, st in self.state.items()
                if st == "held" and (actor is None or k.startswith(actor + ":"))}

    def update(self, s: HandSample) -> list[SpatialEvent]:
        k = self._key(s.actor, s.hand)
        if s.palm_width <= 0 or s.confidence < self.min_confidence:
            return self.lost(s.actor, s.hand, "confiança baixa")
        ratio = s.thumb.distance(s.index) / s.palm_width
        state = self.state.get(k, "idle")
        out: list[SpatialEvent] = []
        self.last_pos[k] = s.pos
        if state == "idle":
            fechando = ratio <= self.close_ratio and s.timestamp >= self.cooldown_until.get(k, 0.0)
            if fechando:
                self.state[k], self.started[k], self.target[k] = "candidate", s.timestamp, s.target_id
            elif self.hover.get(k) != s.target_id:
                self.hover[k] = s.target_id
                out.append(self.core.emit("gesture.hover", s.actor, s.target_id, s.confidence, hand=s.hand))
        elif state == "candidate":
            if ratio >= self.open_ratio or self.target[k] != s.target_id:
                self._reset(k)
            elif s.timestamp - self.started[k] >= self.dwell_s:
                self.state[k] = "held"; self.started[k] = s.timestamp; self.grab_pos[k] = s.pos
                target = self.target[k]
                if target in self.core.objects:
                    self.orig_pos[k] = self.core.objects[target].position
                    out.append(self.core.select(s.actor, target, s.confidence))
                out.append(self.core.emit("gesture.grab", s.actor, target, s.confidence, hand=s.hand,
                                          position=s.pos.tupla()))
        elif state == "held":
            target = self.target[k]
            if ratio >= self.open_ratio:
                out.append(self.core.emit("gesture.release", s.actor, target, s.confidence, hand=s.hand))
                curto = s.timestamp - self.started[k] <= self.click_max_s
                parado = s.pos.distance(self.grab_pos.get(k, s.pos)) <= self.click_max_move
                if curto and parado:
                    out.append(self.core.emit("gesture.click", s.actor, target, s.confidence, hand=s.hand))
                self._reset(k)
                self.cooldown_until[k] = s.timestamp + self.cooldown_s
                self._escala_base.pop(s.actor, None)
            else:
                if self.move_objects and target in self.core.objects and not self._duas_maos(s.actor, target):
                    self.core.move(target, s.pos)
                out.append(self.core.emit("gesture.drag", s.actor, target, s.confidence, hand=s.hand,
                                          position=s.pos.tupla()))
                out += self._escala(s.actor, target, s.confidence)
        return out

    def _duas_maos(self, actor: str, target: str | None) -> bool:
        return target is not None and sum(1 for t in self.held(actor).values() if t == target) >= 2

    def _escala(self, actor: str, target: str | None, conf: float) -> list[SpatialEvent]:
        if not self._duas_maos(actor, target):
            self._escala_base.pop(actor, None); return []
        chaves = [k for k, t in self.held(actor).items() if t == target][:2]
        a, b = (self.last_pos[c] for c in chaves)
        dist = max(a.distance(b), 1e-4)
        obj = self.core.objects.get(target or "")
        if actor not in self._escala_base:
            self._escala_base[actor] = (dist, obj.scale if obj else 1.0)
            return []
        base, escala0 = self._escala_base[actor]
        fator = min(ESCALA_MAX, max(ESCALA_MIN, escala0 * dist / base))
        if obj:
            obj.scale = fator
        return [self.core.emit("gesture.scale", actor, target, conf, scale=round(fator, 3))]

    def lost(self, actor: str, hand: str, reason: str = "rastreamento perdido") -> list[SpatialEvent]:
        """A mão sumiu (confiança baixa, saiu do quadro, câmera caiu): solta o grab VISUAL e cancela."""
        k = self._key(actor, hand)
        out: list[SpatialEvent] = []
        if self.state.get(k) == "held":
            target = self.target.get(k)
            if target in self.core.objects and k in self.orig_pos:
                self.core.move(target, self.orig_pos[k])        # cancelar é desfazer o arrasto, não largar no meio
            out.append(self.core.emit("spatial.tracking_lost", actor, target, 0.0, hand=hand, reason=reason))
            out.append(self.core.emit("gesture.cancel", actor, target, 0.0, hand=hand, reason=reason))
        self._reset(k); self.hover.pop(k, None); self._escala_base.pop(actor, None)
        return out

    def lost_all(self, reason: str) -> list[SpatialEvent]:
        out: list[SpatialEvent] = []
        for k in list(self.state):
            actor, hand = k.rsplit(":", 1)
            out += self.lost(actor, hand, reason)
        return out

    def reset(self, actor: str) -> None:
        """Compatível com o pacote: esquece todas as mãos do ator, sem eventos."""
        for k in [k for k in list(self.state) if k.startswith(actor + ":")]:
            self._reset(k)

    def _reset(self, k: str) -> None:
        for d in (self.state, self.started, self.target, self.grab_pos, self.orig_pos):
            d.pop(k, None)
