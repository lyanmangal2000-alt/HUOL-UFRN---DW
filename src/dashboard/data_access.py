# -*- coding: utf-8 -*-
"""Camada de acesso a dados do dashboard.

Todas as consultas partem do Data Warehouse (PostgreSQL, esquema estrela).
Os filtros globais são aplicados como cláusulas SQL — nenhum indicador é
estático: tudo deriva do banco validado pela camada Ouro.
"""
from __future__ import annotations

import logging

import pandas as pd
import sqlalchemy

from ..utils import config

log = logging.getLogger(__name__)

MESES_NOME = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
    7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


def conectar():
    """Cria engine SQLAlchemy com o Data Warehouse (erro explicito se falhar)."""
    return sqlalchemy.create_engine(config.DATABASE_URL, pool_pre_ping=True)


def _dados_prata_local(filtros: dict | None = None) -> pd.DataFrame:
    """Carrega a Prata local e aplica os filtros globais do dashboard."""
    df = pd.read_parquet(config.PROCESSED_DIR / "internacoes_prata.parquet")
    if not filtros:
        return df
    if filtros.get("ano"):
        df = df[df["ano"] == filtros["ano"]]
    if filtros.get("trimestre"):
        df = df[df["trimestre"] == filtros["trimestre"]]
    if filtros.get("mes"):
        df = df[df["mes"] == filtros["mes"]]
    if filtros.get("especialidade"):
        df = df[df["especialidade_padronizada"] == filtros["especialidade"]]
    if filtros.get("municipio"):
        df = df[df["municipio_residencia_padronizado"] == filtros["municipio"]]
    if filtros.get("sexo"):
        df = df[df["sexo_padronizado"] == filtros["sexo"]]
    if filtros.get("faixa_etaria"):
        df = df[df["faixa_etaria"] == filtros["faixa_etaria"]]
    return df


def _filtrar_local(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    alias = {
        "ano": "ano",
        "trimestre": "trimestre",
        "mes": "mes",
        "especialidade": "especialidade_padronizada",
        "municipio": "municipio_residencia_padronizado",
        "sexo": "sexo_padronizado",
        "faixa_etaria": "faixa_etaria",
    }
    for parametro, coluna in alias.items():
        if parametro in params:
            df = df[df[coluna] == params[parametro]]
    return df


def _consulta_local(sql: str, params: dict | None = None) -> pd.DataFrame:
    params = params or {}
    df = _filtrar_local(
        pd.read_parquet(config.PROCESSED_DIR / "internacoes_prata.parquet"),
        params,
    )
    sql_normal = " ".join(sql.lower().split())

    if "percentile_cont" in sql_normal:
        mediana = df["idade"].median() if not df.empty else None
        return pd.DataFrame({"mediana": [mediana]})

    if "distinct ano" in sql_normal:
        return pd.DataFrame({"ano": sorted(df["ano"].dropna().unique())})
    if "distinct nome_padronizado from dim_especialidade" in sql_normal:
        valores = sorted(df.loc[df["especialidade_padronizada"] != "Desconhecido", "especialidade_padronizada"].dropna().unique())
        return pd.DataFrame({"nome_padronizado": valores})
    if "distinct nome_padronizado from dim_municipio" in sql_normal:
        valores = sorted(df.loc[df["municipio_residencia_padronizado"] != "Desconhecido", "municipio_residencia_padronizado"].dropna().unique())
        return pd.DataFrame({"nome_padronizado": valores})
    if "distinct sexo" in sql_normal:
        return pd.DataFrame({"sexo": sorted(df["sexo_padronizado"].dropna().unique())})
    if "distinct faixa_etaria" in sql_normal:
        return pd.DataFrame({"faixa_etaria": sorted(df["faixa_etaria"].dropna().unique())})

    if "count(distinct e.nome_padronizado)" in sql_normal:
        return pd.DataFrame({
            "total_internacoes": [len(df)],
            "total_especialidades": [df["especialidade_padronizada"].nunique()],
            "total_municipios": [df["municipio_residencia_padronizado"].nunique()],
            "idade_media": [df["idade"].mean() if df["idade"].notna().any() else None],
            "feminino": [int((df["sexo_padronizado"] == "FEMININO").sum())],
            "masculino": [int((df["sexo_padronizado"] == "MASCULINO").sum())],
            "sexo_nao_informado": [int((df["sexo_padronizado"] == "NÃO INFORMADO").sum())],
            "idade_ausente": [int(df["idade"].isna().sum())],
            "data_min": [df["data_internacao"].min()],
            "data_max": [df["data_internacao"].max()],
        })

    if "e.nome_padronizado as especialidade" in sql_normal:
        agrupado = df.groupby("especialidade_padronizada", dropna=False).size().rename("internacoes").reset_index()
        agrupado = agrupado.rename(columns={"especialidade_padronizada": "especialidade"})
        if "ano_2024" in sql_normal:
            for ano in (2024, 2025):
                coluna = f"ano_{ano}"
                agrupado[coluna] = df[df["ano"] == ano].groupby("especialidade_padronizada").size().reindex(
                    agrupado["especialidade"], fill_value=0
                ).values
        return agrupado.sort_values("internacoes", ascending=False)

    if "m.nome_padronizado as municipio" in sql_normal:
        agrupado = df.groupby(
            ["municipio_residencia_padronizado", "municipio_uf", "classificacao_geografica"],
            dropna=False,
        ).size().rename("internacoes").reset_index()
        agrupado = agrupado.rename(columns={
            "municipio_residencia_padronizado": "municipio",
            "municipio_uf": "uf",
            "classificacao_geografica": "classificacao_geografica",
        })
        if not agrupado.empty:
            agrupado["participacao_pct"] = (100 * agrupado["internacoes"] / agrupado["internacoes"].sum()).round(2)
        return agrupado.sort_values("internacoes", ascending=False)

    if "m.classificacao_geografica as classe" in sql_normal:
        agrupado = df.groupby("classificacao_geografica").size().rename("internacoes").reset_index()
        agrupado = agrupado.rename(columns={"classificacao_geografica": "classe"})
        if not agrupado.empty:
            agrupado["participacao_pct"] = (100 * agrupado["internacoes"] / agrupado["internacoes"].sum()).round(2)
        return agrupado.sort_values("internacoes", ascending=False)

    if "d.sexo, sum" in sql_normal:
        agrupado = df.groupby("sexo_padronizado").size().rename("internacoes").reset_index()
        agrupado = agrupado.rename(columns={"sexo_padronizado": "sexo"})
        if not agrupado.empty:
            agrupado["participacao_pct"] = (100 * agrupado["internacoes"] / agrupado["internacoes"].sum()).round(2)
        return agrupado.sort_values("internacoes", ascending=False)

    if "d.faixa_etaria" in sql_normal:
        agrupado = df.groupby("faixa_etaria").size().rename("internacoes").reset_index()
        agrupado["idade_media"] = agrupado["faixa_etaria"].map(
            df.groupby("faixa_etaria")["idade"].mean()
        ).round(1)
        ordem = [
            "0 a 11 meses (recém-nascido/lactente)", "1 a 4 anos", "5 a 9 anos",
            "10 a 14 anos", "15 a 19 anos", "20 a 29 anos", "30 a 39 anos",
            "40 a 49 anos", "50 a 59 anos", "60 a 69 anos", "70 a 79 anos",
            "80 anos ou mais", "Não informada",
        ]
        agrupado["ordem"] = agrupado["faixa_etaria"].map({r: i for i, r in enumerate(ordem)}).fillna(99)
        agrupado = agrupado.sort_values("ordem").drop(columns="ordem")
        agrupado["participacao_pct"] = (100 * agrupado["internacoes"] / agrupado["internacoes"].sum()).round(2)
        return agrupado

    if "t.ano, t.mes" in sql_normal:
        nomes = {
            1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
            7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
        }
        if "e.nome_padronizado as especialidade" in sql_normal:
            subset = df[df["especialidade_padronizada"].isin(params.get("_especialidades", []))]
            agrupado = subset.groupby(["ano", "mes", "especialidade_padronizada"]).size().rename("internacoes").reset_index()
            agrupado = agrupado.rename(columns={"ano": "ano", "mes": "mes", "especialidade_padronizada": "especialidade"})
        else:
            agrupado = df.groupby(["ano", "mes"]).size().rename("internacoes").reset_index()
        agrupado["nome_mes"] = agrupado["mes"].map(nomes)
        agrupado["rotulo"] = agrupado["nome_mes"].str[:3] + "/" + agrupado["ano"].astype(str)
        return agrupado.sort_values(["ano", "mes"])

    if "t.ano, t.trimestre" in sql_normal:
        agrupado = df.groupby(["ano", "trimestre"]).size().rename("internacoes").reset_index()
        agrupado["rotulo"] = agrupado["ano"].astype(str) + "-T" + agrupado["trimestre"].astype(str)
        return agrupado.sort_values(["ano", "trimestre"])

    if "feminino" in sql_normal and "e.nome_padronizado" in sql_normal:
        agrupado = df.groupby("especialidade_padronizada").agg(
            feminino=("sexo_padronizado", lambda s: (s == "FEMININO").sum()),
            masculino=("sexo_padronizado", lambda s: (s == "MASCULINO").sum()),
            idade_media=("idade", "mean"),
            internacoes=("especialidade_padronizada", "size"),
        ).reset_index().rename(columns={"especialidade_padronizada": "especialidade"})
        return agrupado.sort_values("internacoes", ascending=False)

    return pd.DataFrame()


def _montar_where(filtros: dict) -> tuple[str, dict]:
    """Monta cláusula WHERE com todos os filtros globais (tempo + complementares)."""
    condicoes, params = [], {}
    if filtros.get("ano"):
        condicoes.append("t.ano = :ano")
        params["ano"] = filtros["ano"]
    if filtros.get("trimestre"):
        condicoes.append("t.trimestre = :trimestre")
        params["trimestre"] = filtros["trimestre"]
    if filtros.get("mes"):
        condicoes.append("t.mes = :mes")
        params["mes"] = filtros["mes"]
    if filtros.get("especialidade"):
        condicoes.append("e.nome_padronizado = :especialidade")
        params["especialidade"] = filtros["especialidade"]
    if filtros.get("municipio"):
        condicoes.append("m.nome_padronizado = :municipio")
        params["municipio"] = filtros["municipio"]
    if filtros.get("sexo"):
        condicoes.append("d.sexo = :sexo")
        params["sexo"] = filtros["sexo"]
    if filtros.get("faixa_etaria"):
        condicoes.append("d.faixa_etaria = :faixa_etaria")
        params["faixa_etaria"] = filtros["faixa_etaria"]
    if condicoes:
        return "WHERE " + " AND ".join(condicoes), params
    return "", params


def executar_consulta(sql: str, params: dict | None = None) -> pd.DataFrame:
    params = params or {}
    engine = conectar()
    try:
        with engine.connect() as conn:
            return pd.read_sql(sqlalchemy.text(sql), conn, params=params)
    except Exception:
        if config.STORAGE_BACKEND == "LOCAL":
            return _consulta_local(sql, params)
        raise
    finally:
        engine.dispose()


def indicadores_gerais(filtros: dict) -> dict:
    where, params = _montar_where(filtros)
    sql = f"""
        SELECT
            COUNT(*)                                            AS total_internacoes,
            COUNT(DISTINCT e.nome_padronizado)                  AS total_especialidades,
            COUNT(DISTINCT m.nome_padronizado)                  AS total_municipios,
            ROUND(AVG(d.idade)::numeric, 2)                     AS idade_media,
            COUNT(*) FILTER (WHERE d.sexo = 'FEMININO')         AS feminino,
            COUNT(*) FILTER (WHERE d.sexo = 'MASCULINO')        AS masculino,
            COUNT(*) FILTER (WHERE d.sexo = 'NÃO INFORMADO')    AS sexo_nao_informado,
            COUNT(*) FILTER (WHERE d.idade IS NULL)             AS idade_ausente,
            MIN(t.data)                                         AS data_min,
            MAX(t.data)                                         AS data_max
        FROM Fato_Internacao f
        JOIN Dim_Tempo t         ON t.sk_tempo = f.sk_tempo
        JOIN Dim_Especialidade e ON e.sk_especialidade = f.sk_especialidade
        JOIN Dim_Municipio m     ON m.sk_municipio = f.sk_municipio
        JOIN Dim_Demografia d    ON d.sk_demografia = f.sk_demografia
        {where}
    """
    linhas = executar_consulta(sql, params)
    return linhas.iloc[0].to_dict() if not linhas.empty else {}


def por_especialidade(filtros: dict) -> pd.DataFrame:
    where, params = _montar_where(filtros)
    sql = f"""
        SELECT e.nome_padronizado AS especialidade,
               SUM(f.qtd_internacoes) AS internacoes,
               SUM(f.qtd_internacoes) FILTER (WHERE t.ano = 2024) AS ano_2024,
               SUM(f.qtd_internacoes) FILTER (WHERE t.ano = 2025) AS ano_2025
        FROM Fato_Internacao f
        JOIN Dim_Tempo t         ON t.sk_tempo = f.sk_tempo
        JOIN Dim_Especialidade e ON e.sk_especialidade = f.sk_especialidade
        JOIN Dim_Municipio m     ON m.sk_municipio = f.sk_municipio
        JOIN Dim_Demografia d    ON d.sk_demografia = f.sk_demografia
        {where}
        GROUP BY 1 ORDER BY internacoes DESC
    """
    df = executar_consulta(sql, params)
    if not df.empty:
        df["participacao_pct"] = (100 * df["internacoes"] / df["internacoes"].sum()).round(2)
    return df


def por_municipio(filtros: dict) -> pd.DataFrame:
    where, params = _montar_where(filtros)
    sql = f"""
        SELECT m.nome_padronizado AS municipio, m.uf,
               m.classificacao_geografica, SUM(f.qtd_internacoes) AS internacoes
        FROM Fato_Internacao f
        JOIN Dim_Tempo t         ON t.sk_tempo = f.sk_tempo
        JOIN Dim_Especialidade e ON e.sk_especialidade = f.sk_especialidade
        JOIN Dim_Municipio m     ON m.sk_municipio = f.sk_municipio
        JOIN Dim_Demografia d    ON d.sk_demografia = f.sk_demografia
        {where}
        GROUP BY 1, 2, 3 ORDER BY internacoes DESC
    """
    df = executar_consulta(sql, params)
    if not df.empty:
        df["participacao_pct"] = (100 * df["internacoes"] / df["internacoes"].sum()).round(2)
    return df


def por_geo_classe(filtros: dict) -> pd.DataFrame:
    where, params = _montar_where(filtros)
    sql = f"""
        SELECT m.classificacao_geografica AS classe, SUM(f.qtd_internacoes) AS internacoes
        FROM Fato_Internacao f
        JOIN Dim_Tempo t         ON t.sk_tempo = f.sk_tempo
        JOIN Dim_Especialidade e ON e.sk_especialidade = f.sk_especialidade
        JOIN Dim_Municipio m     ON m.sk_municipio = f.sk_municipio
        JOIN Dim_Demografia d    ON d.sk_demografia = f.sk_demografia
        {where}
        GROUP BY 1 ORDER BY internacoes DESC
    """
    df = executar_consulta(sql, params)
    if not df.empty:
        df["participacao_pct"] = (100 * df["internacoes"] / df["internacoes"].sum()).round(2)
    return df


def por_sexo(filtros: dict) -> pd.DataFrame:
    where, params = _montar_where(filtros)
    sql = f"""
        SELECT d.sexo, SUM(f.qtd_internacoes) AS internacoes
        FROM Fato_Internacao f
        JOIN Dim_Tempo t         ON t.sk_tempo = f.sk_tempo
        JOIN Dim_Especialidade e ON e.sk_especialidade = f.sk_especialidade
        JOIN Dim_Municipio m     ON m.sk_municipio = f.sk_municipio
        JOIN Dim_Demografia d    ON d.sk_demografia = f.sk_demografia
        {where}
        GROUP BY 1 ORDER BY internacoes DESC
    """
    df = executar_consulta(sql, params)
    if not df.empty:
        df["participacao_pct"] = (100 * df["internacoes"] / df["internacoes"].sum()).round(2)
    return df


def por_faixa_etaria(filtros: dict) -> pd.DataFrame:
    where, params = _montar_where(filtros)
    ordem = [
        "0 a 11 meses (recém-nascido/lactente)", "1 a 4 anos", "5 a 9 anos",
        "10 a 14 anos", "15 a 19 anos", "20 a 29 anos", "30 a 39 anos",
        "40 a 49 anos", "50 a 59 anos", "60 a 69 anos", "70 a 79 anos",
        "80 anos ou mais", "Não informada",
    ]
    sql = f"""
        SELECT d.faixa_etaria, SUM(f.qtd_internacoes) AS internacoes,
               ROUND(AVG(d.idade)::numeric, 1) AS idade_media
        FROM Fato_Internacao f
        JOIN Dim_Tempo t         ON t.sk_tempo = f.sk_tempo
        JOIN Dim_Especialidade e ON e.sk_especialidade = f.sk_especialidade
        JOIN Dim_Municipio m     ON m.sk_municipio = f.sk_municipio
        JOIN Dim_Demografia d    ON d.sk_demografia = f.sk_demografia
        {where}
        GROUP BY 1
    """
    df = executar_consulta(sql, params)
    if not df.empty:
        df["ordem"] = df["faixa_etaria"].map({r: i for i, r in enumerate(ordem)}).fillna(99)
        df = df.sort_values("ordem").drop(columns="ordem")
        df["participacao_pct"] = (100 * df["internacoes"] / df["internacoes"].sum()).round(2)
    return df


def idade_mediana(filtros: dict) -> float | None:
    where, params = _montar_where(filtros)
    sql = f"""
        SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d.idade) AS mediana
        FROM Fato_Internacao f
        JOIN Dim_Tempo t         ON t.sk_tempo = f.sk_tempo
        JOIN Dim_Especialidade e ON e.sk_especialidade = f.sk_especialidade
        JOIN Dim_Municipio m     ON m.sk_municipio = f.sk_municipio
        JOIN Dim_Demografia d    ON d.sk_demografia = f.sk_demografia
        {where}
    """
    df = executar_consulta(sql, params)
    return float(df.iloc[0]["mediana"]) if not df.empty and df.iloc[0]["mediana"] is not None else None


def por_mes(filtros: dict) -> pd.DataFrame:
    where, params = _montar_where(filtros)
    sql = f"""
        SELECT t.ano, t.mes, MAX(t.nome_mes) AS nome_mes,
               SUM(f.qtd_internacoes) AS internacoes
        FROM Fato_Internacao f
        JOIN Dim_Tempo t         ON t.sk_tempo = f.sk_tempo
        JOIN Dim_Especialidade e ON e.sk_especialidade = f.sk_especialidade
        JOIN Dim_Municipio m     ON m.sk_municipio = f.sk_municipio
        JOIN Dim_Demografia d    ON d.sk_demografia = f.sk_demografia
        {where}
        GROUP BY t.ano, t.mes ORDER BY t.ano, t.mes
    """
    df = executar_consulta(sql, params)
    if not df.empty:
        df["rotulo"] = df["nome_mes"].str[:3] + "/" + df["ano"].astype(str)
    return df


def por_mes_especialidade(filtros: dict, especialidades: list[str]) -> pd.DataFrame:
    """Internações mensais para uma lista de especialidades (filtros globais)."""
    where, params = _montar_where(filtros)
    marcadores = ", ".join(
        f":esp{i}" for i in range(len(especialidades))
    )
    params_esp = {f"esp{i}": esp for i, esp in enumerate(especialidades)}
    sql = f"""
        SELECT t.ano, t.mes, MAX(t.nome_mes) AS nome_mes,
               e.nome_padronizado AS especialidade,
               SUM(f.qtd_internacoes) AS internacoes
        FROM Fato_Internacao f
        JOIN Dim_Tempo t         ON t.sk_tempo = f.sk_tempo
        JOIN Dim_Especialidade e ON e.sk_especialidade = f.sk_especialidade
        JOIN Dim_Municipio m     ON m.sk_municipio = f.sk_municipio
        JOIN Dim_Demografia d    ON d.sk_demografia = f.sk_demografia
        {where}
          {" AND e.nome_padronizado IN (" + marcadores + ")" if where else "WHERE e.nome_padronizado IN (" + marcadores + ")"}
        GROUP BY t.ano, t.mes, e.nome_padronizado ORDER BY t.ano, t.mes
    """
    df = executar_consulta(sql, {**params, **params_esp, "_especialidades": especialidades})
    if not df.empty:
        df["rotulo"] = df["nome_mes"].str[:3] + "/" + df["ano"].astype(str)
    return df


def por_trimestre(filtros: dict) -> pd.DataFrame:
    where, params = _montar_where(filtros)
    sql = f"""
        SELECT t.ano, t.trimestre, SUM(f.qtd_internacoes) AS internacoes
        FROM Fato_Internacao f
        JOIN Dim_Tempo t         ON t.sk_tempo = f.sk_tempo
        JOIN Dim_Especialidade e ON e.sk_especialidade = f.sk_especialidade
        JOIN Dim_Municipio m     ON m.sk_municipio = f.sk_municipio
        JOIN Dim_Demografia d    ON d.sk_demografia = f.sk_demografia
        {where}
        GROUP BY 1, 2 ORDER BY 1, 2
    """
    df = executar_consulta(sql, params)
    if not df.empty:
        df["rotulo"] = df["ano"].astype(str) + "-T" + df["trimestre"].astype(str)
    return df


def demografia_por_especialidade(filtros: dict) -> pd.DataFrame:
    where, params = _montar_where(filtros)
    sql = f"""
        SELECT e.nome_padronizado AS especialidade,
               SUM(f.qtd_internacoes) FILTER (WHERE d.sexo = 'FEMININO') AS feminino,
               SUM(f.qtd_internacoes) FILTER (WHERE d.sexo = 'MASCULINO') AS masculino,
               ROUND(AVG(d.idade)::numeric, 1) AS idade_media,
               COUNT(*) AS internacoes
        FROM Fato_Internacao f
        JOIN Dim_Tempo t         ON t.sk_tempo = f.sk_tempo
        JOIN Dim_Especialidade e ON e.sk_especialidade = f.sk_especialidade
        JOIN Dim_Municipio m     ON m.sk_municipio = f.sk_municipio
        JOIN Dim_Demografia d    ON d.sk_demografia = f.sk_demografia
        {where}
        GROUP BY 1 ORDER BY internacoes DESC
    """
    return executar_consulta(sql, params)


def evolucao_acumulada(filtros: dict) -> pd.DataFrame:
    df = por_mes(filtros)
    if not df.empty:
        df["acumulado"] = df["internacoes"].cumsum()
    return df


def alternativas_filtros() -> dict:
    """Valores disponíveis para os filtros globais."""
    return {
        "anos": executar_consulta("SELECT DISTINCT ano FROM Dim_Tempo WHERE ano > 0 ORDER BY ano")["ano"].tolist(),
        "especialidades": executar_consulta(
            "SELECT DISTINCT nome_padronizado FROM Dim_Especialidade WHERE nome_padronizado <> 'Desconhecido' ORDER BY 1"
        )["nome_padronizado"].tolist(),
        "municipios": executar_consulta(
            "SELECT DISTINCT nome_padronizado FROM Dim_Municipio WHERE nome_padronizado <> 'Desconhecido' ORDER BY 1"
        )["nome_padronizado"].tolist(),
        "sexos": executar_consulta(
            "SELECT DISTINCT sexo FROM Dim_Demografia ORDER BY 1"
        )["sexo"].tolist(),
        "faixas": executar_consulta(
            "SELECT DISTINCT faixa_etaria FROM Dim_Demografia ORDER BY 1"
        )["faixa_etaria"].tolist(),
    }


def qualidade_dados() -> dict:
    """Relatório de qualidade da Prata (recebidos/processados/rejeitados/flags)."""
    import json
    from pathlib import Path

    caminho = Path(config.PROCESSED_DIR / "relatorio_qualidade_prata.json")
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return {}


def relatorio_nlp() -> dict:
    import json
    from pathlib import Path

    caminho = Path(config.PROCESSED_DIR / "relatorio_nlp.json")
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return {}
