# -*- coding: utf-8 -*-
"""Testes dos utilitários de transformação (executam sem infraestrutura)."""
import io
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.utils.especialidades import chave_ascii, padronizar_especialidade
from src.utils.faixas_etarias import FAIXA_INDEFINIDA, eh_plausivel, faixa_etaria
from src.utils.ibge import ValidadorIBGE, classificacao_geografica, normalizar
from src.etl.silver_transform import (
    decodificar_csv,
    padronizar_sexo,
    parse_data,
    validar_cabecalho,
)


# ------------------------------------------------------------- leitura/estrutura
@pytest.fixture(scope="module")
def arquivos_csv():
    arquivos = sorted((RAIZ / "data/raw").glob("*.csv"))
    assert len(arquivos) == 8, "devem existir os 8 CSVs trimestrais no projeto"
    return arquivos


def test_leitura_5_campos_original(arquivos_csv):
    df = decodificar_csv(arquivos_csv[0].read_bytes())
    assert len(df.columns) == 5
    assert df.columns[0] == "data_internacao"
    assert df.columns[-1] == "sexo"


def test_cabecalho_real_e_variante():
    ok, _ = validar_cabecalho(["data_internacao", "especialidade", "município", "idade", "sexo"])
    assert ok, "cabeçalho real (município com acento) deve ser aceito"
    ok2, _ = validar_cabecalho(["data_internacao", "especialidade", "municpio", "idade", "sexo"])
    assert ok2, "variante 'municpio' (descrita no enunciado) também deve ser aceita"


def test_decodificacao_latin1(arquivos_csv):
    # arquivo ISO-8859-1: acentos legíveis após decodificação
    df = decodificar_csv(arquivos_csv[0].read_bytes())
    valores = df.iloc[:, 2].astype(str).unique()
    assert any("í" in v or "ã" in v or "ó" in v for v in valores[:40])


def test_dados_reais_8_trimestres(arquivos_csv):
    totais = [len(decodificar_csv(a.read_bytes())) for a in arquivos_csv]
    assert sum(totais) == 16046, f"total esperado 16046 registros, obtido {sum(totais)}"


# ------------------------------------------------------------------ datas
def test_conversao_data_completa():
    ts, horario_ausente = parse_data("23/01/2024 20:05")
    assert ts is not None and ts.month == 1 and ts.year == 2024
    assert not horario_ausente


def test_conversao_data_sem_horario():
    ts, horario_ausente = parse_data("01/03/2024")
    assert ts is not None and not horario_ausente is None
    assert horario_ausente is True


def test_conversao_data_invalida():
    assert parse_data("32/13/2024 99:99")[0] is None
    assert parse_data("")[0] is None


# ------------------------------------------------------------------ idade
def test_idade_zero_preservada():
    assert faixa_etaria(0) == "0 a 11 meses (recém-nascido/lactente)"


def test_idade_ausente_nao_imputada():
    assert faixa_etaria(None) == FAIXA_INDEFINIDA
    assert faixa_etaria(pd.NA) == FAIXA_INDEFINIDA


def test_faixas_tipicas():
    assert faixa_etaria(4) == "1 a 4 anos"
    assert faixa_etaria(17) == "15 a 19 anos"
    assert faixa_etaria(96) == "80 anos ou mais"


def test_plausibilidade():
    assert eh_plausivel(0) and eh_plausivel(104)
    assert not eh_plausivel(-5) and not eh_plausivel(150)


# ------------------------------------------------------------------ sexo
def test_normalizacao_sexo():
    assert padronizar_sexo("FEMININO") == ("FEMININO", False)
    assert padronizar_sexo("F") == ("FEMININO", True)
    assert padronizar_sexo("M") == ("MASCULINO", True)
    assert padronizar_sexo("") == ("NÃO INFORMADO", True)


# ------------------------------------------------------------------ especialidades
def test_especialidade_padronizada_com_acento():
    assert padronizar_especialidade("CLINICA GERAL") == ("Clínica Geral", False)
    assert padronizar_especialidade("CIRURGIA BARIATRICA") == ("Cirurgia Bariátrica", False)
    assert padronizar_especialidade("POS-TRANSPLANTE") == ("Pós-Transplante", False)


def test_especialidade_inedita_sinaliza_fallback():
    nome, fallback = padronizar_especialidade("ESPECIALIDADE INEDITA XYZ")
    assert fallback is True and nome == "Especialidade Inedita Xyz"


def test_chave_ascii_ignora_acento_e_hifen():
    assert chave_ascii("OLHO-D'ÁGUA DO BORGES") == chave_ascii("Olho d'Água do Borges")


# ------------------------------------------------------------------ municípios IBGE
@pytest.fixture(scope="module")
def validador():
    return ValidadorIBGE()


def test_municipio_rn_validado(validador):
    m = validador.resolver("NATAL")
    assert m.codigo_ibge == "2408102" and m.uf == "RN" and m.classe == "RN"


def test_variante_oficial_acu_assu(validador):
    m = validador.resolver("AÇU")
    assert m.nome == "Assú" and m.codigo_ibge == "2400208"


def test_renomeacao_sao_miguel_do_gostoso(validador):
    m = validador.resolver("SÃO MIGUEL DE TOUROS")
    assert m.nome == "São Miguel do Gostoso" and m.uf == "RN"


def test_renomeacao_campo_grande_augusto_severo(validador):
    m = validador.resolver("AUGUSTO SEVERO")
    assert m.nome == "Campo Grande" and m.uf == "RN"


def test_ambiguo_sem_atribuicao(validador):
    m = validador.resolver("SÃO BENTO")  # MA e PB; nenhum candidato no RN
    assert m.classe == "AMBIGUO" and m.codigo_ibge is None


def test_ambiguo_com_candidato_rn_excecao_documentada(validador):
    m = validador.resolver("PARNAMIRIM")  # RN e PE; único candidato no RN
    assert m.classe == "RN" and m.codigo_ibge == "2403251"
    assert "Ambíguo nacionalmente" in m.observacao


def test_municipio_nao_informado(validador):
    m = validador.resolver("")
    assert m.classe == "NAO_INFORMADO"


def test_classificacao_geografica_natal_interior():
    assert classificacao_geografica("Natal", "RN", "RN") == "Natal"
    assert classificacao_geografica("Assú", "RN", "RN") == "Interior RN"
    assert classificacao_geografica("Recife", "OUTROS_ESTADOS", "PE") == "Outros estados"


# ------------------------------------------------------------------ pipeline prata
def test_transformar_dataframe_preserva_duplicidade_exata():
    from src.etl.silver_transform import transformar_dataframe

    df = pd.DataFrame([
        {"data_internacao": "20/11/2024 08:37", "especialidade": "UROLOGIA",
         "município": "NATAL", "idade": "77", "sexo": "MASCULINO"},
        {"data_internacao": "20/11/2024 08:37", "especialidade": "UROLOGIA",
         "município": "NATAL", "idade": "77", "sexo": "MASCULINO"},
    ])
    base, rejeitados = transformar_dataframe(df, "teste.csv", "teste", 4, ValidadorIBGE())
    assert len(rejeitados) == 0
    assert len(base) == 2, "duplicidade deve ser PRESERVADA (não descartada)"
    assert base["qualidade_duplicidade_exata"].sum() == 1
    assert base["hash_linha"].nunique() == 2, "cada evento preservado tem hash próprio"


def test_parse_data_invalida_gera_rejeicao():
    from src.etl.silver_transform import transformar_dataframe

    df = pd.DataFrame([
        {"data_internacao": "abracadabra", "especialidade": "PEDIATRIA",
         "município": "NATAL", "idade": "5", "sexo": "MASCULINO"},
    ])
    base, rejeitados = transformar_dataframe(df, "teste.csv", "teste", 1, ValidadorIBGE())
    assert len(base) == 0 and len(rejeitados) == 1


def test_faixa_nao_informada_e_sexo_ausente():
    from src.etl.silver_transform import transformar_dataframe

    df = pd.DataFrame([
        {"data_internacao": "11/04/2024 10:14", "especialidade": "PEDIATRIA",
         "município": "", "idade": "", "sexo": ""},
    ])
    base, _ = transformar_dataframe(df, "teste.csv", "teste", 2, ValidadorIBGE())
    linha = base.iloc[0]
    assert linha["faixa_etaria"] == FAIXA_INDEFINIDA
    assert linha["sexo_padronizado"] == "NÃO INFORMADO"
    assert linha["municipio_classe_ibge"] == "NAO_INFORMADO"
    assert bool(linha["idade_ausente"]) and bool(linha["sexo_ausente"])
