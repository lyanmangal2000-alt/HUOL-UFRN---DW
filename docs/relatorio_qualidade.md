# Relatório de qualidade dos dados — HUOL/UFRN BI

**Fonte processada:** CSVs originais do portal oficial de dados abertos do HUOL/UFRN (gov.br), base "06. Internações Hospitalares" — **não houve necessidade de extração de PDF** (ingestão preferencial por CSV, conforme enunciado; os PDFs foram preservados na Bronze como evidência).

**Data da extração/coleta:** 17/11/2026 · **Cobertura:** 01/01/2024 a 31/12/2025 (8 trimestres).

## 1. Totais gerais

| Métrica | Valor |
|---|---|
| Arquivos recebidos | 8 CSVs + 8 PDFs (16 arquivos, todos com SHA-256 registrado) |
| Registros recebidos | **16.046** |
| Registros processados (Prata) | **16.046** (100%) |
| Registros rejeitados | **0** |
| Pendentes de validação | **0** |
| Duplicidades exatas preservadas | 1 (par de linhas idênticas em todas as 5 colunas) |
| Municípios distintos (padronizados) | 197 |
| Especialidades distintas | 50 |
| Datas distintas com internação | 15.858 (Dim_Tempo) |

## 2. Verificação por arquivo trimestral

| Trimestre | Recebidos | Processados | Rejeitados | Horário ausente | Idade ausente | Idade 0 | Sexo ausente | Duplicidades | Período × conteúdo coerente |
|---|---|---|---|---|---|---|---|---|---|
| JanFevMar 2024 | 1.642 | 1.642 | 0 | 1 | 0 | 36 | 0 | 0 | sim |
| AbrMaiJun 2024 | 1.783 | 1.783 | 0 | 0 | 1 | 31 | 1 | 0 | sim |
| JulAgoSet 2024 | 2.110 | 2.110 | 0 | 0 | 0 | 45 | 0 | 0 | sim |
| OutNovDez 2024 | 2.044 | 2.044 | 0 | 0 | 0 | 29 | 0 | 1 | sim |
| JanFevMar 2025 | 1.943 | 1.943 | 0 | 0 | 0 | 26 | 0 | 0 | sim |
| AbrMaiJun 2025 | 2.169 | 2.169 | 0 | 0 | 0 | 33 | 0 | 0 | sim |
| JulAgoSet 2025 | 2.274 | 2.274 | 0 | 0 | 0 | 17 | 0 | 0 | sim |
| OutNovDez 2025 | 2.081 | 2.081 | 0 | 0 | 0 | 28 | 0 | 0 | sim |
| **Total** | **16.046** | **16.046** | **0** | **1** | **1** | **245** | **1** | **1** | 8/8 |

## 3. Inconsistências identificadas e tratamentos aplicados

1. **Registro sem horário** (01/03/2024, Cirurgia Cardiovascular, Natal, 75, M): data válida; preservado com flag `horario_ausente`.
2. **Registro com município, idade e sexo vazios** (11/04/2024, Pediatria): preservado; município → "Não informado", idade → "Não informada", sexo → "NÃO INFORMADO" (sem imputação).
3. **2 registros com sexo "F"** (25/08/2025 e 06/09/2025): normalizados para FEMININO, valor original preservado.
4. **1 registro com sexo vazio**: classificado como "NÃO INFORMADO".
5. **245 registros com idade 0**: preservados como recém-nascidos/lactentes (faixa própria); não tratados como erro.
6. **1 duplicidade exata** (20/11/2024 08:37, Urologia, Natal, 77, M — duas linhas idênticas): **preservada** e sinalizada; sem identificador individual não é possível distinguir duplicação de ingestão de dois eventos reais.
7. **Cabeçalho**: os arquivos oficiais usam `município` (Latin-1); o enunciado cita `municpio`. O pipeline aceita ambas; prevalece a estrutura real (regra do trabalho).
8. **Especialidades**: 49 grafias distintas na fonte, sem colisões após normalização case/acento; 0 registros em fallback.

## 4. Divergência AbrMaiJun 2025 (verificação exigida)

O enunciado aponta divergência entre o título ("Abril–Junho") e a identificação de download ("Março–Abril–Maio") do 2º trimestre de 2025. **Verificação executada:**

- Título e slug publicados hoje no portal: "AbrMaiJun de 2025";
- Conteúdo real do CSV: **apenas meses 4, 5 e 6** (abril 737 · maio 749 · junho 683 = 2.169 registros), sem nenhum registro de março;
- **Conclusão: não há divergência no conteúdo atual**; a suspeita histórica do enunciado ficou registrada e o arquivo foi validado como abril–junho (coerente com o título).

## 5. Municípios — correspondência IBGE

| Situação | Municípios brutos (pares origem→padrão) | Registros |
|---|---|---|
| RN (validados, incl. históricos documentados) | 173 | 16.009 |
| Outros estados (UF única validada) | 18 | 21 |
| Ambíguos entre estados (não atribuídos) | 7 | 10 |
| Sem correspondência (localidades/distritos) | 4 | 4 |
| Não informado (vazio + literal "Não Informado") | 2 | 2 |

Correspondências históricas/variantes documentadas: `AÇU`/`ACU` → **Assú** (grafia oficial IBGE, 2400208); `SÃO MIGUEL DE TOUROS` → **São Miguel do Gostoso** (renomeação oficial); `AUGUSTO SEVERO` → **Campo Grande/RN** (renomeação oficial, plebiscito de 1991); `BOA SAÚDE` → **Januário Cicco** (denominação do IBGE para o município hoje denominado Boa Saúde).

**Ambiguidades não atribuídas** (existem em outros estados): São Bento (MA/PB), Araruna (PB/PR), Boa Vista (RR/PB), Bonito (PA/PE/BA/MS), Conde (PB/BA), Paulista (PB/PE), Santa Rita (MA/PB).

**Exceção documentada única**: Parnamirim (RN 2403251 / PE 2610400) atribuído ao RN — único candidato no estado do hospital; registrado na `Dim_Municipio.municipio_observacao`.

**Sem correspondência**: Japecanga (1), Poço de Pedra (1), Pipa (1 — praia/district de Tibau do Sul), Cana Brava (1). Mantidos com valor original.

## 6. Cobertura temporal

- Primeiro registro: 01/01/2024 08:14 · Último: 31/12/2025 23:59;
- 8/8 trimestres com conteúdo coerente ao título do arquivo;
- Nenhum registro fora do trimestre declarado em seu arquivo.

## 7. Validações automatizadas (pytest — 49 testes)

- Leitura, encoding, número de colunas, cabeçalhos; conversões de data (completa/sem horário/inválida);
- Idade (zero, ausente, plausibilidade) e faixas; sexo; especialidades; municípios IBGE (históricos, ambíguos, exceção Parnamirim);
- Prata: 16.046 registros, hash único por evento, duplicidade preservada, 0 fallback;
- DW: fato = Prata = 16.046; 0 órfãos; membros desconhecidos; consistência DW × Ouro (especialidades, municípios, anos);
- Dashboard: filtros alteram indicadores corretamente;
- Idempotência da Bronze (reexecução não duplica nem diverge).

## 8. Limitações metodológicas (transparência)

- **Sem identificador de paciente**: não é possível calcular tempo de permanência, readmissão ou mortalidade — indicadores dependentes desses campos não foram criados;
- **Município**: a documentação oficial descreve o campo como residência; o painel apresenta-o como "município informado na internação" para não confundir com local de atendimento;
- **Comparativos 2024×2025**: refletem os dados publicados; diferenças podem estar associadas à cobertura/completude da fonte, não necessariamente ao crescimento real da demanda;
- **NLP/Sentimentos**: módulo implementado e testado; sem comentários reais enquanto a Instagram Graph API não estiver autorizada — o dashboard exibe estado de integração pendente, sem qualquer simulação;
- **Exceção Parnamirim**: decisão contextual documentada (único nome ambíguo com candidato no RN); impacto: 421+ registros devidamente geolocalizados em vez de entrarem como "Ambíguo entre estados".
