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
    vault: Path = field(default_factory=lambda: Path(_env("JAIME_VAULT", "./vault")).expanduser().resolve())
    workspace: Path = field(default_factory=lambda: Path(_env("JAIME_WORKSPACE", "~/projetos")).expanduser())
    # voz
    picovoice_key: str = _env("PICOVOICE_ACCESS_KEY")
    wake_word: str = _env("JAIME_WAKE_WORD", "jarvis")
    wake_ppn: str = _env("JAIME_WAKE_PPN")
    deepgram_key: str = _env("DEEPGRAM_API_KEY")
    elevenlabs_key: str = _env("ELEVENLABS_API_KEY")
    elevenlabs_voice: str = _env("ELEVENLABS_VOICE_ID", "")
    voz: str = _env("JAIME_VOZ", "on")                        # on = microfone ligado junto com o HUD; off = só texto
    whisper_modelo: str = _env("JAIME_WHISPER_MODELO", "base")   # small é mais preciso, mas 3,6 s por frase em CPU Intel; base ~1 s
    ativacao: str = _env("JAIME_ATIVACAO", "nome")            # nome = só responde a "Jaime, …"; sempre = responde a tudo
    nome: str = _env("JAIME_NOME", "jaime")
    janela_ativa_s: int = int(_env("JAIME_JANELA_ATIVA_S", "90"))   # depois de chamado, segue a conversa sem o nome
    # canais
    evolution_url: str = _env("EVOLUTION_API_URL")
    evolution_key: str = _env("EVOLUTION_API_KEY")
    evolution_instance: str = _env("EVOLUTION_INSTANCE", "jaime")
    owner_phone: str = _env("JAIME_OWNER_PHONE")
    server_token: str = _env("JAIME_SERVER_TOKEN", "troque-isto")
    bind: str = _env("JAIME_BIND", "127.0.0.1")     # só local por padrão
    port: int = int(_env("JAIME_PORT", "8787"))
    # acesso ao cérebro (palavra-passe falada ou digitada) — hash SHA-256 de "12341234" por padrão
    passphrase_hash: str = _env("JAIME_PASSPHRASE_HASH", "1718c24b10aeb8099e3fc44960ab6949ab76a267352459f203ea1036bec382c2")
    acesso_timeout_min: int = int(_env("JAIME_ACESSO_TIMEOUT_MIN", "30"))
    thinking_tokens: int = int(_env("JAIME_THINKING_TOKENS", "1500"))   # 4000 deixava a resposta por voz lenta
    # cérebro compartilhado (Notion)
    notion_token: str = _env("NOTION_TOKEN")
    notion_root: str = _env("NOTION_ROOT_PAGE_ID", "3db6fab2-88b8-8180-bbe0-dfd72b7f58ff")
    notion_db_diario: str = _env("NOTION_DB_DIARIO", "4f742e96b84140c0a475f857d0d95502")
    notion_db_tarefas: str = _env("NOTION_DB_TAREFAS", "52224d3a0f6d40f0a4e46eaee885c074")
    notion_db_conversas: str = _env("NOTION_DB_CONVERSAS", "714d55db72a3428db267940cdf7ba757")

settings = Settings()
