import streamlit as st
import google.generativeai as genai
import pandas as pd
import json

# Configuration de la page web
st.set_page_config(page_title="Comparateur de Villes Immo", page_icon="🏡", layout="wide")

st.title("🏡 Comparateur de Villes pour Achat Immobilier")
st.write("Entrez les villes que vous souhaitez comparer, et l'IA Gemini analysera le marché pour vous.")

# Récupération de la clé API cachée (dans les secrets de Streamlit)
api_key = st.secrets["GEMINI_API_KEY"]

# Champ pour entrer les villes (laissé vide par défaut)
villes_input = st.text_input(
    "Villes à comparer (séparées par des virgules) :", 
    ""
)

# Bouton de lancement
if st.button("Lancer la comparaison"):
    if not villes_input:
        st.warning("⚠️ Veuillez entrer au moins une ville.")
    else:
        try:
            # Connexion à Gemini
            genai.configure(api_key=api_key)
            
            # Utilisation du modèle 1.5-flash (le plus récent et rapide à ce jour)
            model = genai.GenerativeModel('gemini-1.5-flash')

            # Le "Prompt" caché
            prompt = f"""
            Tu es un expert en immobilier en région parisienne.
            Fais une analyse comparative des villes suivantes : {villes_input}.
            Fournis les données sous un format JSON STRICT (une liste d'objets).
            Chaque objet doit représenter une ville et contenir EXACTEMENT les clés suivantes sous forme de texte synthétique :
            "Ville", "Population", "Prix maison (€/m²)", "Prix appartement (€/m²)",
            "Part maisons", "Part appartements", "Propriétaires", "Locataires",
            "Profil socio-économique", "Sécurité", "Écoles", "Infrastructures sportives", "Nature",
            "Commerces", "Transport vers Paris", "Temps vers Paris", 
            "Aspect culturel", "Ambiance", "Potentiel patrimonial".
            """

            # Affichage d'une animation de chargement
            with st.spinner("Gemini analyse le marché immobilier en cours... Cela peut prendre quelques secondes."):
                
                # L'astuce est ici : on force la configuration "application/json" pour garantir un JSON sans erreur
                reponse = model.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"}
                )
                
                # Le nettoyage du texte n'est plus nécessaire grâce à l'option ci-dessus
                donnees = json.loads(reponse.text)
                df = pd.DataFrame(donnees)
                
                # On inverse les lignes et les colonnes pour avoir les villes en haut et les critères à gauche
                df_transpose = df.set_index("Ville").T
                
                st.success("Analyse terminée !")
                
                # Affichage du tableau sur l'application web
                st.dataframe(df_transpose, use_container_width=True)

        except Exception as e:
            st.error(f"Une erreur s'est produite lors de la génération. Détails techniques : {e}")
