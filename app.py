import streamlit as st
import pandas as pd
from datetime import date
import json
import requests
import plotly.express as px
import gspread # NOUVEL OUTIL POUR GOOGLE SHEETS
from utils import recuperer_donnees_atmo, generer_conseils

from utils import calculer_indice_pollen, calculer_indice_polluant, evaluer_qualite_air

# 1. Configuration de la page web
st.set_page_config(page_title="Mon Suivi Pollen", page_icon="🤧", layout="centered")

# --- CONNEXION À GOOGLE SHEETS ---
# st.cache_resource permet de ne pas se reconnecter à Google à chaque clic
@st.cache_resource
def init_gspread():
    # On récupère le JSON caché dans le coffre-fort Streamlit
    creds_json = st.secrets["google_credentials"]
    creds_dict = json.loads(creds_json)
    return gspread.service_account_from_dict(creds_dict)

gc = init_gspread()
# On ouvre ton fichier par son nom exact
sheet = gc.open("Base_Pollen")
ws_journal = sheet.worksheet("Journal")
ws_profil = sheet.worksheet("Profil")

# --- CHARGEMENT DU PROFIL DEPUIS GOOGLE SHEETS ---
records_profil = ws_profil.get_all_records()
if len(records_profil) > 0:
    ville_actuelle = str(records_profil[0].get("ville", "Lyon"))
    allergies_brutes = str(records_profil[0].get("allergies", ""))
    allergies_actuelles = [a.strip() for a in allergies_brutes.split(",")] if allergies_brutes else []
else:
    ville_actuelle = "Lyon"
    allergies_actuelles = []

# 2. Titre principal
st.title("🌿 Mon Suivi Allergies & Pollen")
st.write("Bienvenue sur ton application personnelle de suivi.")

# 3. Création des 3 onglets principaux
tab1, tab2, tab3 = st.tabs(["🚨 Mes Alertes", "📝 Mon Journal", "👤 Mon Profil et Historique"])

# --- CONTENU DE L'ONGLET 1 : ALERTES & PRÉVISIONS ---
with tab1:
    st.header(f"Conditions à {ville_actuelle}")
    
    col_btn, _ = st.columns([1, 3])
    with col_btn:
        if st.button("🔄 Actualiser"):
            st.rerun()

    try:
        url_geo = f"https://geocoding-api.open-meteo.com/v1/search?name={ville_actuelle}&count=1&language=fr&format=json"
        reponse_geo = requests.get(url_geo).json()
        
        if "results" in reponse_geo:
            lat = reponse_geo["results"][0]["latitude"]
            lon = reponse_geo["results"][0]["longitude"]
            
            variables_pollens = "birch_pollen,grass_pollen,ragweed_pollen,mugwort_pollen,alder_pollen,olive_pollen"
            variables_pollution = "european_aqi,pm10,pm2_5,nitrogen_dioxide,ozone"
            
            url_data = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current={variables_pollens},{variables_pollution}&hourly={variables_pollens},{variables_pollution}&timezone=auto&forecast_days=4"
            reponse_data = requests.get(url_data).json()
            
            donnees_actuelles = reponse_data.get("current", {})
            df_horaire = pd.DataFrame(reponse_data.get("hourly", {}))
            df_horaire['time'] = pd.to_datetime(df_horaire['time'])
            df_horaire['Date'] = df_horaire['time'].dt.date
            
            df_previsions = df_horaire.groupby('Date').max().reset_index()
            df_previsions = df_previsions[df_previsions['Date'] > date.today()].head(3)

            sous_tab1, sous_tab2 = st.tabs(["🤧 Pollens", "🌫️ Pollution"])
            
            # ---> SOUS-ONGLET POLLENS
            with sous_tab1:
                st.subheader("Niveaux de pollen actuels")
                traduction_pollens = {
                    "birch_pollen": "Bouleau", "grass_pollen": "Graminées",
                    "ragweed_pollen": "Ambroisie", "mugwort_pollen": "Armoise",
                    "alder_pollen": "Aulne", "olive_pollen": "Olivier"
                }
                
                risque_max_actuel = 0 
                for cle_api, nom_fr in traduction_pollens.items():
                    valeur_brute = donnees_actuelles.get(cle_api, 0)
                    indice = calculer_indice_pollen(valeur_brute)
                    if indice > risque_max_actuel: risque_max_actuel = indice
                    
                    col1, col2, col3 = st.columns([2, 1, 4])
                    col1.write(f"**{nom_fr}**")
                    col2.write(f"{indice} / 5")
                    col3.progress(indice / 5.0)
                
                st.info(f"🚨 **Risque Pollinique Global : {risque_max_actuel} / 5**")
                
                st.divider()
                st.subheader("📅 Prévisions Risque Maximum (1 à 5)")
                cols_prev = st.columns(len(df_previsions))
                for index, row in df_previsions.iterrows():
                    with cols_prev[index % len(cols_prev)]:
                        st.write(f"**{row['Date'].strftime('%d/%m')}**")
                        pire_indice_jour = max([calculer_indice_pollen(row.get(k, 0)) for k in traduction_pollens.keys()])
                        st.metric(label="Pollen Max", value=f"{pire_indice_jour} / 5")

            # ---> SOUS-ONGLET POLLUTION
            with sous_tab2:
                st.subheader("Qualité de l'air actuelle")
                aqi_actuel = donnees_actuelles.get('european_aqi', 0)
                statut_aqi, _ = evaluer_qualite_air(aqi_actuel)
                mot_statut = statut_aqi.split(" ")[0]
                
                st.metric(label="Indice Européen Global (AQI)", value=f"{int(aqi_actuel)}", delta=mot_statut, delta_color="inverse" if aqi_actuel > 60 else "normal")
                
                st.write("---")
                st.write("**Détail par polluant (Échelle de 1 à 5) :**")
                
                dict_polluants = {
                    'pm10': ('Particules PM10', donnees_actuelles.get('pm10', 0)),
                    'pm2_5': ('Particules PM2.5', donnees_actuelles.get('pm2_5', 0)),
                    'ozone': ('Ozone (O3)', donnees_actuelles.get('ozone', 0)),
                    'no2': ('Dioxyde d\'Azote (NO2)', donnees_actuelles.get('nitrogen_dioxide', 0))
                }

                risque_max_pollution = 0
                for cle_api, (nom_fr, valeur_brute) in dict_polluants.items():
                    indice = calculer_indice_polluant(cle_api, valeur_brute)
                    if indice > risque_max_pollution: risque_max_pollution = indice
                    
                    col1, col2, col3 = st.columns([2, 1, 4])
                    col1.write(f"**{nom_fr}**")
                    col2.write(f"{indice} / 5")
                    col3.progress(indice / 5.0)
                
                st.caption("Données normalisées selon les seuils de l'Agence Européenne pour l'Environnement.")
                
                st.divider()
                st.subheader("📅 Prévisions AQI Global")
                cols_prev_pol = st.columns(len(df_previsions))
                for index, row in df_previsions.iterrows():
                    with cols_prev_pol[index % len(cols_prev_pol)]:
                        st.write(f"**{row['Date'].strftime('%d/%m')}**")
                        aqi_prev = row.get('european_aqi', 0)
                        statut_prev, _ = evaluer_qualite_air(aqi_prev)
                        mot_statut_prev = statut_prev.split(" ")[0]
                        st.metric(label="AQI Max estimé", value=int(aqi_prev), delta=mot_statut_prev, delta_color="inverse" if aqi_prev > 60 else "normal")

                st.divider()
                st.subheader("💡 Conseils Santé du Jour")
                # On génère les conseils intelligents
                liste_conseils = generer_conseils("Ensoleillé", risque_max_actuel, risque_max_pollution)
                for conseil in liste_conseils:
                    st.info(conseil)

                st.divider()
                st.subheader("🇫🇷 Test Connexion Atmo France")
                if st.button("Tester l'API Atmo"):
                    with st.spinner("Génération du Token et connexion en cours..."):
                        # On appelle notre nouvelle fonction !
                        donnees_officielles = recuperer_donnees_atmo()
                        
                        if "erreur" in donnees_officielles:
                            st.error(donnees_officielles["erreur"])
                        else:
                            st.success("Connexion réussie ! Voici à quoi ressemblent les données :")
                            # On affiche les données brutes pour les analyser
                            st.json(donnees_officielles)


        else:
            st.error(f"Impossible de trouver les coordonnées pour la ville : {ville_actuelle}.")
            
    except Exception as e:
        st.error(f"Une erreur est survenue lors de la connexion à l'API : {e}")

# --- CONTENU DE L'ONGLET 2 : JOURNAL ---
with tab2:
    st.header("Saisir mon état du jour")
    
    with st.form("formulaire_journal", clear_on_submit=True):
        st.subheader("1. Environnement & État général")
        col1, col2 = st.columns(2)
        with col1:
            date_saisie = st.date_input("Date", value=date.today())
            meteo = st.selectbox("Météo", ["Ensoleillé", "Nuageux", "Pluvieux", "Venteux"])
        with col2:
            activite = st.selectbox("Activité extérieure", ["Intérieur", "Sortie courte", "Sport/Jardinage", "Longue exposition"])
            sommeil = st.slider("Qualité du sommeil (1=Mauvais, 5=Excellent)", 1, 5, 3)

        st.subheader("2. Symptômes")
        symptomes_globaux = st.slider("Intensité globale des symptômes (1 à 10)", 1, 10, 1)
        symptomes_specifiques = st.multiselect(
            "Symptômes spécifiques",
            ["Nez bouché/qui coule", "Éternuements", "Yeux rouges/qui grattent", "Toux/Asthme", "Fatigue", "Maux de tête"]
        )

        st.subheader("3. Traitement")
        col3, col4 = st.columns(2)
        with col3:
            traitement_pris = st.checkbox("J'ai pris un traitement aujourd'hui")
            type_traitement = st.multiselect("Type", ["Comprimé", "Collyre (Gouttes)", "Spray nasal", "Inhalateur"])
            nom_medicament = st.text_input("Nom du médicament")
        with col4:
            moment_prise = st.multiselect("Moment", ["Matin", "Midi", "Soir", "À la demande"])
            duree_traitement = st.selectbox("Durée", ["Ponctuel", "En cours", "Terminé"])

        soumis = st.form_submit_button("💾 Enregistrer mon journal")

        if soumis:
            # On envoie les données directement dans l'onglet "Journal" du Google Sheets !
            nouvelle_ligne = [
                str(date_saisie),
                meteo,
                activite,
                sommeil,
                symptomes_globaux,
                ", ".join(symptomes_specifiques),
                "Oui" if traitement_pris else "Non",
                ", ".join(type_traitement),
                nom_medicament,
                ", ".join(moment_prise),
                duree_traitement
            ]
            ws_journal.append_row(nouvelle_ligne)
            st.success("🎉 Tes données ont bien été enregistrées en ligne dans ton Google Sheets !")

# --- CONTENU DE L'ONGLET 3 : HISTORIQUE ET PROFIL ---
with tab3:
    st.header("👤 Mon Profil et Historique")
    
    st.subheader("Mes paramètres")
    with st.form("formulaire_profil"):
        ville = st.text_input("📍 Ma ville", value=ville_actuelle)
        liste_allergenes = ["Bouleau", "Graminées", "Ambroisie", "Aulne", "Olivier", "Armoise", "Acariens", "Poils d'animaux"]
        allergies = st.multiselect("🤧 Je suis sensible à :", liste_allergenes, default=[a for a in allergies_actuelles if a in liste_allergenes])
        
        submit_profil = st.form_submit_button("💾 Sauvegarder mon profil")
        if submit_profil:
            # On efface l'ancien profil et on enregistre le nouveau
            ws_profil.clear()
            ws_profil.append_row(["ville", "allergies"]) # On remet les en-têtes
            ws_profil.append_row([ville, ", ".join(allergies)])
            st.success("Ton profil a été mis à jour dans le Cloud !")
            st.info("💡 Pense à rafraîchir la page pour mettre à jour les alertes de ta ville.")

    st.divider()
    
    st.subheader("📊 Évolution de mes symptômes")
    # On lit les données depuis Google Sheets
    records_journal = ws_journal.get_all_records()
    
    if len(records_journal) > 0:
        df = pd.DataFrame(records_journal)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values(by='Date')

        fig = px.line(
            df, x="Date", y="Symptomes_Globaux", markers=True, 
            title="Intensité de mes allergies au fil du temps",
            hover_data=["Meteo", "Symptomes_Specifiques", "Traitement_Pris"]
        )
        fig.update_layout(yaxis=dict(range=[0, 10.5]), hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("🗂️ Mes données enregistrées")
        st.dataframe(df, use_container_width=True)
        
        st.subheader("🗑️ Gérer mes données")
        with st.expander("Clique ici si tu souhaites supprimer une saisie"):
            dates_disponibles = df['Date'].dt.strftime('%Y-%m-%d').unique().tolist()
            with st.form("form_suppression"):
                date_choisie = st.selectbox("Sélectionne la date de l'entrée à supprimer :", ["Choisir..."] + dates_disponibles)
                bouton_supprimer = st.form_submit_button("❌ Supprimer définitivement")
                
                if bouton_supprimer and date_choisie != "Choisir...":
                    # On garde tout ce qui ne correspond pas à la date choisie
                    df_filtre = df[df['Date'].dt.strftime('%Y-%m-%d') != date_choisie]
                    df_filtre['Date'] = df_filtre['Date'].dt.strftime('%Y-%m-%d') # On remet la date en texte pour Google Sheets
                    
                    # On efface tout l'onglet et on le remplit avec les données filtrées
                    ws_journal.clear()
                    en_tetes = df_filtre.columns.values.tolist()
                    valeurs = df_filtre.values.tolist()
                    ws_journal.update([en_tetes] + valeurs)
                    
                    st.success(f"L'entrée du {date_choisie} a été supprimée avec succès !")
                    st.rerun() 
    else:
        st.info("👋 Aucune donnée pour le moment. Remplis ton journal pour voir ton historique !")