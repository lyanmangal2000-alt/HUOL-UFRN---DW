# -*- coding: utf-8 -*-
"""ETL — Camada BRONZE: ingestão dos arquivos do portal de dados abertos.

Preserva os arquivos CSV/PDF reconhecidos e disponíveis em data/raw, sem
alteração de conteúdo, no armazenamento S3-compatível ou no espelho local.
Este repositório inclui os 8 CSVs; os PDFs oficiais não são incluídos.
Cada arquivo ingerido gera um manifesto de proveniência (hash SHA-256,
tamanho, origem, período declarado e data de ingestão).

Execução (a partir da raiz do projeto):
    python -m src.etl.bronze_ingest

O processo é idempotente: arquivos com o mesmo hash já ingeridos são pulados.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

from ..utils import config
from ..utils.storage import agora_utc_iso, get_storage

log = logging.getLogger(__name__)

PAGINA_ORIGEM = (
    "https://www.gov.br/hubrasil/pt-br/hospitais-universitarios/regiao-nordeste/"
    "huol-ufrn/acesso-a-informacao/dados-abertos-1/06%20-%20Internacoes%20Hospitalares"
)

# período declarado no título do arquivo -> trimestre oficial
TRIMESTRES = {
    "JANFEVMAR": ("1º Trimestre", 1),
    "ABRMAIJUN": ("2º Trimestre", 2),
    "JULAGOSET": ("3º Trimestre", 3),
    "OUTNOVDEZ": ("4º Trimestre", 4),
}

SLUG_DOWNLOAD = {
    ("JanFevMar", "2024"): "janfevmar-de-2024",
    ("AbrMaiJun", "2024"): "abrmaijun-de-2024",
    ("JulAgoSet", "2024"): "julagoset-de-2024",
    ("OutNovDez", "2024"): "outnovdez-de-2024",
    ("JanFevMar", "2025"): "janfevmar-de-2025",
    ("AbrMaiJun", "2025"): "AbrMaiJun-de-2025",
    ("JulAgoSet", "2025"): "julagoset-de-2025",
    ("OutNovDez", "2025"): "outnovdez-de-2025",
}

PADRAO_NOME = re.compile(
    r"Interna.+Hospitalares \(Referencia_ (?P<periodo>JanFevMar|AbrMaiJun|JulAgoSet|OutNovDez) de (?P<ano>\d{4})\)\.(?P<ext>csv|pdf)$",
    re.IGNORECASE,
)


def hash_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ler_csv_provisorio(data: bytes) -> dict:
    """Metadados de auditoria do CSV sem interpretar conteúdo (nº de linhas, cabeçalho)."""
    text = data.decode("latin-1")
    linhas = [ln for ln in text.splitlines() if ln.strip()]
    return {
        "cabecalho_bruto": linhas[0] if linhas else "",
        "qtd_linhas_incluindo_cabecalho": len(linhas),
        "qtd_registros_estimada": max(len(linhas) - 1, 0),
    }


def ingerir_arquivo(storage, path: Path) -> dict | None:
    match = PADRAO_NOME.search(path.name)
    if not match:
        log.warning("Arquivo fora do padrão esperado, ignorado: %s", path.name)
        return None
    periodo, ano, ext = match.group("periodo"), match.group("ano"), match.group("ext").lower()
    trimestre, trimestre_num = TRIMESTRES[periodo.upper()]

    data = path.read_bytes()
    sha = hash_sha256(data)

    ano_dir = ano
    key = f"hospital/{ano_dir}/{trimestre_num:02d}_{periodo}/{path.name}"
    bucket = config.BUCKET_BRONZE

    if storage.exists(bucket, key):
        existente = storage.get_bytes(bucket, key)
        if hash_sha256(existente) == sha:
            log.info("Já ingerido (hash idêntico), pulando: %s", key)
            reingestao = False
        else:
            reingestao = True
    else:
        reingestao = False

    uri = storage.put_bytes(bucket, key, data)

    manifest = {
        "arquivo": path.name,
        "bucket": bucket,
        "chave": key,
        "uri": uri,
        "formato": ext,
        "hash_sha256": sha,
        "tamanho_bytes": len(data),
        "ano_referencia": int(ano),
        "periodo_declarado": f"{periodo} de {ano}",
        "trimestre": trimestre,
        "trimestre_num": trimestre_num,
        "origem_pagina": PAGINA_ORIGEM,
        "origem_download": (
            f"{PAGINA_ORIGEM}/06-internacoes-hospitalares-referencia_-"
            f"{SLUG_DOWNLOAD[(periodo, ano)]}.{ext}/@@download/file"
        ),
        "data_ingestao_utc": agora_utc_iso(),
        "camada": "bronze",
        "transformacoes": "nenhuma — cópia fiel do arquivo original",
        "reingestao_com_hash_diferente": reingestao,
    }
    if ext == "csv":
        manifest.update(ler_csv_provisorio(data))
    storage.put_json(
        bucket,
        f"manifests/bronze_{ano}_{trimestre_num:02d}_{periodo}_{ext}.json",
        manifest,
    )
    log.info("Bronze OK: %s (%d bytes, sha256=%s...)", key, len(data), sha[:12])
    return manifest


def executar(raw_dir: Path | None = None) -> list[dict]:
    config.ensure_dirs()
    storage = get_storage()
    raw_dir = Path(raw_dir or config.RAW_DIR)
    manifests = [m for m in (ingerir_arquivo(storage, p) for p in sorted(raw_dir.iterdir())) if m]
    resumo = {
        "camada": "bronze",
        "total_arquivos": len(manifests),
        "csv": sum(1 for m in manifests if m["formato"] == "csv"),
        "pdf": sum(1 for m in manifests if m["formato"] == "pdf"),
        "total_registros_estimado": sum(m.get("qtd_registros_estimada", 0) for m in manifests),
        "executado_em_utc": agora_utc_iso(),
        "arquivos": manifests,
    }
    storage.put_json(config.BUCKET_BRONZE, "manifests/bronze_resumo.json", resumo)
    log.info("Bronze concluída: %d arquivos ingeridos", len(manifests))
    return manifests


if __name__ == "__main__":
    from ..utils.logging_config import configurar_logging

    configurar_logging()
    executar()
