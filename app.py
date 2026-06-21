import streamlit as st
import google.generativeai as genai
import pandas as pd
import json

# Configuration de la page web
st.set_page_config(page_title="Comparateur de Villes Immo", page_icon="🏡", layout="centered")

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
            model = genai.GenerativeModel('gemini-3.1-flash-lite')

            # Le "Prompt" caché
            prompt = f"""
            Tu es un expert en immobilier en France
            Fais une analyse comparative des villes suivantes : {villes_input}.
            Fournis les données sous un format JSON STRICT (une liste d'objets).
            Chaque objet doit représenter une ville et contenir EXACTEMENT les clés suivantes sous forme de texte synthétique :
            "Ville", "Population", "Prix maison (€/m²)", "Prix appartement (€/m²)", ​"Évolution des prix (Tendance)" 
            "Part maisons", "Part appartements", "Propriétaires", "Locataires",
            "Profil socio-économique", "Sécurité", "Qualité des écoles", "Infrastructures sportives", "Nature",
            "Commerces", "Transport vers Paris", "Temps vers Paris", 
            "Activités culturelles", "Ambiance", "Cadre de vie et Quotidien", ​"Taxe foncière", ​"Projets urbains", "Potentiel patrimonial".
            """

            with st.spinner("Gemini analyse le marché immobilier en cours... Cela peut prendre quelques secondes."):
                
                # Génération avec le format JSON forcé pour éviter les erreurs
                reponse = model.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"}
                )
                
                donnees = json.loads(reponse.text)
                df = pd.DataFrame(donnees)
                
                st.success("Analyse terminée !")
                st.markdown("---")
                
                # --- AFFICHAGE OPTIMISÉ POUR SMARTPHONE (Onglets) ---
                st.subheader("📱 Fiches détaillées par ville")
                
                # Récupère le nom des villes pour créer les onglets
                noms_villes = [ville["Ville"] for ville in donnees]
                onglets = st.tabs(noms_villes)
                
                # Remplit chaque onglet avec les données correspondantes
                for i, onglet in enumerate(onglets):
                    with onglet:
                        ville_data = donnees[i]
                        for critere, valeur in ville_data.items():
                            if critere != "Ville": 
                                st.markdown(f"**{critere}** : {valeur}")
                
                st.markdown("---")
                
                # --- AFFICHAGE POUR ORDINATEUR (Tableau global) ---
                with st.expander("📊 Voir le tableau comparatif global (Idéal sur ordinateur)"):
                    # On inverse les lignes et les colonnes pour avoir les villes en haut
                    df_transpose = df.set_index("Ville").T
                    
                    # Remplacement de st.dataframe par st.table pour forcer les sauts de ligne
                    st.table(df_transpose)

        except Exception as e:
            st.error(f"Une erreur s'est produite lors de la génération. Détails techniques : {e}")
