"""Impulsos — seis vontades com nível 0–1 (fase 3, §6). Prioridades com nome, não sentimentos.

| Impulso     | Sobe quando                                              | Desce quando                     |
|-------------|----------------------------------------------------------|----------------------------------|
| Utilidade   | demanda pendente (conversa/fila), João em aperto         | demanda fechada sem correção     |
| Curiosidade | problema em aberto, pergunta sem resposta, erro repetido | problema resolvido               |
| Maestria    | placar caindo em algum tipo (erro/correção)              | placar subindo (acerto)          |
| Criação     | dias sem criar                                           | algo entregue na Vitrine; "não gostei" |
| Ordem       | vault com órfãs/links quebrados, Inbox grande            | saúde do cérebro verde           |
| Vínculo     | pergunta sobre o João sem resposta; datas próximas       | perfil completo, data lembrada   |

Nada aqui edita o orquestrador: `escutar()` assina o bus (jaime/hud/events.py) e traduz os eventos em movimentos;
`observar_placar()` faz o Placar emitir um evento por registro. Persistência em `01-Estado/Vontades.md`
(tabela legível + últimos movimentos), decaimento para o repouso com o tempo, limites 0–1.
Ele diz "quero", não "sofro"."""
from __future__ import annotations
import asyncio, re, time
from datetime import datetime, date
from ..hud.events import bus

ARQUIVO = "01-Estado/Vontades.md"
NOMES = ("utilidade", "curiosidade", "maestria", "criacao", "ordem", "vinculo")
ROTULO = {"utilidade": "Utilidade", "curiosidade": "Curiosidade", "maestria": "Maestria",
          "criacao": "Criação", "ordem": "Ordem", "vinculo": "Vínculo"}
# nível de repouso para onde cada impulso decai quando nada o alimenta, e a velocidade (fração da distância por hora)
REPOUSO = {"utilidade": 0.30, "curiosidade": 0.25, "maestria": 0.20, "criacao": 0.20, "ordem": 0.15, "vinculo": 0.20}
DECAIMENTO_H = {"utilidade": 0.50, "curiosidade": 0.04, "maestria": 0.04, "criacao": 0.0, "ordem": 0.03, "vinculo": 0.03}
CRIACAO_POR_DIA = 0.12          # Criação sobe com os dias sem criar (não decai sozinha)
FILA_ABERTA = ("nova", "em_andamento", "interrompida")   # estados da fila (voice/fila.py) que ainda são demanda
INBOX_GRANDE = 12               # tarefas abertas (mesmo limiar da "semana pesada" em emocao/momento.py)
MOVIMENTOS_MAX = 20
SONDA_S = 10 * 60               # perfil, Inbox e Criação por tempo: a cada 10 min

def _clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))

class Impulsos:
    def __init__(self, vault, relogio=time.time, perguntas=None, perfil=None, sonda_s: int = SONDA_S):
        self.vault, self.relogio, self.perguntas, self.perfil, self.sonda_s = vault, relogio, perguntas, perfil, sonda_s
        self.niveis: dict[str, float] = dict(REPOUSO)
        self.movimentos: list[str] = []
        self.motivos: dict[str, str] = {}           # último motivo que mexeu em cada impulso
        self.atualizado: float = self.relogio()
        self.ultima_criacao: float = self.relogio()
        self.demanda_pendente = False               # conversa aberta ou fila com itens
        self._fila_pendentes = 0
        self._erro_no_turno = False
        self._erros_por_tipo: dict[str, int] = {}
        # contagens já cobradas (Vigília 15/09: a MESMA pergunta sem resposta subia Vínculo/Curiosidade a cada sonda de
        # 10 min até 1,00 e o ranking perdia sentido). Uma situação só empurra o impulso quando cresce.
        self._visto: dict[str, int] = {}
        self._carregar()

    def _novo(self, chave: str, n: int) -> int:
        """Quanto a contagem `chave` cresceu desde a última vez (0 se igual ou menor). Guarda o valor atual."""
        antes = self._visto.get(chave, 0)
        self._visto[chave] = n
        return max(0, n - antes)

    # ── leitura ───────────────────────────────────────
    def nivel(self, nome: str) -> float:
        return self.niveis[nome]

    def ranking(self) -> list[tuple[str, float]]:
        return sorted(self.niveis.items(), key=lambda kv: -kv[1])

    def motivo(self, nome: str) -> str:
        return self.motivos.get(nome, "")

    def dados(self) -> dict:
        return {"niveis": {k: round(v, 2) for k, v in self.niveis.items()}, "demanda_pendente": self.demanda_pendente,
                "dias_sem_criar": round((self.relogio() - self.ultima_criacao) / 86400, 1),
                "motivos": dict(self.motivos), "movimentos": self.movimentos[-8:]}

    def texto(self) -> str:
        return " · ".join(f"{ROTULO[k]} {v:.0%}" for k, v in self.ranking())

    # ── escrita ───────────────────────────────────────
    def mover(self, nome: str, delta: float, motivo: str = "") -> float:
        """Sobe (delta > 0) ou desce (delta < 0) um impulso, com limites 0–1. Registra o motivo e persiste."""
        antes = self.niveis[nome]
        self.niveis[nome] = _clamp(antes + delta)
        if abs(self.niveis[nome] - antes) > 1e-9:
            seta = "↑" if delta > 0 else "↓"
            self.movimentos.append(f"{datetime.fromtimestamp(self.relogio()):%d/%m %H:%M} {ROTULO[nome]} {seta} {abs(delta):.2f} → {self.niveis[nome]:.2f}" + (f" — {motivo}" if motivo else ""))
            self.movimentos = self.movimentos[-MOVIMENTOS_MAX:]
            if motivo:
                self.motivos[nome] = motivo
            self._salvar()
        return self.niveis[nome]

    def subir(self, nome: str, delta: float, motivo: str = "") -> float:
        return self.mover(nome, abs(delta), motivo)

    def descer(self, nome: str, delta: float, motivo: str = "") -> float:
        return self.mover(nome, -abs(delta), motivo)

    def tique(self) -> None:
        """Decaimento com o tempo: cada impulso caminha para o seu repouso; Criação sobe com os dias sem criar."""
        agora = self.relogio()
        horas = max(0.0, (agora - self.atualizado) / 3600)
        if horas <= 0:
            return
        mudou = False
        for nome in NOMES:
            if nome == "criacao":
                novo = _clamp(self.niveis[nome] + CRIACAO_POR_DIA * horas / 24)
            else:
                fator = min(1.0, DECAIMENTO_H[nome] * horas)
                novo = _clamp(self.niveis[nome] + (REPOUSO[nome] - self.niveis[nome]) * fator)
            if abs(novo - self.niveis[nome]) > 1e-9:
                self.niveis[nome] = novo; mudou = True
        self.atualizado = agora
        if mudou:
            self._salvar()

    # ── eventos → movimentos ──────────────────────────
    def evento(self, tipo: str, **d) -> list[str]:
        """Traduz um evento do bus num ou mais movimentos. Devolve os nomes dos impulsos que mexeram."""
        mexeu: list[str] = []
        def sobe(n, delta, m): self.subir(n, delta, m); mexeu.append(n)
        def desce(n, delta, m): self.descer(n, delta, m); mexeu.append(n)

        if tipo == "conversa":
            if d.get("canal") not in ("rotina", "sistema"):
                self.demanda_pendente = True; self._erro_no_turno = False
                sobe("utilidade", 0.15, f"demanda pendente ({d.get('canal', 'conversa')})")
        elif tipo == "resultado":
            if d.get("erro"):
                self._erro_no_turno = True
        elif tipo == "fala_fim":
            if self.demanda_pendente and not self._fila_pendentes:
                self.demanda_pendente = False
                if not self._erro_no_turno:
                    desce("utilidade", 0.10, "demanda fechada sem correção")
        elif tipo == "fila":                         # jaime/voice/fila.py (B): itens=[{estado…}], atual, aguardando
            if "itens" in d:
                self._fila_pendentes = sum(1 for i in (d.get("itens") or []) if isinstance(i, dict) and i.get("estado") in FILA_ABERTA)
            elif "pendentes" in d:
                self._fila_pendentes = int(d["pendentes"] or 0)
            elif d.get("estado") == "pendente":
                self._fila_pendentes += 1
            elif d.get("estado") in ("fechada", "concluida", "concluída"):
                self._fila_pendentes = max(0, self._fila_pendentes - 1)
            if self._fila_pendentes > 0:
                self.demanda_pendente = True
                sobe("utilidade", 0.15, f"{self._fila_pendentes} demanda(s) na fila")
            elif "itens" in d or d.get("estado") in ("fechada", "concluida", "concluída") or d.get("pendentes") == 0:
                self.demanda_pendente = False
                desce("utilidade", 0.10, "fila vazia")
        elif tipo == "humor":
            if d.get("joao_em_problema"):
                sobe("utilidade", 0.20, "o João está em aperto")
        elif tipo == "placar":
            tarefa = d.get("tarefa") or ""
            if d.get("resultado") == "erro" or str(d.get("msg", "")).startswith("correção"):
                if not tarefa and (m := re.search(r"em '([^']+)'", str(d.get("msg", "")))):
                    tarefa = m.group(1)
                n = self._erros_por_tipo[tarefa] = self._erros_por_tipo.get(tarefa, 0) + 1
                sobe("maestria", 0.10, f"placar caindo em '{tarefa or '?'}'")
                if n >= 2:
                    sobe("curiosidade", 0.05, f"erro repetido em '{tarefa or '?'}' ({n}×)")
            elif d.get("resultado") == "acerto":
                self._erros_por_tipo[tarefa] = 0
                # acerto relaxa a Maestria até o repouso, nunca até zero (ficava preso em 0,00 e nunca subia)
                sobra = self.niveis["maestria"] - REPOUSO["maestria"]
                if sobra > 1e-9:
                    desce("maestria", min(0.05, sobra), f"acerto em '{tarefa or '?'}'")
        elif tipo == "estudo":
            msg = str(d.get("msg", ""))
            if msg.startswith("aberto"):
                sobe("curiosidade", 0.15, msg[:80])
            elif msg.startswith("resolvido"):
                desce("curiosidade", 0.20, msg[:80])
                sobe("maestria", 0.05, "aprendi: " + msg[10:70])       # estudo concluído é maestria ganha
            elif "abertos" in d and int(d["abertos"] or 0) == 0 and not msg:
                desce("curiosidade", 0.05, "nenhum problema em aberto")
        elif tipo == "saude":
            probs = [str(p) for p in (d.get("problemas") or [])]
            desordem = [p for p in probs if "órfã" in p or "link quebrado" in p]
            if desordem:
                if self._novo("desordem", len(desordem)):
                    sobe("ordem", min(0.4, 0.05 * len(desordem)), f"{len(desordem)} órfã(s)/link(s) quebrado(s) no vault")
            else:
                self._visto["desordem"] = 0
                if not probs:
                    desce("ordem", 0.20, "saúde do cérebro verde")
        elif tipo == "inbox":
            n = int(d.get("abertas") or 0)
            if n >= INBOX_GRANDE and self._novo("inbox", n):
                sobe("ordem", 0.10, f"Inbox com {n} tarefas")
            elif n < INBOX_GRANDE:
                self._visto["inbox"] = 0
        elif tipo == "perfil":
            sem = int(d.get("perguntas_sem_resposta") or 0); prox = int(d.get("datas_proximas") or 0)
            novas = self._novo("perguntas", sem)
            if novas:
                sobe("vinculo", min(0.3, 0.05 * novas), f"{sem} pergunta(s) sobre o João sem resposta")
                sobe("curiosidade", 0.03, "pergunta sem resposta")
            if self._novo("datas", prox):
                sobe("vinculo", min(0.2, 0.05 * prox), f"{prox} data(s) próxima(s)")
            if d.get("respondida"):
                desce("vinculo", 0.10, f"o João respondeu: {str(d['respondida'])[:50]}")
            if d.get("data_lembrada"):
                desce("vinculo", 0.15, f"data lembrada: {str(d['data_lembrada'])[:50]}")
            if not sem and not prox and d.get("completo"):
                desce("vinculo", 0.10, "perfil completo")
        elif tipo == "vitrine":
            acao = d.get("acao")
            if acao == "entregue":
                self.ultima_criacao = self.relogio()
                desce("criacao", 0.30, f"entreguei {d.get('titulo') or d.get('id') or 'uma criação'}")
            elif acao == "voto":
                if d.get("gostou"):
                    sobe("criacao", 0.10, f"o João gostou de {d.get('titulo') or d.get('id')}")
                    sobe("maestria", 0.10, f"o João gostou de {d.get('titulo') or d.get('id')}")
                else:
                    desce("criacao", 0.15, f"o João não gostou de {d.get('titulo') or d.get('id')}")
        if mexeu:
            self.emitir()
        return mexeu

    def emitir(self) -> None:
        bus.emitir("vontade", **self.dados())

    # ── tasks ─────────────────────────────────────────
    async def escutar(self) -> None:
        """Assina o bus e converte eventos em movimentos; de tempos em tempos, tique + sonda do vault."""
        q = bus.assinar()
        ultimo_tique = self.relogio()
        try:
            while True:
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=60)
                except asyncio.TimeoutError:
                    evt = None
                try:
                    if evt and evt.get("tipo") != "vontade":
                        self.evento(evt["tipo"], **{k: v for k, v in evt.items() if k not in ("tipo", "t")})
                    if self.relogio() - ultimo_tique >= self.sonda_s:
                        ultimo_tique = self.relogio()
                        self.tique(); self.sondar()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    bus.emitir("vontade", erro=f"{type(e).__name__}: {e}"[:160])
        finally:
            bus.cancelar(q)

    def sondar(self) -> None:
        """Olha o vault por conta própria: Inbox (Ordem) e perfil (Vínculo). Emite como eventos, para passar pelas mesmas regras."""
        try:
            self.evento("inbox", abertas=len(self.vault.tarefas_abertas()))
        except Exception:
            pass
        sem, prox = 0, 0
        try:
            if self.perguntas:
                sem = sum(1 for r in self.perguntas.todas() if r.resposta in ("", "—", "?"))
            if self.perfil:
                hoje = date.fromtimestamp(self.relogio())
                prox = sum(1 for dt in self.perfil.datas() if (dt.dias_ate(hoje) or 99) <= 7 and (dt.dias_ate(hoje) or -1) >= 0)
        except Exception:
            pass
        if sem or prox:
            self.evento("perfil", perguntas_sem_resposta=sem, datas_proximas=prox)

    # ── persistência ──────────────────────────────────
    def _carregar(self) -> None:
        txt = self.vault.read(ARQUIVO) if self.vault else ""
        if not txt:
            return
        rot = {v.lower(): k for k, v in ROTULO.items()}
        for m in re.finditer(r"^\|\s*([^|]+?)\s*\|\s*([\d.,]+)\s*\|", txt, re.M):
            nome = rot.get(m.group(1).strip().lower())
            if nome:
                try:
                    self.niveis[nome] = _clamp(float(m.group(2).replace(",", ".")))
                except ValueError:
                    pass
        for chave, attr in (("atualizado", "atualizado"), ("ultima_criacao", "ultima_criacao")):
            if (m := re.search(rf"^- {chave}:\s*(\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}})", txt, re.M)):
                try:
                    setattr(self, attr, datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").timestamp())
                except ValueError:
                    pass
        for m in re.finditer(r"^- (?:motivo )?(\w+): (.+)$", txt.split("## Motivos", 1)[1].split("\n## ", 1)[0] if "## Motivos" in txt else "", re.M):
            if m.group(1) in NOMES:
                self.motivos[m.group(1)] = m.group(2).strip()
        if "## Últimos movimentos" in txt:
            bloco = txt.split("## Últimos movimentos", 1)[1].split("\n## ", 1)[0]
            self.movimentos = [l[2:].strip() for l in bloco.splitlines() if l.startswith("- ") and l[2:].strip() != "nenhum"][-MOVIMENTOS_MAX:]

    def _salvar(self) -> None:
        if not self.vault:
            return
        agora = datetime.fromtimestamp(self.relogio())
        barra = lambda v: "█" * round(v * 10) + "░" * (10 - round(v * 10))
        linhas = ["# Vontades", "",
                  "> Mantido por `jaime/vontade/impulsos.py`. Prioridades com nome, não sentimentos: eu digo \"quero\", não \"sofro\".", "",
                  f"- atualizado: {agora:%Y-%m-%d %H:%M}",
                  f"- ultima_criacao: {datetime.fromtimestamp(self.ultima_criacao):%Y-%m-%d %H:%M}",
                  f"- demanda_pendente: {'sim' if self.demanda_pendente else 'não'}", "",
                  "## Impulsos", "", "| impulso | nível | barra |", "|---|---|---|"]
        linhas += [f"| {ROTULO[k]} | {v:.2f} | {barra(v)} |" for k, v in self.ranking()]
        linhas += ["", "## Motivos", ""] + [f"- {k}: {v}" for k, v in self.motivos.items()] + ([] if self.motivos else ["- nenhum"])
        linhas += ["", "## Últimos movimentos", ""] + [f"- {m}" for m in self.movimentos[-MOVIMENTOS_MAX:]] + ([] if self.movimentos else ["- nenhum"])
        self.vault.write(ARQUIVO, "\n".join(linhas) + "\n")

def observar_placar(placar) -> None:
    """Faz o Placar emitir `placar` (modelo, tarefa, resultado) a cada registro — sem editar o orquestrador."""
    if placar is None or getattr(placar, "_vontade_observado", False):
        return
    original = placar.registrar
    def registrar(modelo, tipo, resultado, *a, **kw):
        r = original(modelo, tipo, resultado, *a, **kw)
        bus.emitir("placar", modelo=modelo, tarefa=tipo, resultado=resultado)
        return r
    placar.registrar = registrar
    placar._vontade_observado = True
