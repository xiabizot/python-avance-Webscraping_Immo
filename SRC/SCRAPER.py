# =============================================================================
# PROJET : Analyse du marché immobilier - Scraping ETREPROPRIO (Maisons Bordeaux R10)
#
# PHASE : COLLECTE EXHAUSTIVE D'ANNONCES
#
# Étapes :
#   1. Récupérer les URLs d'annonces à partir des pages de listing (requests + BS4)
#   2. Pour chaque URL, scraper la page de détail (Selenium + BS4 + JSON-LD)
#   3. Créer un dossier de réception pour le fichier CSV qui sera généré
#   4. Stocker les résultats dans un fichier CSV, avec typage de base
#   5. Afficher le nombre total de lignes extraites + 5 premières lignes du dataframe
# =============================================================================

import requests
import json
import re
from pathlib import Path
import pandas as pd
import time
import random
import csv

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# =============================================================================
# CONFIGURATION DOSSIER
# =============================================================================

# SRC = dossier où se trouve ce script (ex: .../PYTHON_AV-PROJET_IMMO/SRC)
SRC_DIR = Path(__file__).resolve().parent

# Racine du projet (ex: .../PYTHON_AV-PROJET_IMMO)
PROJECT_DIR = SRC_DIR.parent

# Dossier de sortie (jumeau de SRC)
OUTPUT_DIR = PROJECT_DIR / "OUTPUT"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Fichier CSV de sortie
OUTPUT_CSV = OUTPUT_DIR / "data_bordeaux_R10_maisons.csv"

print("PROJECT_DIR :", PROJECT_DIR.resolve())
print("OUTPUT_DIR  :", OUTPUT_DIR.resolve())
print("OUTPUT_CSV  :", OUTPUT_CSV.resolve())

# =============================================================================
# CONFIGURATION GÉNÉRALE
# =============================================================================

# URL modèle pour le listing (Bordeaux - rayon R10)
# {page} sera remplacé par 1, 2, 3, ...
BASE_URL_TEMPLATE = "https://www.etreproprio.com/annonces/thflcpo.lc74056-r0#list"

# Pages à parcourir (inclusives)
START_PAGE = 1
END_PAGE = 30 # Le site Internet concerné n'autorise que 30 pages de résultats / pour un test, se limiter entre 1 à 3 pages

# Liste de user-agents pour limiter les risques de blocage par le site
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
]

# =============================================================================
# OUTILS GÉNÉRIQUES
# =============================================================================

def init_driver():
    """
    Initialisation sécurisée de l'instance Chrome Headless.

    - Mode headless pour ne pas ouvrir de vraie fenêtre
    - Options pour environnements type serveur (no-sandbox, dev-shm)
    - User-agent choisi aléatoirement parmi la liste définie
    """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    return webdriver.Chrome(options=options)


def extract_number(text):
    """
    Extraction d'un entier à partir d'une chaîne contenant du texte.

    Exemple :
        '55 m²'      -> 55
        '2 pièces'   -> 2
        None / ''    -> None
    """
    if not text:
        return None
    res = re.sub(r'[^0-9]', '', str(text))
    return int(res) if res else None


def random_sleep(min_s=1.5, max_s=3.5):
    """
    Pause aléatoire entre min_s et max_s secondes.

    Objectif :
        - imiter un comportement humain
        - réduire le risque de blocage serveur
    """
    time.sleep(random.uniform(min_s, max_s))


# =============================================================================
# PHASE 1 : RÉCUPÉRATION DES URLS D'ANNONCES (LISTING)
# =============================================================================

def get_listing_links(page_num):
    """
    Récupère toutes les URLs d'annonces présentes sur une page de listing.

    Paramètres
    ----------
    page_num : int
        Numéro de page à scraper.

    Retour
    ------
    list[str]
        Liste d'URLs complètes vers les pages de détail des annonces.
    """
    url = BASE_URL_TEMPLATE.format(page=page_num)
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    links = []

    try:
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')

            # Chaque carte d'annonce est dans un div.card-cla-search
            cards = soup.find_all("div", class_="card-cla-search")

            for card in cards:
                # On remonte au parent <a> pour récupérer le lien de l'annonce
                parent = card.find_parent('a')
                if parent and parent.get('href'):
                    href = parent.get('href')
                    # Si l'URL est relative, on la rend absolue
                    full_url = href if href.startswith('http') else "https://www.etreproprio.com" + href
                    links.append(full_url)

        else:
            print(f"[Page {page_num}] Statut HTTP non-200 : {response.status_code}")

    except Exception as e:
        print(f"❌ Échec acquisition liens (Page {page_num}) : {e}")

    return links


# =============================================================================
# PHASE 2 : SCRAPING D'UNE ANNONCE (PAGE DÉTAIL)
# =============================================================================

def scrape_ad_detail(driver, url):
    """
    Scrape toutes les informations importantes d'une annonce individuelle.

    IMPORTANT :
    - AUCUN doublon n'est supprimé, on récupère les données telles qu'elles apparaissent.
    - On utilise Selenium pour laisser le JavaScript charger la page.
    - On utilise BeautifulSoup + JSON-LD pour extraire la description et les méta-données.

    Paramètres
    ----------
    driver : webdriver.Chrome
        Instance Selenium déjà initialisée.
    url : str
        URL de la page de détail de l'annonce.

    Retour
    ------
    dict
        Un dictionnaire contenant une ligne d'annonce avec les champs suivants :
        url, type_bien, titre, prix, surface_habitable, surface_terrain,
        pieces, ville, cp, dpe, ges, features, description
    """
    data = {
        'url': url,
        'type_bien': None,
        'titre': None,
        'prix': None,
        'surface_habitable': None,
        'surface_terrain': None,
        'pieces': None,
        'ville': None,
        'cp': None,
        'dpe': None,
        'ges': None,
        'features': None,
        'description': None,
    }

    try:
        # Chargement de la page d'annonce
        driver.get(url)

        # Attente que le titre soit présent (signe que le JS a fini)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "ep-dtl-title"))
        )

        # Optionnel : petite pause pour s'assurer que tout est bien en place
        random_sleep(0.5, 1.2)

        # On récupère le HTML complet de la page
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # ---------------------------------------------------------------------
        # 1. TITRE & TYPE DE BIEN
        # ---------------------------------------------------------------------
        title_sect = soup.find("section", class_="ep-dtl-title")
        if title_sect and title_sect.find("h1"):
            titre = title_sect.find("h1").get_text(strip=True)
            data['titre'] = titre

            # On déduit le type de bien à partir de mots-clés dans le titre
            for t in ["maison", "appartement", "immeuble", "terrain", "studio", "loft"]:
                if t in titre.lower():
                    data['type_bien'] = t.capitalize()
                    break

        # ---------------------------------------------------------------------
        # 2. LOCALISATION (VILLE + CP)
        #    Exemple HTML : <div class="ep-loc"> — Bordeaux 33100 — </div>
        # ---------------------------------------------------------------------
        loc_tag = soup.find(class_="ep-loc")
        if loc_tag:
            raw_loc = loc_tag.get_text(" ", strip=True).replace("—", " ").strip()
            # On cherche 5 chiffres consécutifs pour le code postal
            cp_match = re.search(r"(\d{5})", raw_loc)
            if cp_match:
                cp = cp_match.group(1)
                data['cp'] = cp
                # La ville = tout ce qui est avant le CP
                ville = raw_loc.split(cp)[0].strip()
                data['ville'] = ville
            else:
                # Si pas de CP trouvé, on met tout dans ville
                data['ville'] = raw_loc

        # ---------------------------------------------------------------------
        # 3. PRIX
        #    Exemple : <div class="ep-price">346 500 €</div>
        # ---------------------------------------------------------------------
        price_tag = soup.find(class_="ep-price")
        if price_tag:
            data['prix'] = extract_number(price_tag.get_text())

        # ---------------------------------------------------------------------
        # 4. SURFACES (habitable / terrain)
        #    Exemple : <div class="ep-area">55 m² / 182 m²</div>
        # ---------------------------------------------------------------------
        area_tag = soup.find(class_="ep-area")
        if area_tag:
            txt = area_tag.get_text(" ", strip=True)
            if "/" in txt:
                parts = txt.split("/")
                data['surface_habitable'] = extract_number(parts[0])
                data['surface_terrain'] = extract_number(parts[1])
            else:
                data['surface_habitable'] = extract_number(txt)

        # ---------------------------------------------------------------------
        # 5. NOMBRE DE PIÈCES
        #    Exemple : <div class="ep-room">2 pièces</div>
        # ---------------------------------------------------------------------
        room_tag = soup.find(class_="ep-room")
        data['pieces'] = extract_number(room_tag.get_text()) if room_tag else None

        # ---------------------------------------------------------------------
        # 6. PERFORMANCE ÉNERGÉTIQUE (DPE / GES)
        #    On cherche la lettre avec la classe "selected" dans les diagrammes
        # ---------------------------------------------------------------------
        for k, c in [('dpe', 'dpe-diagram'), ('ges', 'ges-diagram')]:
            box = soup.find(class_=c)
            if box:
                active = box.find(class_="selected")
                if active:
                    data[k] = active.get_text(strip=True)

        # ---------------------------------------------------------------------
        # 7. FEATURES (parking, balcon, jardin, piscine, ...)
        #    On récupère les titres des icônes dans <div class="ep-features">
        #    AUCUNE suppression de doublons ici.
        # ---------------------------------------------------------------------
        feat_div = soup.find(class_="ep-features")
        if feat_div:
            feats = [img.get("title") for img in feat_div.find_all("img") if img.get("title")]
            data['features'] = ", ".join(feats) if feats else None

        # ---------------------------------------------------------------------
        # 8. DESCRIPTION (JSON-LD en priorité, sinon div HTML)
        #
        #    - On parcourt tous les <script type="application/ld+json">
        #    - On cherche l'objet dont @type == "Product"
        #    - On prend la clé "description" si elle existe
        #    - On nettoie le HTML + retours à la ligne
        # ---------------------------------------------------------------------
        json_tags = soup.find_all('script', type='application/ld+json')
        description_found = None

        for tag in json_tags:
            try:
                content = tag.string
                if not content:
                    continue
                content = json.loads(content)

                # Cas 1 : un dictionnaire
                if isinstance(content, dict) and content.get('@type') == 'Product':
                    description_found = content.get('description')

                # Cas 2 : une liste d'objets JSON-LD
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('@type') == 'Product':
                            description_found = item.get('description')
                            if description_found:
                                break

                if description_found:
                    break

            except Exception:
                # JSON non valide ou non parsable -> on ignore et on continue
                continue

        if description_found:
            # On nettoie le HTML éventuel dans la description
            desc_text = BeautifulSoup(description_found, "html.parser").get_text(
                " ", strip=True
            )
            # On supprime les retours à la ligne pour ne pas décaler les colonnes CSV
            data['description'] = desc_text.replace('\n', ' ').replace('\r', ' ').strip()
        else:
            # Fallback : on prend le texte de la div de description si accessible
            desc_div = soup.find("div", class_="ep-desc")
            if desc_div:
                data['description'] = desc_div.get_text(" ", strip=True)

    except Exception as e:
        print(f"❌ Erreur d'extraction : {url} | {e}")

    return data


# =============================================================================
# PHASE 3 : ORCHESTRATION GLOBALE + SAUVEGARDE
# =============================================================================

def main():
    """
    Orchestrateur principal :
    - initialise Selenium,
    - boucle sur les pages de résultats,
    - récupère les liens d'annonces,
    - scrape chaque annonce en détail,
    - stocke le tout dans un CSV,
    - affiche le nombre total de lignes extraites à la fin.
    """
    # Pour rendre les tirages aléatoires (user-agent, sleep) reproductibles
    random.seed(42)

    print(f"Lancement de la collecte : pages {START_PAGE} -> {END_PAGE}")
    driver = init_driver()
    all_data = []
    
    try:
        for page in range(START_PAGE, END_PAGE + 1):
            print(f"\n--- Indexation Page {page} ---")
            links = get_listing_links(page)

            # Si aucune annonce trouvée, on sort de la boucle (plus de pages utiles)
            if not links:
                print(f"[Page {page}] Aucun lien trouvé, arrêt de la pagination.")
                break

            print(f"[Page {page}] {len(links)} liens d'annonces trouvés.")

            # Boucle sur chaque annonce de la page
            for i, link in enumerate(links):
                print(f"   [Page {page}/{END_PAGE}] Annonce {i+1}/{len(links)} : {link}")
                ad_data = scrape_ad_detail(driver, link)
                all_data.append(ad_data)

                # Contrôle minimal : titre + prix doivent être présents
                if ad_data.get("titre") is None or ad_data.get("prix") is None:
                    print(f"   ⚠ Données incomplètes pour cette annonce (titre ou prix manquant) : {link}")

                # Temporisation entre deux annonces
                random_sleep()

            # Construction du DataFrame à partir de TOUTES les annonces collectées jusqu'ici
            df = pd.DataFrame(all_data)

            # SAFETY CHECK : on vérifie qu'on a bien au moins une ligne avant d'aller plus loin
            if df.empty:
                print("⚠ DataFrame vide après cette page, rien à sauvegarder pour l'instant.")
            else:
                # Typage numérique pour certaines colonnes (hors cp)
                cols_to_fix = ['prix', 'pieces', 'surface_habitable', 'surface_terrain']
                for col in cols_to_fix:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')

                # Optionnel : on force le cp en string propre
                if 'cp' in df.columns:
                    df['cp'] = df['cp'].astype('string')

                # Sauvegarde intermédiaire du CSV (écrase le précédent)
                try:
                    df.to_csv(
                        OUTPUT_CSV,
                        index=False,
                        sep=',',
                        encoding='utf-8-sig',
                        quoting=csv.QUOTE_ALL
                    )
                    print(f"--- Sauvegarde intermédiaire OK : {len(df)} lignes dans {OUTPUT_CSV} ---")
                except PermissionError:
                    print(f"❌ Impossible d'écrire dans {OUTPUT_CSV} (PermissionError).")
                    print("   → Vérifie que le fichier n'est pas ouvert dans Excel ou un autre programme.")
                except Exception as e:
                    print(f"❌ Autre erreur lors de la sauvegarde CSV : {e}")

            # Protection anti-bannissement : grosse pause toutes les 5 pages
            if page % 5 == 0:
                print("Protocole de temporisation (30s)...")
                time.sleep(30)

            # Pause plus longue entre deux pages de résultats
            random_sleep(4.0, 6.0)

    except KeyboardInterrupt:
        print("\n⛔ Arrêt manuel détecté. Fermeture des ressources...")

    except Exception as e:
        print(f"\n❌ Incident majeur dans main() : {e}")

    finally:
        # Fermeture propre du driver Selenium
        driver.quit()
        print("\nDriver Selenium fermé proprement.")

        # Nombre total d'annonces collectées en mémoire
        nb_lignes = len(all_data)
        print(f"\n✅ COLLECTE TERMINÉE.")
        print(f"➡ Nombre total de lignes extraites (all_data) : {nb_lignes}")

        # Vérification de l'existence réelle du fichier sur le disque
        if OUTPUT_CSV.exists():
            print(f"➡ Fichier final disponible : {OUTPUT_CSV}")
            print("\nAperçu des 5 premières lignes du CSV :")
            if not df.empty:
                print(df.head())
            else:
                print("⚠ Pas d'aperçu : df est vide (collecte interrompue ou aucune annonce).")
        else:
            print(f"⚠ Aucun fichier {OUTPUT_CSV} n'a pu être écrit (voir les messages d'erreur ci-dessus).")


# =============================================================================
# POINT D'ENTRÉE
# =============================================================================

if __name__ == "__main__":
    main()
