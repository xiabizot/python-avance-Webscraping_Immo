# Analyse du marche immobilier - Bordeaux (R10)

Projet universitaire (DU Sorbonne Data Analytics) d'analyse du marche immobilier a partir de donnees web scraping.

**Perimetre :** maisons a la vente dans un rayon de 10 km autour de Bordeaux, issues du site EtreProprio.com.

**Problematique :** Comment le prix au metre carre varie-t-il en fonction de la localisation, de la surface et des caracteristiques du bien ?

## Structure du projet

```
PYTHON_AV-PROJET_IMMO/
|-- SRC/                          # Code source
|   |-- SCRAPER.py                # Collecte des annonces (requests + Selenium + BS4)
|   |-- CLEAN_DATA.py             # Nettoyage et structuration des donnees
|   |-- ANALYSE.py                # Exploration statistique et visualisations
|   |-- dashboard.py              # Dashboard interactif Streamlit
|   |-- config.toml.txt           # Configuration Streamlit
|   +-- se_iri24_s.geojson        # Donnees geographiques IRIS
|
|-- DATA/                         # Donnees CSV (brutes et nettoyees)
|-- OUTPUT/                       # Resultats
|   |-- GRAPHS/                   # Graphiques generes par ANALYSE.py
|   +-- data_bordeaux_R10_maisons.csv
|
+-- EXPLORATION.ipynb             # Notebook principal (nettoyage + analyse)
```

## Pipeline

1. **Scraping** (`SRC/SCRAPER.py`) - Collecte exhaustive des annonces via requests, Selenium et BeautifulSoup (parsing HTML + JSON-LD)
2. **Nettoyage** (`SRC/CLEAN_DATA.py`) - Typage, traitement des valeurs manquantes, geolocalisation via Nominatim
3. **Analyse** (`SRC/ANALYSE.py`) - Statistiques descriptives, correlations, visualisations (matplotlib/seaborn)
4. **Dashboard** (`SRC/dashboard.py`) - Application Streamlit interactive avec cartographie Folium et graphiques Plotly

## Installation

```bash
pip install requests pandas beautifulsoup4 selenium lxml numpy geopy matplotlib seaborn scipy streamlit plotly folium streamlit-folium geopandas shapely openpyxl
```

## Lancement du dashboard

```bash
python -m streamlit run SRC/dashboard.py
```

## Technologies

- **Scraping :** requests, BeautifulSoup, Selenium
- **Donnees :** pandas, numpy, geopy
- **Visualisation :** matplotlib, seaborn, plotly
- **Dashboard :** Streamlit, Folium
- **Cartographie :** geopandas, shapely
