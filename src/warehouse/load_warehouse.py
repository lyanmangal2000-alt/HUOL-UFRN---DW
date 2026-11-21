# -*- coding: utf-8 -*-
"""Carga do Data Warehouse (PostgreSQL) a partir da camada Prata.

Estratégia:
  1. Aplica schema.sql (DDL idempotente);
  2. Carrega Dim_Tempo, Dim_Especialidade, Dim_Municipio, Dim_Demografia com
     upsert idempotente (ON CONFLICT DO NOTHING) e membro desconhecido -1;
  3. Carrega Fato_Internacao (1 linha da Prata = 1 evento), idempotente pela
     chave hash_linha (ON CONFLICT DO NOTHING);
  4. Valida integridade referencial e totais (fato x prata).

Execução: python -m src.warehouse.load_warehouse
"""
from __future__ import annotations

import io
import json
import logging

import pandas as pd
from sqlalchemy import create_engine, text

from ..utils import config
from ..utils.storage import get_storage

log = logging.getLogger(__name__)

MEMBRO_DESCONHECIDO = -1

CATEGORIAS_ESPECIALIDADE = {
    # classificação aplicada somente para especialidades de pediatria (sufixo
    # explícito na fonte) e grandes grupos; demais ficam sem categoria.
}

NOME_MES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
    7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


def _engine():
    engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return engine


def aplicar_schema(engine) -> None:
    schema_sql = (config.ROOT_DIR / "src/warehouse/schema.sql").read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(schema_sql))
    log.info("Schema estrela aplicado (DDL idempotente)")


def carregar_dim_tempo(engine, prata: pd.DataFrame) -> None:
    datas = pd.Series(pd.to_datetime(prata["data_internacao"].dropna().unique()))
    linhas = []
    for d in datas:
        linhas.append({
            "sk_tempo": int(d.strftime("%Y%m%d")),
            "data": d.date(),
            "dia": int(d.day),
            "mes": int(d.month),
            "nome_mes": NOME_MES_PT[d.month],
            "trimestre": int((d.month - 1) // 3 + 1),
            "ano": int(d.year),
            "periodo_referencia": f"{d.year}-T{(d.month - 1) // 3 + 1}",
        })
    df = pd.DataFrame(linhas)
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO Dim_Tempo (sk_tempo, data, dia, mes, nome_mes, trimestre, ano, periodo_referencia)
                VALUES (:sk_tempo, :data, :dia, :mes, :nome_mes, :trimestre, :ano, :periodo_referencia)
                ON CONFLICT (sk_tempo) DO NOTHING
            """),
            df.to_dict("records"),
        )
    log.info("Dim_Tempo: %d datas", len(df))


def categoria_especialidade(nome_padronizado: str) -> str | None:
    n = nome_padronizado.lower()
    if "pediátrica" in n or "pediatrico" in n or n == "pediatria":
        return "Pediátricas"
    if "cirurgia" in n or "neurocirurgia" in n:
        return "Cirúrgicas"
    return "Clínicas"


def carregar_dim_especialidade(engine, prata: pd.DataFrame) -> None:
    pares = (
        prata[["especialidade_original", "especialidade_padronizada"]]
        .drop_duplicates()
    )
    records = [
        {
            "nome_original": r["especialidade_original"],
            "nome_padronizado": r["especialidade_padronizada"],
            "categoria": categoria_especialidade(r["especialidade_padronizada"]),
        }
        for _, r in pares.iterrows()
    ]
    # ordena para determinismo do BIGSERIAL em reexecuções
    records.sort(key=lambda x: x["nome_padronizado"])
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO Dim_Especialidade (nome_original, nome_padronizado, categoria)
                VALUES (:nome_original, :nome_padronizado, :categoria)
                ON CONFLICT (nome_padronizado) DO NOTHING
            """),
            records,
        )
    log.info("Dim_Especialidade: %d pares original->padrão", len(records))


def carregar_dim_municipio(engine, prata: pd.DataFrame) -> None:
    cols = [
        "municipio_original", "municipio_residencia_padronizado",
        "municipio_codigo_ibge", "municipio_uf", "municipio_classe_ibge",
        "classificacao_geografica",
    ]
    pares = prata[cols].drop_duplicates()
    records = [
        {
            "nome_original": r["municipio_original"],
            "nome_padronizado": r["municipio_residencia_padronizado"],
            "codigo_ibge": r["municipio_codigo_ibge"],
            "uf": r["municipio_uf"],
            "classe_ibge": r["municipio_classe_ibge"],
            "classificacao_geografica": r["classificacao_geografica"],
        }
        for _, r in pares.iterrows()
    ]
    records.sort(key=lambda x: (x["nome_padronizado"], x["nome_original"]))
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO Dim_Municipio
                    (nome_original, nome_padronizado, codigo_ibge, uf, classe_ibge, classificacao_geografica)
                VALUES (:nome_original, :nome_padronizado, :codigo_ibge, :uf, :classe_ibge, :classificacao_geografica)
                ON CONFLICT (nome_original, nome_padronizado) DO NOTHING
            """),
            records,
        )
    log.info("Dim_Municipio: %d pares original->padrão", len(records))


def carregar_dim_demografia(engine, prata: pd.DataFrame) -> None:
    pares = prata[["sexo_padronizado", "idade", "faixa_etaria"]].drop_duplicates()
    records = [
        {
            "sexo": r["sexo_padronizado"],
            "idade": (None if pd.isna(r["idade"]) else int(r["idade"])),
            "faixa_etaria": r["faixa_etaria"],
        }
        for _, r in pares.iterrows()
    ]
    records.sort(key=lambda x: (x["sexo"], -1 if x["idade"] is None else x["idade"], x["faixa_etaria"]))
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO Dim_Demografia (sexo, idade, faixa_etaria)
                VALUES (:sexo, :idade, :faixa_etaria)
                ON CONFLICT (sexo, COALESCE(idade, -1), faixa_etaria) DO NOTHING
            """),
            records,
        )
    log.info("Dim_Demografia: %d combinações", len(records))


def carregar_fato(engine, prata: pd.DataFrame) -> int:
    flags = []
    for _, r in prata.iterrows():
        f = []
        if r["horario_ausente"]:
            f.append("horario_ausente")
        if r["qualidade_duplicidade_exata"]:
            f.append("duplicidade_exata_preservada")
        if not r["idade_plausivel"]:
            f.append("idade_implausivel")
        flags.append(";".join(f) if f else None)

    records = []
    for i, (_, r) in enumerate(prata.iterrows()):
        dt = pd.Timestamp(r["data_internacao"])
        records.append({
            "sk_tempo": int(dt.strftime("%Y%m%d")),
            "espec_orig": r["especialidade_original"],
            "espec_pad": r["especialidade_padronizada"],
            "mun_orig": r["municipio_original"],
            "mun_pad": r["municipio_residencia_padronizado"],
            "sexo": r["sexo_padronizado"],
            "idade": (None if pd.isna(r["idade"]) else int(r["idade"])),
            "faixa": r["faixa_etaria"],
            "fonte": r["fonte_arquivo"],
            "hash": r["hash_linha"],
            "flags": flags[i],
        })

    inseridos = 0
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO Fato_Internacao
                    (sk_tempo, sk_especialidade, sk_municipio, sk_demografia,
                     qtd_internacoes, fonte_arquivo, hash_linha, flags_qualidade)
                SELECT
                    :sk_tempo,
                    (SELECT sk_especialidade FROM Dim_Especialidade
                      WHERE nome_original = :espec_orig AND nome_padronizado = :espec_pad),
                    (SELECT sk_municipio FROM Dim_Municipio
                      WHERE nome_original = :mun_orig AND nome_padronizado = :mun_pad),
                    (SELECT sk_demografia FROM Dim_Demografia
                      WHERE sexo = :sexo AND ((idade IS NULL AND :idade IS NULL) OR idade = :idade)
                            AND faixa_etaria = :faixa
                      ORDER BY sk_demografia LIMIT 1),
                    1, :fonte, :hash, :flags
                ON CONFLICT (hash_linha) DO NOTHING
            """),
            records,
        )
        inseridos = result.rowcount or 0
    log.info("Fato_Internacao: %d novas linhas inseridas", inseridos)
    return inseridos


def inserir_membros_desconhecidos(engine) -> None:
    """Garante membros desconhecidos com chave -1 nas 4 dimensões."""
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO Dim_Tempo (sk_tempo, data, dia, mes, nome_mes, trimestre, ano, periodo_referencia)
            VALUES (-1, DATE '1900-01-01', 1, 1, 'Desconhecido', 0, 0, 'Desconhecido')
            ON CONFLICT (sk_tempo) DO NOTHING
        """))
        conn.execute(text("""
            INSERT INTO Dim_Especialidade (sk_especialidade, nome_original, nome_padronizado, categoria)
            VALUES (-1, 'Desconhecido', 'Desconhecido', 'Desconhecido')
            ON CONFLICT (nome_padronizado) DO NOTHING
        """))
        conn.execute(text("""
            INSERT INTO Dim_Municipio (sk_municipio, nome_original, nome_padronizado,
                                       codigo_ibge, uf, classe_ibge, classificacao_geografica)
            VALUES (-1, 'Desconhecido', 'Desconhecido', NULL, NULL, 'DESCONHECIDO', 'Desconhecido')
            ON CONFLICT (nome_original, nome_padronizado) DO NOTHING
        """))
        conn.execute(text("""
            INSERT INTO Dim_Demografia (sk_demografia, sexo, idade, faixa_etaria)
            VALUES (-1, 'NÃO INFORMADO', NULL, 'Não informada')
            ON CONFLICT (sk_demografia) DO NOTHING
        """))
    log.info("Membros desconhecidos (-1) garantidos")


def validar(engine, prata: pd.DataFrame) -> dict:
    with engine.connect() as conn:
        total_fato = conn.execute(
            text("SELECT COUNT(*), COALESCE(SUM(qtd_internacoes),0) FROM Fato_Internacao")
        ).one()
        orfaos = conn.execute(text("""
            SELECT COUNT(*) FROM Fato_Internacao f
            LEFT JOIN Dim_Tempo t ON t.sk_tempo = f.sk_tempo
            LEFT JOIN Dim_Especialidade e ON e.sk_especialidade = f.sk_especialidade
            LEFT JOIN Dim_Municipio m ON m.sk_municipio = f.sk_municipio
            LEFT JOIN Dim_Demografia d ON d.sk_demografia = f.sk_demografia
            WHERE t.sk_tempo IS NULL OR e.sk_especialidade IS NULL
               OR m.sk_municipio IS NULL OR d.sk_demografia IS NULL
        """)).scalar()
        por_hash = conn.execute(
            text("SELECT COUNT(DISTINCT hash_linha) FROM Fato_Internacao")
        ).scalar()
    total_prata = len(prata)
    validacao = {
        "total_prata": int(total_prata),
        "total_fato": int(total_fato[0]),
        "soma_qtd_internacoes": int(total_fato[1]),
        "hash_distintos": int(por_hash),
        "registros_orfaos": int(orfaos),
        "consistente_fato_x_prata": int(total_fato[0]) == int(total_prata) and int(orfaos) == 0,
    }
    log.info("Validação DW: %s", validacao)
    return validacao


def executar() -> dict:
    storage = get_storage()
    parquet_prata = storage.get_bytes(
        config.BUCKET_SILVER, "hospital/internacoes/internacoes_prata_consolidado.parquet"
    )
    prata = pd.read_parquet(__import__("io").BytesIO(parquet_prata))

    engine = _engine()
    aplicar_schema(engine)
    inserir_membros_desconhecidos(engine)
    carregar_dim_tempo(engine, prata)
    carregar_dim_especialidade(engine, prata)
    carregar_dim_municipio(engine, prata)
    carregar_dim_demografia(engine, prata)
    carregar_fato(engine, prata)
    validacao = validar(engine, prata)

    relatorio = {"dw_carga": validacao}
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO Dim_Tempo (sk_tempo, data, dia, mes, nome_mes, trimestre, ano, periodo_referencia)
                VALUES (-1, DATE '1900-01-01', 1, 1, 'Desconhecido', 0, 0, 'Desconhecido')
                ON CONFLICT (sk_tempo) DO NOTHING
            """)
        )
    (config.PROCESSED_DIR / "relatorio_carga_dw.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    engine.dispose()
    return validacao


if __name__ == "__main__":
    from ..utils.logging_config import configurar_logging

    configurar_logging()
    executar()
