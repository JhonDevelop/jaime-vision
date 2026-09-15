"""Observador: o Jaime de olho no que o João está fazendo na máquina.

A cada poucos segundos anota o app em primeiro plano e o título da janela (macOS). Com isso:
1. o HUD mostra "você em: Safari · GitHub";
2. cada fala do João chega ao modelo com o contexto atual ("isso aqui" passa a fazer sentido);
3. se o padrão dos últimos minutos parece alguém travado — pulando entre janelas sem parar em
   nenhuma, ou preso numa busca — o Jaime se oferece, por voz, para entender a situação.
   Se o João aceitar, tira uma captura da tela e o modelo olha a imagem antes de propor algo.

Permissões do macOS: nome do app sai sem pedir nada (`lsappinfo`); título da janela precisa de
Acessibilidade para o Terminal (Ajustes → Privacidade → Acessibilidade). Sem ela, fica só o app."""
from __future__ import annotations
import asyncio, re, subprocess, time
from collections import deque
from ..hud.events import bus

INTERVALO_S = 4
JANELA_S = 180              # quanto de histórico a heurística olha
TROCAS_TRAVADO = 12         # trocas de janela/app nesse período sem descansar em nenhuma…
DESCANSO_S = 25             # …"descansar" = ficar mais que isto na mesma janela
BUSCA_TRAVADO_S = 75        # ou tanto tempo seguido numa janela de busca
COOLDOWN_S = 1800           # entre duas ofertas de ajuda (10 min era chato)
BUSCA_RX = re.compile(r"(spotlight|pesquis|search|busca|procur|finder|google|find)", re.I)
ACEITES = {"sim", "pode", "quero", "ajuda", "me ajuda", "pode ajudar", "vai", "por favor", "isso", "claro", "bora"}
RECUSAS = {"não", "nao", "deixa", "depois", "agora não", "agora nao", "tô bem", "to bem", "de boa"}

def app_frontal() -> tuple[str, str]:
    """(app, título da janela). Título vazio quando não há permissão de Acessibilidade."""
    app = ""
    try:
        asn = subprocess.run(["lsappinfo", "front"], capture_output=True, text=True, timeout=3).stdout.strip()
        info = subprocess.run(["lsappinfo", "info", "-only", "name", asn], capture_output=True, text=True, timeout=3).stdout
        m = re.search(r'"LSDisplayName"="([^"]+)"', info) or re.search(r'=\s*"([^"]+)"', info)
        app = m.group(1) if m else ""
    except Exception:
        pass
    janela = ""
    try:
        r = subprocess.run(["osascript", "-e",
            'tell application "System Events" to tell (first application process whose frontmost is true) '
            'to get name of front window'], capture_output=True, text=True, timeout=4)
        if r.returncode == 0:
            janela = r.stdout.strip()
    except Exception:
        pass
    return app, janela

def parece_travado(historico, agora: float) -> str | None:
    """historico: sequência de (t, app, janela). Devolve o motivo, ou None."""
    recente = [h for h in historico if agora - h[0] <= JANELA_S]
    if len(recente) < 6:
        return None
    trocas, maior_permanencia, inicio = 0, 0.0, recente[0][0]
    for a, b in zip(recente, recente[1:]):
        if (a[1], a[2]) != (b[1], b[2]):
            trocas += 1
            maior_permanencia = max(maior_permanencia, b[0] - inicio); inicio = b[0]
    maior_permanencia = max(maior_permanencia, agora - inicio)
    if trocas >= TROCAS_TRAVADO and maior_permanencia < DESCANSO_S:
        apps = []
        for _, app, _ in recente:
            if app and app not in apps:
                apps.append(app)
        return "pulando entre " + ", ".join(apps[:3]) + " sem parar em nenhum"
    ultimo = recente[-1]
    # só o TÍTULO da janela conta como busca — "Google Chrome" no nome do app disparava toda hora
    if ultimo[2] and BUSCA_RX.search(ultimo[2]):
        desde = ultimo[0]
        for h in reversed(recente):
            if (h[1], h[2]) == (ultimo[1], ultimo[2]):
                desde = h[0]
            else:
                break
        if agora - desde >= BUSCA_TRAVADO_S:
            return f"há {int((agora - desde) // 60)} min procurando em {ultimo[1]}"
    return None

def eh_aceite(texto: str) -> bool:
    t = texto.strip().lower().rstrip(".!?")
    return t in ACEITES or any(t.startswith(a + " ") for a in ("sim", "pode", "quero"))

def eh_recusa(texto: str) -> bool:
    return texto.strip().lower().rstrip(".!?") in RECUSAS

def capturar_tela(caminho: str = "/tmp/jaime-tela.png") -> str | None:
    try:
        subprocess.run(["screencapture", "-x", "-t", "png", caminho], check=True, timeout=8,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return caminho
    except Exception:
        return None

class Observador:
    def __init__(self, jaime, ouvido=None):
        self.jaime, self.ouvido = jaime, ouvido
        self.historico: deque = deque(maxlen=400)
        self.atual = ("", "")
        self.oferta_em = 0.0          # quando a última oferta foi feita
        self.oferta_pendente = ""     # motivo, enquanto espera o "sim"
        self.ligado = True

    def contexto(self) -> str:
        app, jan = self.atual
        return f"app={app}" + (f", janela={jan[:80]}" if jan else "") if app else ""

    def resumo_recente(self, s: int = JANELA_S) -> str:
        agora = time.time(); vistos = []
        for _, app, jan in self.historico:
            if agora - _ <= s:
                item = f"{app}" + (f" ({jan[:50]})" if jan else "")
                if item not in vistos:
                    vistos.append(item)
        return " → ".join(vistos[-8:])

    async def rodar(self):
        while True:
            try:
                if self.ligado:
                    app, jan = await asyncio.to_thread(app_frontal)
                    agora = time.time()
                    if app:
                        self.historico.append((agora, app, jan))
                        if (app, jan) != self.atual:
                            self.atual = (app, jan)
                            bus.emitir("contexto", app=app, janela=jan)
                    await self._talvez_oferecer(agora)
            except Exception as e:
                bus.emitir("contexto", erro=f"{type(e).__name__}: {e}"[:120])
            await asyncio.sleep(INTERVALO_S)

    async def _talvez_oferecer(self, agora: float):
        if not self.jaime.acesso.liberado or agora - self.oferta_em < COOLDOWN_S:
            return
        if self.ouvido and (self.ouvido.ocupado or self.ouvido.mudo):
            return
        motivo = parece_travado(self.historico, agora)
        if not motivo:
            return
        self.oferta_em = agora; self.oferta_pendente = motivo
        frase = f"João, percebi que você está {motivo}. Quer que eu dê uma olhada e ajude?"
        bus.emitir("fala", texto=frase); bus.emitir("fala_fim")
        self.jaime.vault.diario(f"Ofereci ajuda: {motivo}", "Log")
        if self.ouvido:
            self.ouvido.ativo_ate = agora + 60      # o "sim" vale sem precisar dizer "Jaime"
            await asyncio.to_thread(self.ouvido.falar, frase)

    def responder_oferta(self, texto: str) -> str | None:
        """Chamado pelo ouvido com cada fala enquanto há oferta pendente. Devolve o prompt para o
        modelo se o João aceitou; "" se recusou; None se a fala não era sobre a oferta."""
        if not self.oferta_pendente or time.time() - self.oferta_em > 90:
            self.oferta_pendente = ""; return None
        if eh_recusa(texto):
            self.oferta_pendente = ""; return ""
        if not eh_aceite(texto):
            return None
        motivo, self.oferta_pendente = self.oferta_pendente, ""
        tela = capturar_tela()
        return (f"[O João aceitou sua oferta de ajuda. Você percebeu: {motivo}. Últimos minutos: {self.resumo_recente()}. "
                + (f"Captura da tela agora em {tela} — use a ferramenta Read nesse arquivo para VER a tela. " if tela else "")
                + "Em até 3 frases faladas: diga o que entendeu que ele está tentando fazer e proponha UM próximo passo concreto; "
                  "se puder resolver você mesmo, pergunte se quer que faça.]")
