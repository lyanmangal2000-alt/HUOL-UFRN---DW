-- =============================================================================
-- DATA WAREHOUSE HUOL/UFRN — Modelo dimensional (esquema estrela)
-- PostgreSQL 16+
--
-- Granularidade da Fato_Internacao: 1 linha = 1 evento de internação validado.
-- qtd_internacoes = 1 por evento (a quantidade analítica deriva da contagem).
--
-- Políticas:
--   * Chaves substitutas (BIGSERIAL) nas dimensões;
--   * Membros desconhecidos com chave -1 (padrão dimensional);
--   * Carga idempotente (ON CONFLICT DO NOTHING / UPDATE) — ver load_warehouse.py;
--   * Dim_Demografia representa atributos do REGISTRO, não identidade de paciente.
-- =============================================================================

-- ---------------------------------------------------------------- Dim_Tempo
CREATE TABLE IF NOT EXISTS Dim_Tempo (
    sk_tempo          BIGINT PRIMARY KEY,
    data              DATE NOT NULL UNIQUE,
    dia               SMALLINT NOT NULL,
    mes               SMALLINT NOT NULL,
    nome_mes          VARCHAR(20) NOT NULL,
    trimestre         SMALLINT NOT NULL,
    ano               SMALLINT NOT NULL,
    periodo_referencia VARCHAR(20) NOT NULL   -- ex.: '2024-T1'
);

-- ------------------------------------------------------- Dim_Especialidade
CREATE TABLE IF NOT EXISTS Dim_Especialidade (
    sk_especialidade   BIGSERIAL PRIMARY KEY,
    nome_original      VARCHAR(120) NOT NULL,
    nome_padronizado   VARCHAR(120) NOT NULL UNIQUE,
    categoria          VARCHAR(60)          -- clínicas / cirúrgicas / pediátricas
);

-- ---------------------------------------------------------- Dim_Municipio
CREATE TABLE IF NOT EXISTS Dim_Municipio (
    sk_municipio        BIGSERIAL PRIMARY KEY,
    nome_original       VARCHAR(120) NOT NULL,
    nome_padronizado    VARCHAR(120) NOT NULL,
    codigo_ibge         CHAR(7),
    uf                  CHAR(2),
    classe_ibge         VARCHAR(30) NOT NULL,   -- RN | OUTROS_ESTADOS | AMBIGUO | ...
    classificacao_geografica VARCHAR(40) NOT NULL, -- Natal | Interior RN | ...
    CONSTRAINT dim_municipio_unico UNIQUE (nome_original, nome_padronizado)
);

-- ----------------------------------------------------------- Dim_Demografia
CREATE TABLE IF NOT EXISTS Dim_Demografia (
    sk_demografia    BIGSERIAL PRIMARY KEY,
    sexo             VARCHAR(20) NOT NULL,     -- MASCULINO | FEMININO | NÃO INFORMADO
    idade            SMALLINT,                 -- NULL quando ausente
    faixa_etaria     VARCHAR(45) NOT NULL
);

-- unicidade NULL-safe: idades ausentes são tratadas como -1 no índice
CREATE UNIQUE INDEX IF NOT EXISTS ux_dim_demografia
    ON Dim_Demografia (sexo, COALESCE(idade, -1), faixa_etaria);

-- -------------------------------------------------------- Fato_Internacao
CREATE TABLE IF NOT EXISTS Fato_Internacao (
    sk_internacao    BIGSERIAL PRIMARY KEY,
    sk_tempo         BIGINT NOT NULL REFERENCES Dim_Tempo (sk_tempo),
    sk_especialidade BIGINT NOT NULL REFERENCES Dim_Especialidade (sk_especialidade),
    sk_municipio     BIGINT NOT NULL REFERENCES Dim_Municipio (sk_municipio),
    sk_demografia    BIGINT NOT NULL REFERENCES Dim_Demografia (sk_demografia),
    qtd_internacoes  SMALLINT NOT NULL DEFAULT 1,
    fonte_arquivo    VARCHAR(200) NOT NULL,
    hash_linha       CHAR(32) NOT NULL UNIQUE,  -- rastreabilidade 1:1 com a Prata
    flags_qualidade  VARCHAR(200)               -- horario_ausente; duplicidade_exata; ...
);

-- ------------------------------------------------------------------ Índices
CREATE INDEX IF NOT EXISTS ix_fato_tempo       ON Fato_Internacao (sk_tempo);
CREATE INDEX IF NOT EXISTS ix_fato_especial    ON Fato_Internacao (sk_especialidade);
CREATE INDEX IF NOT EXISTS ix_fato_municipio   ON Fato_Internacao (sk_municipio);
CREATE INDEX IF NOT EXISTS ix_fato_demografia  ON Fato_Internacao (sk_demografia);
CREATE INDEX IF NOT EXISTS ix_dim_tempo_ano    ON Dim_Tempo (ano, mes);
CREATE INDEX IF NOT EXISTS ix_dim_municipio_uf ON Dim_Municipio (uf);

-- -------------------------------------------------- Vista analítica auxiliar
CREATE OR REPLACE VIEW vw_internacoes AS
SELECT
    f.sk_internacao,
    t.data,
    t.ano,
    t.mes,
    t.nome_mes,
    t.trimestre,
    t.periodo_referencia,
    e.nome_padronizado AS especialidade,
    m.nome_padronizado AS municipio,
    m.codigo_ibge,
    m.uf,
    m.classificacao_geografica,
    d.sexo,
    d.idade,
    d.faixa_etaria,
    f.qtd_internacoes,
    f.fonte_arquivo
FROM Fato_Internacao f
JOIN Dim_Tempo         t ON t.sk_tempo = f.sk_tempo
JOIN Dim_Especialidade e ON e.sk_especialidade = f.sk_especialidade
JOIN Dim_Municipio     m ON m.sk_municipio = f.sk_municipio
JOIN Dim_Demografia    d ON d.sk_demografia = f.sk_demografia;
