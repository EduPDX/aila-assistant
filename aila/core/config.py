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

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

# Camada YAML preenchida por get_settings() e lida pela fonte de config abaixo.
_YAML_LAYER: dict[str, Any] = {}


class _YamlSource(PydanticBaseSettingsSource):
    """Fonte de configuração que injeta o YAML mesclado (default + local).

    Fica ABAIXO das variáveis de ambiente na precedência, então o ambiente
    (e o .env) de fato sobrescreve o YAML.
    """

    def get_field_value(self, field, field_name):  # noqa: ANN001 - assinatura do pydantic
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return _YAML_LAYER

if getattr(sys, "frozen", False):
    # Empacotado (PyInstaller): dados de LEITURA (config/, ui/) vêm do bundle;
    # dados de ESCRITA (data/, logs/, workspace/, models) vão para uma pasta
    # gravável do usuário.
    PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    DATA_ROOT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Aila"
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    DATA_ROOT = PROJECT_ROOT

DATA_ROOT.mkdir(parents=True, exist_ok=True)
CONFIG_DIR = PROJECT_ROOT / "config"


def data_path(rel: str) -> Path:
    """Resolve um caminho de ESCRITA sob a raiz gravável (DATA_ROOT)."""
    p = Path(rel)
    return p if p.is_absolute() else (DATA_ROOT / p)


# --------------------------------------------------------------------------- #
#  Sub-modelos de configuração
# --------------------------------------------------------------------------- #
class AppConfig(BaseModel):
    name: str = "Aila"
    persona: str = "Você é a Aila, uma assistente de IA local."
    # Ao abrir: começar com o chat VAZIO (True) ou RETOMAR a última conversa
    # (False). Vazio evita que um histórico antigo/confuso contamine o modelo.
    fresh_chat_on_start: bool = True


class LLMConfig(BaseModel):
    backend: str = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:7b-instruct"
    code_model: str = "deepseek-coder:6.7b"
    vision_model: str = "llava:7b"
    temperature: float = 0.7
    max_tokens: int = 2048
    num_ctx: int = 8192          # janela de contexto (Ollama usa 2048 por padrão!)
    keep_alive: str = "10m"
    timeout_seconds: int = 120


class ContextConfig(BaseModel):
    max_turns: int = 20
    summarize_after: int = 40
    # Gestão de janela p/ num_ctx pequeno: fração do num_ctx (em chars ~3.5/token)
    # gasta com o histórico de mensagens; o resto fica p/ schemas de tools + resposta.
    window_budget_ratio: float = 0.5
    # quantos resultados de ferramenta RECENTES manter íntegros (os antigos, já
    # usados, são compactados p/ caber sem truncar o system prompt/plano).
    keep_recent_tools: int = 4


class SecurityConfig(BaseModel):
    read_only: bool = True
    confirm_destructive: bool = True    # ações DANGER pedem confirmação
    confirm_review: bool = False        # ações REVIEW pedem confirmação (default: não)
    sandbox_root: str = "./workspace"
    # pastas EXTRA onde a Aila pode ESCREVER além do workspace (ex.: "~/Documents").
    # Vazio = escrita só no workspace (padrão seguro). Aceita ~ e caminhos absolutos.
    write_roots: list[str] = Field(default_factory=list)
    destructive_actions: list[str] = Field(default_factory=list)  # → nível DANGER
    audit_log: str = "./logs/audit.jsonl"
    # ----- Fase 6: níveis de permissão + autonomia -----
    autonomy_level: int = 3             # 1..5 (ver docs). Default preserva o atual.
    blocked_actions: list[str] = Field(default_factory=list)      # nunca executadas
    action_levels: dict[str, str] = Field(default_factory=dict)   # override: ação→nível
    min_autonomy: dict[str, int] = Field(default_factory=dict)    # override: prefixo→nível
    # ----- Fase 10: hardening -----
    tool_timeout: float = 180.0         # backstop global por tool (0 = desliga)
    max_tool_calls: int = 40            # orçamento de tools por tarefa autônoma (subir p/ análises profundas)
    max_repeated_calls: int = 3         # mesma tool+args repetida N vezes = loop
    command_denylist: list[str] = Field(default_factory=list)  # regex extra p/ terminal
    command_allowlist: list[str] = Field(default_factory=list)  # prefixos seguros extra
    # ----- Fase 7: guardrails (trilho de saída — redação de segredos) -----
    guardrails: bool = True             # redige segredos vazados na resposta final


class AgentsConfig(BaseModel):
    enabled: list[str] = Field(default_factory=lambda: ["file", "code"])
    disabled: list[str] = Field(default_factory=list)


class STTConfig(BaseModel):
    engine: str = "faster-whisper"
    model: str = "base"          # tiny | base | small | medium
    language: str = "pt"
    device: str = "auto"         # auto | cuda | cpu


class TTSConfig(BaseModel):
    engine: str = "auto"         # auto | edge | sapi | piper
    voice: str = ""              # vazio = auto; p/ edge: ex. "pt-BR-FranciscaNeural"
    rate: int = 0                # SAPI: -10 (lento) .. 10 (rápido)
    edge_pitch: str = "+0Hz"     # Edge-TTS: tom (ex.: "+30Hz" = mais fino/anime)
    edge_rate: str = "+0%"       # Edge-TTS: velocidade (ex.: "+10%")
    output_enabled: bool = True  # falar as respostas automaticamente


class VoiceConfig(BaseModel):
    enabled: bool = True
    stt: STTConfig = Field(default_factory=STTConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)


class AvatarConfig(BaseModel):
    enabled: bool = False
    # websocket = avatar do navegador; osc = motor 3D (Unreal); both = os dois
    transport: str = "websocket"
    osc_host: str = "127.0.0.1"
    osc_port: int = 8000
    default_emotion: str = "neutral"
    # --- Unreal via Remote Control (sem OSC/Blueprint) ---
    unreal_enabled: bool = False
    unreal_rc_url: str = "http://127.0.0.1:30010"
    unreal_mesh_path: str = ""   # object path do componente de malha no nível
    unreal_anim_base: str = "/Game/CiciToonCharacterShaderPak/Character/Hayakawa/Anim/"
    unreal_mouth_morph: str = ""  # morph da boca p/ lip-sync (ex.: "A"); vazio = sem lip-sync


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
class NetworkConfig(BaseModel):
    # "hybrid" = permite serviços online (pesquisa, APIs externas, TTS neural).
    # "offline" = nada sai do PC (só modelos/ferramentas locais).
    mode: str = "hybrid"


class RoutingConfig(BaseModel):
    """Regras do Model Router (qual provedor por tipo de tarefa).

    ``enabled: false`` = sempre o provedor padrão (passthrough, comportamento
    atual). Quando ligado, ``rules`` mapeia o tipo de tarefa (chat/code/vision/
    reasoning) para uma ORDEM de provedores preferidos (fallback). "local" é o
    provedor padrão local. Nomes desconhecidos/indisponíveis são pulados.
    """

    enabled: bool = False
    default: str = "local"
    rules: dict[str, list[str]] = Field(default_factory=dict)


class ProviderConfig(BaseModel):
    """Provedor externo de LLM (compatível com a API OpenAI).

    Só ``enabled`` + ``api_key`` são necessários; base_url/modelo/capacidades
    têm defaults por provedor no código (aila/llm/openai_compat.py) — os campos
    abaixo são OVERRIDES opcionais (vazio/0 = usa o default do provedor).

    A ``api_key`` NUNCA deve ficar no default.yaml (versionado). Use env:
    ``AILA_PROVIDERS__OPENAI__API_KEY=...`` ou config/local.yaml (gitignored).
    """

    enabled: bool = False
    api_key: str = ""
    model: str = ""       # vazio → default do provedor
    base_url: str = ""    # vazio → default do provedor
    vision: bool = False  # só força True; o default do provedor pode já ser True
    context: int = 0      # 0 → default do provedor


class ProvidersConfig(BaseModel):
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    grok: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    nvidia: ProviderConfig = Field(default_factory=ProviderConfig)

    def items(self) -> list[tuple[str, ProviderConfig]]:
        return [("openai", self.openai), ("gemini", self.gemini),
                ("grok", self.grok), ("deepseek", self.deepseek),
                ("nvidia", self.nvidia)]


class MCPServerConfig(BaseModel):
    """Servidor MCP externo via stdio. ``command``+``args`` iniciam o processo."""
    name: str = ""
    command: str = ""                        # ex.: "npx", "python", "uvx"
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class SkillsConfig(BaseModel):
    """Receitas nomeadas (skill.<nome>) que compõem tools existentes. Embutidas
    sempre disponíveis; ``dir`` aponta p/ skills externas .yaml opcionais."""
    enabled: bool = True
    dir: str = "./skills"


class MCPConfig(BaseModel):
    """Conecta servidores MCP externos como ferramentas (opt-in, offline-safe).

    ``enabled: false`` (default) = nada conecta; comportamento atual intacto.
    Cada tool externa vira ``mcp.<servidor>.<tool>`` e SEMPRE passa por
    ``authorize()`` (nível REVIEW/L2 por padrão — não são leituras)."""
    enabled: bool = False
    servers: list[MCPServerConfig] = Field(default_factory=list)
    startup_timeout: float = 20.0            # p/ conectar + listar tools
    call_timeout: float = 60.0               # p/ cada tools/call


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
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    avatar: AvatarConfig = Field(default_factory=AvatarConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    binary: BinaryConfig = Field(default_factory=BinaryConfig)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # Precedência (maior primeiro): init > env > .env > YAML > secrets.
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            _YamlSource(settings_cls),
            file_secret_settings,
        )

    # ------------------------------------------------------------------ #
    def sandbox_path(self) -> Path:
        root = Path(self.security.sandbox_root)
        if not root.is_absolute():
            root = (DATA_ROOT / root).resolve()
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


def writable_local_yaml() -> Path:
    """Arquivo de overrides GRAVÁVEL (onde a UI salva chaves/preferências).

    Em dev é o próprio ``config/local.yaml``. No ``.exe`` empacotado o ``config/``
    do bundle é somente-leitura, então vai para a pasta gravável do usuário.
    """
    if getattr(sys, "frozen", False):
        return DATA_ROOT / "local.yaml"
    return CONFIG_DIR / "local.yaml"


def update_local_yaml(patch: dict[str, Any]) -> Path:
    """Mescla ``patch`` no local.yaml gravável (preserva o resto). Usado para
    persistir configurações da UI (ex.: chaves de API dos provedores)."""
    path = writable_local_yaml()
    merged = _deep_merge(_load_yaml(path), patch)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(merged, fh, allow_unicode=True, sort_keys=False)
    return path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna a configuração efetiva (cacheada).

    Camadas (maior precedência primeiro): variáveis de ambiente ``AILA_*`` e
    ``.env`` > ``config/local.yaml`` (+ overrides graváveis no .exe) > ``config/default.yaml``.
    """
    global _YAML_LAYER
    data = _load_yaml(CONFIG_DIR / "default.yaml")
    _YAML_LAYER = _deep_merge(data, _load_yaml(CONFIG_DIR / "local.yaml"))
    if getattr(sys, "frozen", False):   # overrides graváveis do usuário (.exe)
        _YAML_LAYER = _deep_merge(_YAML_LAYER, _load_yaml(DATA_ROOT / "local.yaml"))
    return Settings()
