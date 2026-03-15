import streamlit as st
import pandas as pd
from datetime import date
import json
import plotly.express as px
import gspread
from utils import recuperer_donnees_atmo, recuperer_donnees_pollen, generer_conseils, extraire_donnees_atmo, extraire_donnees_pollen, obtenir_code_insee

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

# --- FONCTIONS CACHÉES POUR LIMITER LES APPELS GOOGLE SHEETS ---
@st.cache_data(ttl=60)
def charger_profil(_ws_profil):
    """Charge le profil depuis Google Sheets (caché 60s)."""
    return _ws_profil.get_all_records()

@st.cache_data(ttl=60)
def charger_journal(_ws_journal):
    """Charge l'historique du journal depuis Google Sheets (caché 60s)."""
    return _ws_journal.get_all_records()

@st.cache_data(ttl=300)
def verifier_entetes(_ws_journal):
    """Vérifie si la feuille Journal a des données (caché 5min)."""
    return _ws_journal.get_all_values()

# --- VÉRIFICATION DES EN-TÊTES DU JOURNAL ---
EN_TETES_JOURNAL = [
    "Date", "Meteo", "Activite", "Sommeil", "Symptomes_Globaux",
    "Symptomes_Specifiques", "Traitement_Pris", "Type_Traitement",
    "Nom_Medicament", "Moment_Prise", "Duree_Traitement"
]
# Si la feuille est vide, on insère les en-têtes automatiquement
if not verifier_entetes(ws_journal):
    ws_journal.append_row(EN_TETES_JOURNAL)
    st.cache_data.clear()

# --- CHARGEMENT DU PROFIL DEPUIS GOOGLE SHEETS ---
records_profil = charger_profil(ws_profil)
if len(records_profil) > 0:
    ville_actuelle = str(records_profil[0].get("ville", "Lyon"))
    allergies_brutes = str(records_profil[0].get("allergies", ""))
    allergies_actuelles = [a.strip() for a in allergies_brutes.split(",")] if allergies_brutes else []
else:
    ville_actuelle = "Lyon"
    allergies_actuelles = []

# --- RÉSOLUTION DU CODE INSEE ---
code_insee = obtenir_code_insee(ville_actuelle)
if not code_insee:
    code_insee = "69123"  # Fallback sur Lyon

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
            st.cache_data.clear()
            st.rerun()

    # Initialisation des variables pour les conseils (fallback si API indisponible)
    donnees_pollen = None
    donnees_atmo = None

    # --- SECTION POLLENS (Atmo France) ---
    st.subheader("🤧 Données Officielles Pollen (RNSA / Atmo)")

    with st.spinner("Analyse des capteurs de pollens..."):
        donnees_brutes_pollen = recuperer_donnees_pollen(code_insee)

        if "erreur" in donnees_brutes_pollen:
            st.error(donnees_brutes_pollen["erreur"])
        elif "features" in donnees_brutes_pollen and len(donnees_brutes_pollen["features"]) == 0:
            st.info("🌿 Aucun relevé pollinique n'a été publié pour cette zone à cette date.")
        else:
            donnees_pollen = extraire_donnees_pollen(donnees_brutes_pollen)

            if donnees_pollen:
                # Gestion de l'alerte rouge
                if donnees_pollen['alerte']:
                    st.error(f"⚠️ ALERTE POLLEN EN COURS : Forte présence de {donnees_pollen['responsable']} !")
                else:
                    st.success(f"Données du {donnees_pollen['date']} pour {donnees_pollen['ville']}")

                # Affichage du score global
                st.metric(label="Risque Pollinique Global", value=donnees_pollen['risque_global'], delta=f"Niveau {donnees_pollen['risque_note']}/5", delta_color="inverse")

                # Affichage détaillé par espèce
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Aulne", f"Niveau {donnees_pollen['aulne']}")
                col2.metric("Bouleau", f"Niveau {donnees_pollen['bouleau']}")
                col3.metric("Graminées", f"Niveau {donnees_pollen['graminees']}")
                col4.metric("Ambroisie", f"Niveau {donnees_pollen['ambroisie']}")

    st.divider()

    # --- SECTION POLLUTION (Atmo France) ---
    st.subheader(f"🇫🇷 Qualité de l'air — Atmo France ({ville_actuelle})")

    with st.spinner("Récupération des données officielles..."):
        donnees_json_atmo = recuperer_donnees_atmo(code_insee)

        if "erreur" in donnees_json_atmo:
            st.error(donnees_json_atmo["erreur"])
        else:
            donnees_atmo = extraire_donnees_atmo(donnees_json_atmo)

            if donnees_atmo:
                st.success(f"Données du {donnees_atmo['date']} pour {donnees_atmo['ville']}")

                # Carte HTML avec la couleur officielle dynamique
                st.markdown(
                    f"""
                    <div style="text-align: center; padding: 20px; border-radius: 10px; background-color: #1e1e1e; border: 2px solid {donnees_atmo['couleur']}; box-shadow: 0px 4px 6px rgba(0,0,0,0.3);">
                        <h2 style="color: {donnees_atmo['couleur']}; margin: 0; font-size: 2.5em;">{donnees_atmo['qualite_texte']}</h2>
                        <p style="color: #dddddd; margin: 5px 0 0 0; font-size: 1.2em;">Indice ATMO Global : {donnees_atmo['qualite_note']} / 6</p>
                    </div>
                    <br>
                    """,
                    unsafe_allow_html=True
                )

                # Détail par polluant
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Particules PM10", f"Note: {donnees_atmo['pm10_note']}")
                col2.metric("Particules PM2.5", f"Note: {donnees_atmo['pm25_note']}")
                col3.metric("Dioxyde d'Azote", f"Note: {donnees_atmo['no2_note']}")
                col4.metric("Ozone (O3)", f"Note: {donnees_atmo['o3_note']}")
            else:
                st.info(f"📡 Aucune donnée de qualité de l'air n'est disponible pour {ville_actuelle} (code INSEE : {code_insee}). La couverture Atmo peut varier selon les zones.")

    st.divider()

    # --- SECTION CONSEILS SANTÉ ---
    st.subheader("💡 Conseils Santé du Jour")
    # On récupère les notes de risque depuis les données Atmo déjà chargées
    risque_pollen = donnees_pollen.get('risque_note', 0) if donnees_pollen else 0
    risque_pollution = donnees_atmo.get('qualite_note', 0) if donnees_atmo else 0
    liste_conseils = generer_conseils(risque_pollen, risque_pollution)
    for conseil in liste_conseils:
        st.info(conseil)

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
            st.cache_data.clear()
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
            ws_profil.clear()
            ws_profil.append_row(["ville", "allergies"])
            ws_profil.append_row([ville, ", ".join(allergies)])
            st.cache_data.clear()
            st.success("Ton profil a été mis à jour dans le Cloud !")
            st.info("💡 Pense à rafraîchir la page pour mettre à jour les alertes de ta ville.")

    st.divider()
    
    st.subheader("📊 Évolution de mes symptômes")
    records_journal = charger_journal(ws_journal)
    
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
                    df_filtre = df[df['Date'].dt.strftime('%Y-%m-%d') != date_choisie]
                    df_filtre['Date'] = df_filtre['Date'].dt.strftime('%Y-%m-%d')
                    
                    ws_journal.clear()
                    en_tetes = df_filtre.columns.values.tolist()
                    valeurs = df_filtre.values.tolist()
                    ws_journal.update([en_tetes] + valeurs)
                    
                    st.cache_data.clear()
                    st.success(f"L'entrée du {date_choisie} a été supprimée avec succès !")
                    st.rerun() 
    else:
        st.info("👋 Aucune donnée pour le moment. Remplis ton journal pour voir ton historique !")