import json
import pandas as pd
import streamlit as st
import google.generativeai as genai

# Configuration de la page web
st.set_page_config(page_title="Comparateur de Villes Immo", page_icon="🏡", layout="centered")

st.title("🏡 Comparateur de Villes pour Achat Immobilier")
st.write("Entrez les villes que vous souhaitez comparer, et l'IA Gemini analysera le marché pour vous.")

# Vérification préalable des secrets
if "GEMINI_API_KEY" not in st.secrets:
    st.error("⚠️ La clé API `GEMINI_API_KEY` est manquante dans les secrets Streamlit.")
    st.stop()

api_key = st.secrets["GEMINI_API_KEY"]

# Champ d'entrée des villes
villes_input = st.text_input(
    "Villes à comparer (séparées par des virgules) :", 
    "",
    placeholder="ex: Versailles, Saint-Germain-en-Laye, Rueil-Malmaison"
)

# Bouton de lancement
if st.button("Lancer la comparaison"):
    if not villes_input.strip():
        st.warning("⚠️ Veuillez entrer au moins une ville.")
    else:
        try:
            # Connexion à Gemini
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash')

            # Prompt d'analyse
            prompt = f"""
Tu es un expert senior de l'immobilier résidentiel en France, spécialisé dans l'analyse des marchés locaux, de l'attractivité territoriale, du cadre de vie et du potentiel patrimonial.

Ta mission est de réaliser une analyse comparative rigoureuse, factuelle et homogène des villes suivantes :
{villes_input}

## OBJECTIF
Pour chaque ville, évalue simultanément :
- le marché immobilier ;
- la structure du parc de logements ;
- le profil des habitants ;
- la sécurité ;
- les écoles ;
- les infrastructures et services ;
- les transports et l'accessibilité à Paris (ou métropole régionale) ;
- le cadre de vie ;
- les projets urbains ;
- le potentiel patrimonial à moyen/long terme.

## RÈGLES DE DONNÉES
1. Tu disposes d'un accès Internet en temps réel : récupères les données les plus récentes.
2. Utilise en priorité le type de données que produiraient des sources institutionnelles (INSEE, DVF, collectivités locales, observatoires).
3. Ne mélange pas des données provenant de périodes très différentes.
4. Pour les prix immobiliers, donne des valeurs représentatives et plausibles du marché local.
5. Si une donnée n'est pas connue avec un niveau de confiance suffisant, indique "Non disponible".
6. Ne présente jamais une estimation comme une donnée certaine.
7. Les données doivent être comparables entre toutes les villes.
8. Pour les critères qualitatifs, adopte une analyse équilibrée sans formulation marketing.
9. Analyse la ville elle-même et son environnement immédiat.
10. Si la situation varie fortement selon les quartiers, mentionne-le brièvement.

## GESTION DES CAS PARTICULIERS
- Si un nom de ville existe dans plusieurs communes, retiens la plus peuplée et précise le département (ex : "Saint-Denis (93)").
- Si une ville est mal orthographiée, corrige-la silencieusement.
- N'omets aucune ville et respecte l'ordre fourni dans {villes_input}.

## DÉFINITIONS DES INDICATEURS ET FORMAT ATTENDU
Champs numériques — chaîne de caractères sans unité ni séparateur :
- "Population" : ex "42000"
- "Prix maison (€/m²)" : ex "3200"
- "Prix appartement (€/m²)" : ex "4100"
- "Temps vers Paris" : temps vers Paris centre (ou métropole régionale) en minutes. Ex : "35"

Champs de pourcentage — format "XX%" :
- "Part maisons" / "Part appartements"
- "Propriétaires" / "Locataires"

Champs notés — format "X/5 (justification courte)" :
- "Sécurité", "Qualité des écoles", "Infrastructures sportives", "Nature", "Commerces", "Activités culturelles".
- "Potentiel patrimonial" : commence par une valeur parmi ["Faible", "Modéré", "Bon", "Très bon", "Exceptionnel"] suivie d'une courte justification.

Champs texte libre (1 à 3 phrases) :
- "Évolution des prix (Tendance)", "Profil socio-économique", "Transport vers Paris", "Ambiance", "Cadre de vie et Quotidien", "Taxe foncière", "Projets urbains".

## FORMAT DE SORTIE — CONTRAINTE ABSOLUE
Retourne EXCLUSIVEMENT un JSON valide, sans aucun texte avant ou après, sans balises markdown.

[
  {{
    "Ville": "",
    "Population": "",
    "Prix maison (€/m²)": "",
    "Prix appartement (€/m²)": "",
    "Évolution des prix (Tendance)": "",
    "Part maisons": "",
    "Part appartements": "",
    "Propriétaires": "",
    "Locataires": "",
    "Profil socio-économique": "",
    "Sécurité": "",
    "Qualité des écoles": "",
    "Infrastructures sportives": "",
    "Nature": "",
    "Commerces": "",
    "Transport vers Paris": "",
    "Temps vers Paris": "",
    "Activités culturelles": "",
    "Ambiance": "",
    "Cadre de vie et Quotidien": "",
    "Taxe foncière": "",
    "Projets urbains": "",
    "Potentiel patrimonial": ""
  }}
]
"""

            with st.spinner("Gemini analyse le marché immobilier... Cela peut prendre quelques secondes."):
                reponse = model.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"}
                )

                # Parsing JSON sécurisé
                try:
                    donnees = json.loads(reponse.text)
                except json.JSONDecodeError:
                    st.error("❌ L'IA a renvoyé un format invalide. Veuillez relancer la recherche.")
                    st.stop()

                df = pd.DataFrame(donnees)

                st.success("Analyse terminée !")
                st.markdown("---")

                # Affichage Onglets (Mobile)
                st.subheader("📱 Fiches détaillées par ville")
                noms_villes = [v.get("Ville", f"Ville {i+1}") for i, v in enumerate(donnees)]
                onglets = st.tabs(noms_villes)

                for i, onglet in enumerate(onglets):
                    with onglet:
                        ville_data = donnees[i]
                        for critere, valeur in ville_data.items():
                            if critere != "Ville":
                                st.markdown(f"**{critere}** : {valeur}")

                st.markdown("---")

                # Affichage Tableau Transposé (Desktop)
                with st.expander("📊 Voir le tableau comparatif"):
                    if "Ville" in df.columns:
                        df_transpose = df.set_index("Ville").T
                        st.table(df_transpose)
                    else:
                        st.dataframe(df)

        except Exception as e:
            st.error(f"Une erreur s'est produite lors de la génération : {e}")
