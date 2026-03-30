import math
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import folium
from folium.plugins import MarkerCluster, HeatMap
from streamlit_folium import st_folium

import plotly.express as px

import geopandas as gpd
from shapely.geometry import Point


# ==========================
# PATHS (arborescence prof)
# ==========================
ROOT_DIR = Path(__file__).resolve().parents[1]          # PROJET_IMMOBILIER/
DATA_DIR = ROOT_DIR / "DATA"
DEFAULT_CLEAN_CSV = DATA_DIR / "data_bordeaux_R10_maisons_CLEAN.csv"
DEFAULT_RAW_CSV = DATA_DIR / "data_bordeaux_R10_maisons.csv"
DEFAULT_GEOJSON = DATA_DIR / "IRIS_BORDEAUX.geojson"    # optionnel (si tu veux le poser dans DATA/)

BORDEAUX_CENTER = (44.8378, -0.5792)


# ==========================
# STREAMLIT CONFIG
# ==========================
st.set_page_config(page_title="Bordeaux – Immobilier (Maisons)", layout="wide")

st.title("🏡 Bordeaux – Tableau de bord immobilier (Maisons)")
st.caption(
    "Arborescence M1 respectée (DATA/SRC/NOTEBOOKS/RAPPORT) — "
    "Dashboard Streamlit : Plotly + Carte Folium + Choroplèthe GeoPandas (style DVF)."
)


# ==========================
# LOADERS / UTILS
# ==========================
@st.cache_data
def load_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    # Colonnes attendues (évite crash si certaines colonnes n'existent pas)
    for c in [
        "prix", "surface_habitable", "surface_terrain", "pieces", "prix_m2",
        "lat", "lon", "ville", "cp", "dpe", "ges", "titre", "url", "features"
    ]:
        if c not in df.columns:
            df[c] = np.nan

    # Typage
    for col in ["prix", "surface_habitable", "surface_terrain", "pieces", "prix_m2", "lat", "lon"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Calcul prix/m² si absent / vide
    if df["prix_m2"].isna().all() and df["prix"].notna().any() and df["surface_habitable"].notna().any():
        df["prix_m2"] = (df["prix"] / df["surface_habitable"]).replace([np.inf, -np.inf], np.nan)

    return df


def add_jitter(df: pd.DataFrame, jitter_m: float = 35.0) -> pd.DataFrame:
    """Déplie les points superposés (jitter déterministe par URL)."""
    df = df.copy()
    if df["lat"].notna().sum() == 0 or df["lon"].notna().sum() == 0:
        return df

    mean_lat = float(df["lat"].dropna().mean())
    lat_scale = jitter_m / 111_000.0
    lon_scale = jitter_m / (111_000.0 * math.cos(math.radians(mean_lat)))

    def _j(row):
        key = row.get("url")
        if not isinstance(key, str) or not key.strip():
            key = f"row-{row.name}"
        seed = abs(hash(key)) % (2**32)
        rng = np.random.default_rng(seed)
        return pd.Series({
            "lat_jit": row["lat"] + rng.uniform(-lat_scale, lat_scale),
            "lon_jit": row["lon"] + rng.uniform(-lon_scale, lon_scale),
        })

    jit = df.apply(_j, axis=1)
    df["lat_jit"] = jit["lat_jit"]
    df["lon_jit"] = jit["lon_jit"]
    return df


def core_market_filter(df: pd.DataFrame, enabled: bool) -> pd.DataFrame:
    """Outliers 5–95% sur prix/m², optionnel."""
    if not enabled:
        return df
    x = df["prix_m2"].dropna()
    if len(x) < 20:
        return df
    q05 = float(x.quantile(0.05))
    q95 = float(x.quantile(0.95))
    return df[df["prix_m2"].between(q05, q95)].copy()


def contains_patterns(text: str, patterns: list[str]) -> bool:
    """
    patterns list: chaque pattern peut contenir '|' = OU ; liste = ET.
    Exemple: "terrasse|balcon"
    """
    if not isinstance(text, str):
        return False
    t = text.lower()
    for pat in patterns:
        options = pat.split("|")
        if not any(opt in t for opt in options):
            return False
    return True


@st.cache_data
def load_geojson_file(path: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


@st.cache_data
def load_geojson_upload(uploaded) -> gpd.GeoDataFrame:
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".geojson") as tmp:
        tmp.write(uploaded.getbuffer())
        path = tmp.name
    return load_geojson_file(path)


def points_gdf_from_df(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Transforme df lat/lon -> GeoDataFrame EPSG:4326."""
    tmp = df.dropna(subset=["lat", "lon"]).copy()
    geom = [Point(xy) for xy in zip(tmp["lon"], tmp["lat"])]
    return gpd.GeoDataFrame(tmp, geometry=geom, crs="EPSG:4326")


def make_json_safe(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    FIX IMPORTANT :
    Folium/GeoJSON n'aime pas les Timestamps (datetime) => to_json() crash.
    On convertit toute colonne datetime en string.
    """
    out = gdf.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].astype(str)
    return out


# ==========================
# SIDEBAR: DATA
# ==========================
st.sidebar.header("📁 Données (arborescence projet)")
default_csv_str = str(DEFAULT_CLEAN_CSV) if DEFAULT_CLEAN_CSV.exists() else ""
csv_path = st.sidebar.text_input("CSV clean (par défaut DATA/ANNONCES_CLEAN.CSV)", value=default_csv_str)

if not csv_path or not Path(csv_path).exists():
    st.error(
        "CSV introuvable.\n\n"
        "➡️ Mets ton fichier clean dans : DATA/ANNONCES_CLEAN.CSV\n"
        "ou indique un chemin valide dans la sidebar."
    )
    st.stop()

df_raw = load_data(csv_path)

# ==========================
# SIDEBAR: OPTIONS & FILTERS
# ==========================
st.sidebar.header("⚙️ Options")
enable_core_market = st.sidebar.checkbox("Activer “cœur de marché” (outliers 5–95% sur prix/m²)", value=False)
enable_heatmap = st.sidebar.checkbox("Afficher heatmap (densité)", value=True)
enable_cluster = st.sidebar.checkbox("Activer cluster (marqueurs)", value=True)
jitter_m = st.sidebar.slider("Jitter (mètres) pour déplier les points", 0, 80, 35, step=5)

st.sidebar.header("🎛️ Filtres")

# Prix
prix_min_sel = prix_max_sel = None
if df_raw["prix"].notna().any():
    pmin = int(df_raw["prix"].min())
    pmax = int(df_raw["prix"].max())
    prix_min_sel, prix_max_sel = st.sidebar.slider("Prix (€)", pmin, pmax, (pmin, pmax), step=10_000)

# Surface habitable
surf_min_sel = surf_max_sel = None
if df_raw["surface_habitable"].notna().any():
    smin = int(df_raw["surface_habitable"].min())
    smax = int(df_raw["surface_habitable"].max())
    surf_min_sel, surf_max_sel = st.sidebar.slider("Surface habitable (m²)", smin, smax, (smin, smax), step=5)

# Terrain
terr_min_sel = terr_max_sel = None
terrain_valid = df_raw["surface_terrain"].dropna()
if len(terrain_valid) > 0:
    tmin = int(terrain_valid.min())
    tmax = int(terrain_valid.max())
    terr_min_sel, terr_max_sel = st.sidebar.slider("Surface terrain (m²)", tmin, tmax, (tmin, tmax), step=10)

# Pièces
pieces_vals = sorted([int(x) for x in df_raw["pieces"].dropna().unique().tolist() if np.isfinite(x)])
pieces_sel = st.sidebar.multiselect("Pièces", pieces_vals, default=pieces_vals)

# DPE / GES
dpe_vals = sorted([str(x) for x in df_raw["dpe"].dropna().unique().tolist() if str(x).strip()])
dpe_sel = st.sidebar.multiselect("DPE", dpe_vals, default=dpe_vals)

ges_vals = sorted([str(x) for x in df_raw["ges"].dropna().unique().tolist() if str(x).strip()])
ges_sel = st.sidebar.multiselect("GES", ges_vals, default=ges_vals)

# Features
st.sidebar.markdown("### 🧩 Équipements")
feature_patterns = {
    "Piscine": "piscine",
    "Jardin": "jardin",
    "Terrasse / balcon": "terrasse|balcon",
    "Parking / garage": "parking|garage",
}
selected_patterns = []
for label, pattern in feature_patterns.items():
    if st.sidebar.checkbox(label, value=False):
        selected_patterns.append(pattern)

# Choropleth
st.sidebar.header("🗺️ Choroplèthe (GeoPandas)")
geojson_mode = st.sidebar.radio("Source GeoJSON", ["Upload", "DATA/IRIS_BORDEAUX.geojson (optionnel)"], index=0)

geojson_upload = None
geojson_path = None

if geojson_mode == "Upload":
    geojson_upload = st.sidebar.file_uploader("Uploader GeoJSON IRIS/quartiers", type=["geojson", "json"])
else:
    geojson_path = str(DEFAULT_GEOJSON)
    if not Path(geojson_path).exists():
        st.sidebar.warning("Le fichier DATA/IRIS_BORDEAUX.geojson n'existe pas. Passe sur Upload.")

geo_name_field = st.sidebar.text_input(
    "Champ zone (nom quartier/IRIS)",
    value="nom_iris",
    help="Ton fichier IRIS contient souvent: nom_iris (nom), iris (code), insee (commune)."
)

filter_bordeaux_only = st.sidebar.checkbox("Limiter la choroplèthe à Bordeaux (INSEE=33063)", value=True)
chor_metric = st.sidebar.selectbox("Métrique choroplèthe", ["prix_m2 (médiane)", "prix (médiane)"], index=0)


# ==========================
# APPLY FILTERS
# ==========================
df = df_raw.copy()
mask = pd.Series(True, index=df.index)

if prix_min_sel is not None:
    mask &= df["prix"].between(prix_min_sel, prix_max_sel)

if surf_min_sel is not None:
    mask &= df["surface_habitable"].between(surf_min_sel, surf_max_sel)

if terr_min_sel is not None:
    mask &= df["surface_terrain"].between(terr_min_sel, terr_max_sel)

if pieces_sel:
    mask &= df["pieces"].isin(pieces_sel)

if dpe_sel:
    mask &= df["dpe"].astype(str).isin(dpe_sel)

if ges_sel:
    mask &= df["ges"].astype(str).isin(ges_sel)

if selected_patterns:
    mask &= df["features"].apply(lambda x: contains_patterns(x, selected_patterns))

df_filt = df[mask].copy()

# prix/m² requis pour analyses principales
df_filt = df_filt.dropna(subset=["prix_m2"])
df_filt = core_market_filter(df_filt, enabled=enable_core_market)

# data carte
df_map = df_filt.dropna(subset=["lat", "lon"]).copy()
df_map = add_jitter(df_map, jitter_m=float(jitter_m))


# ==========================
# KPIs
# ==========================
st.subheader("Indicateurs")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Annonces filtrées", f"{len(df_filt):,}".replace(",", " "))
c2.metric("Cartographiables", f"{len(df_map):,}".replace(",", " "))
c3.metric("Prix médian", f"{int(df_filt['prix'].median()):,} €".replace(",", " ") if len(df_filt) else "-")
c4.metric("Prix/m² médian", f"{int(df_filt['prix_m2'].median()):,} €".replace(",", " ") if len(df_filt) else "-")
st.divider()


# ==========================
# TABS
# ==========================
tab_map, tab_stats, tab_choro, tab_table = st.tabs(
    ["🗺️ Carte (annonces)", "📊 Graphiques", "🧩 Choroplèthe (DVF)", "🧾 Table"]
)


# ==========================
# TAB 1: FOLIUM MAP
# ==========================
with tab_map:
    st.subheader("Carte interactive (Folium) – prix au survol + popup")
    m = folium.Map(location=BORDEAUX_CENTER, zoom_start=11, tiles="CartoDB positron")

    if df_map.empty:
        st.warning("Aucun bien cartographiable après filtres (coords manquantes ou filtres trop stricts).")
        st_folium(m, width=1100, height=620)
    else:
        layer = MarkerCluster().add_to(m) if enable_cluster else m

        if enable_heatmap:
            HeatMap(df_map[["lat_jit", "lon_jit"]].values.tolist(), radius=18).add_to(m)

        for _, row in df_map.iterrows():
            title = str(row.get("titre", "Maison"))
            prix = row.get("prix", np.nan)
            surf = row.get("surface_habitable", np.nan)
            pm2 = row.get("prix_m2", np.nan)
            ville = row.get("ville", "")
            cp = row.get("cp", "")
            url = row.get("url", "")

            popup = f"""
            <div style="font-size:13px; line-height:1.4;">
                <strong>{title}</strong><br>
                {ville} ({cp})<br>
                Prix : {prix:,.0f} €<br>
                Surface : {surf:,.0f} m²<br>
                Prix/m² : {pm2:,.0f} €/m²<br><br>
                <a href="{url}" target="_blank">Voir l'annonce</a>
            </div>
            """

            folium.CircleMarker(
                location=[row["lat_jit"], row["lon_jit"]],
                radius=5,
                color="#2E6F9E",
                fill=True,
                fill_opacity=0.75,
                tooltip=f"{prix:,.0f} €".replace(",", " "),
                popup=folium.Popup(popup, max_width=320),
            ).add_to(layer)

        st_folium(m, width=1100, height=620)


# ==========================
# TAB 2: STATS (Plotly + Boxplot + Top/Bottom)
# ==========================
with tab_stats:
    st.subheader("Graphiques (Plotly) – colorés & interactifs")

    row1_left, row1_right = st.columns(2)

    with row1_left:
        st.write("📌 Distribution du prix au m²")
        if len(df_filt) and df_filt["prix_m2"].notna().any():
            fig_pm2 = px.histogram(
                df_filt,
                x="prix_m2",
                nbins=30,
                title="Distribution du prix au m²",
                color_discrete_sequence=["#EF553B"],
            )
            fig_pm2.update_layout(xaxis_title="Prix au m² (€)", yaxis_title="Nombre d'annonces")
            st.plotly_chart(fig_pm2, use_container_width=True)
        else:
            st.info("Pas de données prix/m² après filtres.")

    with row1_right:
        st.write("🏠 Distribution des surfaces habitables")
        if len(df_filt) and df_filt["surface_habitable"].notna().any():
            fig_s = px.histogram(
                df_filt,
                x="surface_habitable",
                nbins=30,
                title="Distribution des surfaces habitables",
                color_discrete_sequence=["#00CC96"],
            )
            fig_s.update_layout(xaxis_title="Surface habitable (m²)", yaxis_title="Nombre de maisons")
            st.plotly_chart(fig_s, use_container_width=True)
        else:
            st.info("Pas de surfaces disponibles après filtres.")

    st.divider()

    row2_left, row2_right = st.columns(2)

    with row2_left:
        st.write("📈 Surface vs Prix (couleur = prix/m²)")
        dd = df_filt.dropna(subset=["surface_habitable", "prix", "prix_m2"])
        if len(dd) > 10:
            fig_sc = px.scatter(
                dd,
                x="surface_habitable",
                y="prix",
                color="prix_m2",
                color_continuous_scale="YlOrRd",
                hover_data=["pieces", "dpe", "ges", "ville", "cp"],
                title="Surface vs Prix (couleur = prix/m²)"
            )
            fig_sc.update_layout(xaxis_title="Surface habitable (m²)", yaxis_title="Prix (€)")
            st.plotly_chart(fig_sc, use_container_width=True)
        else:
            st.info("Pas assez de points pour le scatter.")

    with row2_right:
        st.write("📊 Boxplot – Prix/m² par DPE (coloré)")
        ddd = df_filt.dropna(subset=["prix_m2", "dpe"]).copy()
        if len(ddd) > 10:
            order = ["A", "B", "C", "D", "E", "F", "G"]
            ddd["dpe"] = ddd["dpe"].astype(str).str.upper()
            ddd = ddd[ddd["dpe"].isin(order)]

            fig_box = px.box(
                ddd,
                x="dpe",
                y="prix_m2",
                color="dpe",
                category_orders={"dpe": order},
                color_discrete_sequence=px.colors.qualitative.Set2,
                title="Prix/m² par DPE"
            )
            fig_box.update_layout(xaxis_title="DPE", yaxis_title="Prix/m² (€)")
            st.plotly_chart(fig_box, use_container_width=True)
        else:
            st.info("Pas assez de données pour le boxplot DPE.")

    st.divider()

    st.subheader("🏆 Top 10 / Bottom 10 des maisons par prix/m²")
    if len(df_filt) and df_filt["prix_m2"].notna().any():
        base_cols = ["titre", "ville", "cp", "prix", "surface_habitable", "prix_m2", "pieces", "dpe", "ges", "url"]
        base_cols = [c for c in base_cols if c in df_filt.columns]

        top10 = df_filt.sort_values("prix_m2", ascending=False).head(10)
        bot10 = df_filt.sort_values("prix_m2", ascending=True).head(10)

        cA, cB = st.columns(2)

        with cA:
            st.markdown("### 🔴 Top 10 – plus chères au m²")
            st.dataframe(
                top10[base_cols].style.background_gradient(subset=["prix_m2"], cmap="Reds"),
                use_container_width=True
            )

        with cB:
            st.markdown("### 🟢 Bottom 10 – moins chères au m²")
            st.dataframe(
                bot10[base_cols].style.background_gradient(subset=["prix_m2"], cmap="Greens"),
                use_container_width=True
            )
    else:
        st.info("Pas de prix/m² disponible.")


# ==========================
# TAB 3: CHOROPLETH (DVF)
# ==========================
with tab_choro:
    st.subheader("Choroplèthe GeoPandas (style DVF) – médiane par IRIS/quartier")

    # Charger GeoJSON selon mode
    quartiers = None
    if geojson_upload is not None:
        quartiers = load_geojson_upload(geojson_upload)
    elif geojson_path and Path(geojson_path).exists():
        quartiers = load_geojson_file(geojson_path)

    if quartiers is None:
        st.info(
            "Pour activer la choroplèthe :\n"
            "- soit upload un GeoJSON IRIS/quartiers (sidebar)\n"
            "- soit place un fichier DATA/IRIS_BORDEAUX.geojson\n"
        )
        st.stop()

    # Bordeaux only (si colonne insee)
    if filter_bordeaux_only and "insee" in quartiers.columns:
        quartiers = quartiers[quartiers["insee"].astype(str) == "33063"].copy()

    # Champ zone
    name_field = geo_name_field.strip()
    if not name_field or name_field not in quartiers.columns:
        st.error("Champ zone introuvable. Mets exactement un nom de colonne existante.")
        st.write("Colonnes disponibles:", list(quartiers.columns))
        st.stop()

    # Points
    pts = points_gdf_from_df(df_filt)
    if pts.empty:
        st.warning("Pas de points (lat/lon) après filtres.")
        st.stop()

    # Spatial join
    joined = gpd.sjoin(pts, quartiers, predicate="within", how="left")

    metric_col = "prix_m2" if chor_metric.startswith("prix_m2") else "prix"
    joined_metric = joined.dropna(subset=[name_field, metric_col]).copy()

    if joined_metric.empty:
        st.warning("Aucune zone ne reçoit de valeur (jointure spatiale vide).")
        st.stop()

    agg = (
        joined_metric.groupby(name_field)[metric_col]
        .median()
        .reset_index()
        .rename(columns={metric_col: "median_value"})
    )

    quartiers2 = quartiers.merge(agg, on=name_field, how="left")
    quartiers2 = make_json_safe(quartiers2)  # FIX Timestamp JSON

    st.caption(f"Zones avec valeur estimée : {quartiers2['median_value'].notna().sum()} / {len(quartiers2)}")

    m2 = folium.Map(location=BORDEAUX_CENTER, zoom_start=11, tiles="CartoDB positron")

    folium.Choropleth(
        geo_data=quartiers2.to_json(),
        data=quartiers2,
        columns=[name_field, "median_value"],
        key_on=f"feature.properties.{name_field}",
        fill_color="YlOrRd",
        fill_opacity=0.75,
        line_opacity=0.25,
        nan_fill_opacity=0.10,
        legend_name=f"Médiane {metric_col} ({'€/m²' if metric_col=='prix_m2' else '€'})",
    ).add_to(m2)

    folium.GeoJson(
        quartiers2.to_json(),
        tooltip=folium.GeoJsonTooltip(
            fields=[name_field, "median_value"],
            aliases=["Zone", "Médiane"],
            localize=True,
        ),
    ).add_to(m2)

    st_folium(m2, width=1100, height=620)


# ==========================
# TAB 4: TABLE
# ==========================
with tab_table:
    st.subheader("Table des biens filtrés")
    cols = [
        "ville", "cp", "prix", "surface_habitable", "surface_terrain", "pieces",
        "prix_m2", "dpe", "ges", "titre", "url"
    ]
    cols = [c for c in cols if c in df_filt.columns]

    st.dataframe(df_filt[cols].sort_values("prix_m2", ascending=False), use_container_width=True)

    st.download_button(
        "Télécharger le CSV filtré",
        data=df_filt.to_csv(index=False).encode("utf-8"),
        file_name="ANNONCES_FILTERED.csv",
        mime="text/csv",
    )
