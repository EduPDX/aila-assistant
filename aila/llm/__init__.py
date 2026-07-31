"""Backends de modelos de linguagem (Ollama, llama.cpp, GGUF)."""

from aila.llm.base import ChatChunk, LLMBackend
from aila.llm.registry import get_backend

__all__ = ["LLMBackend", "ChatChunk", "get_backend"]
