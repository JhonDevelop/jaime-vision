"""Fala: ElevenLabs/OpenAI → PCM → placa de som. Feito para não engasgar — e para calar em < 100 ms.

Por que é assim (medido nesta máquina, 14/09/2026):
- A ElevenLabs não entrega o áudio em fluxo contínuo: espera ~0,3 s e despeja a frase inteira em
  ~0,2 s. Tocar "em streaming" não ganhava nada e ainda deixava a placa de som sem dado — era daí
  que vinha a voz picotada. Agora a frase é sintetizada inteira em memória e só então tocada.
- O que realmente travava a conversa eram as pausas ENTRE frases: cada uma abria uma requisição nova
  e o João ouvia ~0,5 s de silêncio a cada ponto final. Agora um sintetizador vai na frente,
  preparando as próximas frases enquanto a atual toca — a fala sai emendada.
- A saída é UM stream de saída aberto para a resposta inteira, com escrita em blocos de ~100 ms:
  assim `parar()` (barge-in) corta no meio da frase em < 100 ms. `afplay` fica de reserva.
- O PCM é reamostrado aqui para a taxa nativa do aparelho (24 kHz → 44,1 kHz), em vez de deixar a
  conversão para o PortAudio — é de lá que vinham os estalos.

Fase 3 (docs/FASE-3-TEMPO-REAL.md): `pre_sintetizar()` prepara a 1ª frase enquanto o João ainda fala,
`tocar_pronto()` toca esse cache em ~0 ms, `parar()` mata tudo (barge-in), `velocidade` 1.0× por padrão
(JAIME_VOZ_VELOCIDADE) e `t_inicio_audio` marca quando a resposta começou a soar (métrica de latência).

Ordem de tentativa: ElevenLabs → OpenAI gpt-4o-mini-tts → `say` do macOS em pt-BR → texto no terminal. Nunca fica mudo.
`voz: falando=true` sai quando a primeira frase começa e só volta a false quando a fila esvazia."""
from __future__ import annotations
import os, queue, re, shutil, subprocess, tempfile, threading, time, wave
from ..config import Settings
from ..hud.events import bus
from .cache_frases import CacheFrases

PCM_SR = 24000                       # pcm_24000 existe no plano gratuito (44100 é só Pro)
# O sotaque vem PRIMEIRO na instrução, e é a parte não negociável. A versão anterior abria com "dicção
# levemente mecânica" e o modelo lia isso como licença para soar estrangeiro — o João ouviu na hora e
# reclamou (17/09). Brasileiro nativo primeiro; o jeito Jarvis vem do RITMO e da entonação contida, não de
# maltratar as vogais.
ESTILO_JARVIS = (
    "Falante NATIVO de português do Brasil, sotaque paulista neutro. Pronúncia brasileira correta: "
    "erres e esses brasileiros, nenhum sotaque estrangeiro, nenhuma sílaba em inglês. "
    "Voz masculina grave. FALE RÁPIDO, no ritmo de uma conversa normal entre duas pessoas que se conhecem — "
    "como quem já sabe a resposta e não precisa pensar para dizer. "
    "Sem pausa entre as palavras, sem pausa dramática, sem alongar vogal, sem soletrar. "
    "Entonação contida e quase reta: informa, não narra. "
    "Sem entusiasmo e sem hesitação.")
VOZ_PADRAO = "JBFqnCBsd6RMkjVDRZzb"  # premade (George) — fala pt-BR com sotaque; troque em ELEVENLABS_VOICE_ID
ADIANTAR = 2                         # quantas frases o sintetizador prepara à frente da que está tocando
BLOCO_S = 0.05                       # escrita na placa em blocos de 50 ms: é o tempo máximo que parar() espera para calar

def limpar_para_fala(texto: str) -> str:
    """O modelo às vezes manda markdown mesmo por voz; o TTS leria os símbolos. Tira tudo que não se fala."""
    t = re.sub(r"```.*?```", " ", texto, flags=re.S)          # blocos de código
    t = re.sub(r"`([^`]*)`", r"\1", t)                        # `código` → código
    t = re.sub(r"https?://\S+", "link", t)                     # URLs não se leem
    t = re.sub(r"^\s*(#{1,6}\s*|[-*•]\s+|\d+[.)]\s+)", "", t, flags=re.M)   # títulos e marcadores de lista
    t = re.sub(r"[*_~#>|]+", "", t)                             # ênfases, tabelas, citações
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)             # [texto](url) → texto
    t = re.sub(r"\s*\n+\s*", ". ", t)                          # quebra de linha vira pausa
    t = re.sub(r"\.\s*\.", ".", t)
    return re.sub(r"[ \t]{2,}", " ", t).strip()

class TTS:
    def __init__(self, s: Settings, ao_tocar=None):
        self.s = s
        self._client = None
        self._falhas = 0
        self._ultima_falha = 0.0
        self._afplay = shutil.which("afplay")
        # saída: JAIME_SAIDA_AUDIO = auto (sounddevice, cai p/ afplay ao falhar) | afplay (robusto no Intel) | sounddevice
        self._saida = os.environ.get("JAIME_SAIDA_AUDIO", "afplay" if self._afplay else "sounddevice").lower()
        self._usar_afplay = self._saida == "afplay"     # sticky: reabrir o PortAudio no Intel dá -9986 e pica o som
        self._afplay_proc = None                         # processo do afplay em curso (para o barge-in cortar)
        self._stream = None          # stream de saída, aberto enquanto durar a resposta
        self._taxa = PCM_SR          # taxa nativa do aparelho, descoberta ao abrir
        self._anterior = ""          # última frase sintetizada (previous_text da ElevenLabs)
        self.ajustes: dict | None = None   # {"stability", "style"} vindos da prosódia (humor); None = .env
        self.instrucoes: str = ""          # instrução de estilo (prosódia) para o gpt-4o-mini-tts
        self.motor = os.environ.get("JAIME_TTS", "auto")   # elevenlabs | openai | auto
        self.velocidade = float(os.environ.get("JAIME_VOZ_VELOCIDADE", "1.2"))
        # 1.2 foi ESCOLHA DELE, de ouvido, entre 1.0, 1.1 e 1.2 (17/09). Antes disso: 1.15 saía
        # atropelado com a instrução velha, e 1.0 com a instrução 'calma' saía lento. O que mudou foi
        # a instrução (ESTILO_JARVIS pede ritmo de conversa); daí 1.2 ficou rápido sem atropelar.
        self._t_nivel = 0.0          # último instante em que publicou a altura da voz
        self.dizendo = ""            # o que ele está dizendo AGORA — o barge-in usa para não se cortar com o próprio eco
        self.frase_atual = ""        # só a frase tocando neste instante (comparação mais precisa que a resposta toda)
        self.t_inicio_audio = 0.0    # quando a resposta atual começou a soar (0 = ainda não)
        self.t_primeiro_som = 0.0    # 1º som do TURNO (muleta incluída) — só `novo_turno()` zera; t_inicio_audio zera a cada resposta
        self.t_fim_audio = 0.0
        self.interrompida = False    # a última fala foi cortada por parar()
        self._openai = None
        # Recebe PCM mono int16 a 24 kHz imediatamente antes de cada bloco ir
        # para a placa. É opcional para não alterar os chamadores existentes.
        self.ao_tocar = ao_tocar
        self._cache_frases = CacheFrases(motor=self.motor, voz=self._voz_cache(), velocidade=self.velocidade,
                                         instrucoes=self.instrucoes)
        if s.openai_key:
            from openai import OpenAI
            self._openai = OpenAI(api_key=s.openai_key)
        if s.elevenlabs_key:
            from elevenlabs.client import ElevenLabs
            self._client = ElevenLabs(api_key=s.elevenlabs_key)
        # pipeline: enfileirar() → [sintetizador] → _prontos → [reprodutor] → placa de som
        self._pedidos: queue.Queue = queue.Queue()
        self._prontos: queue.Queue = queue.Queue(maxsize=ADIANTAR)
        self._pendentes = 0
        self._cond = threading.Condition()
        self._geracao = 0            # parar() avança a geração: itens antigos são descartados
        self._parando = threading.Event()
        # O PortAudio não aguenta abort()/close() numa thread enquanto write() roda em outra (segfault em
        # PaUtil_WriteRingBuffer, 15/09 14:06). Todo acesso ao stream passa por este lock, bloco a bloco.
        self._lock_stream = threading.RLock()
        threading.Thread(target=self._sintetizador, daemon=True).start()
        threading.Thread(target=self._reprodutor, daemon=True).start()

    # ── API ───────────────────────────────────────────────
    def _preparar(self, texto: str) -> str:
        from .persona import aplicar as persona
        return persona(limpar_para_fala(texto))

    def _voz_cache(self) -> str:
        """Inclui as duas vozes possíveis quando o motor automático escolhe o provedor."""
        eleven = getattr(self.s, "elevenlabs_voice", "") or VOZ_PADRAO
        openai = os.environ.get("JAIME_OPENAI_VOZ", "onyx")
        return openai if self.motor == "openai" else (eleven if self.motor == "elevenlabs" else f"{eleven}|{openai}")

    def _cache_atualizar(self) -> None:
        self._cache_frases.configurar(motor=self.motor, voz=self._voz_cache(), velocidade=self.velocidade,
                                      instrucoes=self.instrucoes)

    def _sintetizar_com_cache(self, texto: str, *, guardar_anterior: bool = True, streaming: bool = False):
        self._cache_atualizar()
        if pcm := self._cache_frases.get(texto):
            return pcm
        pcm = self._sintetizar(texto, guardar_anterior=guardar_anterior, streaming=streaming)
        if pcm is None:
            return None
        if not streaming or isinstance(pcm, (bytes, bytearray)):
            self._cache_frases.put(texto, pcm)
            return pcm
        return self._acumular_para_cache(texto, pcm)

    def _acumular_para_cache(self, texto: str, blocos):
        """Grava depois do último bloco em thread própria: a placa nunca espera o disco."""
        def fluxo():
            pcm = bytearray()
            for bloco in blocos:
                pcm += bloco
                yield bloco
            if pcm:
                threading.Thread(target=self._cache_frases.put, args=(texto, bytes(pcm)), daemon=True).start()
        return fluxo()

    def enfileirar(self, texto: str) -> None:
        """Manda falar sem esperar. Use durante a resposta em fluxo: cada frase entra assim que fica
        pronta e o sintetizador já vai preparando a seguinte."""
        texto = self._preparar(texto)
        if not texto:
            return
        with self._cond:
            if self._pendentes == 0:
                self.t_inicio_audio = 0.0; self.interrompida = False; self.dizendo = ""
                bus.emitir("voz", falando=True, estado="falando", texto=texto)
            self.dizendo = (self.dizendo + " " + texto)[-600:]
            self._pendentes += 1
            g = self._geracao
        self._pedidos.put((g, texto))

    def pre_sintetizar(self, texto: str) -> bytes | None:
        """Sintetiza AGORA, sem tocar (rascunho do antecipador). Devolve o PCM ou None se nenhum motor respondeu."""
        texto = self._preparar(texto)
        if not texto:
            return None
        return self._sintetizar_com_cache(texto, guardar_anterior=False)

    def tocar_pronto(self, texto: str, pcm: bytes | None) -> None:
        """Toca um áudio já sintetizado (cache do antecipador) na frente de tudo."""
        texto = self._preparar(texto) or texto
        with self._cond:
            if self._pendentes == 0:
                self.t_inicio_audio = 0.0; self.interrompida = False; self.dizendo = ""
                bus.emitir("voz", falando=True, estado="falando", texto=texto)
            self.dizendo = (self.dizendo + " " + texto)[-600:]
            self._pendentes += 1
            g = self._geracao
        self._anterior = texto
        self._prontos.put((g, texto, pcm if pcm else None))

    def novo_turno(self) -> None:
        """Começa a contar o 1º som do turno: a muleta ('deixa eu ver…') conta como 1ª frase percebida pelo João.
        Antes, enfileirar() zerava t_inicio_audio quando a muleta acabava e o diário dizia 14 s onde o João ouviu algo em 4 s."""
        self.t_primeiro_som = 0.0

    def parar(self) -> int:
        """Barge-in: cala em < 100 ms. Esvazia as filas, corta o bloco em curso e fecha o aparelho.
        Devolve quantas frases ficaram por dizer."""
        with self._cond:
            self._geracao += 1
            restantes = self._pendentes
            self._parando.set()
            for q in (self._pedidos, self._prontos):
                while True:
                    try: q.get_nowait()
                    except queue.Empty: break
            self._pendentes = 0
            self.interrompida = restantes > 0
            self._cond.notify_all()
        proc = self._afplay_proc                              # barge-in: mata a fala em curso pelo afplay
        if proc is not None:
            try: proc.terminate()
            except Exception: pass
        self._fechar_stream()
        self._parando.clear()
        self._anterior = ""
        if restantes:
            bus.emitir("voz", falando=False, estado="ouvindo", interrompida=True)
        return restantes

    def aguardar(self, timeout: float = 300) -> None:
        """Bloqueia até a fila esvaziar."""
        with self._cond:
            self._cond.wait_for(lambda: self._pendentes == 0, timeout=timeout)

    def falar(self, texto: str) -> None:
        """Fala uma coisa só e espera terminar (apresentação, avisos)."""
        self.enfileirar(texto)
        self.aguardar()

    @property
    def ocupado(self) -> bool:
        with self._cond:
            return self._pendentes > 0

    # ── pipeline ──────────────────────────────────────────
    def _sintetizar(self, texto: str, guardar_anterior: bool = True, streaming: bool = False):
        """PCM inteiro (bytes) ou, com `streaming`, um iterador de blocos que já vem com o 1º bloco baixado —
        o reprodutor começa a tocar no primeiro byte em vez de esperar a frase inteira (medido 15/09: 0,5–1,4 s
        até o 1º byte contra 1,3–2,4 s pela frase toda no gpt-4o-mini-tts)."""
        pcm = None
        # 3 falhas seguidas desligam a ElevenLabs por 10 min (cota, rede); depois tenta de novo sozinho
        if self._falhas >= 3 and time.time() - self._ultima_falha > 600:
            self._falhas = 0
        usar_eleven = self._client and self._falhas < 3 and self.motor in ("auto", "elevenlabs")
        if usar_eleven:
            try:
                pcm = self._elevenlabs(texto, guardar_anterior, streaming)
                self._falhas = 0
            except Exception as e:
                self._falhas += 1; self._ultima_falha = time.time()
                print(f"⚠ ElevenLabs falhou ({type(e).__name__}: {str(e)[:80]}); tentando OpenAI/voz local")
        if pcm is None and self._openai and self.motor in ("auto", "openai"):
            try:
                pcm = self._openai_tts(texto, streaming)
            except Exception as e:
                print(f"⚠ OpenAI TTS falhou ({type(e).__name__}: {str(e)[:80]}); usando a voz local")
        return pcm

    @staticmethod
    def _primeiro_e_resto(blocos):
        """Puxa o 1º bloco agora (absorve a latência de rede à frente) e devolve um iterador com ele + o resto."""
        import itertools
        it = iter(blocos)
        primeiro = next(it, None)
        if not primeiro:
            return None
        return itertools.chain([primeiro], it)

    def medir_primeiro_byte(self, texto: str) -> float | None:
        """Segundos até o 1º bloco de áudio da frase (o que o João espera quando não há cache)."""
        texto = self._preparar(texto)
        if not texto:
            return None
        ini = time.time()
        r = self._sintetizar(texto, guardar_anterior=False, streaming=True)
        if r is None:
            return None
        t = time.time() - ini
        for _ in r:                     # esgota (fecha a conexão) sem tocar
            pass
        return t

    def _sintetizador(self) -> None:
        """Vai na frente: busca o áudio da próxima frase enquanto a atual ainda toca."""
        while True:
            g, texto = self._pedidos.get()
            if g != self._geracao:
                continue                        # parar() passou por aqui: frase descartada
            pcm = self._sintetizar_com_cache(texto, streaming=False)   # frase inteira: sem underrun de rede (voz lisa)
            if g != self._geracao:
                continue
            self._prontos.put((g, texto, pcm))

    def _reprodutor(self) -> None:
        while True:
            g, texto, pcm = self._prontos.get()
            if g != self._geracao:
                continue
            # a frase que começa a soar AGORA: é com ela que o barge-in compara o eco mais recente
            self.frase_atual = texto
            try:
                if pcm is not None:
                    self._tocar(pcm, g)
                elif not self._say_nativo(texto):
                    print(f"🔈 {texto}")
            except Exception as e:
                print(f"⚠ áudio falhou ({type(e).__name__}); {texto}")
            finally:
                self.frase_atual = ""          # parou de soar: o eco dela não deve mais vetar um corte
                with self._cond:
                    if g == self._geracao and self._pendentes > 0:
                        self._pendentes -= 1
                    vazio = self._pendentes == 0
                    self._cond.notify_all()
                if vazio and g == self._geracao:
                    self.t_fim_audio = time.time()
                    self._fechar_stream()   # libera o aparelho entre uma resposta e outra
                    bus.emitir("voz", falando=False, estado="ouvindo")

    # ── saídas ────────────────────────────────────────────
    def _elevenlabs(self, texto: str, guardar_anterior: bool = True, streaming: bool = False):
        from elevenlabs import VoiceSettings
        # Emoção: estabilidade baixa e "style" alto deixam a voz seguir a pontuação — exclamação sobe,
        # reticências hesitam, pergunta entoa. O prompt do Jaime escreve pensando nisso quando fala.
        a = self.ajustes or {}
        kw = dict(stability=float(a.get("stability", os.environ.get("JAIME_VOZ_ESTABILIDADE", "0.5"))),
                  similarity_boost=0.8,
                  style=float(a.get("style", os.environ.get("JAIME_VOZ_ESTILO", "0.3"))),
                  use_speaker_boost=True)
        try:
            ajustes = VoiceSettings(speed=self.velocidade, **kw)
        except TypeError:                       # SDK antigo sem `speed`
            ajustes = VoiceSettings(**kw)
        fluxo = self._client.text_to_speech.stream(
            text=texto, voice_id=self.s.elevenlabs_voice or VOZ_PADRAO,
            model_id=os.environ.get("JAIME_TTS_MODELO", "eleven_flash_v2_5"),   # flash: menor latência
            output_format=f"pcm_{PCM_SR}", voice_settings=ajustes,
            optimize_streaming_latency=3,   # ~0,1 s a menos até o primeiro byte
            previous_text=self._anterior[-300:] or None,   # continuidade de entonação entre frases
        )
        if guardar_anterior:
            self._anterior = texto
        if streaming:
            return self._primeiro_e_resto(c for c in fluxo if c)
        return b"".join(c for c in fluxo if c)

    def _openai_kw(self, texto: str) -> dict:
        # A voz do Jarvis: sintetizada, mas humana. O que dá o efeito não é filtro de áudio, é a instrução —
        # dicção marcada, ritmo constante, entonação quase plana com UMA inflexão no fim. Máquina precisa, não
        # robô de desenho. `JAIME_VOZ_ESTILO_BASE` no .env troca isto sem tocar no código.
        base = os.environ.get("JAIME_VOZ_ESTILO_BASE", ESTILO_JARVIS)
        return dict(model=os.environ.get("JAIME_OPENAI_TTS_MODELO", "gpt-4o-mini-tts"), voice=os.environ.get("JAIME_OPENAI_VOZ", "onyx"),
                    input=texto, instructions=(base + " " + self.instrucoes).strip(), response_format="pcm", speed=self.velocidade)

    def _openai_blocos(self, texto: str):
        """Blocos de ~100 ms conforme chegam da rede; para no barge-in."""
        with self._openai.audio.speech.with_streaming_response.create(**self._openai_kw(texto)) as resp:
            for ch in resp.iter_bytes(PCM_SR * 2 // 10):
                if self._parando.is_set():
                    return
                yield ch

    def _openai_tts(self, texto: str, streaming: bool = False):
        """gpt-4o-mini-tts: voz masculina (JAIME_OPENAI_VOZ, padrão onyx) + instrução de estilo vinda da prosódia.
        PCM 24 kHz, a mesma taxa da ElevenLabs — cai no mesmo reprodutor."""
        if streaming:
            return self._primeiro_e_resto(self._openai_blocos(texto))
        with self._openai.audio.speech.with_streaming_response.create(**self._openai_kw(texto)) as resp:
            return b"".join(resp.iter_bytes())

    def _tocar(self, pcm, g: int | None = None) -> None:
        """`pcm`: bytes inteiros (frase já sintetizada). `g` é a geração: se `parar()` avançou, descarta.
        No Intel a reabertura do PortAudio dá -9986 e pica o som — por isso o padrão é afplay (frase inteira,
        liso, coexiste com o microfone), com corte por kill no barge-in. `JAIME_SAIDA_AUDIO=sounddevice` força o outro."""
        buf = bytes(pcm) if isinstance(pcm, (bytes, bytearray)) else b"".join(bytes(t) for t in pcm)
        if g is None:
            g = self._geracao
        cortada = lambda: self._parando.is_set() or g != self._geracao
        if cortada() or not buf:
            return
        # A referência do supressor de eco (voice/eco.py) guarda só os últimos 300 ms: precisa receber o PCM no ritmo em
        # que ele TOCA, não a frase inteira de uma vez (16/09: com afplay a referência era o fim da frase durante a fala
        # toda — similaridade nunca batia, e o barge-in decidia só pela energia).
        if not self.t_inicio_audio:
            self.t_inicio_audio = time.time()
        if not self.t_primeiro_som:
            self.t_primeiro_som = self.t_inicio_audio
        if self._usar_afplay:
            return self._tocar_afplay(buf, cortada)
        try:
            dados = self._na_taxa_do_aparelho(buf)
            bloco = int(self._taxa * BLOCO_S) * 2
            for i in range(0, len(dados), bloco):
                with self._lock_stream:
                    if cortada():
                        return
                    st = self._abrir_stream()
                    self._referencia(buf, i / max(1, len(dados)), (i + bloco) / max(1, len(dados)))
                    st.write(dados[i:i + bloco])
        except Exception as e:
            if cortada():
                return
            print(f"⚠ placa de som falhou ({type(e).__name__}); passando para o afplay (o resto da sessão)")
            self._usar_afplay = True                          # sticky: não reabre mais o PortAudio nesta sessão
            self._fechar_stream()
            self._tocar_afplay(buf, cortada)

    def _referencia(self, buf: bytes, de: float, ate: float) -> None:
        """Entrega ao supressor de eco a fatia de `buf` (PCM 24 kHz) entre as frações `de` e `ate` da frase,
        e publica a ALTURA real dessa fatia — é ela que anima o cérebro no cockpit (antes era um seno falso,
        que não casava com a voz e parecia bug)."""
        a = max(0, min(len(buf), int(de * len(buf)) & ~1)); b = max(a, min(len(buf), int(ate * len(buf)) & ~1))
        if b <= a:
            return
        fatia = buf[a:b]
        self._nivel_da_fatia(fatia)
        if self.ao_tocar:
            try: self.ao_tocar(fatia)
            except Exception: pass

    def _nivel_da_fatia(self, fatia: bytes) -> None:
        """RMS da fatia que está tocando agora → evento `voz.nivel` (0..1), no máximo ~25 por segundo."""
        agora = time.time()
        if agora - self._t_nivel < 0.04:
            return
        self._t_nivel = agora
        try:
            import numpy as np
            x = np.frombuffer(fatia, dtype=np.int16).astype(np.float32)
            if not len(x):
                return
            rms = float(np.sqrt(np.mean(x * x))) / 4200.0        # medido 16/09: a fala normal do TTS bate 0,55-0,75 nesta escala
            bus.emitir("voz", falando=True, estado="falando", nivel=max(0.0, min(1.0, rms)))
        except Exception:
            pass

    def _abrir_stream(self):
        """Um stream por resposta, não por frase: abrir custa 0,09 s e é o que emenda as frases.
        Robusto: se o modo baixa latência falhar (AUHAL -9986 no Intel quando o aparelho está contendido),
        tenta latência alta e depois o padrão antes de deixar o reprodutor cair no afplay."""
        import sounddevice as sd
        with self._lock_stream:
            if self._stream is None:
                try:
                    self._taxa = int(sd.query_devices(kind="output")["default_samplerate"]) or PCM_SR
                except Exception:
                    self._taxa = PCM_SR
                ultimo = None
                for lat in ("low", "high", None):
                    try:
                        kw = dict(samplerate=self._taxa, channels=1, dtype="int16", blocksize=0)
                        if lat is not None:
                            kw["latency"] = lat
                        st = sd.RawOutputStream(**kw); st.start()
                        self._stream = st
                        break
                    except Exception as e:
                        ultimo = e
                        try: st.close()
                        except Exception: pass
                if self._stream is None:
                    raise ultimo or RuntimeError("sem stream de saída")
            return self._stream

    def _fechar_stream(self) -> None:
        with self._lock_stream:                             # espera o bloco em curso (≤ 50 ms) terminar
            st, self._stream = self._stream, None
            if st is not None:
                try: st.abort() if self._parando.is_set() else st.stop(); st.close()
                except Exception: pass

    def _na_taxa_do_aparelho(self, pcm: bytes) -> bytes:
        """Reamostragem linear 24 kHz → taxa do aparelho. Fazer aqui evita os estalos do PortAudio."""
        if self._taxa == PCM_SR:
            return pcm
        import numpy as np
        x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        n = int(len(x) * self._taxa / PCM_SR)
        return np.interp(np.arange(n) * PCM_SR / self._taxa,
                         np.arange(len(x)), x).astype(np.int16).tobytes()

    def _tocar_afplay(self, pcm: bytes, cortada=None) -> None:
        """Toca a frase inteira pelo afplay (liso, sem underrun, coexiste com o mic). Killable: o barge-in mata o
        processo em < 100 ms. `cortada()` diz se a fala foi interrompida."""
        if not self._afplay:
            if not self._say_nativo_pcm(pcm):
                print("🔈 (sem afplay)")
            return
        cortada = cortada or (lambda: self._parando.is_set())
        caminho = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                caminho = f.name
            with wave.open(caminho, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(PCM_SR); w.writeframes(pcm)
            if cortada():
                return
            proc = subprocess.Popen([self._afplay, caminho], stderr=subprocess.DEVNULL)
            self._afplay_proc = proc
            t0 = time.time(); total_s = len(pcm) / 2 / PCM_SR; entregue = 0.0
            while proc.poll() is None:
                if cortada():
                    try: proc.terminate()
                    except Exception: pass
                    break
                # referência de eco no ritmo da reprodução (o afplay não devolve blocos): fatia por tempo decorrido
                ate = min(1.0, (time.time() - t0) / total_s) if total_s > 0 else 1.0
                if ate > entregue:
                    self._referencia(pcm, entregue, ate); entregue = ate
                time.sleep(0.03)
        except Exception as e:
            print(f"⚠ afplay falhou ({type(e).__name__})")
        finally:
            self._afplay_proc = None
            if caminho:
                try: os.unlink(caminho)
                except OSError: pass

    def _say_nativo_pcm(self, pcm: bytes) -> bool:
        return False

    def _say_nativo(self, texto: str) -> bool:
        """macOS: voz local em pt-BR. Grátis, offline, sotaque pior que a ElevenLabs."""
        if not shutil.which("say"):
            return False
        # Eddy é masculina pt-BR; a Luciana (feminina) era o padrão antigo — o João estranhou "voz feminina às vezes"
        subprocess.run(["say", "-v", os.environ.get("JAIME_SAY_VOZ", "Eddy (Português (Brasil))"), "-r", str(int(185 * self.velocidade)), texto],
                       check=False, stderr=subprocess.DEVNULL)
        return True
