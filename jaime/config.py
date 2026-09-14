from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()

@dataclass
class Settings:
    root: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    model: str = _env("JAIME_MODEL", "sonnet")
    vault: Path = field(default_factory=lambda: Path(_env("JAIME_VAULT", "./vault")).expanduser().resolve())
    workspace: Path = field(default_factory=lambda: Path(_env("JAIME_WORKSPACE", "~/projetos")).expanduser())
    # voz
    picovoice_key: str = _env("PICOVOICE_ACCESS_KEY")
    wake_word: str = _env("JAIME_WAKE_WORD", "jarvis")
    wake_ppn: str = _env("JAIME_WAKE_PPN")
    deepgram_key: str = _env("DEEPGRAM_API_KEY")
    elevenlabs_key: str = _env("ELEVENLABS_API_KEY")
    elevenlabs_voice: str = _env("ELEVENLABS_VOICE_ID", "")
    # canais
    evolution_url: str = _env("EVOLUTION_API_URL")
    evolution_key: str = _env("EVOLUTION_API_KEY")
    evolution_instance: str = _env("EVOLUTION_INSTANCE", "jaime")
    owner_phone: str = _env("JAIME_OWNER_PHONE")
    server_token: str = _env("JAIME_SERVER_TOKEN", "troque-isto")

settings = Settings()
