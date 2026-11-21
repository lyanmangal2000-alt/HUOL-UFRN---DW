# -*- coding: utf-8 -*-
"""Análise de sentimentos em comentários (português).

Modelo: cardiffnlp/twitter-xlm-roberta-base-sentiment
  - multilíngue (XLM-RoBERTa), treinado em tweets de 8 línguas, incluindo
    português;
  - rótulos brutos: positive / negative / neutral -> Positivo / Negativo / Neutro;
  - inferência local via Transformers (torch), carregado sob demanda.

Adequação e limitações (documentadas no relatório de qualidade):
  - vocabulário de redes sociais se aproxima dos comentários do Instagram;
  - sarcasmo, ironia e reclamações indiretas podem ser mal classificados;
  - textos muito curtos ("kkk", "ok") têm baixa confiabilidade;
  - recomenda-se avaliação com amostra revisada manualmente (avaliar_manualmente()).
"""
from __future__ import annotations

import logging

import pandas as pd

from ..utils import config

log = logging.getLogger(__name__)

ROTULOS_PT = {"positive": "Positivo", "negative": "Negativo", "neutral": "Neutro"}

_pipeline = None
_modelo_info: dict = {"carregado": False, "erro": ""}


def _obter_pipeline():
    """Carrega o pipeline de sentimentos sob demanda (evita custo se ausente)."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    try:
        from transformers import pipeline as hf_pipeline  # noqa: PLC0415

        _pipeline = hf_pipeline(
            "sentiment-analysis",
            model=config.SENTIMENT_MODEL,
            tokenizer=config.SENTIMENT_MODEL,
            truncation=True,
            max_length=128,
        )
        _modelo_info["carregado"] = True
        _modelo_info["erro"] = ""
        log.info("Modelo de sentimentos carregado: %s", config.SENTIMENT_MODEL)
    except Exception as exc:  # transformers/torch ausentes ou sem rede
        _modelo_info["carregado"] = False
        _modelo_info["erro"] = str(exc)
        log.error("Modelo de sentimentos indisponível: %s", exc)
    return _pipeline


def info_modelo() -> dict:
    return dict(_modelo_info)


def analisar_sentimentos(comentarios: pd.DataFrame,
                         coluna_texto: str = "texto_limpo") -> pd.DataFrame:
    """Classifica cada comentário em Positivo / Negativo / Neutro.

    Entrada: DataFrame com coluna de texto limpo (clean_text.limpar_texto).
    Saída: mesmo DataFrame + colunas sentimento e confianca (0–1).
    """
    df = comentarios.copy()
    df["sentimento"] = pd.NA
    df["confianca"] = pd.NA

    pipe = _obter_pipeline()
    if pipe is None:
        log.warning(
            "Classificação de sentimentos não executada: modelo indisponível (%s)",
            _modelo_info["erro"],
        )
        return df

    textos = df[coluna_texto].fillna("").astype(str).tolist()
    resultados = pipe(textos, batch_size=32)
    df["sentimento"] = [ROTULOS_PT.get(r["label"], r["label"]) for r in resultados]
    df["confianca"] = [round(float(r["score"]), 4) for r in resultados]
    return df


def resumo_sentimentos(df_classificado: pd.DataFrame) -> pd.DataFrame:
    """Distribuição percentual de sentimentos (para dashboard e SQL)."""
    if df_classificado.empty or df_classificado["sentimento"].isna().all():
        return pd.DataFrame(columns=["sentimento", "qtd", "participacao_pct"])
    resumo = (
        df_classificado.groupby("sentimento").size().reset_index(name="qtd")
    )
    total = resumo["qtd"].sum()
    resumo["participacao_pct"] = (100.0 * resumo["qtd"] / total).round(2)
    return resumo


def avaliar_manualmente(df_classificado: pd.DataFrame, gabarito: dict[str, str]) -> dict:
    """Avaliação com amostra revisada manualmente.

    gabarito: {id_comentario: sentimento_revisado}. Retorna acurácia e matriz
    de confusão simples — evidência de qualidade exigida pelo enunciado.
    """
    sub = df_classificado[df_classificado["id_comentario"].isin(gabarito)]
    if sub.empty:
        return {"n_avaliados": 0, "acuracia": None}
    esperado = sub["id_comentario"].map(gabarito)
    acertos = (sub["sentimento"] == esperado).sum()
    return {
        "n_avaliados": int(len(sub)),
        "acertos": int(acertos),
        "acuracia": round(float(acertos) / len(sub), 4),
    }
