import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import scipy.stats as stats # Pour Pearson si besoin via scipy, sinon pandas suffit

# =============================================================================
# CONFIGURATION
# =============================================================================
sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = (10, 6)

# Configuration de l'affichage console pour imiter le "display()" du notebook
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 1000)
pd.set_option("display.precision", 2)

# Chemins
BASE_DIR = os.getcwd()
if os.path.basename(BASE_DIR) == "SRC":
    BASE_DIR = os.path.dirname(BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, "DATA")
INPUT_CSV = os.path.join(DATA_DIR, "data_bordeaux_R10_maisons_CLEAN.csv")
GRAPH_DIR = os.path.join(BASE_DIR, "OUTPUT", "GRAPHS")
os.makedirs(GRAPH_DIR, exist_ok=True)

def save_fig(name):
    path = os.path.join(GRAPH_DIR, name)
    plt.tight_layout()
    plt.savefig(path, dpi=100)
    plt.close()
    print(f"   [GRAPH] 💾 Sauvegardé : {name}")

def print_step(title):
    print(f"\n{'-'*80}")
    print(f" {title}")
    print(f"{'-'*80}")

# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":

    # --- 1. CHARGEMENT (df_explo) ---
    print_step("CHARGEMENT DU FICHIER CLEAN")
    if not os.path.exists(INPUT_CSV):
        raise FileNotFoundError(f"❌ Fichier manquant : {INPUT_CSV}")
    
    df_explo = pd.read_csv(INPUT_CSV)
    print(f"Shape df_explo : {df_explo.shape}")
    print(df_explo.head())

    # --- 2.1 STATS DESCRIPTIVES ---
    print_step("2.1 STATISTIQUES DESCRIPTIVES")
    num_cols_explo = ["prix", "surface_habitable", "surface_terrain", "pieces", "prix_m2"]
    cols = [c for c in num_cols_explo if c in df_explo.columns]
    print(df_explo[cols].describe())

    # --- 2.2 CALCULS BONUS (Moyenne vs Médiane) ---
    print_step("2.2.1 BONUS : Moyenne vs Médiane")
    mean_pm2 = df_explo["prix_m2"].mean()
    median_pm2 = df_explo["prix_m2"].median()

    print(f"Moyenne prix/m² : {mean_pm2:.0f} € / m²")
    print(f"Médiane prix/m² : {median_pm2:.0f} € / m²")

    ratio_mean_median = mean_pm2 / median_pm2
    ecart_relatif = (mean_pm2 - median_pm2) / median_pm2 * 100

    print(f"Rapport moyenne / médiane : {ratio_mean_median:.3f}")
    print(f"Écart relatif moyenne vs médiane : {ecart_relatif:.1f} %")

    # Phrase automatique du notebook
    if ecart_relatif > 0:
        tendance = "supérieure à"
        interpretation = "ce qui suggère que quelques biens très chers tirent la moyenne vers le haut."
    elif ecart_relatif < 0:
        tendance = "inférieure à"
        interpretation = "ce qui est peu fréquent dans ce type de données et peut refléter quelques biens très peu chers."
    else:
        tendance = "égale à"
        interpretation = "ce qui indique une distribution très symétrique des prix au m²."

    print(f"\nInterprétation : le prix/m² médian est d’environ {median_pm2:.0f} € / m², "
          f"avec une moyenne {tendance} la médiane ({mean_pm2:.0f} € / m²), "
          f"soit un écart relatif d’environ {ecart_relatif:.1f} %. "
          f"Globalement, {interpretation}")

    # --- 2.2.2 à 2.2.5 GRAPHIQUES HISTOGRAMMES & BOXPLOT ---
    print_step("2.2.2 - 2.2.5 GRAPHIQUES DE DISTRIBUTION")
    
    # 2.2.2 Histo Prix
    plt.figure()
    plt.hist(df_explo["prix"].dropna(), bins=30)
    plt.title("Distribution des prix")
    plt.xlabel("Prix (€)")
    plt.ylabel("Fréquence")
    save_fig("2.2.2_histo_prix.png")

    # 2.2.3 Histo Surface
    plt.figure()
    plt.hist(df_explo["surface_habitable"].dropna(), bins=30)
    plt.title("Distribution des surfaces habitables")
    plt.xlabel("Surface (m²)")
    save_fig("2.2.3_histo_surface.png")

    # 2.2.4 Histo Prix/m2
    plt.figure()
    plt.hist(df_explo["prix_m2"].dropna(), bins=30)
    plt.title("Distribution du prix au m²")
    plt.xlabel("Prix (€/m²)")
    save_fig("2.2.4_histo_prix_m2.png")

    # 2.2.5 Boxplot
    plt.figure(figsize=(7, 3))
    sns.boxplot(x=df_explo["prix_m2"], color="lightgreen")
    plt.title("Boxplot du prix au m²")
    save_fig("2.2.5_boxplot_prix_m2.png")

    # --- 2.3.1 OUTLIERS TOP 10 ---
    print_step("2.3.1 TOP 10 OUTLIERS (Prix/m²)")
    colonnes_outliers = ["ville", "cp", "prix", "surface_habitable", "surface_terrain", "prix_m2", "dpe", "ges", "features", "url"]
    cols_ok = [c for c in colonnes_outliers if c in df_explo.columns]
    
    top_outliers = df_explo.dropna(subset=["prix_m2"]).sort_values("prix_m2", ascending=False).head(10)[cols_ok]
    print(top_outliers.to_string(index=False))

    # --- 2.3.2 COMPARAISON AVEC/SANS DIAGNOSTIC (Fonction du notebook) ---
    print_step("2.3.2 COMPARAISON PRIX/M² SELON PRÉSENCE DPE/GES")
    
    def compare_prix_m2_diag(df, col_diag, label):
        if col_diag not in df.columns:
            print(f"Colonne {col_diag} absente")
            return
        subset = df.copy()
        subset[f"has_{col_diag}"] = subset[col_diag].notna()
        stats = subset.groupby(f"has_{col_diag}")["prix_m2"].agg(count="count", mean="mean", median="median").round(0)
        print(f"\n=== Prix/m² selon présence de {label} ({col_diag}) ===")
        print(stats)

    compare_prix_m2_diag(df_explo, "dpe", "DPE")
    compare_prix_m2_diag(df_explo, "ges", "GES")

    # --- 2.3.3 PRIX MOYEN PAR VILLE ---
    print_step("2.3.3 PRIX MOYEN PAR VILLE")
    if "ville" in df_explo.columns:
        prix_m2_par_ville = df_explo.groupby("ville")["prix_m2"].mean().sort_values(ascending=False)
        print(prix_m2_par_ville)
        
        plt.figure()
        prix_m2_par_ville.plot(kind="bar")
        plt.title("Prix moyen au m² par ville")
        plt.tight_layout()
        save_fig("2.3.3_barplot_ville.png")

    # --- 2.3.4 RELATION SURFACE/PRIX (SCATTER SIMPLE) ---
    print_step("2.3.4 RELATION SURFACE / PRIX")
    mask = df_explo["surface_habitable"].notna() & df_explo["prix"].notna()
    subset = df_explo[mask].copy()
    
    plt.figure(figsize=(7, 5))
    plt.scatter(subset["surface_habitable"], subset["prix"], s=12, alpha=0.5)
    plt.title("Relation Surface / Prix (df_clean)")
    plt.xlabel("Surface (m²)")
    plt.ylabel("Prix (€)")
    save_fig("2.3.4_scatter_simple.png")
    
    corr = subset[["surface_habitable", "prix"]].corr().iloc[0, 1]
    print(f"Corrélation Pearson : {corr:.3f}")

    # --- 2.3.5 SCATTER ANNOTÉ OUTLIERS ---
    print_step("2.3.5 SCATTER AVEC OUTLIERS MIS EN VALEUR")
    subset_clean = subset.dropna(subset=["prix_m2"])
    outliers_scatter = subset_clean.sort_values("prix_m2", ascending=False).head(3)

    plt.figure(figsize=(7, 5))
    plt.scatter(subset["surface_habitable"], subset["prix"], s=12, alpha=0.5) # Tous
    plt.scatter(outliers_scatter["surface_habitable"], outliers_scatter["prix"], s=60, edgecolor="black", label="Top 3") # Outliers
    
    for _, row in outliers_scatter.iterrows():
        label = f"{row['ville']} ({row['prix_m2']:.0f} €/m²)"
        plt.annotate(label, (row["surface_habitable"], row["prix"]), xytext=(5, 5), textcoords="offset points", fontsize=8)

    plt.title("Relation surface / prix (Focus Outliers)")
    save_fig("2.3.5_scatter_annotated.png")

    # --- 2.4 ANALYSES CROISÉES SUR IQR ---
    print_step("2.4 ANALYSES CROISÉES (Cœur de marché IQR 5-95%)")
    
    q05 = df_explo["prix_m2"].quantile(0.05)
    q95 = df_explo["prix_m2"].quantile(0.95)
    df_clean_iqr = df_explo[(df_explo["prix_m2"] >= q05) & (df_explo["prix_m2"] <= q95)].copy()
    print(f"Filtre IQR : {len(df_clean_iqr)} lignes conservées.")

    # 2.4.1 Creation variable Piscine
    if "features" in df_clean_iqr.columns:
        df_clean_iqr["has_pool"] = df_clean_iqr["features"].str.contains("piscine", case=False, na=False)

    # 2.4.2 Creation variable Grand Terrain
    if "surface_terrain" in df_clean_iqr.columns:
        q75_terrain = df_clean_iqr["surface_terrain"].quantile(0.75)
        df_clean_iqr["grand_terrain"] = df_clean_iqr["surface_terrain"] >= q75_terrain
        print(f"Seuil Grand Terrain : {q75_terrain:.0f} m²")

    # 2.4.3 Stats Piscine
    if "has_pool" in df_clean_iqr.columns:
        print("\n=== Prix/m² selon présence de piscine ===")
        print(df_clean_iqr.groupby("has_pool")["prix_m2"].describe().round(0))

    # 2.4.4 Stats Terrain
    if "grand_terrain" in df_clean_iqr.columns:
        print("\n=== Prix/m² selon taille du terrain ===")
        print(df_clean_iqr.groupby("grand_terrain")["prix_m2"].describe().round(0))

    # 2.4.5 Stats DPE (Simple describe)
    if "dpe" in df_clean_iqr.columns:
        print("\n=== Prix/m² par classe DPE (Simple) ===")
        df_clean_iqr["dpe"] = df_clean_iqr["dpe"].astype(str).str.strip().str.upper()
        # On ne garde que A-G pour l'affichage propre
        df_dpe = df_clean_iqr[df_clean_iqr["dpe"].isin(["A", "B", "C", "D", "E", "F", "G"])]
        print(df_dpe.groupby("dpe")["prix_m2"].describe().round(0).sort_index())

    # 2.4.6 Mapping Zones
    mapping_zone = {
        "Bordeaux": "centre urbain",
        "Mérignac": "périphérie proche", "Pessac": "périphérie proche",
        "Talence": "périphérie proche", "Le Bouscat": "périphérie proche",
        "Gradignan": "périphérie", "Eysines": "périphérie",
        "Pyla-sur-Mer": "littoral premium", "La Teste-de-Buch": "littoral",
        "Arcachon": "littoral premium"
    }
    if "ville" in df_clean_iqr.columns:
        df_clean_iqr["type_zone"] = df_clean_iqr["ville"].map(mapping_zone).fillna("autre / non classé")
        print("\n=== Prix/m² moyen par type de zone ===")
        moyennes_zone = df_clean_iqr.groupby("type_zone")["prix_m2"].mean().sort_values(ascending=False)
        print(moyennes_zone.round(0))

    # 2.4.7 Phrase Rapport Piscine (Calcul précis)
    if "has_pool" in df_clean_iqr.columns:
        mpool = df_clean_iqr.groupby("has_pool")["prix_m2"].mean()
        if True in mpool and False in mpool:
            mean_no = mpool[False]
            mean_yes = mpool[True]
            diff_abs = mean_yes - mean_no
            diff_pct = (diff_abs / mean_no) * 100
            
            phrase_pool = (
                f"\n[PHRASE RAPPORT 2.4.7] Sur le cœur de marché, la présence d'une piscine est associée à un "
                f"surcoût moyen d'environ {diff_pct:.1f} % du prix au mètre carré, "
                f"le prix passant d'environ {mean_no:.0f} €/m² pour les maisons "
                f"sans piscine à {mean_yes:.0f} €/m² pour celles qui en disposent."
            )
            print(phrase_pool)

    # 2.4.8 Comparaison Zones (Boucle détaillée)
    zone_ref = "centre urbain"
    zones_cibles = ["périphérie proche", "périphérie", "autre / non classé"]
    
    if "type_zone" in df_clean_iqr.columns and zone_ref in moyennes_zone.index:
        mean_ref = moyennes_zone.loc[zone_ref]
        print(f"\n=== Comparaisons détaillées vs {zone_ref} ===")
        for z in zones_cibles:
            if z in moyennes_zone.index:
                mean_z = moyennes_zone.loc[z]
                diff_abs = mean_ref - mean_z
                diff_pct = (diff_abs / mean_z) * 100
                print(f"--- {zone_ref} vs {z} ---")
                print(f"Prix moyen/m² {zone_ref:>18} : {mean_ref:8.0f} €/m²")
                print(f"Prix moyen/m² {z:>18} : {mean_z:8.0f} €/m²")
                print(f"Différence absolue             : {diff_abs:8.0f} €/m²")
                print(f"Différence relative            : {diff_pct:8.1f} %\n")
                
                phrase_zone = (
                    f"-> Par rapport à la zone '{z}', le centre urbain présente un "
                    f"prix moyen au mètre carré supérieur d'environ {diff_abs:.0f} €/m², "
                    f"soit un écart d'environ {diff_pct:.1f} %."
                )
                print(phrase_zone)

    # --- 2.5 ANALYSE CONJOINTE DPE / GES ---
    print_step("2.5 MATRICE DPE / GES")
    if "dpe" in df_clean_iqr.columns and "ges" in df_clean_iqr.columns:
        df_ener = df_clean_iqr.dropna(subset=["dpe", "ges", "prix_m2"]).copy()
        df_ener["ges"] = df_ener["ges"].astype(str).str.strip().str.upper()
        # Filtre sur A-G
        valid = ["A", "B", "C", "D", "E", "F", "G"]
        df_ener = df_ener[df_ener["dpe"].isin(valid) & df_ener["ges"].isin(valid)]
        
        # 2.5.3 (Déjà fait en DPE simple)
        # 2.5.4 Moyenne par GES (manquait dans certaines versions)
        print("\n=== Prix/m² moyen par classe GES ===")
        print(df_ener.groupby("ges")["prix_m2"].mean().round(0))

        # 2.5.5 Pivot Table
        print("\n=== Prix/m² moyen par couple (DPE, GES) ===")
        pivot = df_ener.pivot_table(index="dpe", columns="ges", values="prix_m2", aggfunc="mean")
        print(pivot.round(0))

        # 2.5.6 Describe complet par couple
        print("\n=== Statistiques descriptives par couple (DPE, GES) ===")
        print(df_ener.groupby(["dpe", "ges"])["prix_m2"].describe().round(0))

        # Heatmap
        plt.figure(figsize=(8, 6))
        sns.heatmap(pivot, annot=True, fmt=".0f", cmap="YlOrRd", cbar_kws={'label': '€/m²'})
        plt.title("Prix/m² moyen par couple (DPE, GES)")
        save_fig("2.5_heatmap_dpe_ges.png")

    # --- 2.6 AUDIT FINAL VALEURS MANQUANTES ---
    print_step("2.6 AUDIT DES VALEURS MANQUANTES")
    cols_auditer = ["surface_terrain", "pieces", "dpe", "ges", "features"]
    total = len(df_explo)
    resultats = []

    for col in cols_auditer:
        if col in df_explo.columns:
            n_non_null = df_explo[col].notna().sum()
            n_nan = df_explo[col].isna().sum()
            pct_nan = (n_nan / total) * 100 if total > 0 else 0
            resultats.append({
                "colonne": col,
                "non_null": n_non_null,
                "nan": n_nan,
                "pct_nan": round(pct_nan, 1)
            })
    
    df_nan_audit = pd.DataFrame(resultats)
    # Ordre des colonnes exact du notebook
    print(df_nan_audit[["colonne", "non_null", "nan", "pct_nan"]].to_string(index=False))

    print("\n✅ Analyse terminée. Tous les graphiques sont dans OUTPUT/GRAPHS.")