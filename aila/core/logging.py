"""Configuração central de logs via loguru."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from loguru import logger

from aila.core.config import DATA_ROOT

_CONFIGURED = False
_LOG_RETENTION_SECONDS = 7 * 24 * 60 * 60


def _process_log_path(log_dir: Path, pid: int | None = None) -> Path:
    """Retorna um arquivo exclusivo por processo.

    No Windows, dois processos não conseguem rotacionar com segurança o mesmo
    arquivo aberto. Isso ocorre principalmente entre reinícios do Uvicorn e
    instâncias antigas ainda encerrando.
    """
    process_id = os.getpid() if pid is None else pid
    return log_dir / f"aila-{process_id}.log"


def _prune_stale_process_logs(log_dir: Path, *, now: float | None = None) -> None:
    """Remove logs de processos encerrados que excederam a retenção.

    Arquivos ainda bloqueados são simplesmente mantidos para uma próxima
    inicialização. A rotina de logging nunca deve impedir a Aila de iniciar.
    """
    cutoff = (time.time() if now is None else now) - _LOG_RETENTION_SECONDS
    current = _process_log_path(log_dir)
    for path in log_dir.glob("aila-*.log*"):
        try:
            if path != current and path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            continue


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

    log_dir = DATA_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    _prune_stale_process_logs(log_dir)
    try:
        logger.add(
            _process_log_path(log_dir),
            level="DEBUG",
            rotation="10 MB",
            retention="7 days",
            encoding="utf-8",
            enqueue=True,
            catch=True,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {extra[mod]} | {message}",
        )
    except OSError as exc:
        # O console continua disponível mesmo se o diretório estiver bloqueado.
        logger.bind(mod="logging").warning(f"Log em arquivo indisponível: {exc}")

    logger.configure(extra={"mod": "aila"})
    _CONFIGURED = True


def get_logger(module: str):
    """Retorna um logger contextualizado com o nome do módulo."""
    return logger.bind(mod=module)
