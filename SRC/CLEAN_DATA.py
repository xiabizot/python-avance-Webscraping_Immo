# SRC/clean_data.py
import os
import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import time

# --- CONFIGURATION ---
# On se base sur le fait que le script est lancé depuis la racine du projet ou via un IDE qui set le WD
# Si lancé depuis SRC, on remonte d'un cran. Sinon on prend le CWD.
BASE_DIR = os.getcwd() 
if os.path.basename(BASE_DIR) == "SRC":
    BASE_DIR = os.path.dirname(BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, "DATA")
RAW_CSV_PATH = os.path.join(DATA_DIR, "data_bordeaux_R10_maisons.csv")
CLEAN_CSV_PATH = os.path.join(DATA_DIR, "data_bordeaux_R10_maisons_CLEAN.csv")

def load_data():
    """Charge les données brutes."""
    print("--- 1. CHARGEMENT DES DONNÉES ---")
    if not os.path.exists(RAW_CSV_PATH):
        raise FileNotFoundError(f"❌ Fichier brut introuvable : {RAW_CSV_PATH}")
    
    df = pd.read_csv(RAW_CSV_PATH)
    print(f"✅ Fichier brut chargé. Shape : {df.shape}")
    return df

def clean_data(df):
    """Nettoyage : doublons, conversions, filtrage."""
    print("\n--- 2. NETTOYAGE & STRUCTURATION ---")
    
    # 2.1 Suppression des doublons
    before = df.shape[0]
    df = df.drop_duplicates()
    
    # Doublons URL (si colonne existe)
    if "url" in df.columns:
        df = df.drop_duplicates(subset=["url"], keep="first")
    
    print(f"Doublons supprimés. Lignes restantes : {df.shape[0]} (supprimées : {before - df.shape[0]})")

    # 2.2 Conversions numériques
    num_cols = ["prix", "surface_habitable", "surface_terrain", "pieces"]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    
    # Conversion CP en string
    if "cp" in df.columns:
        df["cp"] = df["cp"].astype("string")

    # 2.3 Filtrage "Validité" (Prix > 0, Surface > 10m²)
    mask_valid = (
        df["prix"].notna() & 
        df["surface_habitable"].notna() & 
        (df["prix"] > 0) & 
        (df["surface_habitable"] > 10)
    )
    df_clean = df[mask_valid].copy()
    print(f"Filtrage (Prix > 0, Surface > 10). Lignes valides : {df_clean.shape[0]}")

    # 2.4 Création Prix/m2
    df_clean["prix_m2"] = df_clean["prix"] / df_clean["surface_habitable"]
    print("Variable 'prix_m2' calculée.")
    
    return df_clean

def add_geolocation(df):
    """Ajoute lat/lon via Nominatim."""
    print("\n--- 3. GÉOLOCALISATION (Nominatim) ---")
    
    # Vérification
    if "ville" not in df.columns or "cp" not in df.columns:
        print("⚠️ Colonnes ville/cp manquantes. Pas de géocodage.")
        return df

    # Identifier les couples uniques pour limiter les appels API
    df_localites = df[["ville", "cp"]].drop_duplicates().reset_index(drop=True)
    print(f"Nombre de localités uniques à géocoder : {len(df_localites)}")

    # Setup Geocoder
    geolocator = Nominatim(user_agent="m1_immo_project_script")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.1) # Respect du rate limit

    coords = []
    
    print("Démarrage du géocodage (peut prendre un peu de temps)...")
    for idx, row in df_localites.iterrows():
        query = f"{row['cp']} {row['ville']}, France" if pd.notna(row['cp']) else f"{row['ville']}, France"
        
        lat, lon = None, None
        try:
            location = geocode(query)
            if location:
                lat, lon = location.latitude, location.longitude
        except Exception as e:
            print(f"❌ Erreur sur {query}: {e}")

        coords.append({"ville": row["ville"], "cp": row["cp"], "lat": lat, "lon": lon})
        
        # Petit log de progression
        if (idx + 1) % 5 == 0:
            print(f"   ... {idx + 1}/{len(df_localites)} traités")

    df_coords = pd.DataFrame(coords)
    
    # Merge
    df_final = df.merge(df_coords, on=["ville", "cp"], how="left")
    
    nb_missing = df_final["lat"].isna().sum()
    print(f"Géolocalisation terminée. Annonces sans coordonnées : {nb_missing}")
    
    return df_final

def save_data(df):
    """Sauvegarde le fichier CLEAN final."""
    print("\n--- 4. SAUVEGARDE ---")
    
    # Sélection des colonnes finales
    cols_to_keep = [
        "url", "type_bien", "titre", "prix", "surface_habitable", 
        "surface_terrain", "pieces", "ville", "cp", 
        "dpe", "ges", "features", "description", 
        "prix_m2", "lat", "lon"
    ]
    # On ne garde que celles qui existent vraiment
    final_cols = [c for c in cols_to_keep if c in df.columns]
    
    df_final = df[final_cols]
    df_final.to_csv(CLEAN_CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"✅ SUCCÈS : Fichier sauvegardé sous : {CLEAN_CSV_PATH}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    try:
        # 1. Load
        df_raw = load_data()
        
        # 2. Clean
        df_clean = clean_data(df_raw)
        
        # 3. Geolocate
        # Note : Si tu veux tester sans attendre le géocoding, commente la ligne ci-dessous
        df_geo = add_geolocation(df_clean)
        
        # 4. Save
        save_data(df_geo)
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR : {e}")