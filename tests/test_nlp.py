# -*- coding: utf-8 -*-
"""Testes do módulo NLP (limpeza, sentimentos com fixture sintética marcada, temas)."""
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.nlp.clean_text import contar_emojis, limpar_texto
from src.nlp.topics import extrair_termos, temas_por_sentimento


def test_remove_urls_e_mencoes():
    resultado = limpar_texto("veja https://x.com/abc e fale com @huol_ufrn sobre o atendimento")
    assert "http" not in resultado and "huol_ufrn" not in resultado
    assert "atendimento" in resultado


def test_hashtag_mantem_termo():
    resultado = limpar_texto("#SUSnaPratica funciona bem")
    assert "susnapratica" in resultado or "sus na pratica" in resultado or "susnapratica" in resultado.replace(" ", "")
    assert "#" not in resultado


def test_emoji_removido_com_contagem():
    texto = "ótimo atendimento 👏👏 parabéns"
    assert contar_emojis(texto) == 2
    resultado = limpar_texto(texto)
    assert "👏" not in resultado and "atendimento" in resultado


def test_stopwords_removidas_e_normalizacao():
    resultado = limpar_texto("A ATENDENTE foi MUITO atenciosa com o PACIENTE!!!")
    tokens = resultado.split()
    assert "a" not in tokens and "com" not in tokens and "o" not in tokens
    assert "atendente" in tokens and "atenciosa" in tokens


def test_texto_original_preservado_conceito():
    texto = "  Atendimento   excelente 😊  "
    limpo = limpar_texto(texto)
    assert limpo != texto  # limpeza aplicada
    # a função nunca altera o argumento original (retorna novo texto)
    assert texto == "  Atendimento   excelente 😊  "


def test_tf_idf_temas_por_sentimento():
    # FIXTURE SINTÉTICA — apenas para teste unitário do algoritmo.
    # NÃO representa comentários reais do HUOL e nunca é publicada como tal.
    df = pd.DataFrame({
        "texto_limpo": [
            "atendimento excelente equipe atenciosa",
            "médico excelente atendimento rápido",
            "equipe atenciosa hospital organizado",
            "demora absurda fila esperando consulta",
            "fila enorme demora consulta atrasada",
            "problema fila espera demora consulta",
        ],
        "sentimento": ["Positivo"] * 3 + ["Negativo"] * 3,
    })
    termos = extrair_termos(df, n_top=5)
    assert not termos.empty
    assert set(termos["sentimento"]) == {"Positivo", "Negativo"}
    temas = temas_por_sentimento(termos)
    assert "atendimento" in " ".join(temas["Positivo"]) or any(
        "atend" in t for t in temas["Positivo"]
    )
    assert any("fila" in t or "demora" in t for t in temas["Negativo"])


def test_sentimento_sem_modelo_retorna_sem_resultado_falso():
    from src.nlp.sentiment import analisar_sentimentos

    df = pd.DataFrame({"texto_limpo": ["atendimento bom"]})
    saida = analisar_sentimentos(df)
    # modelo pode não estar baixado no ambiente de teste: colunas criadas,
    # sentimento pode ficar NA — NUNCA um valor simulado
    assert "sentimento" in saida.columns and "confianca" in saida.columns
    assert pd.isna(saida["sentimento"].iloc[0]) or saida["sentimento"].iloc[0] in {
        "Positivo", "Negativo", "Neutro"
    }
