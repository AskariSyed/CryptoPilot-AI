"""Rotating application logging configuration."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(
    level: str = "INFO",
    log_path: str = "logs/cryptopilot.log",
    max_bytes: int = 10_000_000,
    backup_count: int = 5,
) -> None:
    """Configure console and rotating file handlers without duplicating them."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    if root.handlers:
        return

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rotating = RotatingFileHandler(
        path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    rotating.setFormatter(formatter)
    root.addHandler(rotating)
