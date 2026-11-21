# -*- coding: utf-8 -*-
"""ETL — Camada PRATA: padronização, validação e conversão para Parquet.

Regras aplicadas (todas documentadas em docs/regras_transformacao.md):

  Colunas originais  ->  colunas padronizadas
  data_internacao    ->  data_internacao (datetime), hora_internacao,
                         horario_ausente, ano, mes, trimestre
  especialidade      ->  especialidade_original, especialidade_padronizada
  município          ->  municipio_original, municipio_residencia_padronizado,
                         municipio_codigo_ibge, municipio_uf, municipio_classe_ibge,
                         classificacao_geografica
  idade              ->  idade (Int64), idade_ausente, faixa_etaria
  sexo               ->  sexo_original, sexo_padronizado, sexo_ausente

Política de preservação:
  - Nenhum registro semelhante é descartado por coincidir em idade/sexo/
    município/especialidade (a fonte não tem identificador de paciente).
  - Duplicidade EXATA completa (5 colunas iguais) é apenas SINALIZADA.
  - Valores ausentes não são preenchidos; viram categoria "Não informado(a)".
  - Únicos registros REJEITADOS: datas impossíveis de interpretar.

A granularidade da fonte é 1 linha = 1 internação (verificado na auditoria);
qtd_internacoes na Ouro/DW deriva da CONTAGEM de eventos.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
from datetime import datetime

import pandas as pd

from ..utils import config
from ..utils.especialidades import chave_ascii, padronizar_especialidade
from ..utils.faixas_etarias import faixa_etaria, eh_plausivel
from ..utils.ibge import ValidadorIBGE, classificacao_geografica
from ..utils.storage import agora_utc_iso, get_storage

log = logging.getLogger(__name__)

COLUNAS_ESPERADAS = {"data_internacao", "especialidade", "municipio", "idade", "sexo"}
NOMES_PADRAO = [
    "data_internacao", "especialidade", "municipio", "idade", "sexo",
]

TRIMESTRE_POR_MES = {1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 2, 7: 3, 8: 3, 9: 3, 10: 4, 11: 4, 12: 4}
MESES_ESPERADOS_TRIMESTRE = {1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8, 9], 4: [10, 11, 12]}


def decodificar_csv(data: bytes) -> pd.DataFrame:
    """Lê o CSV original (ISO-8859-1/Latin-1, separador ';')."""
    texto = data.decode("latin-1")
    return pd.read_csv(io.StringIO(texto), sep=";", dtype=str, keep_default_na=False)


def validar_cabecalho(colunas: list[str]) -> tuple[bool, str]:
    """Aceita o cabeçalho real ('município') e a variante sem acento/vogal
    ('municpio'), citada na documentação do trabalho como presente na fonte."""
    normalizadas = [chave_ascii(c) for c in colunas]
    # variantes aceitas para o campo de município
    normalizadas = [
        "MUNICIPIO" if c in {"MUNICIPIO", "MUNICPIO"} else c for c in normalizadas
    ]
    ok = normalizadas == [chave_ascii(c) for c in NOMES_PADRAO]
    detalhe = ";".join(colunas)
    return ok, detalhe


def parse_data(valor: str) -> tuple[pd.Timestamp | None, bool]:
    """Retorna (timestamp|None, horario_ausente).

    Formato completo: %d/%m/%Y %H:%M. Fallback: %d/%m/%Y (horário ausente,
    preservando o registro). Datas ilegíveis -> None (registro rejeitado).
    """
    v = str(valor).strip()
    if not v:
        return None, False
    ts = pd.to_datetime(v, format="%d/%m/%Y %H:%M", errors="coerce")
    if pd.notna(ts):
        return ts, False
    ts = pd.to_datetime(v, format="%d/%m/%Y", errors="coerce")
    if pd.notna(ts):
        return ts, True
    return None, False


def padronizar_sexo(valor: str) -> tuple[str, bool]:
    v = str(valor).strip().upper()
    if not v:
        return "NÃO INFORMADO", True
    if v in {"MASCULINO", "M"}:
        return "MASCULINO", v == "M"
    if v in {"FEMININO", "F"}:
        return "FEMININO", v == "F"
    return "NÃO INFORMADO", True


def transformar_dataframe(df: pd.DataFrame, fonte_arquivo: str,
                          periodo_declarado: str, trimestre_num: int,
                          validador: ValidadorIBGE) -> tuple[pd.DataFrame, list[dict]]:
    colunas_renomeadas = {c: NOMES_PADRAO[i] for i, c in enumerate(df.columns)}
    df = df.rename(columns=colunas_renomeadas)

    registros_rejeitados: list[dict] = []
    linhas_processadas: list[dict] = []
    cache_municipios: dict[str, object] = {}
    cache_especialidades: dict[str, tuple[str, bool]] = {}

    for idx, row in df.iterrows():
        ts, horario_ausente = parse_data(row["data_internacao"])
        if ts is None:
            registros_rejeitados.append({
                "fonte_arquivo": fonte_arquivo,
                "linha_arquivo": int(idx) + 2,  # +1 cabeçalho, +1 base 1
                "valor_original": str(row["data_internacao"]),
                "motivo": "data_internacao ilegível (formato não reconhecido)",
            })
            continue

        espec_orig = str(row["especialidade"]).strip()
        if espec_orig in cache_especialidades:
            espec_pad, espec_fallback = cache_especialidades[espec_orig]
        else:
            espec_pad, espec_fallback = padronizar_especialidade(espec_orig)
            cache_especialidades[espec_orig] = (espec_pad, espec_fallback)

        mun_orig = str(row["municipio"]).strip()
        if mun_orig in cache_municipios:
            mun = cache_municipios[mun_orig]
        else:
            mun = validador.resolver(mun_orig)
            cache_municipios[mun_orig] = mun

        idade_raw = str(row["idade"]).strip()
        idade = None
        if idade_raw:
            try:
                idade = int(float(idade_raw))
            except ValueError:
                idade = None

        sexo_orig = str(row["sexo"])
        sexo_pad, sexo_abreviado = padronizar_sexo(sexo_orig)

        linha = {
            "data_internacao": ts.to_pydatetime(),
            "hora_internacao": ts.strftime("%H:%M") if not horario_ausente else None,
            "horario_ausente": horario_ausente,
            "ano": int(ts.year),
            "mes": int(ts.month),
            "trimestre": int(TRIMESTRE_POR_MES[ts.month]),
            "especialidade_original": espec_orig,
            "especialidade_padronizada": espec_pad,
            "especialidade_fallback": bool(espec_fallback),
            "municipio_original": mun_orig,
            "municipio_residencia_padronizado": mun.nome,
            "municipio_codigo_ibge": mun.codigo_ibge,
            "municipio_uf": mun.uf,
            "municipio_classe_ibge": mun.classe,
            "municipio_observacao": mun.observacao,
            "classificacao_geografica": classificacao_geografica(mun.nome, mun.classe, mun.uf),
            "idade": idade,
            "idade_ausente": idade is None,
            "idade_plausivel": (idade is None) or eh_plausivel(idade),
            "sexo_original": sexo_orig,
            "sexo_padronizado": sexo_pad,
            "sexo_ausente": sexo_pad == "NÃO INFORMADO",
            "faixa_etaria": faixa_etaria(idade),
            "fonte_arquivo": fonte_arquivo,
            "fonte_periodo_declarado": periodo_declarado,
            "fonte_trimestre_num": trimestre_num,
        }
        linhas_processadas.append(linha)

    base = pd.DataFrame(linhas_processadas)
    if not base.empty:
        # duplicidade exata sinalizada (preservada) — chave nas 5 colunas da fonte
        chave_duplicidade = [
            "data_internacao", "especialidade_padronizada",
            "municipio_residencia_padronizado", "idade", "sexo_padronizado",
        ]
        base["qualidade_duplicidade_exata"] = base.duplicated(
            subset=chave_duplicidade, keep="first"
        )
        # hash de rastreabilidade por linha — inclui a posição no arquivo para
        # distinguir registros idênticos PRESERVADOS (duplicidade exata
        # sinalizada), garantindo hash único por evento
        def hash_linha(args) -> str:
            r, posicao = args
            texto = "|".join([
                r["data_internacao"].isoformat(), r["especialidade_original"],
                r["municipio_original"], str(r["idade"]), r["sexo_original"],
                r["fonte_arquivo"], str(posicao),
            ])
            return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:32]
        registros = base.to_dict("records")
        base["hash_linha"] = [
            hash_linha((r, i)) for i, r in enumerate(registros)
        ]
        base["horario_ausente"] = base["horario_ausente"].astype(bool)
    else:
        base["qualidade_duplicidade_exata"] = pd.Series(dtype=bool)
        base["hash_linha"] = pd.Series(dtype=str)

    return base, registros_rejeitados


def verificar_periodo(base_arquivo: pd.DataFrame, trimestre_num: int, ano_declarado: int) -> dict:
    meses = sorted(base_arquivo["mes"].unique().tolist()) if not base_arquivo.empty else []
    esperados = MESES_ESPERADOS_TRIMESTRE[trimestre_num]
    anos = sorted(base_arquivo["ano"].unique().tolist()) if not base_arquivo.empty else []
    coerente = set(meses).issubset(esperados) and all(a == ano_declarado for a in anos)
    return {
        "meses_encontrados": meses,
        "meses_esperados": esperados,
        "anos_encontrados": anos,
        "ano_declarado": ano_declarado,
        "coerente_periodo_x_conteudo": bool(coerente),
    }


def executar(storage=None) -> dict:
    config.ensure_dirs()
    storage = storage or get_storage()
    validador = ValidadorIBGE()

    chaves_bronze = [
        k for k in storage.list_keys(config.BUCKET_BRONZE, "hospital/")
        if k.endswith(".csv")
    ]
    log.info("Ingestão Prata: %d arquivos CSV na Bronze", len(chaves_bronze))

    bases, relatorios = [], []
    for chave in chaves_bronze:
        data = storage.get_bytes(config.BUCKET_BRONZE, chave)
        nome = chave.rsplit("/", 1)[-1]
        # metadados derivados do caminho bronze: hospital/<ano>/<TT>_<Periodo>/
        partes = chave.split("/")
        ano_declarado = int(partes[1])
        periodo = partes[2].split("_", 1)[1]
        trimestre_num = {"JanFevMar": 1, "AbrMaiJun": 2, "JulAgoSet": 3, "OutNovDez": 4}[periodo]

        df = decodificar_csv(data)
        ok, detalhe = validar_cabecalho(list(df.columns))
        if not ok:
            log.error("Cabeçalho inesperado em %s: %s", nome, detalhe)
            raise ValueError(f"Cabeçalho inesperado no arquivo {nome}: {detalhe}")

        base, rejeitados = transformar_dataframe(
            df, nome, f"{periodo} de {ano_declarado}", trimestre_num, validador
        )
        verificacao = verificar_periodo(base, trimestre_num, ano_declarado)

        rel = {
            "fonte_arquivo": nome,
            "registros_recebidos": int(len(df)),
            "registros_processados": int(len(base)),
            "registros_rejeitados": len(rejeitados),
            "rejeitados": rejeitados,
            "horario_ausente": int(base["horario_ausente"].sum()) if not base.empty else 0,
            "idade_ausente": int(base["idade_ausente"].sum()) if not base.empty else 0,
            "idade_zero_recem_nascido": int((base["idade"] == 0).sum()) if not base.empty else 0,
            "municipio_ausente_ou_nao_informado": int(
                (base["municipio_classe_ibge"] == "NAO_INFORMADO").sum()
            ) if not base.empty else 0,
            "sexo_ausente": int(base["sexo_ausente"].sum()) if not base.empty else 0,
            "duplicidades_exatas_preservadas": int(base["qualidade_duplicidade_exata"].sum())
            if not base.empty else 0,
            "especialidades_fallback": int(base["especialidade_fallback"].sum())
            if not base.empty else 0,
            "verificacao_periodo": verificacao,
        }
        relatorios.append(rel)
        bases.append(base)
        log.info(
            "Prata OK %s: %d recebidos / %d processados / %d rejeitados",
            nome, rel["registros_recebidos"], rel["registros_processados"],
            rel["registros_rejeitados"],
        )

    consolidado = pd.concat(bases, ignore_index=True)
    consolidado = consolidado.sort_values(
        ["data_internacao", "fonte_arquivo"], kind="stable"
    ).reset_index(drop=True)

    # ---- gravação em Parquet (particionado por ano) + consolidado ----
    caminho_local = config.PROCESSED_DIR / "internacoes_prata.parquet"
    consolidado.to_parquet(caminho_local, index=False)
    for ano, grupo in consolidado.groupby("ano"):
        key_part = f"hospital/internacoes/ano={int(ano)}/internacoes_prata_{int(ano)}.parquet"
        storage.put_bytes(
            config.BUCKET_SILVER, key_part,
            grupo.to_parquet(index=False),
        )
    storage.put_bytes(
        config.BUCKET_SILVER, "hospital/internacoes/internacoes_prata_consolidado.parquet",
        consolidado.to_parquet(index=False),
    )

    resumo = {
        "camada": "prata",
        "executado_em_utc": agora_utc_iso(),
        "total_recebidos": int(sum(r["registros_recebidos"] for r in relatorios)),
        "total_processados": int(len(consolidado)),
        "total_rejeitados": int(sum(r["registros_rejeitados"] for r in relatorios)),
        "pendentes_validacao": 0,
        "arquivos": relatorios,
        "arquivo_parquet_local": str(caminho_local),
        "municipios_distintos_padronizados": int(
            consolidado["municipio_residencia_padronizado"].nunique()
        ),
        "especialidades_distintas": int(consolidado["especialidade_padronizada"].nunique()),
        "duplicidades_exatas_preservadas": int(
            consolidado["qualidade_duplicidade_exata"].sum()
        ),
    }
    storage.put_json(
        config.BUCKET_SILVER, "hospital/_qualidade/relatorio_qualidade_prata.json", resumo
    )
    (config.PROCESSED_DIR / "relatorio_qualidade_prata.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info(
        "Prata concluída: %d processados (%d rejeitados)",
        resumo["total_processados"], resumo["total_rejeitados"],
    )
    return resumo


if __name__ == "__main__":
    from ..utils.logging_config import configurar_logging

    configurar_logging()
    executar()
