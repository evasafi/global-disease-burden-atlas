"""
Build an interactive choropleth map with two dropdowns (Measure, Cause)
that control a single dynamic layer — only one choropleth is visible
at a time, with a legend that updates to match.

Usage:
    python build_map.py

Output:
    ../dashboards/disease_burden_map.html
"""

import pandas as pd
import geopandas as gpd
import json
from sqlalchemy import create_engine
import urllib

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
SERVER = r"DESKTOP-RNQBFDM\SQLEXPRESS"
DATABASE = "DiseaseBurdenAtlas"
OUTPUT_PATH = "../dashboards/disease_burden_map.html"

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

print("Pulling data from SQL Server...")
query = """
SELECT
    l.iso3_code,
    l.location_name,
    c.cause_name,
    me.measure_name,
    f.val
FROM fact_disease_burden f
JOIN dim_location l ON f.location_id = l.location_id
JOIN dim_cause c ON f.cause_id = c.cause_id
JOIN dim_measure me ON f.measure_id = me.measure_id
JOIN dim_metric met ON f.metric_id = met.metric_id
WHERE met.metric_name = 'Rate'
  AND me.measure_name IN ('Deaths', 'DALYs (Disability-Adjusted Life Years)')
"""
df = pd.read_sql(query, engine)
print(f"Pulled {len(df):,} rows.")

# ------------------------------------------------------------------
# LOAD WORLD SHAPEFILE (geometry only, simplified for smaller file size)
# ------------------------------------------------------------------
print("Loading world shapefile...")
world = gpd.read_file(
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"
)
iso_col = "ISO_A3" if "ISO_A3" in world.columns else "iso_a3"
world = world.rename(columns={iso_col: "iso3_code"})[["iso3_code", "geometry"]]
world["geometry"] = world["geometry"].simplify(0.05, preserve_topology=True)

# ------------------------------------------------------------------
# BUILD LOOKUP: {measure: {cause: {iso3: {name, val}}}}
# ------------------------------------------------------------------
print("Building data lookup...")
data_lookup = {}
for measure in df["measure_name"].unique():
    data_lookup[measure] = {}
    for cause in df["cause_name"].unique():
        subset = df[(df["measure_name"] == measure) & (df["cause_name"] == cause)]
        data_lookup[measure][cause] = {
            row["iso3_code"]: {"name": row["location_name"], "val": round(row["val"], 2)}
            for _, row in subset.iterrows()
        }

geojson_str = world.to_json()
data_json = json.dumps(data_lookup)

measures = sorted(df["measure_name"].unique())
causes = sorted(df["cause_name"].unique())

measure_options = "\n".join(f'<option value="{m}">{m}</option>' for m in measures)
cause_options = "\n".join(f'<option value="{c}">{c}</option>' for c in causes)

# ------------------------------------------------------------------
# BUILD HTML
# ------------------------------------------------------------------
html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Global Disease Burden Atlas</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body {{ margin: 0; padding: 0; height: 100%; font-family: Arial, sans-serif; }}
  #map {{ position: absolute; top: 70px; bottom: 0; left: 0; right: 0; }}
  #header {{
    height: 70px; display: flex; align-items: center; justify-content: space-between;
    padding: 0 20px; background: #1a1a2e; color: white; box-sizing: border-box;
  }}
  #header h1 {{ font-size: 20px; margin: 0; }}
  #header p {{ font-size: 12px; margin: 2px 0 0 0; color: #ccc; }}
  #controls {{
    position: absolute; top: 82px; left: 50px; z-index: 1000;
    background: white; padding: 12px 16px; border-radius: 6px;
    box-shadow: 0 1px 5px rgba(0,0,0,0.4); font-size: 14px;
  }}
  #controls label {{ font-weight: bold; margin-right: 6px; }}
  #controls select {{ margin-right: 16px; padding: 4px; }}
  .legend {{
    background: white; padding: 8px 10px; border-radius: 6px;
    box-shadow: 0 1px 5px rgba(0,0,0,0.4); font-size: 12px; line-height: 18px;
  }}
  .legend i {{ width: 18px; height: 12px; float: left; margin-right: 6px; opacity: 0.85; }}
</style>
</head>
<body>

<div id="header">
  <div>
    <h1>Global Disease Burden Atlas</h1>
    <p>Country-level disease burden, 2023 &middot; Source: Institute for Health Metrics and Evaluation (IHME), Global Burden of Disease Study 2023</p>
  </div>
</div>

<div id="controls">
  <label>Measure:</label>
  <select id="measureSelect">
    {measure_options}
  </select>
  <label>Cause:</label>
  <select id="causeSelect">
    {cause_options}
  </select>
</div>

<div id="map"></div>

<script>
  const dataLookup = {data_json};
  const geoData = {geojson_str};

  const southWest = L.latLng(-60, -190);
  const northEast = L.latLng(85, 190);
  const bounds = L.latLngBounds(southWest, northEast);

  const map = L.map('map', {{
    worldCopyJump: false,
    maxBounds: bounds,
    maxBoundsViscosity: 1.0,
    minZoom: 2
  }}).setView([15, 10], 2);

  L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    noWrap: true
  }}).addTo(map);

  const colors = ["#ffffb2", "#fed976", "#feb24c", "#fd8d3c", "#f03b20", "#bd0026"];

  function getColor(v, max) {{
    const t = v / max;
    if (t > 0.83) return colors[5];
    if (t > 0.66) return colors[4];
    if (t > 0.5) return colors[3];
    if (t > 0.33) return colors[2];
    if (t > 0.16) return colors[1];
    return colors[0];
  }}

  let geoLayer;
  let legend = L.control({{position: 'bottomright'}});

  function updateMap() {{
    const measure = document.getElementById('measureSelect').value;
    const cause = document.getElementById('causeSelect').value;
    const values = dataLookup[measure][cause];

    const vals = Object.values(values).map(d => d.val);
    const max = Math.max(...vals);

    if (geoLayer) {{ map.removeLayer(geoLayer); }}

    geoLayer = L.geoJSON(geoData, {{
      style: function(feature) {{
        const iso = feature.properties.iso3_code;
        const entry = values[iso];
        return {{
          fillColor: entry ? getColor(entry.val, max) : "#d3d3d3",
          weight: 0.5,
          color: "#666",
          fillOpacity: 0.8
        }};
      }},
      onEachFeature: function(feature, layer) {{
        const iso = feature.properties.iso3_code;
        const entry = values[iso];
        if (entry) {{
          layer.bindTooltip(`<b>${{entry.name}}</b><br>${{measure}} rate per 100k: ${{entry.val}}`);
        }}
      }}
    }}).addTo(map);

    if (legend._map) {{ map.removeControl(legend); }}
    legend = L.control({{position: 'bottomright'}});
    legend.onAdd = function() {{
      const div = L.DomUtil.create('div', 'legend');
      div.innerHTML = `<b>${{measure}}<br>${{cause}}</b><br>rate per 100k<br>`;
      const steps = [0, 0.16, 0.33, 0.5, 0.66, 0.83];
      for (let i = 0; i < steps.length; i++) {{
        div.innerHTML += `<i style="background:${{colors[i]}}"></i> ${{Math.round(steps[i]*max)}}${{i < steps.length-1 ? '&ndash;' + Math.round(steps[i+1]*max) : '+'}}<br>`;
      }}
      return div;
    }};
    legend.addTo(map);
  }}

  document.getElementById('measureSelect').addEventListener('change', updateMap);
  document.getElementById('causeSelect').addEventListener('change', updateMap);

  updateMap();
</script>

</body>
</html>
"""

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\nMap saved to {OUTPUT_PATH}")
print("Open that file in a browser to view it.")
