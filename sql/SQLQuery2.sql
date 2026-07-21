-- ============================================
-- DIMENSION TABLES
-- ============================================

CREATE TABLE dim_cause (
    cause_id        INT PRIMARY KEY,
    cause_name      NVARCHAR(200) NOT NULL
);

CREATE TABLE dim_location (
    location_id     INT PRIMARY KEY,
    location_name   NVARCHAR(200) NOT NULL,
    region          NVARCHAR(100) NULL,      -- fill in later for map grouping
    iso3_code       CHAR(3) NULL             -- add later, needed for GeoPandas join
);

CREATE TABLE dim_measure (
    measure_id      INT PRIMARY KEY,
    measure_name    NVARCHAR(100) NOT NULL   -- Deaths, DALYs, YLDs, YLLs
);

CREATE TABLE dim_metric (
    metric_id       INT PRIMARY KEY,
    metric_name     NVARCHAR(50) NOT NULL    -- Number, Rate
);

CREATE TABLE dim_age (
    age_id          INT PRIMARY KEY,
    age_name        NVARCHAR(50) NOT NULL
);

CREATE TABLE dim_sex (
    sex_id          INT PRIMARY KEY,
    sex_name        NVARCHAR(20) NOT NULL
);

-- ============================================
-- FACT TABLE
-- ============================================

CREATE TABLE fact_disease_burden (
    fact_id         BIGINT IDENTITY(1,1) PRIMARY KEY,
    cause_id        INT NOT NULL FOREIGN KEY REFERENCES dim_cause(cause_id),
    location_id     INT NOT NULL FOREIGN KEY REFERENCES dim_location(location_id),
    measure_id      INT NOT NULL FOREIGN KEY REFERENCES dim_measure(measure_id),
    metric_id       INT NOT NULL FOREIGN KEY REFERENCES dim_metric(metric_id),
    age_id          INT NOT NULL FOREIGN KEY REFERENCES dim_age(age_id),
    sex_id          INT NOT NULL FOREIGN KEY REFERENCES dim_sex(sex_id),
    year            SMALLINT NOT NULL,
    val             FLOAT NOT NULL,
    upper            FLOAT NOT NULL,
    lower            FLOAT NOT NULL
);

CREATE INDEX idx_fact_cause ON fact_disease_burden(cause_id);
CREATE INDEX idx_fact_location ON fact_disease_burden(location_id);