# -*- coding: utf-8 -*-
"""Identificação de temas recorrentes com TF-IDF e n-gramas (scikit-learn).

Produz tabelas de termos/expressões mais característicos por classe de
sentimento (positivo, negativo, neutro), alimentando a Tela 6 do dashboard
e as consultas SQL de termos frequentes.
"""
from __future__ import annotations

import logging

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

log = logging.getLogger(__name__)


def extrair_termos(df: pd.DataFrame, coluna_texto: str = "texto_limpo",
                   coluna_sentimento: str = "sentimento",
                   n_top: int = 20, ngramas: tuple = (1, 2)) -> pd.DataFrame:
    """Top termos TF-IDF por sentimento.

    Retorna DataFrame: termo, sentimento, tfidf_medio, frequencia.
    """
    colunas = ["termo", "sentimento", "tfidf_medio", "frequencia"]
    df = df.copy()
    df[coluna_texto] = df[coluna_texto].fillna("")
    df = df[df[coluna_texto].str.strip() != ""]
    if df.empty or df[coluna_sentimento].isna().all():
        return pd.DataFrame(columns=colunas)

    saidas = []
    for sentimento in sorted(df[coluna_sentimento].dropna().unique()):
        sub = df[df[coluna_sentimento] == sentimento]
        if len(sub) < 3:
            continue  # amostra mínima para TF-IDF estável
        vetorizador = TfidfVectorizer(
            ngram_range=ngramas, min_df=2, max_features=5000,
            sublinear_tf=True,
        )
        matriz = vetorizador.fit_transform(sub[coluna_texto])
        nomes = vetorizador.get_feature_names_out()
        medias = matriz.mean(axis=0).A1
        freq = (matriz > 0).sum(axis=0).A1
        top_idx = medias.argsort()[::-1][:n_top]
        for i in top_idx:
            saidas.append({
                "termo": nomes[i],
                "sentimento": sentimento,
                "tfidf_medio": round(float(medias[i]), 6),
                "frequencia": int(freq[i]),
            })
    return pd.DataFrame(saidas, columns=colunas)


def temas_por_sentimento(df_termos: pd.DataFrame) -> dict[str, list[str]]:
    """Dicionário sentimento -> lista de termos (para narrativa do dashboard)."""
    if df_termos.empty:
        return {}
    return {
        sentimento: grupo.sort_values("tfidf_medio", ascending=False)["termo"].tolist()
        for sentimento, grupo in df_termos.groupby("sentimento")
    }
