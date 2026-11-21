-- =============================================================================
-- 01 — RESPOSTAS ÀS PERGUNTAS DE NEGÓCIO (enunciado AV2)
-- Executar no Data Warehouse carregado: psql -d huol_dw -f sql/01_perguntas_negocio.sql
-- =============================================================================

-- =============================================================================
-- PERGUNTA 1 — Quais especialidades hospitalares concentram o maior número de
-- internações?
-- =============================================================================
SELECT
    e.nome_padronizado                            AS especialidade,
    SUM(f.qtd_internacoes)                        AS internacoes,
    ROUND(100.0 * SUM(f.qtd_internacoes)
          / SUM(SUM(f.qtd_internacoes)) OVER (), 2) AS participacao_pct,
    SUM(f.qtd_internacoes) FILTER (WHERE t.ano = 2024) AS internacoes_2024,
    SUM(f.qtd_internacoes) FILTER (WHERE t.ano = 2025) AS internacoes_2025
FROM Fato_Internacao f
JOIN Dim_Especialidade e ON e.sk_especialidade = f.sk_especialidade
JOIN Dim_Tempo t         ON t.sk_tempo = f.sk_tempo
GROUP BY e.nome_padronizado
ORDER BY internacoes DESC
LIMIT 15;

-- =============================================================================
-- PERGUNTA 2 — Qual é o perfil etário e de gênero dos pacientes internados?
-- =============================================================================
SELECT
    d.sexo,
    d.faixa_etaria,
    SUM(f.qtd_internacoes)                        AS internacoes,
    ROUND(100.0 * SUM(f.qtd_internacoes)
          / SUM(SUM(f.qtd_internacoes)) OVER (), 2) AS participacao_pct
FROM Fato_Internacao f
JOIN Dim_Demografia d ON d.sk_demografia = f.sk_demografia
GROUP BY d.sexo, d.faixa_etaria
ORDER BY d.sexo, internacoes DESC;

-- Resumo por sexo ---------------------------------------------------------------
SELECT
    d.sexo,
    SUM(f.qtd_internacoes)                        AS internacoes,
    ROUND(100.0 * SUM(f.qtd_internacoes)
          / SUM(SUM(f.qtd_internacoes)) OVER (), 2) AS participacao_pct
FROM Fato_Internacao f
JOIN Dim_Demografia d ON d.sk_demografia = f.sk_demografia
GROUP BY d.sexo
ORDER BY internacoes DESC;

-- Idade média/mediana dos registros com idade informada ------------------------
SELECT
    ROUND(AVG(d.idade)::numeric, 2) AS idade_media,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d.idade) AS idade_mediana,
    COUNT(*) AS registros_com_idade,
    SUM(CASE WHEN d.idade IS NULL THEN 1 ELSE 0 END) AS registros_sem_idade
FROM Fato_Internacao f
JOIN Dim_Demografia d ON d.sk_demografia = f.sk_demografia;

-- =============================================================================
-- PERGUNTA 3 — Existem padrões por município, especialmente Natal em comparação
-- com os demais municípios?
-- =============================================================================
SELECT
    m.classificacao_geografica,
    SUM(f.qtd_internacoes)                        AS internacoes,
    ROUND(100.0 * SUM(f.qtd_internacoes)
          / SUM(SUM(f.qtd_internacoes)) OVER (), 2) AS participacao_pct
FROM Fato_Internacao f
JOIN Dim_Municipio m ON m.sk_municipio = f.sk_municipio
GROUP BY m.classificacao_geografica
ORDER BY internacoes DESC;

-- Top 20 municípios --------------------------------------------------------------
SELECT
    m.nome_padronizado                            AS municipio,
    m.uf,
    m.classificacao_geografica,
    SUM(f.qtd_internacoes)                        AS internacoes,
    ROUND(100.0 * SUM(f.qtd_internacoes)
          / SUM(SUM(f.qtd_internacoes)) OVER (), 2) AS participacao_pct
FROM Fato_Internacao f
JOIN Dim_Municipio m ON m.sk_municipio = f.sk_municipio
GROUP BY m.nome_padronizado, m.uf, m.classificacao_geografica
ORDER BY internacoes DESC
LIMIT 20;

-- =============================================================================
-- PERGUNTA 4 — Há sazonalidade nas internações, considerando os meses de 2024
-- e 2025?
-- =============================================================================
SELECT
    t.ano,
    t.mes,
    MAX(t.nome_mes)                               AS nome_mes,
    SUM(f.qtd_internacoes)                        AS internacoes,
    ROUND(100.0 * SUM(f.qtd_internacoes)
          / SUM(SUM(f.qtd_internacoes)) OVER (PARTITION BY t.ano), 2) AS pct_no_ano
FROM Fato_Internacao f
JOIN Dim_Tempo t ON t.sk_tempo = f.sk_tempo
GROUP BY t.ano, t.mes
ORDER BY t.ano, t.mes;

-- Comparação trimestral (períodos equivalentes 2024 x 2025) ---------------------
SELECT
    t.trimestre,
    SUM(f.qtd_internacoes) FILTER (WHERE t.ano = 2024) AS ano_2024,
    SUM(f.qtd_internacoes) FILTER (WHERE t.ano = 2025) AS ano_2025,
    ROUND(100.0 * (
        SUM(f.qtd_internacoes) FILTER (WHERE t.ano = 2025) -
        SUM(f.qtd_internacoes) FILTER (WHERE t.ano = 2024)
    ) / NULLIF(SUM(f.qtd_internacoes) FILTER (WHERE t.ano = 2024), 0), 2) AS variacao_pct
FROM Fato_Internacao f
JOIN Dim_Tempo t ON t.sk_tempo = f.sk_tempo
GROUP BY t.trimestre
ORDER BY t.trimestre;

-- =============================================================================
-- PERGUNTAS 5 e 6 — "O que as pessoas estão dizendo sobre o hospital?" e
-- "Quais sentimentos predominam nos comentários do Instagram?"
--
-- ATENÇÃO: dependem da carga da tabela de comentários processados pelo módulo
-- NLP (src/nlp). Sem acesso autorizado à Instagram Graph API, as tabelas ficam
-- vazias e o dashboard apresenta estado de integração pendente — NENHUM
-- resultado simulado é apresentado como real.
-- =============================================================================
SELECT 'Tabela de comentários ainda não carregada — integração Instagram Graph API pendente'
       AS situacao
WHERE NOT EXISTS (SELECT 1 FROM information_schema.tables
                  WHERE table_name = 'Nlp_Comentarios');

-- Quando os comentários forem carregados (Nlp_Comentarios e Nlp_Termos), use:
--   SELECT sentimento, COUNT(*),
--          ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
--   FROM Nlp_Comentarios GROUP BY sentimento;
--
--   SELECT t.termo, t.sentimento, SUM(t.frequencia) AS freq_total
--   FROM Nlp_Termos t GROUP BY t.termo, t.sentimento
--   ORDER BY freq_total DESC LIMIT 30;
