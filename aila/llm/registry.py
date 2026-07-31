"""Fábrica de backends de LLM a partir da configuração."""

from __future__ import annotations

from aila.core.config import LLMConfig
from aila.llm.base import LLMBackend
from aila.llm.ollama_backend import OllamaBackend


def get_backend(cfg: LLMConfig) -> LLMBackend:
    """Instancia o backend indicado em ``cfg.backend``."""
    if cfg.backend == "ollama":
        return OllamaBackend(
            base_url=cfg.base_url,
            default_model=cfg.model,
            keep_alive=cfg.keep_alive,
            timeout=cfg.timeout_seconds,
        )
    if cfg.backend == "llamacpp":
        # Fase futura: servidor llama.cpp (compatível com API OpenAI).
        raise NotImplementedError(
            "Backend llama.cpp ainda não implementado. Use 'ollama' por enquanto. "
            "Veja docs/ROADMAP.md."
        )
    raise ValueError(f"Backend de LLM desconhecido: {cfg.backend!r}")
