"""Carregamento de configuração em camadas.

Precedência (maior primeiro):
    1. Variáveis de ambiente com prefixo ``AILA_`` (aninhamento com ``__``)
    2. ``config/local.yaml`` (não versionado, opcional)
    3. ``config/default.yaml`` (versionado)

Uso::

    from aila.core.config import get_settings
    settings = get_settings()
    print(settings.llm.model)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


# --------------------------------------------------------------------------- #
#  Sub-modelos de configuração
# --------------------------------------------------------------------------- #
class AppConfig(BaseModel):
    name: str = "Aila"
    persona: str = "Você é a Aila, uma assistente de IA local."


class LLMConfig(BaseModel):
    backend: str = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:7b-instruct"
    code_model: str = "deepseek-coder:6.7b"
    vision_model: str = "llava:7b"
    temperature: float = 0.7
    max_tokens: int = 2048
    keep_alive: str = "10m"
    timeout_seconds: int = 120


class ContextConfig(BaseModel):
    max_turns: int = 20
    summarize_after: int = 40


class SecurityConfig(BaseModel):
    read_only: bool = True
    confirm_destructive: bool = True
    sandbox_root: str = "./workspace"
    destructive_actions: list[str] = Field(default_factory=list)
    audit_log: str = "./logs/audit.jsonl"


class AgentsConfig(BaseModel):
    enabled: list[str] = Field(default_factory=lambda: ["file", "code"])
    disabled: list[str] = Field(default_factory=list)


class STTConfig(BaseModel):
    engine: str = "faster-whisper"
    model: str = "base"          # tiny | base | small | medium
    language: str = "pt"
    device: str = "auto"         # auto | cuda | cpu


class TTSConfig(BaseModel):
    engine: str = "auto"         # auto | sapi | piper
    voice: str = ""              # vazio = auto (voz pt-BR se disponível)
    rate: int = 0                # SAPI: -10 (lento) .. 10 (rápido)
    output_enabled: bool = True  # falar as respostas automaticamente


class VoiceConfig(BaseModel):
    enabled: bool = True
    stt: STTConfig = Field(default_factory=STTConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)


class AvatarConfig(BaseModel):
    enabled: bool = False
    transport: str = "websocket"
    default_emotion: str = "neutral"


class BinaryConfig(BaseModel):
    # Caminho da instalação do Ghidra (a pasta que contém support/analyzeHeadless).
    # Vazio = integração Ghidra desabilitada (triagem básica continua funcionando).
    ghidra_path: str = ""
    analysis_timeout: int = 600  # segundos (Ghidra é lento)


class MemoryConfig(BaseModel):
    enabled: bool = True
    embed_model: str = "nomic-embed-text"
    top_k: int = 4              # nº de memórias recuperadas por turno
    min_score: float = 0.55     # similaridade mínima (0-1) para injetar
    store_conversations: bool = True  # grava cada troca automaticamente
    db_path: str = "./data/memory.db"


# --------------------------------------------------------------------------- #
#  Settings raiz
# --------------------------------------------------------------------------- #
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AILA_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )

    app: AppConfig = Field(default_factory=AppConfig)
    host: str = "127.0.0.1"
    port: int = 8770
    log_level: str = "INFO"

    llm: LLMConfig = Field(default_factory=LLMConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    avatar: AvatarConfig = Field(default_factory=AvatarConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    binary: BinaryConfig = Field(default_factory=BinaryConfig)

    # ------------------------------------------------------------------ #
    def sandbox_path(self) -> Path:
        root = Path(self.security.sandbox_root)
        if not root.is_absolute():
            root = (PROJECT_ROOT / root).resolve()
        return root


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna a configuração efetiva (cacheada)."""
    data = _load_yaml(CONFIG_DIR / "default.yaml")
    data = _deep_merge(data, _load_yaml(CONFIG_DIR / "local.yaml"))
    # Pydantic-settings aplica os overrides de ambiente por cima do YAML.
    return Settings(**data)
