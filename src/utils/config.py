# -*- coding: utf-8 -*-
"""Configuração central do projeto (lê variáveis de ambiente / arquivo .env)."""
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
REFERENCE_DIR = DATA_DIR / "reference"
PROCESSED_DIR = DATA_DIR / "processed"
LAKE_LOCAL_DIR = DATA_DIR / "lake"
LOGS_DIR = ROOT_DIR / "logs"


def _carregar_env(arquivo: Path = None) -> None:
    """Carrega variáveis de um arquivo .env simples (sem dependência externa).

    O .env do projeto tem precedência sobre variáveis herdadas do ambiente
    (evita conflito com variáveis genéricas de outros contextos). Variáveis
    exportadas com o prefixo HUOL_ têm precedência máxima sobre o .env.
    """
    arquivo = arquivo or ROOT_DIR / ".env"
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        chave, valor = chave.strip(), valor.strip().strip('"').strip("'")
        if chave:
            os.environ[chave] = valor


_carregar_env()


def _env(key: str, default: str = "") -> str:
    prefixada = os.getenv("HUOL_" + key)
    if prefixada:
        return prefixada
    valor = os.getenv(key)
    if valor is not None and valor != "":
        return valor
    return default


# ---------------------------------------------------------------- S3 / MinIO
STORAGE_BACKEND = _env("STORAGE_BACKEND", "S3").upper()          # S3 | LOCAL
S3_ENDPOINT = _env("S3_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = _env("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = _env("S3_SECRET_KEY", "minioadmin")
BUCKET_BRONZE = _env("S3_BUCKET_BRONZE", "bronze")
BUCKET_SILVER = _env("S3_BUCKET_SILVER", "silver")
BUCKET_GOLD = _env("S3_BUCKET_GOLD", "gold")

# ------------------------------------------------------------- PostgreSQL
DATABASE_URL = _env(
    "DATABASE_URL",
    "postgresql+psycopg2://huol:huol_secret@localhost:5432/huol_dw",
)

# ------------------------------------------------------------------- NLP
IG_ACCESS_TOKEN = _env("IG_ACCESS_TOKEN", "")
IG_USER_ID = _env("IG_USER_ID", "")
IG_API_VERSION = _env("IG_API_VERSION", "v21.0")
SENTIMENT_MODEL = _env("SENTIMENT_MODEL", "cardiffnlp/twitter-xlm-roberta-base-sentiment")
NLP_COMMENTS_INPUT = ROOT_DIR / _env("NLP_COMMENTS_INPUT", "data/nlp/comentarios_huol.csv")


def ensure_dirs() -> None:
    for d in (DATA_DIR, RAW_DIR, REFERENCE_DIR, PROCESSED_DIR, LAKE_LOCAL_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
