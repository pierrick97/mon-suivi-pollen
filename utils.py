# utils.py
import pandas as pd

def calculer_indice_pollen(valeur_brute):
    """Échelle de 0 à 5 pour le pollen"""
    if pd.isna(valeur_brute) or valeur_brute <= 0: return 0
    elif valeur_brute < 10: return 1  
    elif valeur_brute < 50: return 2  
    elif valeur_brute < 100: return 3 
    elif valeur_brute < 500: return 4 
    else: return 5                    

def calculer_indice_polluant(polluant, valeur_brute):
    """
    Convertit la concentration brute (µg/m³) en un indice de 1 à 5
    Basé sur les directives de l'Agence Européenne pour l'Environnement.
    """
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
    """Évaluation de l'AQI Européen global"""
    if pd.isna(aqi): return "Inconnu", 0
    elif aqi <= 20: return "Bon (1/5)", aqi
    elif aqi <= 40: return "Moyen (2/5)", aqi
    elif aqi <= 60: return "Dégradé (3/5)", aqi
    elif aqi <= 80: return "Mauvais (4/5)", aqi
    else: return "Très Mauvais (5/5)", aqi