# -*- coding: utf-8 -*-
"""Faixas etárias padronizadas (documentadas no dicionário de dados).

Regras:
  - Idade 0 é PRESERVADA como "0 a 11 meses (recém-nascido/lactente)" — não é
    erro, pode representar recém-nascidos internados;
  - Idades ausentes geram a categoria "Não informada" — nunca são preenchidas
    com mediana ou estimativa;
  - Quinquenais até 19 anos e decenais a partir dos 20, prática comum em
    estatísticas de saúde.
"""
from __future__ import annotations

FAIXA_INDEFINIDA = "Não informada"

_LIMIARES = [
    (0, 0, "0 a 11 meses (recém-nascido/lactente)"),
    (1, 4, "1 a 4 anos"),
    (5, 9, "5 a 9 anos"),
    (10, 14, "10 a 14 anos"),
    (15, 19, "15 a 19 anos"),
    (20, 29, "20 a 29 anos"),
    (30, 39, "30 a 39 anos"),
    (40, 49, "40 a 49 anos"),
    (50, 59, "50 a 59 anos"),
    (60, 69, "60 a 69 anos"),
    (70, 79, "70 a 79 anos"),
    (80, 200, "80 anos ou mais"),
]

ORDEM_FAIXAS = [rotulo for _, _, rotulo in _LIMIARES] + [FAIXA_INDEFINIDA]


def _eh_ausente(idade) -> bool:
    """Detecta None/NaN/pd.NA de forma robusta a diferentes tipos."""
    if idade is None:
        return True
    try:
        resultado = bool(idade != idade)  # NaN
    except Exception:
        return False
    if resultado:
        return True
    try:
        import pandas as pd  # noqa: PLC0415

        return bool(pd.isna(idade))
    except Exception:
        return False


def faixa_etaria(idade):
    """Classifica a idade (int/float/None/NaN/pd.NA) na faixa etária padronizada."""
    if _eh_ausente(idade):
        return FAIXA_INDEFINIDA
    try:
        i = int(idade)
    except (TypeError, ValueError):
        return FAIXA_INDEFINIDA
    if i < 0:
        return FAIXA_INDEFINIDA
    for lo, hi, rotulo in _LIMIARES:
        if lo <= i <= hi:
            return rotulo
    return FAIXA_INDEFINIDA


def eh_plausivel(idade) -> bool:
    """Idade plausível: inteiro entre 0 e 120 (fora disso é sinalizada)."""
    if _eh_ausente(idade):
        return False
    try:
        i = int(idade)
    except (TypeError, ValueError):
        return False
    return 0 <= i <= 120
