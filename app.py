import json
import pandas as pd
import streamlit as st
import google.generativeai as genai

# Configuration de la page web
st.set_page_config(page_title="Comparateur de Villes Immo", page_icon="🏡", layout="centered")

st.title("🏡 Comparateur de Villes pour Achat Immobilier")
st.write("Entrez les villes que vous souhaitez comparer, et l'IA Gemini analysera le marché pour vous.")

# Vérification préalable de la clé API
if "GEMINI_API_KEY" not in st.secrets:
    st.error("⚠️ La clé API `GEMINI_API_KEY` est manquante dans les secrets Streamlit.")
    st.stop()

api_key = st.secrets["GEMINI_API_KEY"]

# Champ pour entrer les villes
villes_input = st.text_input(
    "Villes à comparer (séparées par des virgules) :", 
    ""
)

# Bouton de lancement
if st.button("Lancer la comparaison"):
    if not villes_input.strip():
        st.warning("⚠️ Veuillez entrer au moins une ville.")
    else:
        try:
            # Connexion à Gemini
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-3.6-flash')

            # Le "Prompt" caché (Intégral)
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
- les transports et l'accessibilité à Paris ;
- le cadre de vie ;
- les quartiers résidentiels les plus recherchés ;
- les projets urbains ;
- le potentiel patrimonial à moyen/long terme.

L'objectif est de permettre à un particulier ou un investisseur de comparer objectivement les villes et d'identifier leurs forces, leurs faiblesses et leur potentiel immobilier.

## RÈGLES DE DONNÉES

1. Tu disposes d'un accès Internet en temps réel : récupères les données les plus récentes
2. Utilise en priorité le type de données que produiraient des sources institutionnelles ou reconnues (INSEE, DVF, données gouvernementales, collectivités locales, observatoires immobiliers) comme référentiel de qualité, même si tu ne les consultes pas directement.
3. Ne mélange pas des données provenant de périodes très différentes ; reste sur une méthodologie et une période de référence cohérentes pour toutes les villes.
4. Pour les prix immobiliers, donne des valeurs représentatives et plausibles du marché local ; évite tout chiffre manifestement aberrant ou une précision illusoire (arrondis raisonnables).
5. Si une donnée n'est pas connue avec un niveau de confiance suffisant, indique "Non disponible" plutôt que d'inventer une valeur. N'utilise "Non disponible" que pour des données réellement incertaines, pas par excès de prudence sur des villes connues.
6. Ne présente jamais une estimation comme une donnée certaine.
7. Les données doivent être comparables entre toutes les villes : même méthodologie, mêmes unités, même niveau de granularité.
8. Pour les critères qualitatifs, adopte une analyse équilibrée : ni excessivement positive, ni excessivement négative, sans formulation marketing.
9. Analyse la ville elle-même et son environnement immédiat, pas seulement des généralités sur son département ou sa région.
10. Si la situation varie fortement selon les quartiers, mentionne brièvement cette hétérogénéité dans la synthèse concernée.

## GESTION DES CAS PARTICULIERS

- Si un nom de ville existe dans plusieurs communes de France (ex : Saint-Denis), retiens la commune la plus probable compte tenu du contexte (la plus peuplée par défaut) et précise le département entre parenthèses dans le champ "Ville" (ex : "Saint-Denis (93)").
- Si une ville est mal orthographiée mais reconnaissable, corrige-la silencieusement. Si elle est réellement introuvable, indique "Non disponible" pour tous les champs sauf "Ville", qui reprend l'entrée telle quelle.
- N'omets jamais une ville de la liste d'entrée et n'en ajoute aucune non demandée.
- Respecte l'ordre des villes tel que fourni dans {villes_input}.

## DÉFINITIONS DES INDICATEURS ET FORMAT ATTENDU PAR CHAMP

Champs numériques — chaîne de caractères ne contenant QUE des chiffres, sans unité, sans espace, sans séparateur de milliers (l'unité est déjà portée par le nom de la clé) :
- "Population" : population municipale la plus récente connue. Ex : "42000"
- "Prix maison (€/m²)" : prix moyen/médian estimé des maisons. Ex : "3200€"
- "Prix appartement (€/m²)" : prix moyen/médian estimé des appartements. Ex : "4100€"
- "Temps vers Paris" : temps de trajet réaliste vers Paris intra-muros en minutes, en priorité en transport en commun. Ex : "35 min"

Champs de pourcentage — chaîne au format "XX%" :
- "Part maisons" / "Part appartements" : doivent sommer à 100% (sauf "Non disponible")
- "Propriétaires" / "Locataires" : doivent sommer à 100% (sauf "Non disponible")

Champs notés — chaîne au format "X/10 (justification factuelle courte, 5 à 8 mots)" :
- "Sécurité" : niveau de sécurité et principales caractéristiques locales, sans affirmation sensationnaliste.
- "Qualité des écoles" : offre scolaire, réputation, établissements notables, présence de privé.
- "Infrastructures sportives" : quantité, diversité, accessibilité des équipements.
- "Nature" : accès aux parcs, forêts, cours d'eau, littoral, sentiers.
- "Commerces" : diversité et accessibilité des commerces et services du quotidien.
- "Activités culturelles" : cinémas, théâtres, musées, patrimoine, événements.
- "Potentiel patrimonial" : remplace la note par une appréciation parmi "Faible", "Modéré", "Bon", "Très bon", "Exceptionnel" suivie d'une justification courte tenant compte de l'attractivité économique, la démographie, l'accessibilité, les projets urbains, la rareté du foncier, la demande locative et résidentielle, et le niveau actuel des prix. Ex : "Bon (demande locative forte, rareté du foncier)"

Champs texte libre — 1 à 3 phrases courtes, factuelles, sans marketing (ou "Non disponible") :
- "Évolution des prix (Tendance)" : choisis une valeur parmi ["Forte hausse", "Hausse modérée", "Stable", "Baisse modérée", "Forte baisse", "Évolution contrastée"], avec un ordre de grandeur si pertinent (ex : "Hausse modérée (+2 à 4%/an)").
- "Profil socio-économique" : revenus, CSP dominantes, familles/étudiants/retraités, niveau de vie.
- "Transport vers Paris" : modes disponibles (train, RER, Transilien, métro, tram, bus, voiture, autoroute).
- "Ambiance" : atmosphère générale (familiale, résidentielle, bourgeoise, populaire, étudiante, dynamique, calme, villageoise, urbaine), avec contrastes de quartiers si pertinent.
- "Cadre de vie et Quotidien" : calme, densité, circulation, stationnement, praticité pour une famille ou un actif.
- "Meilleurs quartiers résidentiels" : Les deux suartiers résidentiels (maisons individuelles) les plus recherchés et prisés qui ont les meilleures notes de tous les points ci-dessus.
- "Taxe foncière" : niveau et ordre de grandeur pour un bien type avec exemple de superficie; précise si la variabilité selon le bien est forte.
- "Projets urbains" : projets crédibles, annoncés ou engagés, impactant transports, logements, commerces, équipements ou prix.

## FORMAT DE SORTIE — CONTRAINTE ABSOLUE

Retourne EXCLUSIVEMENT un JSON valide, sans aucun texte avant ou après, sans balises markdown (pas de ```json), sans commentaire.

La sortie doit être une liste JSON d'objets. Chaque objet doit contenir EXACTEMENT les clés suivantes, dans cet ordre, avec des valeurs qui sont TOUTES des chaînes de caractères :

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
    "Temps vers Paris (min)": "",
    "Activités culturelles": "",
    "Ambiance": "",
    "Cadre de vie et Quotidien": "",
    "Meilleurs quartiers résidentiels": "",
    "Taxe foncière": "",
    "Projets urbains": "",
    "Potentiel patrimonial": ""
  }}
]

## EXEMPLE ILLUSTRATIF (style et format attendus uniquement — ne pas réutiliser ces valeurs comme référence)

[
  {{
    "Ville": "Versailles (78)",
    "Population": "85000",
    "Prix maison (€/m²)": "7800€",
    "Prix appartement (€/m²)": "6900€",
    "Évolution des prix (Tendance)": "Stable",
    "Part maisons": "35%",
    "Part appartements": "65%",
    "Propriétaires": "58%",
    "Locataires": "42%",
    "Profil socio-économique": "CSP+ aisée, nombreuses familles avec enfants",
    "Sécurité": "8/10 (faible délinquance, ville résidentielle)",
    "Qualité des écoles": "5/10 (établissements réputés, options internationales)",
    "Infrastructures sportives": "4/10 (nombreux clubs et équipements)",
    "Nature": "4/10 (parcs, forêt à proximité)",
    "Commerces": "4/10 (centre-ville dynamique, marchés)",
    "Transport vers Paris": "RER C, train, autoroute A13",
    "Temps vers Paris": "35 min",
    "Activités culturelles": "4/10 (château, musées, festivals)",
    "Ambiance": "Chic, calme, patrimoniale",
    "Cadre de vie et Quotidien": "Ville verte et sécurisée, forte vie associative",
    "Meilleurs quartiers résidentiels": "Notre-Dame, Porchefontaine", 
    "Taxe foncière": "Environ 1400€/an pour un bien moyen, variable selon le quartier",
    "Projets urbains": "Rénovation de quartiers résidentiels, développement des mobilités douces",
    "Potentiel patrimonial": "Bon (marché stable et recherché, rareté du foncier)"
  }}
]

## CONTRAINTES JSON

- Retourne uniquement du JSON, aucun texte hors JSON, aucun bloc ```json, aucun commentaire.
- Aucune clé supplémentaire, aucune clé manquante.
- Respecte exactement l'orthographe et les accents des clés.
- Toutes les valeurs sont des chaînes de caractères, y compris les nombres.
- Échappe correctement les guillemets et caractères spéciaux nécessaires au JSON.
- Le nombre d'objets doit être exactement égal au nombre de villes fournies dans {villes_input}.
- Respecte exactement l'ordre des villes fourni dans {villes_input}.
- N'ajoute aucun classement ou score global qui ne figure pas dans les clés demandées.

## STYLE

Les réponses doivent être synthétiques, factuelles, comparables d'une ville à l'autre, orientées décision immobilière, suffisamment précises pour être utiles à un acheteur ou investisseur, et dépourvues de formulations marketing.

## CONTRÔLE DE COHÉRENCE (à effectuer silencieusement avant de répondre)

1. Toutes les villes de {villes_input} sont présentes, dans le même ordre, sans ajout ni omission.
2. Chaque objet possède exactement les 23 clés demandées, dans le même ordre, sans clé en trop ni manquante.
3. Toutes les valeurs sont des chaînes de caractères.
4. Les champs numériques (Population, Prix maison, Prix appartement, Temps vers Paris) ne contiennent que des chiffres, sans unité ni séparateur.
5. Les champs de pourcentage sont au format "XX%" et les paires (Part maisons/Part appartements, Propriétaires/Locataires) somment à 100% sauf "Non disponible".
6. Les champs notés respectent le format "X/10 (justification)" ou l'échelle qualitative prévue pour le Potentiel patrimonial.
7. Aucune donnée n'a été inventée avec une fausse précision : "Non disponible" est utilisé quand la confiance est insuffisante.
8. Les villes homonymes ont été désambiguïsées avec le département.
9. Le JSON produit est syntaxiquement valide et ne contient aucun texte, balise ou commentaire en dehors du tableau JSON.

Génère maintenant la réponse pour les villes suivantes : {villes_input}
            """

            with st.spinner("Gemini analyse le marché immobilier en cours... Cela peut prendre quelques secondes."):
                reponse = model.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"}
                )
                
                # Parsing sécurisé du JSON
                try:
                    donnees = json.loads(reponse.text)
                except json.JSONDecodeError:
                    st.error("❌ Erreur dans le format retourné par l'IA. Veuillez relancer la comparaison.")
                    st.stop()

                df = pd.DataFrame(donnees)
                
                st.success("Analyse terminée !")
                st.markdown("---")
                
                # --- AFFICHAGE OPTIMISÉ POUR SMARTPHONE (Onglets) ---
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
                
                # --- AFFICHAGE POUR ORDINATEUR (Tableau global) ---
                with st.expander("📊 Voir le tableau comparatif"):
                    if "Ville" in df.columns:
                        df_transpose = df.set_index("Ville").T
                        st.table(df_transpose)
                    else:
                        st.dataframe(df)

        except Exception as e:
            st.error(f"Une erreur s'est produite lors de la génération. Détails techniques : {e}")
