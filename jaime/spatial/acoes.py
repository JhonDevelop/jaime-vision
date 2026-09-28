"""Fase 3 — ações reais, com o mesmo cinto de segurança do resto do Jaime.

    gesto/voz → intenção → objeto resolvido → dono + confiança (policy.py) → recurso canônico dentro do escopo
      → PRÉVIA (sempre) → Vigia real (mesmo hook das ferramentas) → execução (ou dry-run) → observa o SO
      → RECIBO (idempotente pelo ID da proposta) → Undo

- `JAIME_SPATIAL_DRY_RUN=on` (padrão): tudo até o recibo acontece, menos o efeito no SO.
- Gesto sozinho nunca basta para classe sensível (lixeira): precisa de confirmação explícita (voz/HUD).
- Apagar definitivo, publicar, enviar, instalar: negado aqui. Não há gesto para isso.
- Repetir o mesmo evento (rede, duplo clique, retry) devolve o MESMO recibo: nada roda duas vezes.
- Monitores mudaram (hotplug/escala) → mover janela fica suspenso até validar o apontamento.

Backends: macOS (`open`, AppleScript/System Events, Finder) e Windows (os.startfile, Win32). Cada chamada de SO
fica atrás de um `Executor` para os testes usarem um dublê — a suíte nunca toca o computador de verdade."""
from __future__ import annotations
import asyncio, json, os, platform, subprocess, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol
from uuid import uuid4
from .core import SpatialCore
from .policy import ProposedAction, evaluate

VERBOS = {
    # verbo: (classe na policy.py, descrição)
    "open": ("open", "abrir"),
    "move_window": ("move_window", "mover a janela"),
    "move_to_trash": ("move_to_trash", "mover para a Lixeira"),
    "delete_forever": ("delete_forever", "apagar definitivamente"),
    "send": ("send", "enviar"),
    "publish": ("publish", "publicar"),
    "install": ("install", "instalar"),
}
NUNCA = frozenset({"delete_forever", "send", "publish", "install", "run_command"})
PREVIA_TTL_S = 90.0


@dataclass
class ActionProposal:
    verbo: str
    alvo_id: str
    ator: str
    confianca: float
    origem: str = "gesto"                 # gesto | voz | hud | ferramenta
    args: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex[:12])


@dataclass
class Preview:
    proposta_id: str
    verbo: str
    alvo_id: str
    resumo: str
    status: str                           # allow | review | deny
    motivo: str
    recurso: str = ""
    efeitos: list[str] = field(default_factory=list)
    undo: str = ""
    dry_run: bool = True
    criado: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self); d.pop("criado", None); return d


@dataclass
class ActionReceipt:
    id: str
    proposta_id: str
    verbo: str
    alvo_id: str
    executado: bool
    dry_run: bool
    resumo: str
    quando: float
    undo_dados: dict = field(default_factory=dict)
    erro: str = ""
    desfeito: bool = False
    ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class Executor(Protocol):
    def abrir(self, caminho: str) -> None: ...
    def janela(self, app: str, titulo: str = "") -> tuple[int, int, int, int] | None: ...
    def mover_janela(self, app: str, titulo: str, x: int, y: int) -> None: ...
    def lixeira(self, caminho: str) -> str: ...
    def restaurar(self, na_lixeira: str, destino: str) -> None: ...


# ── backends reais ───────────────────────────────────────────────────────────
def _osa(script: str, timeout: float = 10) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "osascript falhou").strip()[:200])
    return r.stdout.strip()


def _aspas(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


class ExecutorMac:
    """macOS: precisa de Acessibilidade para mover janela (a mesma permissão que o pyautogui já pede)."""
    def abrir(self, caminho: str) -> None:
        subprocess.run(["open", caminho], check=True, timeout=10, capture_output=True)

    def janela(self, app: str, titulo: str = "") -> tuple[int, int, int, int] | None:
        filtro = f' whose name contains {_aspas(titulo)}' if titulo else ""
        out = _osa(f'tell application "System Events" to tell process {_aspas(app)} to get {{position, size}} of (first window{filtro})')
        nums = [int(float(x)) for x in out.replace(" ", "").split(",") if x.strip().lstrip("-").replace(".", "").isdigit()]
        return tuple(nums[:4]) if len(nums) >= 4 else None  # type: ignore[return-value]

    def mover_janela(self, app: str, titulo: str, x: int, y: int) -> None:
        filtro = f' whose name contains {_aspas(titulo)}' if titulo else ""
        _osa(f'tell application "System Events" to tell process {_aspas(app)} to set position of (first window{filtro}) to {{{int(x)}, {int(y)}}}')

    def lixeira(self, caminho: str) -> str:
        # o Finder põe na Lixeira de verdade (com "Pôr de Volta"); devolve onde o item ficou
        out = _osa(f'tell application "Finder" to POSIX path of (delete (POSIX file {_aspas(caminho)} as alias) as alias)')
        return out

    def restaurar(self, na_lixeira: str, destino: str) -> None:
        if Path(destino).exists():
            raise RuntimeError("já existe algo no caminho original; não sobrescrevo")
        if not Path(na_lixeira).exists():
            raise RuntimeError("o item não está mais na Lixeira")
        os.replace(na_lixeira, destino)


class ExecutorWindows:
    """Windows: mover janela via Win32; lixeira via SHFileOperation com FOF_ALLOWUNDO."""
    def abrir(self, caminho: str) -> None:
        os.startfile(caminho)  # type: ignore[attr-defined]

    def _hwnd(self, app: str, titulo: str):
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        achado = []
        Proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def cb(h, _):
            if not user32.IsWindowVisible(h):
                return True
            n = user32.GetWindowTextLengthW(h)
            buf = ctypes.create_unicode_buffer(n + 1); user32.GetWindowTextW(h, buf, n + 1)
            if (titulo or app).lower() in buf.value.lower():
                achado.append(h); return False
            return True
        user32.EnumWindows(Proc(cb), 0)
        return achado[0] if achado else None

    def janela(self, app: str, titulo: str = ""):
        import ctypes
        from ctypes import wintypes
        h = self._hwnd(app, titulo)
        if not h:
            return None
        r = wintypes.RECT(); ctypes.windll.user32.GetWindowRect(h, ctypes.byref(r))
        return (r.left, r.top, r.right - r.left, r.bottom - r.top)

    def mover_janela(self, app: str, titulo: str, x: int, y: int) -> None:
        import ctypes
        h = self._hwnd(app, titulo)
        if not h:
            raise RuntimeError("janela não encontrada")
        SWP_NOSIZE, SWP_NOZORDER = 0x0001, 0x0004
        if not ctypes.windll.user32.SetWindowPos(h, 0, int(x), int(y), 0, 0, SWP_NOSIZE | SWP_NOZORDER):
            raise RuntimeError("SetWindowPos falhou")

    def lixeira(self, caminho: str) -> str:
        import ctypes
        from ctypes import wintypes
        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                        ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL), ("hNameMappings", ctypes.c_void_p),
                        ("lpszProgressTitle", wintypes.LPCWSTR)]
        FO_DELETE, FOF_ALLOWUNDO, FOF_NOCONFIRMATION, FOF_SILENT = 3, 0x40, 0x10, 0x4
        op = SHFILEOPSTRUCTW(None, FO_DELETE, caminho + "\0", None, FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT, False, None, None)
        if ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) != 0:
            raise RuntimeError("SHFileOperation falhou")
        return "Lixeira do Windows"

    def restaurar(self, na_lixeira: str, destino: str) -> None:
        raise RuntimeError("no Windows, restaure pela Lixeira (clique direito › Restaurar)")


def executor_do_sistema() -> Executor | None:
    so = platform.system()
    return ExecutorMac() if so == "Darwin" else ExecutorWindows() if so == "Windows" else None


# ── o adaptador ──────────────────────────────────────────────────────────────
class AdaptadorAcoes:
    def __init__(self, core: SpatialCore, executor: Executor | None, dono_ok: Callable[[], bool],
                 vigia: Callable[[str, dict], Awaitable[dict]] | None = None, dry_run: bool = True,
                 raizes: list[Path] | None = None, proibidas: list[Path] | None = None,
                 emitir: Callable[..., None] | None = None, telas=None, limiar: float = 0.85,
                 log: Path | None = None, relogio: Callable[[], float] = time.monotonic):
        self.core, self.executor, self.dono_ok, self.vigia = core, executor, dono_ok, vigia
        self.dry_run, self.emitir, self.telas, self.limiar, self.relogio = dry_run, emitir or (lambda *a, **k: None), telas, limiar, relogio
        self.raizes = [Path(r).expanduser().resolve() for r in (raizes or [])]
        self.proibidas = [Path(r).expanduser().resolve() for r in (proibidas or [])]
        self.previas: dict[str, tuple[ActionProposal, Preview]] = {}
        self.recibos: dict[str, ActionReceipt] = {}       # proposta_id → recibo (idempotência)
        self.por_recibo: dict[str, ActionReceipt] = {}
        self.duplicados_bloqueados = 0
        self.log = log

    # ── recurso canônico ───────────────────────────────
    def recurso(self, ref: str | None) -> tuple[Path | None, str]:
        """Caminho real, dentro do escopo, sem `..` nem symlink escapando. (caminho, motivo_se_negado)."""
        if not ref:
            return None, "objeto virtual: não há arquivo por trás"
        if ".." in Path(ref).parts:
            return None, "caminho com '..' recusado"
        try:
            p = Path(ref).expanduser().resolve(strict=True)
        except (FileNotFoundError, OSError, RuntimeError):
            return None, "o arquivo não existe (um objeto virtual não prova que o arquivo existe)"
        if any(p == r or r in p.parents for r in self.proibidas):
            return None, "caminho protegido (vault/identidade/segredos)"
        if not any(p == r or r in p.parents for r in self.raizes):
            return None, "fora das pastas liberadas para ações espaciais"
        return p, ""

    # ── prévia ─────────────────────────────────────────
    async def propor(self, p: ActionProposal) -> Preview:
        obj = self.core.objects.get(p.alvo_id)
        rotulo = (obj.label or obj.id) if obj else p.alvo_id
        desc = VERBOS.get(p.verbo, (p.verbo, p.verbo))[1]
        pv = Preview(p.id, p.verbo, p.alvo_id, f"{desc} {rotulo}", "deny", "", dry_run=self.dry_run, criado=self.relogio())
        if p.verbo in NUNCA:
            pv.motivo = "isso nunca sai de um gesto nem de uma prévia espacial — use o fluxo normal com o Vigia"
            return self._guardar(p, pv)
        if obj is None:
            pv.motivo = "objeto não existe mais na cena"; return self._guardar(p, pv)
        d = evaluate(ProposedAction(VERBOS.get(p.verbo, (p.verbo,))[0], p.alvo_id, p.ator, p.confianca, p.origem),
                     unlocked=self.dono_ok(), owner=p.ator == "joao", threshold=self.limiar)
        pv.status, pv.motivo = d.status, d.reason
        if d.status == "deny":
            return self._guardar(p, pv)
        if p.verbo in ("open", "move_to_trash"):
            caminho, motivo = self.recurso(obj.resource_ref)
            if caminho is None:
                pv.status, pv.motivo = "deny", motivo; return self._guardar(p, pv)
            pv.recurso = str(caminho)
            if p.verbo == "open":
                pv.efeitos = [f"abre {caminho} no {'Finder' if platform.system() == 'Darwin' else 'app padrão'}"]
                pv.undo = "nada a desfazer (abrir não altera o arquivo)"
            else:
                pv.efeitos = [f"move {caminho} para a Lixeira (recuperável)"]
                pv.undo = "restaura ao caminho original"
                pv.status = "review"            # gesto nunca basta: precisa de confirmação explícita
        elif p.verbo == "move_window":
            if self.telas is not None and self.telas.suspenso:
                pv.status, pv.motivo = "deny", self.telas.suspenso; return self._guardar(p, pv)
            app = p.args.get("app") or (obj.metadata.get("app") if obj else "")
            if not app or "x" not in p.args or "y" not in p.args:
                pv.status, pv.motivo = "deny", "faltou app/posição de destino"; return self._guardar(p, pv)
            pv.recurso = f"janela {app}" + (f" «{p.args.get('titulo')}»" if p.args.get("titulo") else "")
            pv.efeitos = [f"move {pv.recurso} para ({int(p.args['x'])}, {int(p.args['y'])})"]
            pv.undo = "volta a janela à posição anterior"
        if self.dry_run:
            pv.efeitos = [f"[dry-run] {e}" for e in pv.efeitos]
        return self._guardar(p, pv)

    def _guardar(self, p: ActionProposal, pv: Preview) -> Preview:
        self.previas[p.id] = (p, pv)
        tipo = "action.denied" if pv.status == "deny" else "action.preview"
        self.emitir("espacial", evento=tipo, object_id=p.alvo_id, proposta_id=p.id, status=pv.status,
                    resumo=pv.resumo + (f" — {pv.efeitos[0]}" if pv.efeitos else ""), motivo=pv.motivo, undo=pv.undo)
        return pv

    # ── execução ───────────────────────────────────────
    async def executar(self, proposta_id: str, confirmado: bool = False) -> ActionReceipt:
        if proposta_id in self.recibos:                       # idempotência: o mesmo evento não age duas vezes
            self.duplicados_bloqueados += 1
            return self.recibos[proposta_id]
        par = self.previas.get(proposta_id)
        if not par:
            return self._recibo_falho(proposta_id, "", "", "prévia não encontrada")
        p, pv = par
        if self.relogio() - pv.criado > PREVIA_TTL_S:
            return self._recibo_falho(p.id, p.verbo, p.alvo_id, "prévia vencida — proponha de novo")
        if pv.status == "deny":
            return self._recibo_falho(p.id, p.verbo, p.alvo_id, f"negado: {pv.motivo}")
        if pv.status == "review" and not confirmado:
            return self._recibo_falho(p.id, p.verbo, p.alvo_id, "precisa de confirmação explícita (voz ou HUD)", guardar=False)
        if not self.dono_ok():                                 # o cérebro pode ter trancado entre a prévia e agora
            return self._recibo_falho(p.id, p.verbo, p.alvo_id, "sessão do dono fechada")
        if p.verbo == "move_window" and self.telas is not None and self.telas.suspenso:
            return self._recibo_falho(p.id, p.verbo, p.alvo_id, self.telas.suspenso)
        if self.vigia is not None:
            decisao = await self.vigia(f"mcp__espacial__{p.verbo}", {"alvo": pv.recurso or p.alvo_id, "caminho": pv.recurso, **p.args})
            saida = (decisao or {}).get("hookSpecificOutput", {})
            if saida.get("permissionDecision") == "deny":
                return self._recibo_falho(p.id, p.verbo, p.alvo_id, f"Vigia: {saida.get('permissionDecisionReason', '')[:160]}", guardar=False)
        t0 = self.relogio()
        rid = uuid4().hex[:12]
        if self.dry_run or self.executor is None:
            r = ActionReceipt(rid, p.id, p.verbo, p.alvo_id, False, True, f"[dry-run] {pv.efeitos[0] if pv.efeitos else pv.resumo}",
                              time.time(), undo_dados={}, erro="" if self.executor or self.dry_run else "sem backend de SO")
            return self._fechar(r, t0)
        try:
            undo = await asyncio.to_thread(self._efeito, p, pv)
            r = ActionReceipt(rid, p.id, p.verbo, p.alvo_id, True, False, pv.efeitos[0] if pv.efeitos else pv.resumo, time.time(), undo)
        except Exception as e:
            r = ActionReceipt(rid, p.id, p.verbo, p.alvo_id, False, False, pv.resumo, time.time(), erro=f"{type(e).__name__}: {str(e)[:160]}")
        return self._fechar(r, t0)

    def _efeito(self, p: ActionProposal, pv: Preview) -> dict:
        ex = self.executor
        assert ex is not None
        if p.verbo == "open":
            ex.abrir(pv.recurso); return {}
        if p.verbo == "move_window":
            app, titulo = p.args.get("app", ""), p.args.get("titulo", "")
            antes = ex.janela(app, titulo)
            if not antes:
                raise RuntimeError("janela não encontrada")
            ex.mover_janela(app, titulo, int(p.args["x"]), int(p.args["y"]))
            depois = ex.janela(app, titulo)                    # observa o SO: o recibo diz o que aconteceu, não o que se pediu
            if not depois or abs(depois[0] - int(p.args["x"])) > 40 or abs(depois[1] - int(p.args["y"])) > 40:
                raise RuntimeError(f"o SO não moveu a janela (está em {depois})")
            return {"app": app, "titulo": titulo, "x": antes[0], "y": antes[1]}
        if p.verbo == "move_to_trash":
            onde = ex.lixeira(pv.recurso)
            if Path(pv.recurso).exists():
                raise RuntimeError("o arquivo continua no lugar")
            return {"na_lixeira": onde, "original": pv.recurso}
        raise RuntimeError(f"verbo sem efeito implementado: {p.verbo}")

    def _recibo_falho(self, pid: str, verbo: str, alvo: str, motivo: str, guardar: bool = True) -> ActionReceipt:
        r = ActionReceipt(uuid4().hex[:12], pid, verbo, alvo, False, self.dry_run, motivo, time.time(), erro=motivo)
        self.emitir("espacial", evento="action.denied", object_id=alvo, proposta_id=pid, motivo=motivo)
        if guardar and pid:
            self.recibos[pid] = r
        self.por_recibo[r.id] = r
        return r

    def _fechar(self, r: ActionReceipt, t0: float) -> ActionReceipt:
        r.ms = round((self.relogio() - t0) * 1000, 2)
        self.recibos[r.proposta_id] = r; self.por_recibo[r.id] = r
        self.emitir("espacial", evento="action.receipt", object_id=r.alvo_id, recibo_id=r.id, proposta_id=r.proposta_id,
                    executado=r.executado, dry_run=r.dry_run, resumo=r.resumo, erro=r.erro)
        self._registrar(r)
        return r

    def _registrar(self, r: ActionReceipt) -> None:
        """Log JSON fora do vault: decisão, IDs, latência — sem conteúdo de arquivo."""
        if not self.log:
            return
        try:
            self.log.parent.mkdir(parents=True, exist_ok=True)
            with self.log.open("a", encoding="utf-8") as f:
                f.write(json.dumps({k: v for k, v in r.to_dict().items() if k != "undo_dados"}, ensure_ascii=False) + "\n")
        except OSError:
            pass

    # ── undo ───────────────────────────────────────────
    async def desfazer(self, recibo_id: str) -> tuple[bool, str]:
        r = self.por_recibo.get(recibo_id)
        if not r:
            return False, "recibo não encontrado"
        if r.desfeito:
            return True, "já estava desfeito"
        if r.dry_run or not r.executado:
            r.desfeito = True
            return True, "nada a desfazer (não houve efeito no SO)"
        try:
            if r.verbo == "move_window":
                u = r.undo_dados
                await asyncio.to_thread(self.executor.mover_janela, u["app"], u["titulo"], u["x"], u["y"])
            elif r.verbo == "move_to_trash":
                u = r.undo_dados
                await asyncio.to_thread(self.executor.restaurar, u["na_lixeira"], u["original"])
            elif r.verbo == "open":
                return False, "abrir não se desfaz (feche a janela se quiser)"
            r.desfeito = True
            self.emitir("espacial", evento="action.undo", object_id=r.alvo_id, recibo_id=r.id, resumo=f"desfeito: {r.resumo}")
            return True, "desfeito"
        except Exception as e:
            return False, f"{type(e).__name__}: {str(e)[:160]}"
