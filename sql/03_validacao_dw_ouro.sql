-- =============================================================================
-- 03 — VALIDAÇÃO CRUZADA: Data Warehouse x Camada Ouro
-- As métricas do dashboard devem ser idênticas aos conjuntos analíticos.
-- Verificação executada pelos testes automatizados (tests/test_validacao.py).
-- =============================================================================

-- V1. Total geral de internações
SELECT 'V1_total_geral' AS verificacao,
       SUM(qtd_internacoes) AS valor_dw
FROM Fato_Internacao;

-- V2. Por especialidade (top 5)
SELECT 'V2_especialidade' AS verificacao,
       e.nome_padronizado AS chave,
       SUM(qtd_internacoes) AS valor_dw
FROM Fato_Internacao f
JOIN Dim_Especialidade e ON e.sk_especialidade = f.sk_especialidade
GROUP BY e.nome_padronizado
ORDER BY valor_dw DESC
LIMIT 5;

-- V3. Por município (top 5)
SELECT 'V3_municipio' AS verificacao,
       m.nome_padronizado AS chave,
       SUM(qtd_internacoes) AS valor_dw
FROM Fato_Internacao f
JOIN Dim_Municipio m ON m.sk_municipio = f.sk_municipio
GROUP BY m.nome_padronizado
ORDER BY valor_dw DESC
LIMIT 5;

-- V4. Por sexo
SELECT 'V4_sexo' AS verificacao,
       d.sexo AS chave,
       SUM(qtd_internacoes) AS valor_dw
FROM Fato_Internacao f
JOIN Dim_Demografia d ON d.sk_demografia = f.sk_demografia
GROUP BY d.sexo;

-- V5. Por faixa etária
SELECT 'V5_faixa_etaria' AS verificacao,
       d.faixa_etaria AS chave,
       SUM(qtd_internacoes) AS valor_dw
FROM Fato_Internacao f
JOIN Dim_Demografia d ON d.sk_demografia = f.sk_demografia
GROUP BY d.faixa_etaria
ORDER BY valor_dw DESC;

-- V6. Por ano
SELECT 'V6_ano' AS verificacao,
       t.ano AS chave,
       SUM(qtd_internacoes) AS valor_dw
FROM Fato_Internacao f
JOIN Dim_Tempo t ON t.sk_tempo = f.sk_tempo
GROUP BY t.ano
ORDER BY t.ano;

-- V7. Por mês (primeiros 6 meses de 2024 para amostragem)
SELECT 'V7_mes_2024' AS verificacao,
       t.mes AS chave,
       SUM(qtd_internacoes) AS valor_dw
FROM Fato_Internacao f
JOIN Dim_Tempo t ON t.sk_tempo = f.sk_tempo
WHERE t.ano = 2024 AND t.mes <= 6
GROUP BY t.mes
ORDER BY t.mes;
