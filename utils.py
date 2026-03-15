import requests
import streamlit as st
import datetime

# --- CONVERSION VILLE → CODE INSEE ---
@st.cache_data(ttl=86400)
def obtenir_code_insee(nom_ville):
    """Convertit un nom de ville en code INSEE via l'API Geo du gouvernement."""
    try:
        url = f"https://geo.api.gouv.fr/communes?nom={nom_ville}&fields=code&format=json&limit=1&boost=population"
        reponse = requests.get(url, timeout=10)
        if reponse.status_code == 200:
            resultats = reponse.json()
            if resultats and len(resultats) > 0:
                return resultats[0]["code"]
            else:
                return None
        else:
            return None
    except Exception:
        return None

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
def recuperer_donnees_atmo(code_insee="69123"):
    """Utilise le token pour télécharger les données officielles."""
    token = obtenir_token_atmo()
    if not token:
        return {"erreur": "Impossible de générer le token."}
    
    # On recule d'un jour pour être sûr d'avoir les données [cite: 343]
    hier = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    # La syntaxe EXACTE recommandée par la FAQ Atmo France ! [cite: 308, 309, 310]
    filtre_json = '{"code_zone":{"operator":"=","value":"' + code_insee + '"},"date_ech":{"operator":"=","value":"' + hier + '"}}'
    url = f"https://admindata.atmo-france.org/api/data/112/{filtre_json}?withGeom=false"
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        reponse = requests.get(url, headers=headers, timeout=30) 
        if reponse.status_code == 200:
            try:
                # On essaie de lire les données
                return reponse.json()
            except ValueError:
                # Si ça plante (Expecting value...), on affiche le texte brut !
                return {"erreur": f"Le serveur a répondu mais ce n'est pas du JSON. Voici le texte brut : {reponse.text}"}
        else:
            return {"erreur": f"Code serveur {reponse.status_code} : {reponse.text}"}
    except Exception as e:
        return {"erreur": str(e)}

@st.cache_data(ttl=3600)
def recuperer_donnees_pollen(code_insee="69123"):
    """Utilise le token pour télécharger les données officielles de pollen (ID 122)."""
    token = obtenir_token_atmo()
    if not token:
        return {"erreur": "Token invalide."}
    
    # On cible hier pour éviter les soucis de mise à jour l'après-midi
    hier = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    # On utilise l'ID 122 (Pollen) et le code zone (commune) 69123 (Lyon)
    filtre_json = '{"code_zone":{"operator":"=","value":"' + code_insee + '"},"date_ech":{"operator":"=","value":"' + hier + '"}}'
    url = f"https://admindata.atmo-france.org/api/data/122/{filtre_json}?withGeom=false"
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        reponse = requests.get(url, headers=headers, timeout=30) 
        if reponse.status_code == 200:
            try:
                return reponse.json()
            except ValueError:
                return {"erreur": "Le serveur n'a pas renvoyé de JSON."}
        else:
            return {"erreur": f"Code {reponse.status_code}"}
    except Exception as e:
        return {"erreur": str(e)}


# --- EXPERTISE SANTÉ ---
def generer_conseils(risque_pollen, risque_pollution):
    """Génère des conseils basés sur les niveaux de risque pollen et pollution (Atmo France)."""
    conseils = []

    if risque_pollen >= 3:
        conseils.append("🌬️ **Pollens :** Le risque pollinique est élevé. Évite de faire sécher le linge dehors et brosse ou rince tes cheveux le soir.")
    elif risque_pollen >= 1:
        conseils.append("🤧 **Pollens :** Risque pollinique modéré. Reste attentif à tes symptômes.")

    if risque_pollution >= 3:
        conseils.append("⚠️ **Pollution :** La pollution de l'air exacerbe les allergies aux pollens et te rend plus sensible.")

    conseils.append("🪟 **Maison :** N'oublie pas : 10 min d'aération pour renouveler l'air d'une pièce.")

    return conseils


def extraire_donnees_atmo(json_brut):
    """Extrait les informations essentielles du JSON d'Atmo France."""
    try:
        # On vérifie que la boîte "features" existe et n'est pas vide
        if "features" in json_brut and len(json_brut["features"]) > 0:
            # On va chercher le trésor dans "properties"
            donnees = json_brut["features"][0]["properties"]
            
            return {
                "ville": donnees.get("lib_zone", "Inconnue"),
                "date": donnees.get("date_ech", "Inconnue"),
                "qualite_texte": donnees.get("lib_qual", "Inconnu"),
                "qualite_note": donnees.get("code_qual", 0),
                "couleur": donnees.get("coul_qual", "#ffffff"),
                "pm10_note": donnees.get("code_pm10", 0),
                "pm25_note": donnees.get("code_pm25", 0),
                "no2_note": donnees.get("code_no2", 0),
                "o3_note": donnees.get("code_o3", 0)
            }
        else:
            return None
    except Exception as e:
        return None


def extraire_donnees_pollen(json_brut):
    """Extrait les niveaux de pollens du JSON d'Atmo France."""
    try:
        if "features" in json_brut and len(json_brut["features"]) > 0:
            donnees = json_brut["features"][0]["properties"]
            
            return {
                "ville": donnees.get("lib_zone", "Inconnue"),
                "date": donnees.get("date_ech", "Inconnue"),
                "risque_global": donnees.get("lib_qual", "Inconnu"),
                "risque_note": donnees.get("code_qual", 0),
                "alerte": donnees.get("alerte", False),
                "responsable": donnees.get("pollen_resp", "Aucun"),
                "aulne": donnees.get("code_aul", 0),
                "bouleau": donnees.get("code_boul", 0),
                "graminees": donnees.get("code_gram", 0),
                "ambroisie": donnees.get("code_ambr", 0)
            }
        else:
            return None
    except Exception as e:
        return None

