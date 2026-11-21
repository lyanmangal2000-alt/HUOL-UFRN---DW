# HUOL/UFRN — BI de Internações Hospitalares 2024–2025

Projeto de **Business Intelligence, Data Lake, Data Warehouse e Análise de Sentimentos** para o trabalho **"Hospital Privado — Rumo ao Credenciamento SUS"**, tendo como objeto de estudo o **Hospital Universitário Onofre Lopes (HUOL/UFRN/EBSERH)**, em Natal/RN.

Os dados são públicos e oficiais, publicados no portal de dados abertos do HUOL (gov.br), base **"06. Internações Hospitalares"**: 8 arquivos trimestrais (jan/2024 a dez/2025) com `data_internacao`, `especialidade`, `município`, `idade` e `sexo`.

---

## 1. Apresentação e problema de negócio

Um hospital privado pretende se preparar para o **credenciamento pelo SUS**. Para dimensionar essa decisão, o projeto analisa as internações hospitalares do HUOL — referência de atendimento público universitário na região — respondendo a seis perguntas de negócio:

1. Quais especialidades hospitalares concentram o maior número de internações?
2. Qual é o perfil etário e de gênero dos pacientes internados?
3. Existem padrões por município, especialmente Natal em comparação com os demais municípios?
4. Há sazonalidade nas internações, considerando os meses de 2024 e 2025?
5. O que as pessoas estão dizendo sobre o hospital?
6. Quais sentimentos predominam nos comentários do Instagram: positivos, negativos ou neutros?

As perguntas 1–4 são respondidas integralmente com os dados reais; as perguntas 5–6 dependem de acesso **autorizado** à Instagram Graph API — o módulo NLP está implementado e o dashboard apresenta estado de "integração pendente", **sem inventar resultados** (diretriz anti-simulação do enunciado).

## 2. Arquitetura

![Arquitetura](docs/arquitetura/diagrama_arquitetura.png)

```
Fontes oficiais (gov.br + IBGE + Instagram Graph API)
        │
        ▼
BRONZE ── cópia fiel (CSV/PDF) + manifestos com hash SHA-256      [bucket S3]
        │
        ▼
PRATA  ── padronização, validação IBGE, faixas etárias, Parquet   [bucket S3]
        │
        ▼
OURO   ── 11 conjuntos analíticos Parquet + relatórios qualidade  [bucket S3]
        │
        ▼
DATA WAREHOUSE ── PostgreSQL 16, esquema estrela                  [Docker]
        │
        ▼
DASHBOARD ── Streamlit + Plotly (7 telas, filtros globais SQL)
```

Componentes NLP: `instagram_client` (Graph API) → `clean_text` → `sentiment` (cardiffnlp/twitter-xlm-roberta-base-sentiment) → `topics` (TF-IDF) → Ouro.

## 3. Tecnologias

| Camada | Tecnologia |
|---|---|
| Ingestão/processamento | Python 3.12, pandas, PyArrow (Parquet) |
| Data Lake | S3-compatível — **MinIO** (Docker, produção) |
| Data Warehouse | PostgreSQL 16, SQLAlchemy, psycopg2 |
| NLP | Transformers (XLM-RoBERTa), scikit-learn (TF-IDF), spaCy pt-BR |
| Visualização | Streamlit, Plotly |
| Infra/testes | Docker Compose, pytest |

> **Nota sobre MinIO:** a distribuição comunitária do MinIO deixou de ser publicada para download direto (dl.min.io retorna 410). O `docker-compose.yml` deste projeto usa a imagem oficial `minio/minio` normalmente. No ambiente de desenvolvimento deste projeto, a API S3 foi validada com **SeaweedFS** (S3-compatível) — o código não muda: ambas expõem a mesma API S3, configurável por variáveis em `.env`.

## 4. Estrutura do projeto

```
huol-bi-analytics/
├── data/
│   ├── raw/                 # 8 CSVs + 8 PDFs oficiais (fonte da ingestão)
│   ├── reference/           # listas IBGE (Brasil e RN)
│   ├── processed/           # Parquet/relatórios gerados (reconstruíveis)
│   └── README.md
├── src/
│   ├── etl/                 # bronze_ingest · silver_transform · gold_curate
│   ├── warehouse/           # schema.sql (estrela) · load_warehouse.py
│   ├── nlp/                 # instagram_client · clean_text · sentiment · topics · pipeline
│   ├── dashboard/           # app.py · telas.py · data_access.py
│   └── utils/               # config · storage (S3/LOCAL) · ibge · especialidades · faixas_etarias
├── sql/                     # perguntas de negócio · qualidade · validação DW×Ouro
├── tests/                   # 49 testes pytest
├── docs/                    # arquitetura/, imagens/, dicionário, regras, qualidade, guia de gravação
├── scripts/                 # utilitários de operação
├── docker-compose.yml       # MinIO + PostgreSQL
├── requirements.txt
├── .env.example             # modelo de configuração (nunca versionar .env real)
├── .gitignore
└── README.md
```

## 5. Pré-requisitos

- Docker + Docker Compose (para MinIO e PostgreSQL);
- Python 3.11+ (recomendado 3.12);
- VS Code com terminal integrado;
- ~1 GB de espaço (dependências Python incl. transformers/torch).

## 6. Instalação e execução no VS Code (passo a passo)

Abra a pasta do projeto no VS Code (`File > Open Folder`) e use o terminal integrado:

```bash
# 1. Ambiente virtual
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configuração do ambiente
cp .env.example .env          # edite apenas se mudar host/portas/senhas

# 3. Infraestrutura (MinIO + PostgreSQL)
docker compose up -d
docker compose ps             # aguarde ambos "healthy"

# 4. Spacy pt-BR (para lematização do NLP — opcional)
python -m spacy download pt_core_news_sm

# 5. Pipeline ETL (ordem obrigatória)
python -m src.etl.bronze_ingest       # Bronze: 16 arquivos + manifestos
python -m src.etl.silver_transform    # Prata: padronização + Parquet
python -m src.etl.gold_curate         # Ouro: 11 conjuntos analíticos
python -m src.warehouse.load_warehouse  # DW: estrela + carga idempotente

# 6. NLP (sem token do Instagram, grava estado "integração pendente")
python -m src.nlp.pipeline

# 7. Dashboard
streamlit run src/dashboard/app.py    # abre http://localhost:8501

# 8. Testes
python -m pytest tests/ -v

# 9. Consultas SQL (outro terminal)
docker compose exec -T postgres psql -U huol -d huol_dw -c "\dt"
docker compose exec -T postgres psql -U huol -d huol_dw < sql/01_perguntas_negocio.sql
```

### Configuração do MinIO
- API S3: `http://localhost:9000` — Console: `http://localhost:9001` (minioadmin/minioadmin);
- Buckets `bronze`, `silver` e `gold` são criados automaticamente na primeira execução;
- Alternativa sem Docker: `STORAGE_BACKEND=LOCAL` em `.env` cria o espelho em `data/lake/`.

### Configuração do PostgreSQL
- `postgresql://huol:huol_secret@localhost:5432/huol_dw` (ver `DATABASE_URL` no `.env`);
- O esquema estrela é criado/aplicado de forma idempotente por `load_warehouse.py`;
- Credenciais só de desenvolvimento — troque em ambiente real e **nunca versionar**.

## 7. Fontes de dados e licenças

- Base hospitalar: **gov.br — HUOL/UFRN, "06. Internações Hospitalares"**
  `https://www.gov.br/hubrasil/pt-br/hospitais-universitarios/regiao-nordeste/huol-ufrn/acesso-a-informacao/dados-abertos-1/06%20-%20Internacoes%20Hospitalares`
- Municípios: **API de Localidades do IBGE** (`servicodados.ibge.gov.br`), cópias em `data/reference/`;
- Instagram: perfil público `@huol_ufrn` via **Instagram Graph API** (requer credenciais do Meta for Developers).

## 8. Dados: cobertura e limitações (resumo)

- **16.046 internações**, 01/01/2024 a 31/12/2025, 5 campos, sem identificador de paciente;
- Não existem campos de alta, permanência, desfecho — indicadores dependentes deles **não são calculados**;
- `município`: validado contra o IBGE; nomes ambíguos entre estados não são atribuídos (exceção única e documentada: Parnamirim RN/PE → RN);
- Idade 0 = recém-nascido/lactente (245 registros, preservados); 1 idade ausente mantida como "Não informada";
- 1 duplicidade exata (5 colunas idênticas) **preservada e sinalizada**;
- Detalhes completos: `docs/relatorio_qualidade.md` e Tela 7 do dashboard.

## 9. LGPD

- A base publicada **não contém** dados pessoais identificáveis (sem nome, prontuário, CPF ou identificador);
- No NLP, comentários são processados preservando o texto original apenas para auditoria interna; **autores nunca são exibidos** no dashboard nem na documentação;
- Credenciais (tokens do Instagram, senhas) ficam apenas em `.env` (ignorado pelo Git);
- Base de municípios e logs não contêm dados pessoais.

## 10. Dicionário de dados e regras

- `docs/dicionario_dados.md` — colunas da fonte, da Prata, do DW (fato e dimensões) e da Ouro;
- `docs/regras_transformacao.md` — cada regra aplicada e por quê;
- `docs/relatorio_qualidade.md` — recebidos/processados/rejeitados/pendentes por arquivo.

## 11. Principais consultas (respostas rápidas)

```sql
-- P1: especialidades com maior volume
SELECT e.nome_padronizado, SUM(f.qtd_internacoes) AS internacoes
FROM Fato_Internacao f JOIN Dim_Especialidade e USING (sk_especialidade)
GROUP BY 1 ORDER BY internacoes DESC LIMIT 10;

-- P3: Natal x interior
SELECT m.classificacao_geografica, SUM(f.qtd_internacoes)
FROM Fato_Internacao f JOIN Dim_Municipio m USING (sk_municipio)
GROUP BY 1 ORDER BY 2 DESC;
```

Arquivos completos: `sql/01_perguntas_negocio.sql`, `sql/02_qualidade_dados.sql`, `sql/03_validacao_dw_ouro.sql`.

## 12. Resultados-chave (dados reais validados)

| Indicador | Valor |
|---|---|
| Internações (2024+2025) | **16.046** |
| Especialidades distintas | 50 |
| Municípios padronizados | 197 |
| Especialidade líder | Cardiologia (1.440; 9,0%) |
| Idade média / mediana | 48,6 / 52 anos |
| Faixa predominante | 60 a 69 anos (20,0%) |
| Sexo | 50,7% feminino · 49,3% masculino |
| Origem | Interior RN 64,8% · Natal 34,9% |
| 2025 vs 2024 | +11,7% (todos os trimestres acima de 2024) |

## 13. Limitações e reprodução

- As perguntas 5–6 (sentimentos) permanecem em estado de preparação enquanto não houver acesso autorizado à Instagram Graph API; o módulo está pronto e testado (fixtures apenas para testes, claramente marcadas);
- A coleta dos CSVs foi feita em 17/11/2026; republicações no portal podem atualizar arquivos — reexecute o ETL (idempotente) para refletir;
- Guia completo de gravação do vídeo de apresentação: `docs/guia_gravacao.pdf`.

## 14. Referências

- Portal de dados abertos HUOL/UFRN (gov.br/hubrasil) — base 06;
- Plano de Dados Abertos do HUOL 2025–2027;
- IBGE — API de Localidades (municípios, códigos e UFs);
- Meta for Developers — Instagram Graph API (comentários, mídias);
- Kimball, R. — *The Data Warehouse Toolkit* (modelagem dimensional);
- cardiffnlp/twitter-xlm-roberta-base-sentiment (Hugging Face) — modelo de sentimentos multilíngue.
