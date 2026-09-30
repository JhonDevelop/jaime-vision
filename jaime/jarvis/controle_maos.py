"""As mãos do João controlando o computador inteiro, não só a tela do Jarvis.

Cada mão tem a sua função (30/09, escolha do João):
- DIREITA = mouse. A base do indicador guia o cursor (não a ponta: assim a pinça não faz o cursor pular).
  · pinça rápida (indicador + polegar) → clique; duas seguidas → clique duplo;
  · pinça segurando (ou pinça + mover) → arrasta (botão apertado até abrir a pinça);
  · pinça do dedo MÉDIO com o polegar → botão direito;
  · punho fechado → "levanta o mouse": o cursor para, dá para reposicionar a mão.
- ESQUERDA = apoio. Pinça + subir/descer → rola a tela (como joystick: quanto mais longe do ponto da pinça, mais
  rápido); pinça + lado → rolagem horizontal.
- as DUAS mãos abertas paradas por 2 s → desliga o controle (e a voz: "desliga o controle do computador").
"troca as mãos" inverte os papéis (canhoto).

Segurança:
- só liga com o cérebro destrancado e sem visita na linha; se trancar no meio, desliga e solta o botão;
- ENSAIO (nada é clicado, só mostrado) até a calibração dos dois cantos da área confortável, ou sem a permissão de
  Acessibilidade, ou com `JAIME_MAOS_SO_ENSAIO=on`;
- mão sumiu por 0,4 s → solta qualquer botão apertado (nunca fica arrastando sozinho);
- é o mouse do João na mão dele: não passa pelo Vigia, e gesto nenhum aprova ação do Jaime.
A origem dos pontos é o navegador (aba do Jarvis) ou o rastreador nativo (`maos_nativo.py`): os dois mandam o mesmo
formato — `[{"lado": "direita"|"esquerda", "p": [[x, y], …21]}]` em coordenadas da imagem crua (sem espelho).
"""
from __future__ import annotations
import json, math, os, time
from dataclasses import dataclass, field
from pathlib import Path

from ..spatial.filtro import OneEuro

ARQ = Path(os.environ.get("JAIME_MAOS_ARQ", "~/Jaime/identidade/maos.json")).expanduser()
FECHA, ABRE = 0.32, 0.46          # pinça normalizada pelo tamanho da palma, com histerese
CLIQUE_S = 0.30                   # pinça mais longa que isto vira arrasto
MOVE_ARRASTO_PX = 28              # ou pinça que anda mais que isto
DUPLO_S, DUPLO_PX = 0.45, 30
DIREITO_S = 0.60
PERDA_S = 0.40
PARAR_S = 2.0
ZONA_MORTA = 0.035                # rolagem: folga em volta do ponto da pinça
GANHO_ROLAGEM = 2600.0            # px/s por unidade de deslocamento além da zona morta


def _d(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def palma(p) -> float:
    return _d(p[0], p[9]) or 1e-3


def razao(p, dedo: int = 8) -> float:
    return _d(p[4], p[dedo]) / palma(p)


def aberta(p) -> bool:
    return all(_d(p[i], p[0]) > _d(p[i - 2], p[0]) * 1.1 for i in (8, 12, 16, 20))


def fechada(p) -> bool:
    return all(_d(p[i], p[0]) < _d(p[i - 2], p[0]) * 1.05 for i in (8, 12, 16, 20))


def pontos_validos(p) -> list[tuple[float, float]] | None:
    try:
        pts = [(float(q[0]), float(q[1])) for q in p]
    except (TypeError, ValueError, IndexError):
        return None
    if len(pts) != 21 or not all(math.isfinite(x) and math.isfinite(y) and -0.5 < x < 1.5 and -0.5 < y < 1.5 for x, y in pts):
        return None
    return pts


@dataclass
class Mao:
    pinca: bool = False
    pinca_t: float = 0.0
    pinca_pos: tuple = (0.0, 0.0)
    pinca_bruta: tuple = (0.0, 0.0)
    arrastando: bool = False
    medio: bool = False
    medio_t: float = 0.0
    visto: float = 0.0
    rolagem: tuple | None = None
    acumulado: list = field(default_factory=lambda: [0.0, 0.0])
    ultimo_t: float = 0.0


class ControleMaos:
    def __init__(self, mouse=None, mouse_fn=None, emitir=None, falar=None, pode=None, arquivo: Path | None = None,
                 relogio=time.monotonic, env=None):
        e = os.environ if env is None else env
        self._mouse, self.mouse_fn = mouse, mouse_fn
        self.emitir = emitir or (lambda *a, **k: None)
        self.falar = falar or (lambda texto: None)
        self.pode = pode or (lambda: (True, ""))
        self.arquivo, self.relogio = Path(arquivo or ARQ), relogio
        self.ensaio_forcado = (e.get("JAIME_MAOS_SO_ENSAIO", "off") or "off").lower() in ("1", "on", "true")
        self.desativado = (e.get("JAIME_MAOS_SO", "on") or "on").lower() in ("0", "off", "false")
        dados = self._ler()
        self.calib: dict | None = dados.get("calib")
        self.trocar: bool = bool(dados.get("trocar"))
        self.ligado = False
        self.etapa = 0                 # calibração: 1 = canto de cima à esquerda, 2 = canto de baixo à direita
        self._p1 = None
        self.maos = {"direita": Mao(), "esquerda": Mao()}
        self._fx, self._fy = OneEuro(min_cutoff=1.2, beta=6.0), OneEuro(min_cutoff=1.2, beta=6.0)
        self.pos: tuple | None = None
        self._ultimo_clique = (-9.0, (0.0, 0.0))
        self._parar_desde: float | None = None
        self._parar_ref = (0.0, 0.0, 0.0)
        self._ultimo_evento = 0.0
        self.contagem = {"cliques": 0, "arrastos": 0, "direitos": 0, "rolagens": 0}
        self.nativo = False            # o rastreador nativo está alimentando: a aba do navegador só observa

    # ── estado ────────────────────────────────────────
    def _ler(self) -> dict:
        try:
            return json.loads(self.arquivo.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _gravar(self) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self.arquivo.write_text(json.dumps({"calib": self.calib, "trocar": self.trocar}), encoding="utf-8")
        try:
            os.chmod(self.arquivo, 0o600)
        except OSError:
            pass

    @property
    def mouse(self):
        if self._mouse is None and self.mouse_fn is not None:
            try:
                self._mouse = self.mouse_fn()
            except Exception:
                self._mouse = None
            self.mouse_fn = None
        return self._mouse

    @property
    def ensaio(self) -> bool:
        m = self.mouse
        return self.ensaio_forcado or not self.calib or m is None or not m.permitido()

    def papel(self, lado: str) -> str:
        mouse = "esquerda" if self.trocar else "direita"
        return "mouse" if lado == mouse else "apoio"

    def estado(self) -> dict:
        return {"ligado": self.ligado, "ensaio": self.ensaio, "etapa": self.etapa, "calibrado": bool(self.calib),
                "trocar": self.trocar, "nativo": self.nativo, "mouse": getattr(self.mouse, "nome", None) if self.ligado else None, **self.contagem}

    def _avisar(self, texto: str = "", falar: bool = False) -> None:
        self.emitir("maos_so", texto=texto, **self.estado())
        if falar and texto:
            self.falar(texto)

    # ── comandos ──────────────────────────────────────
    def ligar(self) -> str:
        if self.desativado:
            return "O controle do computador pela mão está desligado na configuração (JAIME_MAOS_SO=off)."
        ok, motivo = self.pode()
        if not ok:
            return motivo or "Agora não posso ligar o controle do computador."
        self.ligado, self.maos = True, {"direita": Mao(), "esquerda": Mao()}
        if not self.calib:
            self.etapa, self._p1 = 1, None
            texto = ("Vamos calibrar em dois toques. Com a mão direita, faça uma pinça rápida no ponto que vai ser o canto "
                     "de cima, à esquerda, da sua área confortável.")
            self._avisar(texto)
            return texto
        m = self.mouse
        if m is None:
            texto = "Não achei como mexer o mouse neste sistema; fico só mostrando na tela."
        elif not m.permitido():
            texto = ("Falta a permissão de Acessibilidade para o Python do Jaime, em Ajustes do Sistema, Privacidade e "
                     "Segurança, Acessibilidade. Até lá fico em ensaio: mostro, mas não clico.")
        elif self.ensaio_forcado:
            texto = "Controle ligado em ensaio: mostro o que faria, sem clicar."
        else:
            texto = ("Controle do computador ligado. Mão direita é o mouse: pinça clica, segurar arrasta, dedo médio "
                     "com o polegar é o botão direito, punho fechado solta o cursor. Mão esquerda rola a tela com a pinça.")
        self._avisar(texto)
        return texto

    def desligar(self, motivo: str = "") -> str:
        self.soltar_tudo()
        era = self.ligado
        self.ligado, self.etapa = False, 0
        texto = f"Controle do computador desligado{': ' + motivo if motivo else ''}." if era else "O controle do computador já estava desligado."
        self._avisar(texto)
        return texto

    def recalibrar(self) -> str:
        self.calib = None
        self._gravar()
        return self.ligar()

    def trocar_maos(self) -> str:
        self.trocar = not self.trocar
        self._gravar()
        texto = ("Trocado: a mão esquerda agora é o mouse e a direita rola." if self.trocar
                 else "Destrocado: a mão direita é o mouse e a esquerda rola.")
        self._avisar(texto)
        return texto

    def soltar_tudo(self) -> None:
        for m in self.maos.values():
            if m.arrastando:
                self._mouse_do("soltar", "esquerdo")
                m.arrastando = False
            m.pinca = m.medio = False
            m.rolagem = None

    # ── entrada ───────────────────────────────────────
    def _lados(self, maos) -> dict:
        validas = []
        for m in (maos or [])[:2]:
            if isinstance(m, dict) and (pts := pontos_validos(m.get("p") or [])):
                validas.append((str(m.get("lado", "")), pts))
        if len(validas) == 2 and validas[0][0] == validas[1][0]:
            # rastreador confuso: na imagem crua, a mão DIREITA de quem está de frente fica à ESQUERDA (x menor)
            validas.sort(key=lambda v: v[1][0][0])
            validas = [("direita", validas[0][1]), ("esquerda", validas[1][1])]
        return {lado: pts for lado, pts in validas if lado in ("direita", "esquerda")}

    def receber(self, maos, t: float | None = None) -> None:
        if not self.ligado:
            return
        t = self.relogio() if t is None else t
        ok, motivo = self.pode()
        if not ok:
            self.desligar(motivo or "cérebro trancado")
            return
        por_lado = self._lados(maos)
        for lado in por_lado:
            self.maos[lado].visto = t
        self.vigiar(t)
        if self._duas_palmas_paradas(por_lado, t):
            self.desligar("as duas mãos abertas")
            return
        mouse_lado = "esquerda" if self.trocar else "direita"
        apoio_lado = "direita" if self.trocar else "esquerda"
        if self.etapa:
            if mouse_lado in por_lado:
                self._calibrar(por_lado[mouse_lado], t)
            return
        if mouse_lado in por_lado:
            self._mao_mouse(self.maos[mouse_lado], por_lado[mouse_lado], t)
        if apoio_lado in por_lado:
            self._mao_apoio(self.maos[apoio_lado], por_lado[apoio_lado], t)
        if t - self._ultimo_evento > 0.08 and self.pos is not None:     # ~12 Hz para a tela mostrar o cursor
            self._ultimo_evento = t
            x, y, w, h = self._area()
            self.emitir("maos_so", _efemero=True, cursor=[round((self.pos[0] - x) / w, 4), round((self.pos[1] - y) / h, 4)],
                        arrastando=any(m.arrastando for m in self.maos.values()), ensaio=self.ensaio)

    def vigiar(self, t: float | None = None) -> None:
        """Mão sumiu → solta o que estava apertado. Chamado a cada mensagem e quando o canal fica quieto."""
        t = self.relogio() if t is None else t
        for m in self.maos.values():
            if (m.pinca or m.arrastando or m.medio or m.rolagem) and t - m.visto > PERDA_S:
                if m.arrastando:
                    self._mouse_do("soltar", "esquerdo")
                m.pinca = m.arrastando = m.medio = False
                m.rolagem = None

    # ── calibração ────────────────────────────────────
    def _ponto(self, p) -> tuple[float, float]:
        return (1.0 - p[5][0], p[5][1])            # base do indicador, espelhada (como um espelho, a mão direita vai à direita)

    def _calibrar(self, p, t) -> None:
        m = self.maos["direita" if not self.trocar else "esquerda"]
        if fechada(p):
            m.pinca = False
            return
        r = razao(p)
        if not m.pinca and r < FECHA:
            m.pinca, m.pinca_t, m.pinca_bruta = True, t, self._ponto(p)
            return
        if m.pinca and r > ABRE:
            m.pinca = False
            if t - m.pinca_t > 1.2:
                return
            u, v = m.pinca_bruta
            if self.etapa == 1:
                self._p1, self.etapa = (u, v), 2
                self._avisar("Agora a pinça no canto de baixo, à direita.", falar=True)
                return
            u0, v0 = self._p1
            if u - u0 < 0.12 or v - v0 < 0.08:
                self.etapa, self._p1 = 1, None
                self._avisar("Os dois pontos ficaram perto demais. De novo: canto de cima, à esquerda.", falar=True)
                return
            self.calib = {"u0": round(u0, 4), "v0": round(v0, 4), "u1": round(u, 4), "v1": round(v, 4)}
            self.etapa = 0
            self._gravar()
            if self.ensaio:
                texto = ("Calibrado. Ainda em ensaio: " + ("falta a permissão de Acessibilidade para o Python do Jaime."
                                                           if self.mouse is not None and not self.mouse.permitido() else "mostro, mas não clico."))
            else:
                texto = "Calibrado. A mão direita agora é o mouse do computador."
            self._avisar(texto, falar=True)

    # ── mapeamento ────────────────────────────────────
    def _area(self):
        m = self.mouse
        try:
            x, y, w, h = m.area() if m is not None else (0, 0, 1920, 1080)
        except Exception:
            x, y, w, h = (0, 0, 1920, 1080)
        return x, y, max(1, w), max(1, h)

    def _tela(self, u, v) -> tuple[float, float]:
        c = self.calib or {"u0": 0.2, "v0": 0.2, "u1": 0.8, "v1": 0.75}
        x, y, w, h = self._area()
        fx = min(1.0, max(0.0, (u - c["u0"]) / max(0.05, c["u1"] - c["u0"])))
        fy = min(1.0, max(0.0, (v - c["v0"]) / max(0.05, c["v1"] - c["v0"])))
        return (x + fx * (w - 1), y + fy * (h - 1))

    def _mouse_do(self, acao: str, *args) -> None:
        if self.ensaio or self.mouse is None:
            return
        try:
            getattr(self.mouse, acao)(*args)
        except Exception as e:
            self._avisar(f"o mouse do sistema falhou: {type(e).__name__}")

    # ── mão do mouse ──────────────────────────────────
    def _mao_mouse(self, m: Mao, p, t) -> None:
        u, v = self._ponto(p)
        u, v = self._fx(u, t), self._fy(v, t)
        alvo = self._tela(u, v)
        if fechada(p):                                        # punho: "levantou o mouse" — cursor parado, nada apertado
            if m.arrastando:
                self._mouse_do("soltar", "esquerdo")
                self.contagem["arrastos"] += 1
            m.pinca = m.medio = m.arrastando = False
            return
        rz, rm = razao(p, 8), razao(p, 12)
        # botão direito: dedo médio com o polegar (e o indicador longe)
        if not m.pinca and not m.medio and rm < FECHA and rz > ABRE:
            m.medio, m.medio_t = True, t
        elif m.medio and rm > ABRE:
            m.medio = False
            if t - m.medio_t < DIREITO_S and self.pos is not None:
                self._mouse_do("apertar", "direito"); self._mouse_do("soltar", "direito")
                self.contagem["direitos"] += 1
                self.emitir("maos_so", acao="direito", ensaio=self.ensaio)
        # pinça principal
        if not m.pinca and not m.medio and rz < FECHA:
            m.pinca, m.pinca_t, m.pinca_pos = True, t, (self.pos or alvo)
            m.pinca_bruta = alvo
        elif m.pinca and rz > ABRE:
            m.pinca = False
            if m.arrastando:
                self._mouse_do("soltar", "esquerdo")
                m.arrastando = False
                self.contagem["arrastos"] += 1
                self.emitir("maos_so", acao="solta", ensaio=self.ensaio)
            else:
                t0, p0 = self._ultimo_clique
                cliques = 2 if t - t0 < DUPLO_S and _d(p0, m.pinca_pos) < DUPLO_PX else 1
                self._mouse_do("mover", *m.pinca_pos)
                self._mouse_do("apertar", "esquerdo", cliques); self._mouse_do("soltar", "esquerdo", cliques)
                self._ultimo_clique = (t, m.pinca_pos)
                self.contagem["cliques"] += 1
                self.emitir("maos_so", acao="duplo" if cliques == 2 else "clique", ensaio=self.ensaio)
        if m.pinca and not m.arrastando:
            if t - m.pinca_t > CLIQUE_S or _d(alvo, m.pinca_bruta) > MOVE_ARRASTO_PX:
                self._mouse_do("mover", *m.pinca_pos)
                self._mouse_do("apertar", "esquerdo")
                m.arrastando = True
                self.emitir("maos_so", acao="arrasta", ensaio=self.ensaio)
            else:
                return                                        # pinça curta: o cursor fica parado para o clique cair certo
        self.pos = alvo
        self._mouse_do("mover", alvo[0], alvo[1], m.arrastando)

    # ── mão de apoio ──────────────────────────────────
    def _mao_apoio(self, m: Mao, p, t) -> None:
        u, v = self._ponto(p)
        r = razao(p)
        dt = min(0.1, max(0.0, t - (m.ultimo_t or t)))
        m.ultimo_t = t
        if fechada(p):
            m.pinca, m.rolagem = False, None
            return
        if not m.pinca and r < FECHA:
            m.pinca, m.rolagem, m.acumulado = True, (u, v), [0.0, 0.0]
            return
        if m.pinca and r > ABRE:
            m.pinca, m.rolagem = False, None
            return
        if not m.pinca or m.rolagem is None:
            return
        def vel(delta):
            a = abs(delta) - ZONA_MORTA
            return 0.0 if a <= 0 else math.copysign(a * GANHO_ROLAGEM, delta)
        m.acumulado[0] += vel(m.rolagem[1] - v) * dt           # mão sobe → rola para cima
        m.acumulado[1] += vel(u - m.rolagem[0]) * dt
        dy, dx = int(m.acumulado[0]), int(m.acumulado[1])
        if dy or dx:
            m.acumulado[0] -= dy; m.acumulado[1] -= dx
            self._mouse_do("rolar", dy, dx)
            self.contagem["rolagens"] += 1

    # ── parar com as duas mãos ────────────────────────
    def _duas_palmas_paradas(self, por_lado: dict, t: float) -> bool:
        if len(por_lado) == 2 and all(aberta(p) and razao(p) > ABRE for p in por_lado.values()):
            centro = tuple(round(p[9][0], 2) for p in por_lado.values())
            if self._parar_desde is None or _d(self._parar_ref, centro + (0,)) > 0.05:
                self._parar_desde, self._parar_ref = t, centro + (0,)
                return False
            return t - self._parar_desde >= PARAR_S
        self._parar_desde = None
        return False
