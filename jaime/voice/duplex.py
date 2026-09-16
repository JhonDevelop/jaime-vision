"""Ouvido full-duplex — escuta enquanto pensa, pensa enquanto o João fala, cala quando ele abre a boca.
(docs/FASE-3-TEMPO-REAL.md §2; ligado com JAIME_VOZ_MODO=duplex, o padrão.)

microfone ─► Silero VAD ─► frames vão AO VIVO para o STT em streaming (stt_stream.py) ─► transcrição viva no HUD
                │                                              │ a cada ~500 ms de texto novo
                │                                              ▼
                │                                       Antecipador ─► frase_fechou? (fim de turno semântico)
                │                                                   ─► rascunho ≥ 0.8 → tts.pre_sintetizar (cache)
                ▼
         DetectorFim: 450 ms de silêncio se a frase fechou · 700 ms sem parecer · 1200 ms se "ainda vai continuar"
                │ fim
                ▼
         texto final ─► antecipação ainda bate? ─► toca o cache (~0 ms) ─► Jaime completa em streaming ─► TTS
                                                                                     ▲
         BARGE-IN: voz do João (VAD alto + acima do eco medido) durante a fala dele ──┘ tts.parar() em < 100 ms

Sem cancelamento de eco, o microfone ouve a própria voz do Jaime: o barge-in só dispara quando a voz do João
passa bem acima do nível de eco medido no começo de cada fala dele (JAIME_BARGE_IN=on|off|fone; "fone" = sem
guarda de eco, para quem usa fone de ouvido)."""
from __future__ import annotations
import asyncio, os, re, threading, time
from collections import Counter, deque
from ..hud.events import bus
from .escuta import (Ouvido, SR, FRAME, FRAME_MS, PRE_ROLL_MS, VAD_INICIO, VAD_FIM, MIN_FALA_MS, MAX_FALA_S, LIXO_WHISPER)
from .antecipador import Antecipador, Antecipacao, modelo_openai
from . import stt_stream
from .eco import SupressorDeEco

SILENCIO_FECHOU_MS = 450      # antecipador diz que a frase fechou
SILENCIO_INCERTO_MS = 700     # ainda sem parecer (ou sem antecipador)
SILENCIO_ABERTO_MS = 1500     # antecipador diz que o João ainda vai continuar ("…e também")
BARGE_IN_PROB = 0.82          # VAD enquanto o Jaime fala
BARGE_IN_MS = 320             # voz qualificada contínua para cortar por energia (2 cortes por eco em 16/09 tinham 160 e 224 ms;
                              # as falas reais do João por cima tinham 416–3296 ms)
# Calibrado com as linhas "Barge-in não cortou" do diário (16/09 08:13–08:16, alto-falante, sem fone): a voz do João
# ficou entre 1,2× e 2,5× o eco (1,8× segurava quase tudo) e os vetos por similaridade a 0,82–0,88 eram o João.
BARGE_IN_ECO_X = 1.4          # RMS do João precisa ser 1,4× o eco medido (sem AEC); 1,25 cortou por eco 2× em 16/09 08:46
BARGE_IN_ECO_SIM = 0.92       # o supressor só VETA quando tem quase certeza de que é o próprio eco
BARGE_IN_SUSTENTADO_MS = 700  # rms ≥ BARGE_IN_SUST_X × eco por este tempo corta mesmo sem passar do limiar: eco não fica 2–3 s acima da própria média
BARGE_IN_SUST_X = 1.15        # (sem VAD) o eco oscila em torno de 1,0× a própria média; 1,15× por 700 ms é outra pessoa
# As contagens são por JANELA deslizante, não por frames consecutivos: prob e rms oscilam a cada 32 ms e um contador que
# soma/subtrai (ou zera) nunca chegava ao mínimo — 16/09 09:15–09:21: 8 falas com 352–1376 ms acima do eco e nenhum corte.
BARGE_IN_JANELA_MS = 640      # janela do corte por energia (precisa de BARGE_IN_MS qualificados dentro dela)
# Piso de voz: energia sozinha corta com toque de telefone (16/09 10:09: 64 ms de VAD, rms 9× o eco, sim 0,39). Metade
# dos frames da janela precisa ter alguma probabilidade de voz — o VAD esparso do João passa, campainha/telefone não.
BARGE_IN_VAD_PISO = 0.35
BARGE_IN_VAD_FRACAO = 0.5
BARGE_IN_JANELA_SUST_MS = 1000  # janela do corte por voz sustentada
# VOZ DE VERDADE, não barulho (16/09, pedido do João: "qualquer barulho ele interrompe"). Energia alta o suficiente
# qualquer coisa tem: porta, teclado, prato, carro, música de fundo. O que só a fala tem é o VAD FORTE — probabilidade
# ≥ BARGE_IN_PROB numa boa parte da janela. Sem esse mínimo, não corta, por mais alto que esteja.
# É uma FRAÇÃO da janela, não um tempo fixo: quando o João fala por cima do áudio do Jaime o VAD forte dispara em
# ~1 de cada 4 frames (16/09 09:46), enquanto o toque do telefone deu 64 ms em 640 (0,1) e ruído de porta/teclado menos.
BARGE_IN_VOZ_FORTE_FRACAO = 0.2
ESPERAR_CACHE_S = 1.2         # fim de turno com pré-síntese em curso: vale esperar até isto pela 1ª frase pronta
PRE_SINTESES_POR_TURNO = 2    # rascunhos locais sintetizados por turno, no máximo (o texto cresce e o alvo muda)

MULETAS_RX = re.compile(r"\b(é|eh|tipo|então|entao|assim|hum+|ãh+|né|sabe|enfim|aí|ai)\b", re.I)

def hesitando(texto: str) -> bool:
    """Está repetindo ou hesitando? ≥ 3 muletas, ou uma palavra 3× seguidas, ou o mesmo trigrama duas vezes."""
    t = (texto or "").lower()
    if len(MULETAS_RX.findall(t)) >= 3:
        return True
    palavras = re.findall(r"[a-zà-ú]+", t)
    if any(palavras[i] == palavras[i + 1] == palavras[i + 2] for i in range(len(palavras) - 2)):
        return True
    tri = Counter(tuple(palavras[i:i + 3]) for i in range(len(palavras) - 2))
    return any(n >= 2 for n in tri.values()) and len(palavras) >= 8

def interjeicao(a: Antecipacao, maximo: int = 8) -> str:
    """"Já entendi. Quer que eu X?" em no máximo `maximo` palavras."""
    acao = re.sub(r"\s+", " ", (a.acao_prevista or a.intencao or "").strip().rstrip(".?!"))
    if not acao:
        return ""
    acao = acao[0].lower() + acao[1:]
    frase = f"Entendi. Quer que eu {acao}?"
    return frase if len(frase.split()) <= maximo else ""

class DetectorFim:
    """Fim de turno = silêncio (VAD) + critério semântico. Máquina de estados pura, testável.
    `alimentar(prob)` devolve "inicio" quando a fala começa, "fim" quando o turno termina, "curto" quando
    terminou mas era ruído, ou None. `frase_fechou` (True/False/None) vem do antecipador e muda o limiar."""
    def __init__(self, fechou_ms: int = SILENCIO_FECHOU_MS, incerto_ms: int = SILENCIO_INCERTO_MS, aberto_ms: int = SILENCIO_ABERTO_MS,
                 min_fala_ms: int = MIN_FALA_MS, max_s: float = MAX_FALA_S, frame_ms: int = FRAME_MS,
                 inicio: float = VAD_INICIO, fim: float = VAD_FIM):
        self.fechou_ms, self.incerto_ms, self.aberto_ms = fechou_ms, incerto_ms, aberto_ms
        self.min_fala_ms, self.max_s, self.frame_ms, self.inicio, self.fim = min_fala_ms, max_s, frame_ms, inicio, fim
        self.frase_fechou: bool | None = None
        self.falando = False
        self._ms_voz = self._ms_sil = self._ms_total = 0
        self.t_inicio = 0.0
        self.t_ultima_voz = 0.0

    @property
    def limite_ms(self) -> int:
        return self.fechou_ms if self.frase_fechou is True else (self.aberto_ms if self.frase_fechou is False else self.incerto_ms)

    @property
    def silencio_ms(self) -> int:
        return self._ms_sil

    @property
    def duracao_ms(self) -> int:
        return self._ms_total

    def alimentar(self, prob: float, agora: float | None = None) -> str | None:
        agora = time.time() if agora is None else agora
        if not self.falando:
            if prob < self.inicio:
                return None
            self.falando = True
            self._ms_voz = self._ms_sil = self._ms_total = 0
            self.frase_fechou = None
            self.t_inicio = self.t_ultima_voz = agora
            self._ms_voz += self.frame_ms; self._ms_total += self.frame_ms
            return "inicio"
        self._ms_total += self.frame_ms
        if prob >= self.fim:
            self._ms_voz += self.frame_ms; self._ms_sil = 0; self.t_ultima_voz = agora
        else:
            self._ms_sil += self.frame_ms
        if self._ms_sil >= self.limite_ms or self._ms_total >= self.max_s * 1000:
            self.falando = False
            return "fim" if self._ms_voz >= self.min_fala_ms else "curto"
        return None

    def cancelar(self) -> None:
        self.falando = False; self._ms_voz = self._ms_sil = self._ms_total = 0; self.frase_fechou = None

class OuvidoDuplex(Ouvido):
    """Mesmo contrato do Ouvido (start/stop/falar/ativo/mudo/ocupado), com STT em streaming, antecipador,
    fim de turno semântico e barge-in. `fluxo` e `antecipador` são injetáveis (testes)."""
    def __init__(self, jaime, s, loop: asyncio.AbstractEventLoop | None = None, fluxo=None, antecipador=None):
        super().__init__(jaime, s, loop)
        self.det = DetectorFim()
        self.fluxo = fluxo
        self.antecipador = antecipador
        self.barge_in = os.environ.get("JAIME_BARGE_IN", "on").lower()
        self.interromper_joao = os.environ.get("JAIME_INTERROMPER", "0").lower() in ("1", "on", "true")
        self._interjeitou = False
        self.interrompido = False
        self._fila_audio: asyncio.Queue | None = None
        self._lock_turno = asyncio.Lock()
        self._pre: deque = deque(maxlen=max(1, PRE_ROLL_MS // FRAME_MS))
        self._pcm_turno = bytearray()
        self._parcial_texto = ""
        self._t_fim_fala = 0.0
        self._t_texto = 0.0
        self._barge_ms = 0
        self._supressor_eco = SupressorDeEco()
        self._barge_stats: dict = {}                      # por fala do Jaime: voz ouvida, acima do eco, vetada, cortou
        self._janela_energia: deque = deque(maxlen=max(1, BARGE_IN_JANELA_MS // FRAME_MS))
        self._janela_sust: deque = deque(maxlen=max(1, BARGE_IN_JANELA_SUST_MS // FRAME_MS))
        self._janela_vad: deque = deque(maxlen=max(1, BARGE_IN_JANELA_MS // FRAME_MS))
        self._janela_vad_sust: deque = deque(maxlen=max(1, BARGE_IN_JANELA_SUST_MS // FRAME_MS))
        self._janela_piso: deque = deque(maxlen=max(1, BARGE_IN_JANELA_MS // FRAME_MS))
        self._barge_emitido = 0.0
        self._eco_rms = 0.0
        self._eco_amostras = 0
        self.turnos = 0
        self._cache_task: asyncio.Task | None = None    # pré-síntese em curso (rascunho local ou do modelo)
        self._cache_rascunho = ""
        self._pre_sinteses = 0

    # ── carga ────────────────────────────────────────────
    def _carregar(self):
        super()._carregar()
        # O TTS entrega a referência no instante em que cada bloco vai tocar.
        # A atribuição mantém compatibilidade com dublês de teste e TTS antigos.
        if self._tts is not None:
            self._tts.ao_tocar = self._supressor_eco.ao_tocar
        if self.fluxo is None:
            local = (lambda pcm, sr: self._stt._whisper_sync(pcm)) if getattr(self._stt, "_whisper", None) else None
            self.fluxo = stt_stream.escolher(self.s, transcritor_local=local)
        if self.antecipador is None:
            fn = None
            modelo = os.environ.get("JAIME_ANTECIPADOR_MODEL", "") or "gpt-4o-mini"   # 15/09: 2–3 s, mas o melhor rascunho; roda em segundo plano
            if getattr(self.s, "openai_key", "") and modelo != "off":
                try:
                    from openai import AsyncOpenAI
                    fn = modelo_openai(AsyncOpenAI(api_key=self.s.openai_key), modelo)
                except Exception:
                    fn = None
            self.antecipador = Antecipador(fn, on_modelo=self._modelo_chegou)
        self.fluxo.on_parcial = self._parcial

    def _garantir_fila(self) -> asyncio.Queue:
        if self._fila_audio is None:
            self._fila_audio = asyncio.Queue()
        return self._fila_audio

    # ── microfone (thread) ───────────────────────────────
    def _rodar(self):
        try:
            import numpy as np, sounddevice as sd
            self._carregar()
            asyncio.run_coroutine_threadsafe(self._consumir(), self.loop)
        except Exception as e:
            self.erro = f"{type(e).__name__}: {e}"
            bus.emitir("voz", estado="erro", erro=self.erro[:200], falando=False); return
        ultimo_nivel = 0.0
        try:
            with sd.RawInputStream(samplerate=SR, blocksize=FRAME, dtype="int16", channels=1) as mic:
                bus.emitir("voz", estado="ouvindo", falando=False, ativacao=self.s.ativacao, nome=self.s.nome, modo="duplex",
                           stt=getattr(self.fluxo, "nome", "?"), barge_in=self.barge_in)
                while not self._parar.is_set():
                    frame, _ = mic.read(FRAME)
                    frame = bytes(frame)
                    pcm = np.frombuffer(frame, dtype=np.int16)
                    if not self.ativo:
                        self.det.cancelar(); self._vad._janela.clear(); continue
                    prob = self._vad.prob(pcm)
                    rms = float(np.sqrt(np.mean(pcm.astype(np.float32) ** 2)))
                    agora = time.time()
                    if agora - ultimo_nivel > 0.1:
                        ultimo_nivel = agora
                        bus.emitir("escuta", nivel=round(min(1.0, rms / 2500), 3), voz=round(prob, 2),
                                   gravando=self.det.falando, janela_ativa=self.janela_ativa)
                    if self.mudo:
                        self._barge(prob, rms, frame); continue
                    if self._barge_stats:
                        self._fim_da_fala()               # o Jaime acabou de falar: resumo do barge-in dessa fala
                    self._alimentar(prob, frame)
        except Exception as e:
            self.erro = f"{type(e).__name__}: {e}"
            bus.emitir("voz", estado="erro", erro=self.erro[:200], falando=False)

    def _alimentar(self, prob: float, frame: bytes, agora: float | None = None) -> str | None:
        """Um frame do microfone com a probabilidade de voz. Pode ser chamado de qualquer thread."""
        ev = self.det.alimentar(prob, agora)
        if ev == "inicio":
            self._pcm_turno = bytearray(); self._parcial_texto = ""; self.cache_audio = None; self._interjeitou = False
            if self.antecipador: self.antecipador.limpar()
            self._t_fim_fala = 0.0
            for f in self._pre:
                self._pcm_turno += f; self._enviar(f)
            self._pre.clear()
        if self.det.falando or ev in ("fim", "curto"):
            self._pcm_turno += frame; self._enviar(frame)
        else:
            self._pre.append(frame)
        if ev == "fim":
            self._t_fim_fala = time.time() if agora is None else agora
            self._enviar(None)
        elif ev == "curto":
            self._enviar(b"")
        return ev

    def _enviar(self, item) -> None:
        fila = self._garantir_fila()
        try:
            self.loop.call_soon_threadsafe(fila.put_nowait, item)
        except RuntimeError:
            fila.put_nowait(item)

    def _barge(self, prob: float, rms: float, frame: bytes) -> bool:
        """Enquanto o Jaime fala: o João falou por cima? Mede o eco no começo e exige voz bem acima dele."""
        if self.barge_in == "off" or not self._tts:
            return False
        if not getattr(self._tts, "t_inicio_audio", 0.0):
            # a fala ainda não começou a soar (latência do TTS): nada para calibrar — antes o eco era medido
            # neste silêncio e o limiar ficava no chão (16/09).
            self._eco_amostras = 0; self._eco_rms = 0.0
            return False
        if self._eco_amostras < 10:                       # ~320 ms iniciais de cada fala: calibra o eco
            self._eco_rms = (self._eco_rms * self._eco_amostras + rms) / (self._eco_amostras + 1); self._eco_amostras += 1
            return False
        acima_do_eco = self.barge_in == "fone" or rms >= BARGE_IN_ECO_X * max(self._eco_rms, 80.0)
        res = self._supressor_eco.eh_eco(frame)
        sim = res[1] if res else 0.0
        provavel_eco = self.barge_in != "fone" and sim >= BARGE_IN_ECO_SIM
        st = self._barge_stats
        if not st:
            st.update(voz_ms=0, acima_ms=0, veto_ms=0, rms_max=0.0, sim_max=0.0, eco=0.0, cortou=False)
        st["eco"] = self._eco_rms
        # estatísticas de TODOS os frames (as janelas decidem por energia): 'voz' é só o VAD ≥ 0,82; 'acima do eco', rms,
        # similaridade e veto valem para qualquer frame — antes 'rms máx 1421 vs eco 877×1,4' saía com 'acima do eco 0 ms' (13:30)
        st["rms_max"] = max(st["rms_max"], rms); st["sim_max"] = max(st["sim_max"], sim)
        if acima_do_eco: st["acima_ms"] += FRAME_MS
        if provavel_eco: st["veto_ms"] += FRAME_MS
        if prob >= BARGE_IN_PROB:
            st["voz_ms"] += FRAME_MS
        agora = time.time()
        if agora - self._barge_emitido >= 0.5:
            self._barge_emitido = agora
            bus.emitir("barge", **{k: (round(v, 1) if isinstance(v, float) else v) for k, v in st.items()})
        # As janelas contam ENERGIA, não VAD: o VAD fica esparso quando o João fala junto com o áudio do Jaime (16/09 09:46:
        # 832 ms acima do eco espalhados, janela máx 224/320) e, de todo modo, eco também é fala para o VAD — quem separa
        # o João do eco é a razão rms/eco e o veto de similaridade. O VAD segue só nas estatísticas (vad máx).
        self._janela_energia.append(acima_do_eco and not provavel_eco)
        self._janela_sust.append(rms >= BARGE_IN_SUST_X * max(self._eco_rms, 80.0) and not provavel_eco)
        self._janela_vad.append(prob >= BARGE_IN_PROB)
        self._janela_vad_sust.append(prob >= BARGE_IN_PROB)
        self._janela_piso.append(prob >= BARGE_IN_VAD_PISO)
        self._barge_ms = sum(self._janela_energia) * FRAME_MS
        sustentado_ms = sum(self._janela_sust) * FRAME_MS
        piso = sum(self._janela_piso) / max(1, len(self._janela_piso))
        st["janela_max"] = max(st.get("janela_max", 0), self._barge_ms); st["sust_max"] = max(st.get("sust_max", 0), sustentado_ms)
        st["vad_max"] = max(st.get("vad_max", 0), sum(self._janela_vad) * FRAME_MS); st["piso_max"] = max(st.get("piso_max", 0.0), piso)
        # Só VOZ corta. Energia alta qualquer barulho tem (porta, teclado, prato, carro, música); o que só a fala
        # tem é VAD forte numa fração real da janela. Sem isso, não corta, por mais alto que esteja (pedido do João, 16/09).
        forte = sum(self._janela_vad) / max(1, len(self._janela_vad))
        forte_sust = sum(self._janela_vad_sust) / max(1, len(self._janela_vad_sust))
        st["forte_max"] = round(max(st.get("forte_max", 0.0), forte), 2)
        energia = self._barge_ms >= BARGE_IN_MS and forte >= BARGE_IN_VOZ_FORTE_FRACAO
        sustentado = sustentado_ms >= BARGE_IN_SUSTENTADO_MS and forte_sust >= BARGE_IN_VOZ_FORTE_FRACAO
        if (not energia and not sustentado) or piso < BARGE_IN_VAD_FRACAO:
            return False
        st["cortou"] = True; st["motivo"] = "energia" if energia else "sustentado"
        self._barge_ms = 0; self._janela_energia.clear(); self._janela_sust.clear(); self._janela_vad.clear(); self._janela_vad_sust.clear(); self._janela_piso.clear()
        restantes = self._tts.parar()
        self._nao_ditas = restantes
        self.interrompido = True
        self.mudo = False
        self._cancelar_modelo()
        bus.emitir("voz", estado="interrompido", falando=False, restantes=restantes)
        self.det.cancelar(); self._alimentar(prob, frame)
        return True

    def _fim_da_fala(self) -> None:
        """Fecha as estatísticas de barge-in da fala que acabou. Voz ouvida por ≥ 400 ms sem cortar vira uma linha no
        diário — é o dado que faltava para calibrar os limiares (16/09: o João falou por cima do briefing e nada cortou)."""
        st, self._barge_stats = self._barge_stats, {}
        self._eco_amostras = 0; self._eco_rms = 0.0; self._barge_ms = 0; self._janela_energia.clear(); self._janela_sust.clear(); self._janela_vad.clear(); self._janela_vad_sust.clear(); self._janela_piso.clear()
        bus.emitir("barge", fim=True, **{k: (round(v, 1) if isinstance(v, float) else v) for k, v in st.items()})
        linha = ""
        if max(st.get("voz_ms", 0), st.get("acima_ms", 0)) >= 400 and not st.get("cortou"):
            linha = (f"Barge-in não cortou: voz por {st['voz_ms']} ms durante a minha fala (acima do eco {st['acima_ms']} ms, "
                     f"vetada como eco {st['veto_ms']} ms; rms máx {st['rms_max']:.0f} vs eco {st['eco']:.0f}×{BARGE_IN_ECO_X}; sim máx {st['sim_max']:.2f}; "
                     f"janela máx {st.get('janela_max', 0)}/{BARGE_IN_MS} ms, sustentada máx {st.get('sust_max', 0)}/{BARGE_IN_SUSTENTADO_MS} ms, "
                     f"vad máx {st.get('vad_max', 0)}/{BARGE_IN_JANELA_MS} ms, piso de voz máx {st.get('piso_max', 0.0):.0%}/{BARGE_IN_VAD_FRACAO:.0%})")
        elif st.get("cortou"):
            # também quando corta: é assim que se vê um corte pelo próprio eco (o João reclama "você não terminou de falar")
            linha = (f"Barge-in cortou ({st.get('motivo', '?')}): voz {st['voz_ms']} ms, rms máx {st['rms_max']:.0f} vs eco {st['eco']:.0f}, "
                     f"sim máx {st['sim_max']:.2f}, piso de voz {st.get('piso_max', 0.0):.0%}")
        if linha:
            vault = getattr(self.jaime, "vault", None)
            if vault is not None:
                try: self.loop.call_soon_threadsafe(vault.diario, linha, "Log")
                except Exception:
                    try: vault.diario(linha, "Log")
                    except Exception: pass

    def _cancelar_modelo(self) -> None:
        """O modelo pode estar no meio da resposta: pede ao Agent SDK para interromper (não bloqueia)."""
        cli = getattr(self.jaime, "_client", None)
        if cli is not None and hasattr(cli, "interrupt"):
            try:
                asyncio.run_coroutine_threadsafe(cli.interrupt(), self.loop)
            except Exception:
                pass

    def _interjeitar(self, a: Antecipacao) -> bool:
        """Jaime interrompe o João (§2.2) — só com JAIME_INTERROMPER ligado e todos os critérios valendo."""
        if not (self.interromper_joao and self._tts) or self._interjeitou:
            return False
        if a.completude < 0.9 or a.ambigua or self.det.duracao_ms <= 4000 or not hesitando(self._parcial_texto):
            return False
        frase = interjeicao(a)
        if not frase:
            return False
        self._interjeitou = True
        bus.emitir("antecipacao", interjeicao=frase)
        self.mudo = True; self._tts.enfileirar(frase)
        threading.Thread(target=self._aguardar_fala, name="interjeicao", daemon=True).start()
        return True

    # ── STT / antecipação (loop) ─────────────────────────
    async def _consumir(self):
        fila = self._garantir_fila()
        try:
            if self.fluxo and not self.fluxo.conectado:
                await self.fluxo.iniciar()
        except Exception as e:
            self.erro = f"STT streaming: {type(e).__name__}: {e}"
            bus.emitir("voz", estado="erro", erro=self.erro[:200], falando=False)
        while not self._parar.is_set():
            item = await fila.get()
            try:
                if item is None:
                    texto = (await self.fluxo.finalizar()).strip()
                    self._t_texto = time.time()
                    bus.emitir("transcricao_viva", texto=texto, final=True)
                    pcm = bytes(self._pcm_turno)
                    asyncio.create_task(self._turno(texto, pcm, self._t_fim_fala, self._t_texto))
                elif item == b"":
                    await self.fluxo.finalizar()
                    if self.antecipador: self.antecipador.limpar()
                else:
                    if self.fluxo and not self.fluxo.conectado:
                        try: await self.fluxo.iniciar()
                        except Exception: pass
                    await self.fluxo.enviar(item)
            except Exception as e:
                bus.emitir("voz", estado="erro", erro=f"duplex: {type(e).__name__}: {e}"[:200], falando=False)

    def _parcial(self, texto: str) -> None:
        self._parcial_texto = texto
        bus.emitir("transcricao_viva", texto=texto, final=False)
        if self.antecipador and self.antecipador.pode_avaliar(texto):
            try:
                self.loop.create_task(self._antecipar(texto))
            except RuntimeError:
                asyncio.run_coroutine_threadsafe(self._antecipar(texto), self.loop)

    async def _antecipar(self, texto: str) -> Antecipacao | None:
        """Heurística agora (fim de turno); o modelo refina em segundo plano e chama `_modelo_chegou`."""
        if self.antecipador.on_modelo is None:
            self.antecipador.on_modelo = self._modelo_chegou
        a = await self.antecipador.avaliar(texto)
        if not a:
            return None
        self._aplicar(a)
        return a

    def _aplicar(self, a: Antecipacao) -> None:
        # o parecer sobre "fechou?" só vale se o texto não cresceu enquanto o modelo pensava (um parecer antigo não apaga o atual)
        if a.texto == self._parcial_texto.strip():
            self.det.frase_fechou = a.frase_fechou
        bus.emitir("antecipacao", intencao=a.intencao, completude=a.completude, fechou=a.frase_fechou,
                   rascunho=a.rascunho, origem=a.origem, latencia=round(a.latencia_s, 2))
        if a.origem == "heuristica" and a.especulavel:
            self._pre_sintetizar(a)                      # rascunho local: sintetiza já, enquanto o João ainda fala
        self._interjeitar(a)

    def _pre_sintetizar(self, a: Antecipacao) -> None:
        """Sintetiza a 1ª frase em segundo plano; no máximo PRE_SINTESES_POR_TURNO vezes por turno."""
        if not self._tts or not a.rascunho:
            return
        if self.cache_audio and self.cache_audio[0] == a.rascunho:
            return
        if self._cache_task and not self._cache_task.done() and self._cache_rascunho == a.rascunho:
            return
        if a.origem == "heuristica" and self._pre_sinteses >= PRE_SINTESES_POR_TURNO:
            return
        self._pre_sinteses += 1; self._cache_rascunho = a.rascunho
        self._cache_task = self.loop.create_task(self._sintetizar_cache(a.rascunho))

    async def _sintetizar_cache(self, rascunho: str) -> None:
        pcm = await asyncio.to_thread(self._tts.pre_sintetizar, rascunho)
        u = self.antecipador.ultima if self.antecipador else None
        if u and u.rascunho == rascunho:                 # o texto não mudou de rumo enquanto sintetizava
            self.cache_audio = (rascunho, pcm)

    async def _modelo_chegou(self, a: Antecipacao) -> None:
        self._aplicar(a)
        if a.especulavel:
            self._pre_sintetizar(a)

    def _motivo(self, antecip: Antecipacao | None, texto_final: str) -> str:
        """Por que a antecipação vai (ou não) ser usada — uma frase para o diário."""
        u = self.antecipador.ultima if self.antecipador else None
        if u is None:
            return "nenhuma (sem parcial avaliada)"
        if not u.especulavel:
            return f"sem rascunho ({u.origem}, completude {u.completude:.1f})"
        if antecip is None:
            return f"não bateu: «{u.texto[:30]}» ≠ «{texto_final[:30]}»"
        if self.cache_audio is None:
            return f"rascunho «{u.rascunho[:30]}» sem áudio a tempo"
        return f"pronta: «{u.rascunho[:30]}»"

    async def _turno(self, texto: str, pcm: bytes, t_fim_fala: float, t_texto: float):
        async with self._lock_turno:
            self.ocupado = True
            try:
                if len(texto) < 3 or LIXO_WHISPER.search(texto):
                    return
                self.turnos += 1
                antecip = self.antecipador.confere(texto) if self.antecipador else None
                self._pre_sinteses = 0
                if antecip and self.cache_audio is None and self._cache_task and not self._cache_task.done():
                    # a 1ª frase ainda está sendo sintetizada: esperar um pouco sai mais rápido que modelo + TTS do zero
                    try:
                        await asyncio.wait_for(asyncio.shield(self._cache_task), ESPERAR_CACHE_S)
                    except (asyncio.TimeoutError, Exception):
                        pass
                if self.cache_audio and (antecip is None or self.cache_audio[0] != antecip.rascunho):
                    self.cache_audio = None              # cache de outra intenção (ou de outro turno) não pode tocar
                self._motivo_antecip = self._motivo(antecip, texto)
                self._eco_rms = 0.0; self._eco_amostras = 0; self._barge_ms = 0; self.interrompido = False
                await self._tratar_texto(texto, pcm, antecipacao=antecip, t_fim_fala=t_fim_fala, t_texto=t_texto)
            except Exception as e:
                bus.emitir("voz", estado="erro", erro=f"{type(e).__name__}: {e}"[:200], falando=False)
            finally:
                self.ocupado = False
                bus.emitir("voz", estado="ouvindo", falando=False)
