# Pasta `data/`

## `raw/` — fontes oficiais (NÃO modificar)
Os 8 CSVs trimestrais oficiais do portal de dados abertos do HUOL/UFRN (gov.br),
de jan/2024 a dez/2025, ISO-8859-1, separador `;`.

Os PDFs originais não são incluídos neste repositório. A ingestão Bronze aceita
CSV e PDF quando presentes localmente, mas este projeto usa os 8 CSVs.

São a entrada da ingestão Bronze. A estrutura e os nomes devem ser preservados.

## `reference/` — referências oficiais
- `municipios_brasil_ibge.json` — 5.571 municípios (API de Localidades do IBGE, 17/11/2026);
- `municipios_rn_ibge.json` — 167 municípios do RN.

## `processed/` — artefatos gerados (reconstruíveis pelo ETL)
Parquet da Prata, 11 conjuntos analíticos da Ouro e relatórios JSON
(`relatorio_qualidade_prata.json`, `relatorio_qualidade_ouro.json`,
`relatorio_carga_dw.json`, `relatorio_nlp.json`).

## `lake/` — espelho local do Data Lake (apenas com `STORAGE_BACKEND=LOCAL`)
Mesma estrutura de buckets/chaves do S3 (bronze/silver/gold). Em produção,
use o MinIO via `docker compose up -d` — os dados ficam nos volumes do Docker.

> Nada nesta pasta é fonte de verdade: tudo pode ser reconstruído com
> `python -m src.etl.bronze_ingest && python -m src.etl.silver_transform &&
> python -m src.etl.gold_curate && python -m src.warehouse.load_warehouse`.
