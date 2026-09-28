"""Serviço espacial: fonte → fila bounded → rastreador → filtro → gestos → bus do HUD.

Caminho quente (reflexo local), sem LLM por frame:
  frame ──► fila (1–2, descarta o mais velho) ──► landmarks (thread) ──► One Euro ──► pinça ──► bus

Ciclo de vida: `iniciar()` cria as tasks; `parar()` cancela e FECHA a fonte (câmera solta) — o servidor de voz
não é tocado. Kill switch (`desligar_rastreamento`, HUD e voz) para só o rastreamento.

Identidade: mão na câmera não prova quem é. Com câmera real, o rastreamento só roda com o cérebro destrancado e
sem convidado na linha (`dono_ok`); em simulação/replay os dados são sintéticos e o ator vira "demo", que nenhuma
política deixa agir no SO.

Bus: usa o `Bus` existente (jaime/hud/events.py), tipo "espacial". Cursor/drag/hover são efêmeros (não entram no
histórico de 300 — senão 10 s de arrasto apagavam a memória recente do HUD) e têm teto de frequência."""
from __future__ import annotations
import asyncio, time
from typing import Callable
from .config import ConfigEspacial
from .core import SpatialCore, SpatialEvent, Vec3
from .filtro import FiltroMao
from .fontes import RastreadorIdentidade
from .gestures import HandSample, PinchMachine
from .landmarks import CameraFrame, HandPose, alvo_em, cursor as cursor_de, largura_palma, razao_pinca, POLEGAR, INDICADOR
from .metricas import Metricas

EFEMEROS = frozenset({"gesture.drag", "gesture.hover", "gesture.scale", "spatial.cursor"})


def _emitir_bus(tipo: str, **dados) -> None:
    from ..hud.events import bus
    bus.emitir(tipo, **dados)


class ServicoEspacial:
    def __init__(self, cfg: ConfigEspacial, emitir: Callable[..., None] | None = None, core: SpatialCore | None = None,
                 fonte=None, rastreador=None, dono_ok: Callable[[], bool] = lambda: True,
                 relogio: Callable[[], float] = time.monotonic):
        self.cfg = cfg
        self.emitir = emitir or _emitir_bus
        self.core = core or SpatialCore()
        self.fonte, self.rastreador = fonte, rastreador or RastreadorIdentidade()
        self.dono_ok, self.relogio = dono_ok, relogio
        self.pinca = PinchMachine(self.core, min_confidence=cfg.rastreio_conf_min)
        self.filtro = FiltroMao()
        self.metricas = Metricas()
        self.rodando = False
        self.rastreando = False
        self.erro = ""
        self.motivo_parada = ""
        self._tasks: list[asyncio.Task] = []
        self._fila: asyncio.Queue | None = None
        self._visto: dict[str, float] = {}          # "ator:mão" → último relógio em que a mão apareceu
        self._ultimo_frame = 0.0
        self._ultimo_efemero: dict[str, float] = {}
        self._suspenso = ""
        self.ouvintes: list[Callable[[SpatialEvent], None]] = []   # fase 3: gestos → intenções
        self.extras: list[Callable[[], object]] = []                # tasks auxiliares (ex.: vigia de monitores), mesmo ciclo de vida

    # ── ciclo de vida ──────────────────────────────────
    def _fonte_padrao(self):
        from .fontes import FonteSequencia, FonteReplay, FonteOpenCV, RastreadorMediaPipe
        from .simulador import cenario, poses
        m = self.cfg.modo
        if m == "sim":
            return FonteSequencia(poses(cenario(self.cfg.cenario, self.core), ruido=0.002), repetir=self.cfg.repetir)
        if m == "replay":
            if not self.cfg.replay:
                raise RuntimeError("JAIME_SPATIAL=replay exige JAIME_SPATIAL_REPLAY=<arquivo .jsonl>")
            return FonteReplay(self.cfg.replay, repetir=self.cfg.repetir)
        if m == "camera":
            self.rastreador = self.rastreador if not isinstance(self.rastreador, RastreadorIdentidade) else RastreadorMediaPipe()
            return FonteOpenCV(int(self.cfg.cameras[0]) if self.cfg.cameras[0].isdigit() else 0)
        raise RuntimeError("JAIME_SPATIAL=off")

    async def iniciar(self) -> None:
        if self.rodando:
            return
        for t in self._tasks:                 # restos de uma execução que terminou sozinha
            t.cancel()
        self._tasks = []
        self.erro = self.motivo_parada = ""
        try:
            if self.fonte is None:
                self.fonte = self._fonte_padrao()
        except Exception as e:
            self.erro = str(e)[:200]
            self._estado_bus(); return
        self._fila = asyncio.Queue(maxsize=self.cfg.fila)
        self.rodando = self.rastreando = True
        self._ultimo_frame = self.relogio()
        self._tasks = [asyncio.create_task(self._produzir(), name="espacial:fonte"),
                       asyncio.create_task(self._consumir(), name="espacial:gestos"),
                       asyncio.create_task(self._vigiar(), name="espacial:watchdog")]
        self._tasks += [asyncio.create_task(f(), name=f"espacial:extra{i}") for i, f in enumerate(self.extras)]
        self._publicar_cena()
        self._estado_bus()

    async def parar(self, motivo: str = "parado") -> None:
        """Cancela as tasks e solta a câmera. Idempotente."""
        self.motivo_parada = motivo
        for e in self.pinca.lost_all(motivo):
            self._publicar(e)
        self.rodando = self.rastreando = False
        if self.fonte is not None:
            try:
                self.fonte.fechar()
            except Exception:
                pass
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks = []
        self._soltar_fonte()
        self._estado_bus()

    def _encerrar_resto(self) -> None:
        """A fonte acabou (ou caiu): cancela as OUTRAS tasks (watchdog, monitores…) e esquece a fonte, para um
        `iniciar()` depois criar uma nova em vez de reusar a fechada. Não cancela a task que está chamando."""
        atual = asyncio.current_task()
        for t in self._tasks:
            if t is not atual:
                t.cancel()
        self._soltar_fonte()

    def _soltar_fonte(self) -> None:
        if self.fonte is not None:
            try:
                self.fonte.fechar()
            except Exception:
                pass
        self.fonte = None
        try:
            self.rastreador.fechar()
        except Exception:
            pass
        if self.cfg.modo == "camera":
            self.rastreador = RastreadorIdentidade()      # o MediaPipe fechado não serve mais: iniciar() cria outro

    async def desligar_rastreamento(self, motivo: str = "kill switch") -> dict:
        """Kill switch (HUD/voz): para o rastreamento na hora; o resto do Jaime segue."""
        await self.parar(motivo)
        return self.estado()

    # ── tasks ──────────────────────────────────────────
    async def _produzir(self) -> None:
        assert self._fila is not None
        try:
            async for frame in self.fonte.frames():
                if self._fila.full():
                    try:
                        self._fila.get_nowait(); self.metricas.descartados += 1   # o velho sai: nunca atrasar a mão
                    except asyncio.QueueEmpty:
                        pass
                self._fila.put_nowait(frame)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.erro = f"fonte: {str(e)[:160]}"
            for ev in self.pinca.lost_all("câmera caiu"):
                self._publicar(ev)
            self._estado_bus()
        finally:
            if self._fila.full():                       # o fim nunca pode se perder: sem ele o consumidor espera para sempre
                try:
                    self._fila.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                self._fila.put_nowait(None)
            except asyncio.QueueFull:
                pass

    async def _consumir(self) -> None:
        assert self._fila is not None
        while True:
            frame = await self._fila.get()
            if frame is None:
                if self._fila.empty():
                    break
                continue
            try:
                await self.processar(frame)
            except asyncio.CancelledError:
                raise
            except Exception as e:     # um frame ruim não derruba o laço
                self.erro = f"frame {frame.frame_id}: {type(e).__name__}: {str(e)[:120]}"
        if self.rodando:
            for ev in self.pinca.lost_all("fonte terminou"):
                self._publicar(ev)
            self.rodando = self.rastreando = False
            self.motivo_parada = self.motivo_parada or ("erro na fonte" if self.erro else "fonte terminou")
            self._encerrar_resto()
            self._estado_bus()

    async def _vigiar(self) -> None:
        """Sem frames com algo agarrado = cancela (câmera travou sem erro, driver dormiu)."""
        while True:
            await asyncio.sleep(0.25)
            if self.relogio() - self._ultimo_frame > max(0.75, self.cfg.perda_s * 3) and self.pinca.held():
                for ev in self.pinca.lost_all("sem frames"):
                    self._publicar(ev)

    # ── um frame ───────────────────────────────────────
    def _ator(self) -> str:
        if self.cfg.modo in ("sim", "replay"):
            return "demo"
        return "joao" if self.dono_ok() else "desconhecido"

    async def processar(self, frame: CameraFrame) -> list[SpatialEvent]:
        agora = self.relogio()
        self._ultimo_frame = agora
        self.metricas.frame(agora)
        self.metricas.registrar("fila_ms", (agora - frame.capture_ts) * 1000)
        if self.cfg.modo == "camera" and not self.dono_ok():
            if not self._suspenso:
                self._suspenso = "cérebro trancado ou convidado na linha"
                for ev in self.pinca.lost_all(self._suspenso):
                    self._publicar(ev)
                self._estado_bus()
            return []                                   # frame descartado sem nem rodar o rastreador
        if self._suspenso:
            self._suspenso = ""; self._estado_bus()
        if isinstance(self.rastreador, RastreadorIdentidade):
            maos = self.rastreador.detect(frame)
        else:
            maos = await asyncio.to_thread(self.rastreador.detect, frame)
        t_lm = self.relogio()
        self.metricas.registrar("landmarks_ms", (t_lm - agora) * 1000)
        ator = self._ator()
        tm = frame.ts                                   # tempo da mídia: replay acelerado dá o mesmo resultado que ao vivo
        eventos: list[SpatialEvent] = []
        cursores = []
        vistos = set()
        for pose in maos:
            if not pose.valida():
                continue
            k = f"{ator}:{pose.hand_id}"
            vistos.add(k); self._visto[k] = tm
            lm = self.filtro(k, pose.landmarks, tm)
            cur = cursor_de(lm, self.cfg.espelhar)
            alvo = alvo_em(self.core, cur.x, cur.y)
            amostra = HandSample(ator, Vec3(*lm[POLEGAR]), Vec3(*lm[INDICADOR]), largura_palma(lm), tm,
                                 pose.confidence, alvo.id if alvo else None, pose.hand_id, cur)
            eventos += self.pinca.update(amostra)
            cursores.append({"hand": pose.hand_id, "x": round(cur.x, 4), "y": round(cur.y, 4),
                             "pinca": round(min(razao_pinca(lm), 9.99), 3),
                             "estado": self.pinca.state.get(k, "idle"), "alvo": alvo.id if alvo else None,
                             "lm": [[round((1 - p[0]) if self.cfg.espelhar else p[0], 3), round(p[1], 3)] for p in lm]})
        for k, t in list(self._visto.items()):       # mãos que sumiram
            if k not in vistos and tm - t > self.cfg.perda_s:
                a, h = k.rsplit(":", 1)
                eventos += self.pinca.lost(a, h, "mão saiu do quadro")
                self.filtro.esquecer(k); self._visto.pop(k, None)
        t_g = self.relogio()
        self.metricas.registrar("gesto_ms", (t_g - t_lm) * 1000)
        for ev in eventos:
            self._publicar(ev, frame)
        self._publicar_cursor(cursores, frame)
        self.metricas.registrar("captura_evento_ms", (self.relogio() - frame.capture_ts) * 1000)
        return eventos

    # ── saída para o bus ───────────────────────────────
    def _publicar(self, ev: SpatialEvent, frame: CameraFrame | None = None) -> None:
        self.metricas.eventos[ev.kind] += 1
        for f in self.ouvintes:
            try:
                f(ev)
            except Exception:
                pass
        efemero = ev.kind in EFEMEROS
        if efemero and not self._pode_efemero(ev.kind):
            return
        d = ev.to_dict()
        if ev.object_id and ev.object_id in self.core.objects:
            o = self.core.objects[ev.object_id]
            d["obj"] = {"pos": o.position.tupla(), "scale": round(o.scale, 3), "label": o.label}
        self.emitir("espacial", evento=ev.kind, _efemero=efemero, wall_ms=round(frame.wall_ms, 1) if frame else 0,
                    **{k: v for k, v in d.items() if k != "kind"})

    def _pode_efemero(self, chave: str) -> bool:
        agora = self.relogio()
        if agora - self._ultimo_efemero.get(chave, 0.0) < 1.0 / max(self.cfg.hz_efemero, 1.0):
            return False
        self._ultimo_efemero[chave] = agora
        return True

    def _publicar_cursor(self, cursores: list[dict], frame: CameraFrame) -> None:
        if not self._pode_efemero("spatial.cursor"):
            return
        self.emitir("espacial", evento="spatial.cursor", _efemero=True, maos=cursores, wall_ms=round(frame.wall_ms, 1))

    def _publicar_cena(self) -> None:
        self.emitir("espacial", evento="spatial.scene", **self.core.cena())

    def _estado_bus(self) -> None:
        self.emitir("espacial", evento="spatial.estado", **self.estado(curto=True))

    def estado(self, curto: bool = False) -> dict:
        d = {"modo": self.cfg.modo, "rodando": self.rodando, "rastreando": self.rastreando, "erro": self.erro,
             "suspenso": self._suspenso, "parada": self.motivo_parada, "dry_run": self.cfg.dry_run,
             "rastreador": getattr(self.rastreador, "nome", type(self.rastreador).__name__)}
        if not curto:
            d["metricas"] = self.metricas.resumo()
            d["cena"] = self.core.cena()
        return d

    def registrar_render(self, amostras_ms: list[float]) -> None:
        """O HUD manda, em lote, quanto cada evento levou do frame até ser desenhado (Date.now() − wall_ms)."""
        for ms in amostras_ms[:500]:
            try:
                v = float(ms)
            except (TypeError, ValueError):
                continue
            if 0 <= v < 10_000:
                self.metricas.registrar("evento_render_ms", v)
