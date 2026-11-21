-- =============================================================================
-- 02 — INDICADORES DE QUALIDADE DOS DADOS (Data Warehouse)
-- Registro de recebidos / processados / rejeitados / pendentes e inconsistências.
-- =============================================================================

-- 1. Cobertura temporal --------------------------------------------------------
SELECT MIN(t.data) AS primeira_internacao,
       MAX(t.data) AS ultima_internacao,
       COUNT(DISTINCT t.data) AS dias_com_internacao,
       COUNT(DISTINCT (t.ano, t.trimestre)) AS trimestres_cobertos
FROM Fato_Internacao f
JOIN Dim_Tempo t ON t.sk_tempo = f.sk_tempo;

-- 2. Registros sinalizados na carga ----------------------------------------------
SELECT COALESCE(flags_qualidade, '(sem sinalizações)') AS flag_qualidade,
       COUNT(*)                                        AS registros
FROM Fato_Internacao
GROUP BY flags_qualidade
ORDER BY registros DESC;

-- 3. Registros com campos ausentes ------------------------------------------------
SELECT
    SUM(CASE WHEN d.idade IS NULL THEN 1 ELSE 0 END)                          AS idade_ausente,
    SUM(CASE WHEN d.sexo = 'NÃO INFORMADO' THEN 1 ELSE 0 END)                 AS sexo_nao_informado,
    SUM(CASE WHEN m.nome_padronizado = 'Não Informado' THEN 1 ELSE 0 END)     AS municipio_nao_informado,
    COUNT(*)                                                                   AS total_registros
FROM Fato_Internacao f
JOIN Dim_Demografia d ON d.sk_demografia = f.sk_demografia
JOIN Dim_Municipio m  ON m.sk_municipio = f.sk_municipio;

-- 4. Municípios por classe IBGE ----------------------------------------------------
SELECT m.classe_ibge,
       COUNT(DISTINCT m.nome_original || '->' || m.nome_padronizado) AS pares_origem_pdr,
       COUNT(DISTINCT m.nome_padronizado)                            AS municipios_distintos
FROM Dim_Municipio m
GROUP BY m.classe_ibge
ORDER BY pares_origem_pdr DESC;

-- 5. Divergência período declarado x conteúdo (por arquivo fonte) ------------------
SELECT f.fonte_arquivo,
       COUNT(*)                                   AS registros,
       MIN(t.data)                                AS data_minima,
       MAX(t.data)                                AS data_maxima,
       MIN(t.periodo_referencia)                  AS periodo_real
FROM Fato_Internacao f
JOIN Dim_Tempo t ON t.sk_tempo = f.sk_tempo
GROUP BY f.fonte_arquivo
ORDER BY f.fonte_arquivo;

-- 6. Consistência: soma da fato x contagem de eventos ------------------------------
SELECT (SELECT SUM(qtd_internacoes) FROM Fato_Internacao)      AS soma_qtd,
       (SELECT COUNT(*) FROM Fato_Internacao)                  AS total_eventos,
       CASE WHEN (SELECT SUM(qtd_internacoes) FROM Fato_Internacao)
                 = (SELECT COUNT(*) FROM Fato_Internacao)
            THEN 'CONSISTENTE' ELSE 'DIVERGENTE' END           AS status;
