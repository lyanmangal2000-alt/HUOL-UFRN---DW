# -*- coding: utf-8 -*-
"""ETL — Camada OURO: conjuntos analíticos prontos para o Data Warehouse e BI.

Produz tabelas agregadas a partir da Prata. qtd_internacoes deriva da
CONTAGEM de eventos de internação (granularidade validada na auditoria:
1 linha da fonte = 1 internação).

Todos os conjuntos possuem rastreabilidade até a origem (fonte_arquivo da Prata
e manifestos da Bronze) e são gravados em Parquet no bucket Ouro e em
data/processed/ para reuso local.
"""
from __future__ import annotations

import io
import json
import logging

import pandas as pd

from ..utils import config
from ..utils.storage import agora_utc_iso, get_storage

log = logging.getLogger(__name__)

MESES_NOME = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
    7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


def _pct(part: float, total: float) -> float:
    return round(100.0 * part / total, 2) if total else 0.0


def curar(prata: pd.DataFrame) -> dict[str, pd.DataFrame]:
    conjuntos: dict[str, pd.DataFrame] = {}
    total = len(prata)

    # ---------------- especialidade ----------------
    espec = (
        prata.groupby(["especialidade_padronizada", "ano"], dropna=False)
        .size().unstack("ano", fill_value=0).reset_index()
        .rename(columns={"especialidade_padronizada": "especialidade"})
    )
    espec["total"] = espec[[c for c in espec.columns if isinstance(c, int)]].sum(axis=1)
    espec["participacao_pct"] = espec["total"].apply(lambda x: _pct(x, total))
    for ano in [c for c in espec.columns if isinstance(c, int)]:
        espec[f"participacao_{ano}_pct"] = espec[ano].apply(lambda x: _pct(x, espec[ano].sum()))
    conjuntos["internacoes_por_especialidade"] = espec.sort_values("total", ascending=False)

    # ---------------- município ----------------
    muni = (
        prata.groupby(
            ["municipio_residencia_padronizado", "municipio_uf",
             "municipio_classe_ibge", "classificacao_geografica"], dropna=False
        ).size().reset_index(name="qtd")
        .rename(columns={"municipio_residencia_padronizado": "municipio_padronizado"})
        .sort_values("qtd", ascending=False)
    )
    muni["participacao_pct"] = muni["qtd"].apply(lambda x: _pct(x, total))
    conjuntos["internacoes_por_municipio"] = muni

    # ---------------- sexo ----------------
    sexo = prata.groupby("sexo_padronizado", dropna=False).size().reset_index(name="qtd")
    sexo.columns = ["sexo", "qtd"]
    sexo["participacao_pct"] = sexo["qtd"].apply(lambda x: _pct(x, total))
    conjuntos["internacoes_por_sexo"] = sexo

    # ---------------- faixa etária ----------------
    faixa = prata.groupby("faixa_etaria", dropna=False).size().reset_index(name="qtd")
    ordem = [f for f in [
        "0 a 11 meses (recém-nascido/lactente)", "1 a 4 anos", "5 a 9 anos",
        "10 a 14 anos", "15 a 19 anos", "20 a 29 anos", "30 a 39 anos",
        "40 a 49 anos", "50 a 59 anos", "60 a 69 anos", "70 a 79 anos",
        "80 anos ou mais", "Não informada",
    ] if f in faixa["faixa_etaria"].values]
    faixa["ordem"] = faixa["faixa_etaria"].map({r: i for i, r in enumerate(ordem)})
    faixa = faixa.sort_values("ordem").drop(columns="ordem")
    faixa["participacao_pct"] = faixa["qtd"].apply(lambda x: _pct(x, total))
    conjuntos["internacoes_por_faixa_etaria"] = faixa

    # ---------------- tempo: ano / trimestre / mês ----------------
    conjuntos["internacoes_por_ano"] = (
        prata.groupby("ano").size().reset_index(name="qtd").sort_values("ano")
    )
    trim = (
        prata.groupby(["ano", "trimestre"]).size().reset_index(name="qtd").sort_values(["ano", "trimestre"])
    )
    trim["rotulo"] = trim["ano"].astype(str) + "-T" + trim["trimestre"].astype(str)
    conjuntos["internacoes_por_trimestre"] = trim

    mes = (
        prata.groupby(["ano", "mes"]).size().reset_index(name="qtd").sort_values(["ano", "mes"])
    )
    mes["nome_mes"] = mes["mes"].map(MESES_NOME)
    mes["rotulo"] = mes["nome_mes"].str[:3] + "/" + mes["ano"].astype(str)
    conjuntos["internacoes_por_mes"] = mes

    # evolução acumulada por mês
    mes_ac = mes.copy()
    mes_ac["acumulado"] = mes_ac["qtd"].cumsum()
    conjuntos["evolucao_acumulada"] = mes_ac

    # ---------------- comparativo 2024 x 2025 ----------------
    piv = (
        prata.groupby(["especialidade_padronizada", "ano"]).size()
        .unstack("ano", fill_value=0).reset_index()
        .rename(columns={"especialidade_padronizada": "especialidade"})
    )
    for col_ano in (2024, 2025):
        if col_ano not in piv.columns:
            piv[col_ano] = 0
    piv["variacao_absoluta"] = piv[2025] - piv[2024]
    piv["variacao_pct"] = piv.apply(
        lambda r: round(100.0 * (r[2025] - r[2024]) / r[2024], 2) if r[2024] else None, axis=1
    )
    conjuntos["comparativo_2024_2025"] = piv.sort_values("total_geral", ascending=False) \
        if "total_geral" in piv.columns else piv.sort_values(2024, ascending=False)

    # ---------------- Natal x interior ----------------
    geo = prata.groupby("classificacao_geografica").size().reset_index(name="qtd")
    geo["participacao_pct"] = geo["qtd"].apply(lambda x: _pct(x, total))
    conjuntos["natal_vs_demais"] = geo

    # ---------------- indicadores gerais ----------------
    idades_validas = prata.loc[prata["idade"].notna(), "idade"]
    faixa_pred = (
        conjuntos["internacoes_por_faixa_etaria"].sort_values("qtd", ascending=False).iloc[0]
    )
    espec_top = conjuntos["internacoes_por_especialidade"].iloc[0]
    muni_top = conjuntos["internacoes_por_municipio"].iloc[0]
    dmin, dmax = prata["data_internacao"].min(), prata["data_internacao"].max()
    indicadores = {
        "total_internacoes": int(total),
        "periodo_minimo": str(dmin.date()),
        "periodo_maximo": str(dmax.date()),
        "total_especialidades": int(prata["especialidade_padronizada"].nunique()),
        "total_municipios": int(prata["municipio_residencia_padronizado"].nunique()),
        "idade_media_registros_validos": round(float(idades_validas.mean()), 2) if len(idades_validas) else None,
        "idade_mediana_registros_validos": float(idades_validas.median()) if len(idades_validas) else None,
        "registros_com_idade": int(len(idades_validas)),
        "registros_sem_idade": int(total - len(idades_validas)),
        "faixa_etaria_predominante": str(faixa_pred["faixa_etaria"]),
        "faixa_etaria_predominante_qtd": int(faixa_pred["qtd"]),
        "especialidade_maior_volume": str(espec_top["especialidade"]),
        "especialidade_maior_volume_qtd": int(espec_top["total"]),
        "municipio_maior_volume": str(muni_top["municipio_padronizado"]),
        "municipio_maior_volume_qtd": int(muni_top["qtd"]),
    }
    for _, r in conjuntos["internacoes_por_sexo"].iterrows():
        indicadores[f"pct_{str(r['sexo']).lower().replace(' ', '_')}"] = float(r["participacao_pct"])
    conjuntos["indicadores_gerais"] = pd.DataFrame(
        [{"indicador": k, "valor": ("" if v is None else str(v))} for k, v in indicadores.items()]
    )
    conjuntos["_indicadores_dict"] = indicadores  # não será gravado como parquet

    return conjuntos


def executar(storage=None) -> tuple[dict[str, pd.DataFrame], dict]:
    config.ensure_dirs()
    storage = storage or get_storage()

    parquet_prata = storage.get_bytes(
        config.BUCKET_SILVER, "hospital/internacoes/internacoes_prata_consolidado.parquet"
    )
    prata = pd.read_parquet(io.BytesIO(parquet_prata))
    log.info("Ouro: %d registros da Prata recebidos", len(prata))

    conjuntos = curar(prata)
    indicadores = conjuntos.pop("_indicadores_dict")

    relatorio_prata = json.loads(
        storage.get_bytes(
            config.BUCKET_SILVER, "hospital/_qualidade/relatorio_qualidade_prata.json"
        )
    )

    # gravação no Ouro
    for nome, df in conjuntos.items():
        if nome.startswith("_"):
            continue
        storage.put_bytes(config.BUCKET_GOLD, f"hospital/{nome}.parquet", df.to_parquet(index=False))
        df.to_parquet(config.PROCESSED_DIR / f"{nome}.parquet", index=False)

    qualidade = {
        "camada": "ouro",
        "executado_em_utc": agora_utc_iso(),
        "conjuntos_produzidos": sorted([c for c in conjuntos if not c.startswith("_")]),
        "indicadores_gerais": indicadores,
        "relatorio_prata": relatorio_prata,
    }
    storage.put_json(config.BUCKET_GOLD, "hospital/_qualidade/relatorio_qualidade_ouro.json", qualidade)
    (config.PROCESSED_DIR / "relatorio_qualidade_ouro.json").write_text(
        json.dumps(qualidade, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("Ouro concluída: %d conjuntos analíticos", len(conjuntos))
    return conjuntos, qualidade


if __name__ == "__main__":
    from ..utils.logging_config import configurar_logging

    configurar_logging()
    executar()
