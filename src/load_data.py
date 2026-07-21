"""
Load IHME GBD CSV data into the DiseaseBurdenAtlas SQL Server star schema.

Usage:
    python load_data.py

"""

import pandas as pd
from sqlalchemy import create_engine
import urllib


# 1. CONFIG — adjust these two lines to match your setup
CSV_PATH = "../data/raw/IHME-GBD_2023_DATA-85e41064-1.csv"  
SERVER = r"DESKTOP-RNQBFDM\SQLEXPRESS"
DATABASE = "DiseaseBurdenAtlas"


# 2. BUILD CONNECTION (Windows Authentication, ODBC Driver 18)
params = urllib.parse.quote_plus(
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"Trusted_Connection=yes;"
    f"TrustServerCertificate=yes;"
)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")


# 3. READ CSV (force UTF-8 to fix accented country names)
print("Reading CSV...")
df = pd.read_csv(CSV_PATH, encoding="utf-8")

# Drop the redundant population_group columns (all "1 / All Population")
df = df.drop(columns=["population_group_id", "population_group_name"], errors="ignore")

print(f"Loaded {len(df):,} rows.")
print(df.columns.tolist())


# 4. BUILD & LOAD DIMENSION TABLES (deduped)
def load_dimension(df, id_col, name_col, table_name, engine):
    dim = df[[id_col, name_col]].drop_duplicates().rename(
        columns={id_col: id_col, name_col: name_col}
    )
    dim.to_sql(table_name, engine, if_exists="append", index=False)
    print(f"Loaded {len(dim):,} rows into {table_name}")

print("\nLoading dimension tables...")
load_dimension(df, "cause_id", "cause_name", "dim_cause", engine)
load_dimension(df, "location_id", "location_name", "dim_location", engine)
load_dimension(df, "measure_id", "measure_name", "dim_measure", engine)
load_dimension(df, "metric_id", "metric_name", "dim_metric", engine)
load_dimension(df, "age_id", "age_name", "dim_age", engine)
load_dimension(df, "sex_id", "sex_name", "dim_sex", engine)


# 5. LOAD FACT TABLE
fact_cols = [
    "cause_id", "location_id", "measure_id", "metric_id",
    "age_id", "sex_id", "year", "val", "upper", "lower"
]
fact_df = df[fact_cols]

print("\nLoading fact table (this may take a minute for ~16k rows)...")
fact_df.to_sql("fact_disease_burden", engine, if_exists="append", index=False, chunksize=1000)

print(f"\nDone. Loaded {len(fact_df):,} rows into fact_disease_burden.")
