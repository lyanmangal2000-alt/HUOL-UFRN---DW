# Regras de transformação — ETL HUOL/UFRN

Cada regra indica **o que é feito, por quê e onde está implementada**. Princípio geral: a estrutura real da fonte prevalece; nada é inventado; valores ausentes são preservados e sinalizados.

## 1. Ingestão (Bronze — `src/etl/bronze_ingest.py`)

| # | Regra |
|---|---|
| 1.1 | Os arquivos CSV/PDF reconhecidos e disponíveis em `data/raw/` são copiados **byte a byte** para `bronze/hospital/<ano>/<trimestre>/`; nenhum conteúdo é alterado. Este repositório inclui os 8 CSVs; os PDFs não são incluídos. |
| 1.2 | Cada arquivo gera manifesto JSON (`bronze/manifests/...`) com SHA-256, tamanho, URL de origem, período declarado e data de ingestão (UTC). |
| 1.3 | Ingestão **idempotente**: arquivo com mesmo hash existente é pulado; hash diferente marca `reingestao_com_hash_diferente=true`. |

## 2. Leitura e estrutura (Prata — `src/etl/silver_transform.py`)

| # | Regra |
|---|---|
| 2.1 | Encoding **ISO-8859-1 (Latin-1)**, separador `;`. |
| 2.2 | Cabeçalho validado contra 5 colunas; aceita `município` (real) e `municpio` (variante citada no enunciado). Cabeçalho inesperado **interrompe** o ETL (falha explícita). |
| 2.3 | A auditoria constatou que a base é **1 linha = 1 internação**; a quantidade analítica deriva da contagem de eventos. |

## 3. Datas e horários

| # | Regra |
|---|---|
| 3.1 | Formato completo `dd/mm/aaaa HH:MM`. |
| 3.2 | Fallback `dd/mm/aaaa`: registro **preservado** com `horario_ausente=true` (1 ocorrência: 01/03/2024). |
| 3.3 | Datas ilegíveis → **rejeitadas** (excluídas da Prata, listadas no relatório com linha e valor original). Na base atual: 0 rejeições. |
| 3.4 | `ano`, `mes`, `trimestre` derivados da data (sem uso do período do nome do arquivo para os números). |

## 4. Idade

| # | Regra |
|---|---|
| 4.1 | Conversão numérica; idade **0 é preservada** como recém-nascido/lactente (245 registros) — não é erro. |
| 4.2 | Idade ausente → nulo + faixa "Não informada"; **nunca imputada** (sem mediana/média). 1 ocorrência. |
| 4.3 | Idades fora de 0–120 → flag `idade_implausivel` (0 ocorrências na base atual). |
| 4.4 | Faixas: quinquenais até 19 anos; decenais de 20–79; 80+; "Não informada" (ver dicionário). |

## 5. Sexo

| # | Regra |
|---|---|
| 5.1 | `M`/`F` (2 registros) normalizados para MASCULINO/FEMININO; vazio (1 registro) → "NÃO INFORMADO". |
| 5.2 | O valor original é preservado em `sexo_original` para auditoria. |

## 6. Especialidades (`src/utils/especialidades.py`)

| # | Regra |
|---|---|
| 6.1 | Chave técnica ASCII (case/acento/hífen ignorados) garante unicidade — auditoria comprovou **0 colisões**. |
| 6.2 | Nome padrão: Title Case com acentuação correta (ex.: `CLINICA GERAL` → `Clínica Geral`) — correção de apresentação, **sem mesclar** especialidades distintas (Cirurgia Cardíaca ≠ Cardiovascular, etc.). |
| 6.3 | Especialidade não mapeada → fallback Title Case + flag `especialidade_fallback` (auditoria; atualmente 0). |

## 7. Municípios (`src/utils/ibge.py`)

| # | Regra |
|---|---|
| 7.1 | Normalização: uppercase, ASCII, pontuação removida (`OLHO-D'ÁGUA` = `Olho d'Água`). |
| 7.2 | Validação contra a base **nacional** do IBGE (5.571 municípios). Nome único → código + UF. |
| 7.3 | **Nomes históricos/variantes oficiais documentados** (aplicados antes da busca): `AÇU` → Assú (grafia IBGE, 2400208); `SÃO MIGUEL DE TOUROS` → São Miguel do Gostoso (renomeação oficial); `AUGUSTO SEVERO` → Campo Grande/RN (renomeação oficial, plebiscito 1991); `BOA SAÚDE` → Januário Cicco (nome listado pelo IBGE para o município hoje denominado Boa Saúde). |
| 7.4 | **Ambiguidades entre estados NÃO são atribuídas** (São Bento, Araruna, Boa Vista, Bonito, Conde, Paulista, Santa Rita → classe AMBIGUO, sem código). |
| 7.5 | **Exceção única e documentada**: `PARNAMIRIM` (RN 2403251 / PE 2610400) — atribuído ao RN por ser o único candidato no estado do hospital, com observação registrada na dimensão e no relatório de qualidade. |
| 7.6 | Sem correspondência (ex.: Japecanga, Pipa, Poço de Pedra, Cana Brava — distritos/localidades) → classe SEM_CORRESPONDENCIA, valor original preservado. Vazio ou literal "Não Informado" → NAO_INFORMADO. |
| 7.7 | Classificação geográfica: `Natal` (município de Natal); `Interior RN` (demais RN validados); `Outros estados` (UF validada ≠ RN); demais classes mantidas — **sem inferência de interior sem regra documentada**. |
| 7.8 | Não há conversão "residência × atendimento": o campo é tratado como **município informado na internação** (a documentação oficial descreve residência; o painel informa essa distinção). |

## 8. Duplicidades e preservação

| # | Regra |
|---|---|
| 8.1 | **Nenhum registro semelhante é descartado** por coincidir em idade/sexo/município/especialidade (sem identificador de paciente não é possível confirmar duplicidade). |
| 8.2 | Duplicidade **exata completa** (5 colunas iguais, 1 par em outnovdez/2024) é **preservada** e sinalizada via `qualidade_duplicidade_exata`. |
| 8.3 | `hash_linha` inclui a posição no arquivo para garantir hash único por evento preservado (rastreabilidade 1:1 com o DW). |

## 9. Carga do DW (`src/warehouse/load_warehouse.py`)

| # | Regra |
|---|---|
| 9.1 | DDL idempotente (`CREATE TABLE IF NOT EXISTS`); membros desconhecidos (−1) garantidos nas 4 dimensões. |
| 9.2 | Dimensões com upsert `ON CONFLICT ... DO NOTHING`; unicidade NULL-safe em Dim_Demografia (`COALESCE(idade,-1)`). |
| 9.3 | Fato: 1 linha Prata = 1 linha fato; idempotência pela chave `hash_linha`. |
| 9.4 | Validação pós-carga: total fato = total Prata; soma `qtd_internacoes` = contagem; 0 registros órfãos. |

## 10. NLP (`src/nlp/`)

| # | Regra |
|---|---|
| 10.1 | Coleta somente via **Instagram Graph API oficial** com token/permissões válidas; sem acesso, o pipeline grava estado `INTEGRACAO_PENDENTE` e **não gera resultados**. |
| 10.2 | Texto original sempre preservado (auditoria); limpeza remove URLs/menções/emojis, mantém termos de hashtags, remove stopwords pt-BR e lematiza (spaCy `pt_core_news_sm`, opcional). |
| 10.3 | Sentimentos: `cardiffnlp/twitter-xlm-roberta-base-sentiment` (multilíngue, adequado a pt-BR e a redes sociais); rótulos mapeados para Positivo/Negativo/Neutro; sarcasmo/ironia são limitações documentadas; avaliação por amostra revisada via `avaliar_manualmente()`. |
| 10.4 | Temas: TF-IDF (1–2 gramas, min_df=2) por classe de sentimento; amostras <3 comentários não geram ranking (evita instabilidade). |
| 10.5 | Anonimização: autores nunca são publicados no dashboard ou na documentação (LGPD). |
