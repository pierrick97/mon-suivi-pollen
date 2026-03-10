import pandas as pd
import requests
import streamlit as st

# --- CONNEXION AUTOMATIQUE À ATMO FRANCE ---
@st.cache_data(ttl=3600)
def obtenir_token_atmo():
    """Simule la connexion avec email/mot de passe pour récupérer le Token JWT."""
    try:
        # On vérifie d'abord que les secrets existent bien
        if "atmo_username" not in st.secrets or "atmo_password" not in st.secrets:
            st.error("🚨 Les identifiants Atmo sont introuvables dans les secrets Streamlit. Vérifie le fichier secrets.toml ou tes variables sur le Cloud !")
            return None
            
        url = "https://admindata.atmo-france.org/api/login"
        payload = {
            "username": st.secrets["atmo_username"],
            "password": st.secrets["atmo_password"]
        }
        reponse = requests.post(url, json=payload)
        
        if reponse.status_code == 200:
            return reponse.json().get("token")
        else:
            # Si le serveur refuse, on affiche sa réponse brute pour comprendre !
            st.error(f"🛑 Refus du serveur Atmo (Code {reponse.status_code}) : {reponse.text}")
            return None
            
    except Exception as e:
        st.error(f"💥 Erreur technique système : {e}")
        return None

@st.cache_data(ttl=3600)
def recuperer_donnees_atmo(endpoint="/api/v2/data/indices/atmo"):
    """Utilise le token pour télécharger les données officielles."""
    token = obtenir_token_atmo()
    if not token:
        return {"erreur": "Impossible de générer le token. Regarde l'erreur rouge au-dessus !"}
    
    # Astuce de la FAQ : on ajoute ?withGeom=false pour que ce soit plus rapide
    url = f"https://admindata.atmo-france.org{endpoint}?withGeom=false"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        reponse = requests.get(url, headers=headers)
        if reponse.status_code == 200:
            return reponse.json()
        else:
            return {"erreur": f"Code serveur {reponse.status_code} : {reponse.text}"}
    except Exception as e:
        return {"erreur": str(e)}

# --- ALGORITHMES DE NORMALISATION ---
def calculer_indice_pollen(valeur_brute):
    if pd.isna(valeur_brute) or valeur_brute <= 0: return 0
    elif valeur_brute < 10: return 1  
    elif valeur_brute < 50: return 2  
    elif valeur_brute < 100: return 3 
    elif valeur_brute < 500: return 4 
    else: return 5                    

def calculer_indice_polluant(polluant, valeur_brute):
    if pd.isna(valeur_brute) or valeur_brute < 0: return 0
    if polluant == 'pm10':
        if valeur_brute <= 20: return 1
        elif valeur_brute <= 40: return 2
        elif valeur_brute <= 50: return 3
        elif valeur_brute <= 100: return 4
        else: return 5
    elif polluant == 'pm2_5':
        if valeur_brute <= 10: return 1
        elif valeur_brute <= 20: return 2
        elif valeur_brute <= 25: return 3
        elif valeur_brute <= 50: return 4
        else: return 5
    elif polluant == 'ozone':
        if valeur_brute <= 50: return 1
        elif valeur_brute <= 100: return 2
        elif valeur_brute <= 130: return 3
        elif valeur_brute <= 240: return 4
        else: return 5
    elif polluant == 'no2':
        if valeur_brute <= 40: return 1
        elif valeur_brute <= 90: return 2
        elif valeur_brute <= 120: return 3
        elif valeur_brute <= 230: return 4
        else: return 5
    return 0

def evaluer_qualite_air(aqi):
    if pd.isna(aqi): return "Inconnu", 0
    elif aqi <= 20: return "Bon (1/5)", aqi
    elif aqi <= 40: return "Moyen (2/5)", aqi
    elif aqi <= 60: return "Dégradé (3/5)", aqi
    elif aqi <= 80: return "Mauvais (4/5)", aqi
    else: return "Très Mauvais (5/5)", aqi

# --- EXPERTISE SANTÉ ---
def generer_conseils(meteo, risque_pollen, risque_pollution):
    """Génère des conseils basés sur la documentation officielle."""
    conseils = []
    
    if meteo == "Pluvieux":
        conseils.append("🌧️ **Météo :** Tu respires mieux grâce à la pluie ! Elle lessive l'air, en entraînant les pollens vers le sol.")
    elif meteo in ["Ensoleillé", "Venteux"] and risque_pollen >= 2:
        conseils.append("🌬️ **Pollens :** Le vent favorise la dispersion. Évite de faire sécher le linge dehors, pour ne pas que les pollens se déposent sur le linge humide.")
        
    if risque_pollen >= 3:
        conseils.append("🚿 **Routine :** Brosse ou rince tes cheveux le soir, les pollens s'y déposent en grand nombre.")
        
    if risque_pollution >= 3:
        conseils.append("⚠️ **Alerte :** La pollution de l'air exacerbe les allergies aux pollens et te rend plus sensible.")
    
    conseils.append("🪟 **Maison :** N'oublie pas : 10 min d'aération pour renouveler l'air d'une pièce.")
    
    return conseils