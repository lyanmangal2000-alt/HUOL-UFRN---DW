# -*- coding: utf-8 -*-
"""Camada de armazenamento do Data Lake.

Abstrai o armazenamento compatível com S3 (MinIO em produção; SeaweedFS validado
no ambiente de desenvolvimento) e um espelho em sistema de arquivos local
(fallback para execução sem infraestrutura de rede).

Mesma semântica de chaves nos dois modos, garantindo reprodutibilidade:
  <bucket>/<chave>            ->  S3        (boto3)
  DATA_LAKE_DIR/<bucket>/<chave> -> LOCAL   (disco)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import config

log = logging.getLogger(__name__)


class LocalStorage:
    """Espelho em disco com a mesma estrutura de buckets do S3."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root or config.LAKE_LOCAL_DIR)

    def _path(self, bucket: str, key: str) -> Path:
        return self.root / bucket / key

    def put_bytes(self, bucket: str, key: str, data: bytes) -> str:
        path = self._path(bucket, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"local://{bucket}/{key}"

    def put_json(self, bucket: str, key: str, obj) -> str:
        payload = json.dumps(obj, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        return self.put_bytes(bucket, key, payload)

    def get_bytes(self, bucket: str, key: str) -> bytes:
        return self._path(bucket, key).read_bytes()

    def exists(self, bucket: str, key: str) -> bool:
        return self._path(bucket, key).exists()

    def list_keys(self, bucket: str, prefix: str = "") -> list[str]:
        base = self._path(bucket, prefix)
        if not base.exists():
            return []
        return [
            p.relative_to(self.root / bucket).as_posix()
            for p in sorted(base.rglob("*"))
            if p.is_file()
        ]


class S3Storage:
    """Armazenamento S3 real (MinIO, SeaweedFS ou qualquer API S3 compatível)."""

    def __init__(self) -> None:
        import boto3  # import tardio para permitir execução sem boto3 no modo LOCAL

        self.client = boto3.client(
            "s3",
            endpoint_url=config.S3_ENDPOINT,
            aws_access_key_id=config.S3_ACCESS_KEY,
            aws_secret_access_key=config.S3_SECRET_KEY,
            region_name="us-east-1",
        )
        self._ensure_buckets()

    def _ensure_buckets(self) -> None:
        existing = {b["Name"] for b in self.client.list_buckets().get("Buckets", [])}
        for bucket in (config.BUCKET_BRONZE, config.BUCKET_SILVER, config.BUCKET_GOLD):
            if bucket not in existing:
                self.client.create_bucket(Bucket=bucket)
                log.info("Bucket criado: %s", bucket)

    def put_bytes(self, bucket: str, key: str, data: bytes) -> str:
        self.client.put_object(Bucket=bucket, Key=key, Body=data)
        return f"s3://{bucket}/{key}"

    def put_json(self, bucket: str, key: str, obj) -> str:
        payload = json.dumps(obj, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        return self.put_bytes(bucket, key, payload)

    def get_bytes(self, bucket: str, key: str) -> bytes:
        resp = self.client.get_object(Bucket=bucket, Key=key)
        return resp["Body"].read()

    def exists(self, bucket: str, key: str) -> bool:
        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False

    def list_keys(self, bucket: str, prefix: str = "") -> list[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return sorted(keys)


def get_storage():
    """Fábrica de armazenamento conforme STORAGE_BACKEND (S3 ou LOCAL)."""
    if config.STORAGE_BACKEND == "S3":
        log.info("Armazenamento: S3 em %s", config.S3_ENDPOINT)
        return S3Storage()
    log.info("Armazenamento: espelho local em %s", config.LAKE_LOCAL_DIR)
    return LocalStorage()


def agora_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
