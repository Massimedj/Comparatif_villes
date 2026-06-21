import streamlit as st
import google.generativeai as genai
import pandas as pd
import json

# Configuration de la page web
st.set_page_config(page_title="Comparateur de Villes Immo", page_icon="🏡", layout="wide")

st.title("🏡 Comparateur de Villes pour Achat Immobilier")
st.write("Entrez les villes que vous souhaitez comparer, et l'IA Gemini analysera le marché pour vous.")

# Demander la clé API à l'utilisateur
api_key = st.text_input("Votre clé API Google Gemini (obligatoire)", type="password")

# Champ pour entrer les villes
villes_input = st.text_input(
    "Villes à comparer (séparées par des virgules) :", 
    
)

# Bouton de lancement
if st.button("Lancer la comparaison"):

    elif not villes_input:
        st.warning("⚠️ Veuillez entrer au moins une ville.")
    else:
        try:
            # Connexion à Gemini
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-3.5-flash')

            # Le "Prompt" caché que l'application envoie à Gemini
            prompt = f"""
            Tu es un expert en immobilier en région parisienne.
            Fais une analyse comparative des villes suivantes : {villes_input}.
            Fournis les données sous un format JSON STRICT (une liste d'objets).
            Chaque objet doit représenter une ville et contenir EXACTEMENT les clés suivantes sous forme de texte synthétique :
            "Ville", "Population", "Prix maison (€/m²)", "Prix appartement (€/m²)",
            "Part maisons", "Part appartements", "Propriétaires", "Locataires",
            "Profil socio-économique", "Sécurité", "Écoles", "Nature",
            "Commerces", "Transport vers Paris", "Temps vers Kléber (Paris)",
            "Ambiance", "Potentiel patrimonial".

            Ne renvoie QUE le JSON brut, sans introduction, sans conclusion, et sans balises de code Markdown (```json).
            """

            # Affichage d'une animation de chargement
            with st.spinner("Gemini analyse le marché immobilier en cours... Cela peut prendre quelques secondes."):
                reponse = model.generate_content(prompt)
                
                # Nettoyage de la réponse pour s'assurer que c'est du JSON valide
                texte_json = reponse.text.replace('```json', '').replace('```', '').strip()
                
                # Transformation du texte JSON en tableau de données (DataFrame)
                donnees = json.loads(texte_json)
                df = pd.DataFrame(donnees)
                
                # On inverse les lignes et les colonnes pour avoir les villes en haut et les critères à gauche
                df_transpose = df.set_index("Ville").T
                
                st.success("Analyse terminée !")
                
                # Affichage du tableau sur l'application web
                st.dataframe(df_transpose, use_container_width=True)

        except Exception as e:
            st.error(f"Une erreur s'est produite lors de la génération. Détails techniques : {e}")
