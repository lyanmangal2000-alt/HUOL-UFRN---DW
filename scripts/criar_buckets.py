# -*- coding: utf-8 -*-
"""Cria os buckets bronze/silver/gold no armazenamento configurado (MinIO).

Uso: python scripts/criar_buckets.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.logging_config import configurar_logging  # noqa: E402
from src.utils.storage import get_storage  # noqa: E402

if __name__ == "__main__":
    configurar_logging()
    storage = get_storage()
    print("Buckets garantidos (bronze, silver, gold).")
