"""
Cluster countries by their disease burden "fingerprint" — i.e. their
DALYs rate profile across all 10 causes — using K-Means.

Usage:
    python cluster_countries.py

This runs in two passes:
  PASS 1: Computes the elbow curve + silhouette scores for k=2..10
          and saves a plot to ../notebooks/elbow_plot.png so you can
          pick the best k.
  PASS 2: Once you set CHOSEN_K below (after reviewing the plot),
          re-run to assign each country to a cluster and write the
          result back to a new dim_cluster / country_cluster table
          in SQL Server.
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text
import urllib

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
SERVER = r"DESKTOP-RNQBFDM\SQLEXPRESS"
DATABASE = "DiseaseBurdenAtlas"

# Set this to None for the first run (elbow method only).
# After reviewing ../notebooks/elbow_plot.png, set it to your chosen
# k (e.g. 4) and re-run to get final cluster assignments.
CHOSEN_K = 4

# ------------------------------------------------------------------
# CONNECT & PULL DATA
# ------------------------------------------------------------------
params = urllib.parse.quote_plus(
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"Trusted_Connection=yes;"
    f"TrustServerCertificate=yes;"
)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

print("Pulling DALYs rate data...")
query = """
SELECT
    l.location_id,
    l.location_name,
    l.iso3_code,
    c.cause_name,
    f.val
FROM fact_disease_burden f
JOIN dim_location l ON f.location_id = l.location_id
JOIN dim_cause c ON f.cause_id = c.cause_id
JOIN dim_measure me ON f.measure_id = me.measure_id
JOIN dim_metric met ON f.metric_id = met.metric_id
WHERE met.metric_name = 'Rate'
  AND me.measure_name = 'DALYs (Disability-Adjusted Life Years)'
"""
df = pd.read_sql(query, engine)
print(f"Pulled {len(df):,} rows.")

# ------------------------------------------------------------------
# PIVOT: one row per country, one column per cause
# ------------------------------------------------------------------
pivot = df.pivot_table(
    index=["location_id", "location_name", "iso3_code"],
    columns="cause_name",
    values="val"
).reset_index()

# Drop any country with missing values across causes (can't cluster incomplete rows)
before = len(pivot)
pivot = pivot.dropna()
after = len(pivot)
if before != after:
    print(f"Dropped {before - after} countries with incomplete data.")

feature_cols = [c for c in pivot.columns if c not in ("location_id", "location_name", "iso3_code")]
X = pivot[feature_cols].values

# Standardize — essential since causes have wildly different scales
# (e.g. cardiovascular DALYs rate vs diarrheal disease DALYs rate)
X_scaled = StandardScaler().fit_transform(X)

# ------------------------------------------------------------------
# PASS 1: ELBOW METHOD + SILHOUETTE SCORES
# ------------------------------------------------------------------
if CHOSEN_K is None:
    print("\nRunning elbow method for k=2..10...")
    inertias = []
    silhouettes = []
    k_range = range(2, 11)

    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)
        inertias.append(km.inertia_)
        silhouettes.append(silhouette_score(X_scaled, labels))
        print(f"  k={k}: inertia={km.inertia_:.1f}, silhouette={silhouettes[-1]:.3f}")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    ax1.plot(list(k_range), inertias, marker="o")
    ax1.set_xlabel("k")
    ax1.set_ylabel("Inertia (within-cluster sum of squares)")
    ax1.set_title("Elbow Method")

    ax2.plot(list(k_range), silhouettes, marker="o", color="darkorange")
    ax2.set_xlabel("k")
    ax2.set_ylabel("Silhouette Score")
    ax2.set_title("Silhouette Score (higher = better separation)")

    plt.tight_layout()
    plt.savefig("../notebooks/elbow_plot.png", dpi=150)
    print("\nSaved elbow plot to ../notebooks/elbow_plot.png")
    print("Review the plot, pick your k (look for the 'elbow' bend + a strong silhouette score),")
    print("then set CHOSEN_K at the top of this script and re-run.")

# ------------------------------------------------------------------
# PASS 2: FINAL CLUSTERING + WRITE TO DATABASE
# ------------------------------------------------------------------
else:
    print(f"\nRunning final K-Means with k={CHOSEN_K}...")
    km = KMeans(n_clusters=CHOSEN_K, random_state=42, n_init=10)
    pivot["cluster"] = km.fit_predict(X_scaled)

    sil = silhouette_score(X_scaled, pivot["cluster"])
    print(f"Silhouette score: {sil:.3f}")

    # Print cluster profiles (mean DALYs rate per cause, per cluster)
    print("\nCluster profiles (mean DALYs rate per cause):")
    profile = pivot.groupby("cluster")[feature_cols].mean().round(0)
    print(profile.to_string())

    print("\nCountries per cluster:")
    for c in sorted(pivot["cluster"].unique()):
        countries = pivot[pivot["cluster"] == c]["location_name"].tolist()
        print(f"\nCluster {c} ({len(countries)} countries): {', '.join(countries[:10])}{' ...' if len(countries) > 10 else ''}")

    # ------------------------------------------------------------------
    # WRITE TO SQL SERVER
    # ------------------------------------------------------------------
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS country_cluster"))
        conn.execute(text("""
            CREATE TABLE country_cluster (
                location_id INT PRIMARY KEY,
                cluster_id  INT NOT NULL
            )
        """))

    out = pivot[["location_id", "cluster"]].rename(columns={"cluster": "cluster_id"})
    out.to_sql("country_cluster", engine, if_exists="append", index=False)
    print(f"\nWrote {len(out)} rows to country_cluster table.")
