"""Configuração central de logs via loguru."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from aila.core.config import PROJECT_ROOT

_CONFIGURED = False


def setup_logging(level: str = "INFO") -> None:
    """Configura sinks de console e arquivo. Idempotente."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        colorize=True,
        format=(
            "<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | "
            "<cyan>{extra[mod]}</cyan> | <level>{message}</level>"
        ),
    )

    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "aila.log",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {extra[mod]} | {message}",
    )

    logger.configure(extra={"mod": "aila"})
    _CONFIGURED = True


def get_logger(module: str):
    """Retorna um logger contextualizado com o nome do módulo."""
    return logger.bind(mod=module)
