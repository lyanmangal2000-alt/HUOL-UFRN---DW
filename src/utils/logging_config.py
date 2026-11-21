# -*- coding: utf-8 -*-
"""Configuração de logging compartilhada pelos módulos do pipeline."""
import logging
import sys

from . import config

_FORMATO = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def configurar_logging(nivel: int = logging.INFO) -> None:
    config.ensure_dirs()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    handlers = [logging.StreamHandler(sys.stdout)]
    handlers.append(logging.FileHandler(config.LOGS_DIR / "pipeline.log", encoding="utf-8"))
    logging.basicConfig(level=nivel, format=_FORMATO, handlers=handlers, force=True)
