"""Rotating file logger factory."""
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

from config import LOG_DIR


def get_logger(name: str) -> logging.Logger:
    """Return a configured rotating-file logger."""
    logger = logging.getLogger(name)
    if getattr(logger, "_configured", False):
        return logger
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    fh = RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    logger._configured = True  # type: ignore[attr-defined]
    return logger
