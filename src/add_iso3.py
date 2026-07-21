"""
Add ISO3 country codes to dim_location, needed to join GBD data to
shapefiles in GeoPandas.

Usage:
    python add_iso3.py

This will:
  1. Pull all location_name values from dim_location
  2. Try to match each to a pycountry ISO3 code
  3. Print any names that failed to match, so you can add manual
     overrides in the MANUAL_OVERRIDES dict below and re-run
  4. Once everything matches, add an iso3_code column (if not already
     there) and update dim_location in SQL Server
"""

import pandas as pd
import pycountry
from sqlalchemy import create_engine, text
import urllib

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
SERVER = r"DESKTOP-RNQBFDM\SQLEXPRESS"
DATABASE = "DiseaseBurdenAtlas"

# GBD uses some non-standard / historical names that pycountry's
# fuzzy search won't catch automatically. Add to this as needed —
# the script will tell you which names still need an entry.
MANUAL_OVERRIDES = {
    "Democratic Republic of the Congo": "COD",
    "Congo": "COG",
    "Viet Nam": "VNM",
    "Russian Federation": "RUS",
    "Iran (Islamic Republic of)": "IRN",
    "Bolivia (Plurinational State of)": "BOL",
    "Venezuela (Bolivarian Republic of)": "VEN",
    "United Republic of Tanzania": "TZA",
    "Republic of Korea": "KOR",
    "Democratic People's Republic of Korea": "PRK",
    "Lao People's Democratic Republic": "LAO",
    "Syrian Arab Republic": "SYR",
    "CÃ´te d'Ivoire": "CIV",
    "Côte d'Ivoire": "CIV",
    "Türkiye": "TUR",
    "Turkey": "TUR",
    "Republic of Moldova": "MDA",
    "United States of America": "USA",
    "United States Virgin Islands": "VIR",
    "United Kingdom": "GBR",
    "United Kingdom of Great Britain and Northern Ireland": "GBR",
    "Micronesia (Federated States of)": "FSM",
    "Brunei Darussalam": "BRN",
    "Cabo Verde": "CPV",
    "Eswatini": "SWZ",
    "North Macedonia": "MKD",
    "Czechia": "CZE",
    "Taiwan (Province of China)": "TWN",
    "Palestine": "PSE",
    "State of Palestine": "PSE",
}

# ------------------------------------------------------------------
# CONNECT
# ------------------------------------------------------------------
params = urllib.parse.quote_plus(
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"Trusted_Connection=yes;"
    f"TrustServerCertificate=yes;"
)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

# ------------------------------------------------------------------
# PULL LOCATIONS
# ------------------------------------------------------------------
locations = pd.read_sql("SELECT location_id, location_name FROM dim_location", engine)
print(f"Pulled {len(locations)} locations.")

# ------------------------------------------------------------------
# MATCH TO ISO3
# ------------------------------------------------------------------
def get_iso3(name):
    if name in MANUAL_OVERRIDES:
        return MANUAL_OVERRIDES[name]
    try:
        result = pycountry.countries.search_fuzzy(name)
        return result[0].alpha_3
    except LookupError:
        return None

locations["iso3_code"] = locations["location_name"].apply(get_iso3)

unmatched = locations[locations["iso3_code"].isna()]
if len(unmatched) > 0:
    print(f"\n{len(unmatched)} locations could not be matched:")
    for name in unmatched["location_name"]:
        print(f"  - {name}")
    print("\nAdd these to MANUAL_OVERRIDES in this script and re-run.")
    print("(No database changes made yet.)")
else:
    print("\nAll locations matched! Updating dim_location...")

    # Add iso3_code column if it doesn't exist yet
    with engine.begin() as conn:
        try:
            conn.execute(text(
                "ALTER TABLE dim_location ADD iso3_code CHAR(3) NULL"
            ))
            print("Added iso3_code column.")
        except Exception:
            print("iso3_code column already exists, continuing.")

    # Update each row
    with engine.begin() as conn:
        for _, row in locations.iterrows():
            conn.execute(
                text("UPDATE dim_location SET iso3_code = :iso3 WHERE location_id = :id"),
                {"iso3": row["iso3_code"], "id": row["location_id"]}
            )

    print(f"Updated {len(locations)} rows with ISO3 codes.")
