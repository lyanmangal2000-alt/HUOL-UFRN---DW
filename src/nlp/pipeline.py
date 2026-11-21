# -*- coding: utf-8 -*-
"""Execução do módulo NLP completo (limpeza -> sentimentos -> temas).

Entrada: CSV de comentários em data/nlp/comentarios_huol.csv com colunas
    id_comentario, texto, data, autor (opcional), curtidas, id_publicacao
  (formato produzido por src.nlp.instagram_client quando a Graph API está
   autorizada, ou amostra legítima disponibilizada pelo hospital).

Saída (bucket Ouro + data/processed):
    nlp_comentarios.parquet     — comentários + texto original + limpo + sentimento
    nlp_resumo_sentimentos.parquet
    nlp_termos.parquet          — TF-IDF por sentimento
    relatorio_nlp.json          — modelo, limitações, rastreabilidade

POLÍTICA ANTI-SIMULAÇÃO: sem arquivo de comentários reais, o pipeline não
produz resultados fictícios — grava apenas o relatório de indisponibilidade.
"""
from __future__ import annotations

import io
import json
import logging

import pandas as pd

from ..utils import config
from ..utils.storage import agora_utc_iso, get_storage
from .clean_text import contar_emojis, limpar_texto
from .sentiment import analisar_sentimentos, info_modelo, resumo_sentimentos
from .topics import extrair_termos

log = logging.getLogger(__name__)

COLUNAS_ESPERADAS = ["id_comentario", "texto", "data"]


def executar(caminho_entrada=None, storage=None) -> dict:
    config.ensure_dirs()
    storage = storage or get_storage()
    caminho_entrada = caminho_entrada or config.NLP_COMMENTS_INPUT

    if not caminho_entrada.exists():
        relatorio = {
            "status": "INTEGRACAO_PENDENTE",
            "motivo": (
                "Nenhum arquivo de comentários disponível. A coleta depende de "
                "acesso autorizado à Instagram Graph API (token e permissões "
                "validadas no Meta for Developers). Nenhum resultado simulado "
                "foi gerado."
            ),
            "modelo_previsto": config.SENTIMENT_MODEL,
            "caminho_esperado": str(caminho_entrada),
            "executado_em_utc": agora_utc_iso(),
        }
        storage.put_json(config.BUCKET_GOLD, "hospital/nlp/relatorio_nlp.json", relatorio)
        (config.PROCESSED_DIR / "relatorio_nlp.json").write_text(
            json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log.warning("NLP: %s", relatorio["motivo"])
        return relatorio

    df = pd.read_csv(caminho_entrada)
    faltando = [c for c in COLUNAS_ESPERADAS if c not in df.columns]
    if faltando:
        raise ValueError(f"CSV de comentários sem colunas obrigatórias: {faltando}")

    log.info("NLP: processando %d comentários", len(df))
    df["texto_original"] = df["texto"].astype(str)
    df["emojis_removidos"] = df["texto_original"].apply(contar_emojis)
    df["texto_limpo"] = df["texto_original"].apply(limpar_texto)
    df = analisar_sentimentos(df)
    resumo = resumo_sentimentos(df)
    termos = extrair_termos(df)

    df.to_parquet(config.PROCESSED_DIR / "nlp_comentarios.parquet", index=False)
    resumo.to_parquet(config.PROCESSED_DIR / "nlp_resumo_sentimentos.parquet", index=False)
    termos.to_parquet(config.PROCESSED_DIR / "nlp_termos.parquet", index=False)
    storage.put_bytes(
        config.BUCKET_GOLD, "hospital/nlp/nlp_comentarios.parquet",
        df.to_parquet(index=False),
    )
    storage.put_bytes(
        config.BUCKET_GOLD, "hospital/nlp/nlp_resumo_sentimentos.parquet",
        resumo.to_parquet(index=False),
    )
    storage.put_bytes(
        config.BUCKET_GOLD, "hospital/nlp/nlp_termos.parquet",
        termos.to_parquet(index=False),
    )

    relatorio = {
        "status": "PROCESSADO",
        "comentarios": int(len(df)),
        "modelo": config.SENTIMENT_MODEL,
        "modelo_carregado": info_modelo(),
        "resumo": resumo.to_dict("records"),
        "limitacoes": [
            "Sarcasmo e ironia podem ser mal classificados.",
            "Textos muito curtos têm baixa confiabilidade.",
            "Autores anonimizados no dashboard (LGPD).",
        ],
        "executado_em_utc": agora_utc_iso(),
    }
    storage.put_json(config.BUCKET_GOLD, "hospital/nlp/relatorio_nlp.json", relatorio)
    (config.PROCESSED_DIR / "relatorio_nlp.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return relatorio


if __name__ == "__main__":
    from ..utils.logging_config import configurar_logging

    configurar_logging()
    executar()
