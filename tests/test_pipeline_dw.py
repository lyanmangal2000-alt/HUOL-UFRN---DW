# -*- coding: utf-8 -*-
"""Testes de pipeline e Data Warehouse.

Os testes de DW exigem PostgreSQL e Data Lake ativos (docker compose up -d ou
sandbox local). Se indisponíveis, são PULADOS com aviso — nunca falham falsamente.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import text

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))


def _servicos_disponiveis() -> bool:
    try:
        from src.utils import config
        import sqlalchemy

        engine = sqlalchemy.create_engine(config.DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as c:
            c.execute(sqlalchemy.text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


def _s3_disponivel() -> bool:
    try:
        from src.utils.storage import get_storage

        get_storage()
        return True
    except Exception:
        return False


requer_dw = pytest.mark.skipif(not _servicos_disponiveis(), reason="PostgreSQL indisponível")
requer_s3 = pytest.mark.skipif(not _s3_disponivel(), reason="Data Lake S3 indisponível")


# ------------------------------------------------------- camada Ouro (Parquet)
@pytest.fixture(scope="module")
def ouro():
    caminho = RAIZ / "data/processed/internacoes_prata.parquet"
    if not caminho.exists():
        pytest.skip("Prata ainda não materializada (execute o ETL)")
    return pd.read_parquet(caminho)


def test_total_prata_igual_fonte(ouro):
    assert len(ouro) == 16046


def test_cobertura_temporal_completa(ouro):
    assert ouro["data_internacao"].min().date().isoformat() == "2024-01-01"
    assert ouro["data_internacao"].max().date().isoformat() == "2025-12-31"


def test_granularidade_evento(ouro):
    assert (ouro.groupby(["data_internacao", "especialidade_padronizada", "fonte_arquivo"])
            .size() >= 1).all()


def test_idade_zero_preservada_no_volume(ouro):
    recem_nascidos = ouro[ouro["faixa_etaria"] == "0 a 11 meses (recém-nascido/lactente)"]
    assert len(recem_nascidos) == 245, "245 registros de lactentes devem estar preservados"


def test_duplicidade_exata_preservada_e_sinalizada(ouro):
    assert ouro["qualidade_duplicidade_exata"].sum() == 1
    assert len(ouro) == 16046


def test_hash_linha_unico(ouro):
    assert ouro["hash_linha"].nunique() == 16046


def test_sem_especialidade_fallback(ouro):
    assert ouro["especialidade_fallback"].sum() == 0


def test_municipios_ambiguos_nao_atribuidos(ouro):
    amb = ouro[ouro["municipio_classe_ibge"] == "AMBIGUO"]
    assert amb["municipio_codigo_ibge"].isna().all()


# --------------------------------------------------------- Data Warehouse
@pytest.fixture(scope="module")
def dw():
    if not _servicos_disponiveis():
        pytest.skip("PostgreSQL indisponível")
    import sqlalchemy
    from sqlalchemy import text
    from src.utils import config

    engine = sqlalchemy.create_engine(config.DATABASE_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()


@requer_dw
def test_fato_igual_prata(dw):
    with dw.connect() as c:
        total = c.execute(text("SELECT COUNT(*) FROM Fato_Internacao")).scalar()
        soma = c.execute(text("SELECT SUM(qtd_internacoes) FROM Fato_Internacao")).scalar()
    assert total == soma == 16046


@requer_dw
def test_integridade_referencial(dw):
    with dw.connect() as c:
        orfaos = c.execute(text("""
            SELECT COUNT(*) FROM Fato_Internacao f
            LEFT JOIN Dim_Tempo t ON t.sk_tempo=f.sk_tempo
            LEFT JOIN Dim_Especialidade e ON e.sk_especialidade=f.sk_especialidade
            LEFT JOIN Dim_Municipio m ON m.sk_municipio=f.sk_municipio
            LEFT JOIN Dim_Demografia d ON d.sk_demografia=f.sk_demografia
            WHERE t.sk_tempo IS NULL OR e.sk_especialidade IS NULL
               OR m.sk_municipio IS NULL OR d.sk_demografia IS NULL
        """)).scalar()
    assert orfaos == 0


@requer_dw
def test_dimensoes_populadas(dw):
    from sqlalchemy import text

    with dw.connect() as c:
        tempo = c.execute(text("SELECT COUNT(*) FROM Dim_Tempo")).scalar()
        espec = c.execute(text("SELECT COUNT(*) FROM Dim_Especialidade")).scalar()
        muni = c.execute(text("SELECT COUNT(*) FROM Dim_Municipio")).scalar()
        demo = c.execute(text("SELECT COUNT(*) FROM Dim_Demografia")).scalar()
    assert tempo >= 500 and espec >= 50 and muni >= 190 and demo >= 190


@requer_dw
def test_membros_desconhecidos(dw):
    from sqlalchemy import text

    with dw.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM Dim_Tempo WHERE sk_tempo=-1")).scalar() == 1
        assert c.execute(text("SELECT COUNT(*) FROM Dim_Especialidade WHERE sk_especialidade=-1")).scalar() == 1
        assert c.execute(text("SELECT COUNT(*) FROM Dim_Municipio WHERE sk_municipio=-1")).scalar() == 1
        assert c.execute(text("SELECT COUNT(*) FROM Dim_Demografia WHERE sk_demografia=-1")).scalar() == 1


@requer_dw
def test_consistencia_dw_x_ouro(dw):
    from sqlalchemy import text

    with dw.connect() as c:
        dw_esp = dict(c.execute(text("""
            SELECT e.nome_padronizado, SUM(f.qtd_internacoes)
            FROM Fato_Internacao f
            JOIN Dim_Especialidade e ON e.sk_especialidade=f.sk_especialidade
            GROUP BY 1
        """)).all())
        dw_ano = dict(c.execute(text("""
            SELECT t.ano, SUM(f.qtd_internacoes)
            FROM Fato_Internacao f
            JOIN Dim_Tempo t ON t.sk_tempo=f.sk_tempo
            GROUP BY 1
        """)).all())
    espec = pd.read_parquet(RAIZ / "data/processed/internacoes_por_especialidade.parquet")
    anos = pd.read_parquet(RAIZ / "data/processed/internacoes_por_ano.parquet")
    for _, r in espec.iterrows():
        assert dw_esp.get(r["especialidade"], 0) == int(r["total"]), r["especialidade"]
    for _, r in anos.iterrows():
        assert dw_ano.get(int(r["ano"]), 0) == int(r["qtd"])


# ------------------------------------------------------------- filtros dashboard
@requer_dw
def test_filtros_dashboard_atualizam_indicadores(dw):
    from src.dashboard import data_access as d

    sem_filtro = d.indicadores_gerais({})
    com_filtro = d.indicadores_gerais({"ano": 2025, "especialidade": "Cardiologia"})
    assert sem_filtro["total_internacoes"] == 16046
    assert 0 < com_filtro["total_internacoes"] < sem_filtro["total_internacoes"]
    assert com_filtro["total_especialidades"] == 1

    geo = d.por_geo_classe({"mes": 3, "municipio": "Natal", "faixa_etaria": "60 a 69 anos"})
    assert not geo.empty and geo["classe"].tolist() == ["Natal"]


@requer_dw
def test_montar_where_sem_filtros():
    from src.dashboard.data_access import _montar_where

    clausula, params = _montar_where({})
    assert clausula == "" and params == {}
    clausula, params = _montar_where({"ano": 2024, "sexo": "FEMININO"})
    assert clausula.startswith("WHERE") and "t.ano = :ano" in clausula and params["ano"] == 2024


# ------------------------------------------------------------- idempotência S3
@requer_s3
def test_bronze_idempotente():
    from src.etl.bronze_ingest import executar

    primeira = executar()
    segunda = executar()
    assert len(primeira) == len(segunda) == 16
    assert not any(m["reingestao_com_hash_diferente"] for m in segunda)
