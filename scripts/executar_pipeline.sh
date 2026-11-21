#!/bin/bash
# Executa o pipeline completo na ordem correta (espelho dos comandos do README)
set -e
cd "$(dirname "$0")/.."

echo "== [1/5] Bronze (ingestão fiel + manifestos) =="
python -m src.etl.bronze_ingest
echo "== [2/5] Prata (padronização + Parquet) =="
python -m src.etl.silver_transform
echo "== [3/5] Ouro (conjuntos analíticos) =="
python -m src.etl.gold_curate
echo "== [4/5] NLP (comentários, se disponíveis) =="
python -m src.nlp.pipeline || true
echo "== [5/5] Data Warehouse (esquema estrela + carga idempotente) =="
python -m src.warehouse.load_warehouse

echo "Pipeline concluído. Dashboard: streamlit run src/dashboard/app.py"
