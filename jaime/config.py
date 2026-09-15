from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def _env(name: str, default: str = "") -> str:
    """Variável ausente OU vazia no .env cai no default — um `X=` no arquivo não deve
    apagar um default sensato (foi o que derrubou o JAIME_PASSPHRASE_HASH no primeiro boot)."""
    return os.environ.get(name, "").strip() or default

@dataclass
class Settings:
    root: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    model: str = _env("JAIME_MODEL", "claude-opus-5")
    # Córtex: quem pensa em cada tipo de tarefa (jaime/cortex/roteador.py)
    model_decisao: str = _env("JAIME_MODEL_DECISAO", "claude-fable-5-1")
    model_codigo: str = _env("JAIME_MODEL_CODIGO", "claude-opus-5")
    model_padrao: str = _env("JAIME_MODEL_PADRAO", "claude-sonnet-5")
    model_rotina: str = _env("JAIME_MODEL_ROTINA", "claude-haiku-4-5-20251001")
    cortex_exploracao: float = float(_env("JAIME_CORTEX_EXPLORACAO", "0.10"))
    # OpenAI como segundo provedor (texto, decisão, imagem, voz) — ações no mundo continuam pela Anthropic
    openai_key: str = _env("OPENAI_API_KEY")
    openai_model: str = _env("JAIME_OPENAI_MODEL", "gpt-5.5")
    openai_model_rapido: str = _env("JAIME_OPENAI_MODEL_RAPIDO", "gpt-5.6-luna")
    openai_uso: str = _env("JAIME_OPENAI_USO", "minimo")      # minimo = só voz/imagem e "pensa bem" explícito; normal = roteador e juiz
    vault: Path = field(default_factory=lambda: Path(_env("JAIME_VAULT", "./vault")).expanduser().resolve())
    workspace: Path = field(default_factory=lambda: Path(_env("JAIME_WORKSPACE", "~/projetos")).expanduser())
    # onde o João está (clima, fuso): Franca/SP por padrão
    lat: float = float(_env("JAIME_LAT", "-20.5386"))
    lon: float = float(_env("JAIME_LON", "-47.4008"))
    # voz
    picovoice_key: str = _env("PICOVOICE_ACCESS_KEY")
    wake_word: str = _env("JAIME_WAKE_WORD", "jarvis")
    wake_ppn: str = _env("JAIME_WAKE_PPN")
    deepgram_key: str = _env("DEEPGRAM_API_KEY")
    elevenlabs_key: str = _env("ELEVENLABS_API_KEY")
    elevenlabs_voice: str = _env("ELEVENLABS_VOICE_ID", "")
    voz: str = _env("JAIME_VOZ", "on")                        # on = microfone ligado junto com o HUD; off = só texto
    voz_modo: str = _env("JAIME_VOZ_MODO", "duplex")          # duplex (STT streaming + antecipador + barge-in) | pipeline (turno a turno) | conversa (Realtime fala-para-fala)
    stt_stream: str = _env("JAIME_STT_STREAM", "auto")        # deepgram | openai | local | auto
    antecipador_model: str = _env("JAIME_ANTECIPADOR_MODEL", "")   # vazio = JAIME_OPENAI_MODEL_RAPIDO; "off" = só heurística
    barge_in: str = _env("JAIME_BARGE_IN", "on")              # on | off | fone (sem guarda de eco)
    voz_velocidade: float = float(_env("JAIME_VOZ_VELOCIDADE", "1.15"))
    realtime_model: str = _env("JAIME_REALTIME_MODEL", "gpt-realtime-2")
    realtime_voz: str = _env("JAIME_REALTIME_VOZ", "cedar")
    whisper_modelo: str = _env("JAIME_WHISPER_MODELO", "base")   # small é mais preciso, mas 3,6 s por frase em CPU Intel; base ~1 s
    ativacao: str = _env("JAIME_ATIVACAO", "nome")            # nome = só responde a "Jaime, …"; sempre = responde a tudo
    nome: str = _env("JAIME_NOME", "jaime")
    janela_ativa_s: int = int(_env("JAIME_JANELA_ATIVA_S", "25"))   # depois de chamado, segue a conversa sem o nome (90 pegava a sala inteira)
    # canais
    evolution_url: str = _env("EVOLUTION_API_URL")
    evolution_key: str = _env("EVOLUTION_API_KEY")
    evolution_instance: str = _env("EVOLUTION_INSTANCE", "jaime")
    owner_phone: str = _env("JAIME_OWNER_PHONE")
    server_token: str = _env("JAIME_SERVER_TOKEN", "troque-isto")
    # conexões (fase 2, etapa 8)
    google_client_secret: Path = field(default_factory=lambda: Path(_env("GOOGLE_CLIENT_SECRET_FILE", "~/Jaime/google-client-secret.json")).expanduser())
    google_token: Path = field(default_factory=lambda: Path(_env("GOOGLE_TOKEN_FILE", "~/Jaime/google-token.json")).expanduser())
    telegram_token: str = _env("TELEGRAM_BOT_TOKEN")
    ha_url: str = _env("HA_URL", "http://homeassistant.local:8123").rstrip("/")
    ha_token: str = _env("HA_TOKEN")
    camera: str = _env("JAIME_CAMERA", "0")
    visao_max_passos: int = int(_env("JAIME_VISAO_MAX_PASSOS", "60"))
    visao_intervalo_s: float = float(_env("JAIME_VISAO_INTERVALO_S", "2"))
    meta_token: str = _env("META_ACCESS_TOKEN")
    meta_app_secret: str = _env("META_APP_SECRET")
    meta_verify_token: str = _env("META_VERIFY_TOKEN", "troque-isto-tambem")
    meta_whatsapp_phone_id: str = _env("META_WHATSAPP_PHONE_ID")
    meta_instagram_id: str = _env("META_INSTAGRAM_ACCOUNT_ID")
    # modo autônomo
    autonomo_horas: float = float(_env("JAIME_AUTONOMO_HORAS", "2"))
    autonomo_custo_usd: float = float(_env("JAIME_AUTONOMO_CUSTO_USD", "5"))
    autonomo_ferramentas: str = _env("JAIME_AUTONOMO_FERRAMENTAS", "Read,Write,Edit,Bash,Glob,Grep,WebSearch,WebFetch")
    owner_telegram_id: str = _env("JAIME_OWNER_TELEGRAM_ID")
    bind: str = _env("JAIME_BIND", "127.0.0.1")     # só local por padrão
    port: int = int(_env("JAIME_PORT", "8787"))
    # acesso ao cérebro (palavra-passe falada ou digitada) — hash SHA-256 de "12341234" por padrão
    passphrase_hash: str = _env("JAIME_PASSPHRASE_HASH", "1718c24b10aeb8099e3fc44960ab6949ab76a267352459f203ea1036bec382c2")
    acesso_timeout_min: int = int(_env("JAIME_ACESSO_TIMEOUT_MIN", "30"))
    thinking_tokens: int = int(_env("JAIME_THINKING_TOKENS", "0"))   # 0 = sem pensamento estendido: por voz, cada segundo conta
    # cérebro compartilhado (Notion)
    notion_token: str = _env("NOTION_TOKEN")
    notion_root: str = _env("NOTION_ROOT_PAGE_ID", "3db6fab2-88b8-8180-bbe0-dfd72b7f58ff")
    notion_db_diario: str = _env("NOTION_DB_DIARIO", "4f742e96b84140c0a475f857d0d95502")
    notion_db_tarefas: str = _env("NOTION_DB_TAREFAS", "52224d3a0f6d40f0a4e46eaee885c074")
    notion_db_conversas: str = _env("NOTION_DB_CONVERSAS", "714d55db72a3428db267940cdf7ba757")

settings = Settings()
