# Dicionário de dados — HUOL/UFRN BI

## 1. Fonte original (camada Bronze — cópia fiel)

Arquivos: `06. Internações Hospitalares (Referencia_ <Período> de <Ano>).csv` — 8 trimestrais, ISO-8859-1 (Latin-1), separador `;`, 5 colunas, CRLF.

| Coluna original | Tipo na fonte | Interpretação validada |
|---|---|---|
| `data_internacao` | texto `dd/mm/aaaa HH:MM` | data e horário da internação (1 registro sem horário, preservado) |
| `especialidade` | texto (maiúsculas) | especialidade hospitalar (49 valores distintos na fonte; 50 após padronização, incluindo "NÃO INFORMADO" como categoria de segurança) |
| `município` | texto | município informado na internação; a documentação oficial do portal descreve "município de residência". NÃO confundir com município de atendimento (campo que não existe na base) |
| `idade` | texto numérico | idade registrada (0 = recém-nascido/lactente, preservado; 1 registro sem idade) |
| `sexo` | texto | MASCULINO / FEMININO / 2 registros "F" (abreviação) / 1 registro vazio |

> O enunciado do trabalho menciona o cabeçalho `municpio`; nos arquivos oficiais efetivamente publicados o cabeçalho é `município` (com acento, codificado em Latin-1). Por regra do projeto, **prevalece a estrutura real da fonte**, e o pipeline aceita ambas as variantes.

## 2. Camada Prata (`internacoes_prata*.parquet`)

| Coluna | Tipo | Descrição |
|---|---|---|
| `data_internacao` | datetime | data/hora da internação (registro sem horário mantém data, com flag) |
| `hora_internacao` | string | HH:MM (nulo quando `horario_ausente`) |
| `horario_ausente` | bool | verdadeiro para o registro sem hora/minuto |
| `ano`, `mes`, `trimestre` | int | derivados da data |
| `especialidade_original` | string | valor exato da fonte |
| `especialidade_padronizada` | string | forma canônica (Title Case + acentuação correta) |
| `especialidade_fallback` | bool | verdadeiro se não estava no mapa (auditoria) — 0 registros |
| `municipio_original` | string | valor exato da fonte |
| `municipio_residencia_padronizado` | string | nome oficial IBGE (ou valor original quando sem correspondência) |
| `municipio_codigo_ibge` | string(7) | código IBGE quando correspondência única/documentada |
| `municipio_uf` | string(2) | UF do município validado |
| `municipio_classe_ibge` | string | RN / OUTROS_ESTADOS / AMBIGUO / SEM_CORRESPONDENCIA / NAO_INFORMADO |
| `municipio_observacao` | string | justificativa da correspondência (histórico/contexto/ambiguidade) |
| `classificacao_geografica` | string | Natal / Interior RN / Outros estados / Ambíguo entre estados / Sem correspondência IBGE / Não informado |
| `idade` | Int64 | idade (nulo = ausente, nunca imputada) |
| `idade_ausente` | bool | idade ausente |
| `idade_plausivel` | bool | idade entre 0 e 120 |
| `sexo_original` | string | valor exato da fonte |
| `sexo_padronizado` | string | MASCULINO / FEMININO / NÃO INFORMADO |
| `sexo_ausente` | bool | sexo ausente na fonte |
| `faixa_etaria` | string | faixa padronizada (ver §3) |
| `fonte_arquivo` | string | nome do arquivo trimestral de origem |
| `fonte_periodo_declarado` | string | período declarado no título do arquivo |
| `fonte_trimestre_num` | int | trimestre declarado |
| `qualidade_duplicidade_exata` | bool | 2ª ocorrência de linha idêntica nas 5 colunas (preservada) |
| `hash_linha` | char(32) | SHA-256 truncado do evento (inclui posição no arquivo) — rastreabilidade 1:1 com o DW |

## 3. Faixas etárias (regra documentada)

| Faixa | Regra |
|---|---|
| 0 a 11 meses (recém-nascido/lactente) | idade = 0 |
| 1 a 4 anos / 5 a 9 anos / 10 a 14 anos / 15 a 19 anos | quinquenais |
| 20–29, 30–39, 40–49, 50–59, 60–69, 70–79 | decenais |
| 80 anos ou mais | idade ≥ 80 |
| Não informada | idade ausente (nunca imputada) |

## 4. Data Warehouse (PostgreSQL, esquema estrela)

### Fato_Internacao — granularidade: 1 linha = 1 internação validada
| Coluna | Tipo | Descrição |
|---|---|---|
| `sk_internacao` | BIGSERIAL PK | chave substituta |
| `sk_tempo` | BIGINT FK | Dim_Tempo (YYYYMMDD) |
| `sk_especialidade` | BIGINT FK | Dim_Especialidade |
| `sk_municipio` | BIGINT FK | Dim_Municipio |
| `sk_demografia` | BIGINT FK | Dim_Demografia |
| `qtd_internacoes` | SMALLINT | 1 por evento (quantidade analítica = contagem) |
| `fonte_arquivo` | varchar(200) | rastreabilidade ao arquivo trimestral |
| `hash_linha` | char(32) UNIQUE | hash da Prata (idempotência da carga) |
| `flags_qualidade` | varchar | `horario_ausente; duplicidade_exata_preservada; idade_implausivel` |

### Dimensões
| Dimensão | Atributos | Membro desconhecido |
|---|---|---|
| Dim_Tempo | data, dia, mês, nome_mes, trimestre, ano, periodo_referencia | sk = −1 |
| Dim_Especialidade | nome_original, nome_padronizado (único), categoria (Clínicas/Cirúrgicas/Pediátricas) | sk = −1 |
| Dim_Municipio | nome_original, nome_padronizado, codigo_ibge, uf, classe_ibge, classificacao_geografica | sk = −1 |
| Dim_Demografia | sexo, idade (nulo = não informada), faixa_etaria — representa o REGISTRO, não o paciente | sk = −1 |

Vista `vw_internacoes` expõe a junção completa para BI.

## 5. Camada Ouro (conjuntos analíticos)

| Conjunto | Chaves | Métricas |
|---|---|---|
| internacoes_por_especialidade | especialidade, ano (2024, 2025) | total, participacao_pct (geral e por ano) |
| internacoes_por_municipio | municipio_padronizado, uf, classe, classificação | qtd, participacao_pct |
| internacoes_por_sexo | sexo | qtd, participacao_pct |
| internacoes_por_faixa_etaria | faixa_etaria (ordenada) | qtd, participacao_pct |
| internacoes_por_ano / por_trimestre / por_mes | chaves temporais | qtd (+ rótulos) |
| evolucao_acumulada | mês | qtd, acumulado |
| comparativo_2024_2025 | especialidade | qtds por ano, variação absoluta e % |
| natal_vs_demais | classificacao_geografica | qtd, participacao_pct |
| indicadores_gerais | indicador/valor | totais, médias, destaques |

## 6. NLP (`nlp_comentarios.parquet`, quando carregado)

| Coluna | Descrição |
|---|---|
| id_comentario, texto_original, data, autor, curtidas, id_publicacao | coleta Graph API (autor usado apenas internamente — nunca exibido) |
| texto_limpo | saída da limpeza (URLs/menções/emojis removidos, hashtags sem '#', stopwords, lematização pt-BR) |
| emojis_removidos | contagem (auditoria) |
| sentimento | Positivo / Negativo / Neutro |
| confianca | score do modelo (0–1) |
