import streamlit as st
import google.generativeai as genai
import pandas as pd
import json

# Configuration de la page web (layout="centered" est souvent plus élégant sur mobile)
st.set_page_config(page_title="Comparateur de Villes Immo", page_icon="🏡", layout="centered")

st.title("🏡 Comparateur de Villes pour Achat Immobilier")
st.write("Entrez les villes que vous souhaitez comparer, et l'IA Gemini analysera le marché pour vous.")

# Récupération de la clé API cachée (dans les secrets de Streamlit)
api_key = st.secrets["GEMINI_API_KEY"]

# Champ pour entrer les villes (laissé vide par défaut, comme demandé)
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
            model = genai.GenerativeModel('gemini-3.5-flash')

            # Le "Prompt" caché
            prompt = f"""
            Tu es un expert en immobilier en France.
            Fais une analyse comparative des villes suivantes : {villes_input}.
            Fournis les données sous un format JSON STRICT (une liste d'objets).
            Chaque objet doit représenter une ville et contenir EXACTEMENT les clés suivantes sous forme de texte synthétique :
            "Ville", "Population", "Prix maison (€/m²)", "Prix appartement (€/m²)",
            "Part maisons", "Part appartements", "Propriétaires", "Locataires",
            "Profil socio-économique", "Sécurité", "Écoles", "Infrastructures sportives", "Nature",
            "Commerces", "Transport vers Paris", "Temps vers Paris", 
            "Aspect culturel", "Ambiance", "Potentiel patrimonial".
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
                            if critere != "Ville": # On n'affiche pas la clé "Ville" puisqu'elle est déjà dans le titre de l'onglet
                                st.markdown(f"**{critere}** : {valeur}")
                
                st.markdown("---")
                
                # --- AFFICHAGE POUR ORDINATEUR (Tableau global) ---
                with st.expander("📊 Voir le tableau comparatif global (Idéal sur ordinateur)"):
                    # On inverse les lignes et les colonnes pour avoir les villes en haut
                    df_transpose = df.set_index("Ville").T
                    st.dataframe(df_transpose, use_container_width=True)

        except Exception as e:
            st.error(f"Une erreur s'est produite lors de la génération. Détails techniques : {e}")
