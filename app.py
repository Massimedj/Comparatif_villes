import io
import json
import pandas as pd
import streamlit as st
import google.generativeai as genai

from openpyxl.styles import Font, PatternFill
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

# Configuration de la page web
st.set_page_config(page_title="Comparateur Immobilier & Scolaire", page_icon="🏡", layout="centered")

st.title("🏡 Comparateur Immobilier & Scolaire")
st.write("Analysez et comparez des villes, leurs quartiers et leurs écoles.")

# Vérification préalable de la clé API
if "GEMINI_API_KEY" not in st.secrets:
    st.error("⚠️ La clé API `GEMINI_API_KEY` est manquante dans les secrets Streamlit.")
    st.stop()

api_key = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=api_key)
# Modèle mis à jour : gemini-3.6-flash
model = genai.GenerativeModel('gemini-3.6-flash')


# --- FONCTIONS D'EXPORT ---

def generer_excel_simple(df, sheet_name="Données"):
    """Exporte un DataFrame vers Excel sans transposition (lignes = entités)."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        feuille = writer.sheets[sheet_name]

        # Mise en forme de l'en-tête
        for cellule in feuille[1]:
            cellule.font = Font(bold=True, color="FFFFFF")
            cellule.fill = PatternFill(start_color="FF4B4B", end_color="FF4B4B", fill_type="solid")

        # Ajustement des largeurs de colonnes
        for colonne in feuille.columns:
            longueur_max = max((len(str(c.value)) for c in colonne if c.value is not None), default=10)
            lettre_colonne = colonne[0].column_letter
            feuille.column_dimensions[lettre_colonne].width = min(longueur_max + 2, 50)

        feuille.freeze_panes = "A2"
    return buffer.getvalue()


def generer_pdf_simple(df, title="Tableau"):
    """Exporte un DataFrame vers PDF sans transposition."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1 * cm, rightMargin=1 * cm,
        topMargin=1 * cm, bottomMargin=1 * cm
    )

    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle("cell", parent=styles["Normal"], fontSize=7, leading=9)
    header_style = ParagraphStyle(
        "header", parent=styles["Normal"], fontSize=8, leading=10,
        textColor=colors.white, fontName="Helvetica-Bold"
    )

    elements = [
        Paragraph(title, styles["Title"]),
        Spacer(1, 0.5 * cm)
    ]

    # Construction du tableau avec retour à la ligne automatique dans les cellules
    data = [[Paragraph(str(col), header_style) for col in df.columns]]
    for _, ligne in df.iterrows():
        row = [Paragraph(str(v), cell_style) for v in ligne]
        data.append(row)

    nb_colonnes = len(df.columns)
    largeur_disponible = landscape(A4)[0] - 2 * cm
    largeur_colonne = largeur_disponible / max(nb_colonnes, 1)
    col_widths = [largeur_colonne] * nb_colonnes

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FF4B4B")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
    ]))

    elements.append(table)
    doc.build(elements)
    return buffer.getvalue()


# --- CRÉATION DES TROIS ONGLETS ---
tab1, tab2, tab3 = st.tabs([
    "🏙️ Comparaison de villes",
    "🏘️ Comparaison des quartiers",
    "🎓 Comparaison des écoles"
])

# ============================================================
# ONGLET 1 : COMPARAISON DE VILLES
# ============================================================
with tab1:
    st.header("Comparaison de villes")
    villes_input = st.text_input(
        "Villes à comparer (séparées par des virgules) :",
        key="villes_input"
    )

    if st.button("Lancer la comparaison", key="btn_villes"):
        if not villes_input.strip():
            st.warning("⚠️ Veuillez entrer au moins une ville.")
        else:
            try:
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
- les quartiers (caractéristiques, catégorie sociale, sécurité, écoles de rattachement, transports) ;
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
- "Prix maison (€/m²)" : prix moyen/médian estimé des maisons en euros et ajouter "€" à la fin. Ex : "3200€"
- "Prix appartement (€/m²)" : prix moyen/médian estimé des appartements en euros et ajouter "€" à la fin. Ex : "4100€"
- "Temps vers Paris" : temps de trajet réaliste vers Paris intra-muros en minutes et ajouter "min" à la fin, en priorité en transport en commun. Ex : "35 min"

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
- "Quartiers principaux" : liste des noms des quartiers les plus importants ou connus de la ville, séparés par des virgules. Ex : "Centre-ville, Notre-Dame, Porchefontaine"
- "Quartiers" : liste d'objets JSON représentant **tous les quartiers** de la ville (ou la quasi-totalité si la ville est très étendue). Chaque objet doit contenir exactement les clés "Nom", "Caractéristiques", "Catégorie sociale", "Sécurité", "Écoles", "Transports". Toutes les valeurs sont des chaînes de caractères. Si un aspect est inconnu, écris "Non disponible".
- "Meilleurs quartiers résidentiels" : Les deux quartiers résidentiels (maisons individuelles) les plus recherchés et prisés.
- "Taxe foncière" : niveau et ordre de grandeur pour un bien type avec exemple de superficie; précise si la variabilité selon le bien est forte.
- "Projets urbains" : projets crédibles, annoncés ou engagés, impactant transports, logements, commerces, équipements ou prix.

## FORMAT DE SORTIE — CONTRAINTE ABSOLUE

Retourne EXCLUSIVEMENT un JSON valide, sans aucun texte avant ou après, sans balises markdown (pas de ```json), sans commentaire.

La sortie doit être une liste JSON d'objets. Chaque objet doit contenir EXACTEMENT les clés suivantes, dans cet ordre, avec des valeurs qui sont TOUTES des chaînes de caractères, SAUF pour la clé "Quartiers" qui doit être une liste d'objets comme défini ci-dessus :

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
    "Quartiers principaux": "",
    "Quartiers": [],
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
    "Quartiers principaux": "Centre-ville, Notre-Dame, Porchefontaine, Montreuil, Satory",
    "Quartiers": [
      {{"Nom": "Centre-ville", "Caractéristiques": "Appartements anciens", "Catégorie sociale": "Aisée", "Sécurité": "Élevée", "Écoles": "Lycée Hoche, Collège Rameau", "Transports": "Gare Rive Droite, bus"}},
      {{"Nom": "Notre-Dame", "Caractéristiques": "Maisons bourgeoises", "Catégorie sociale": "Familles CSP+", "Sécurité": "Élevée", "Écoles": "École privée Saint-Jean", "Transports": "Gare Rive Gauche"}},
      {{"Nom": "Porchefontaine", "Caractéristiques": "Résidentiel, verdoyant", "Catégorie sociale": "Classes moyennes supérieures", "Sécurité": "Bonne", "Écoles": "Groupe scolaire public", "Transports": "Bus, accès A13"}},
      {{"Nom": "Montreuil", "Caractéristiques": "Quartier résidentiel, maisons avec jardins", "Catégorie sociale": "Familles aisées", "Sécurité": "Très bonne", "Écoles": "École privée, collège", "Transports": "Bus, gare à proximité"}},
      {{"Nom": "Satory", "Caractéristiques": "Zone pavillonnaire", "Catégorie sociale": "Mixte", "Sécurité": "Bonne", "Écoles": "École publique", "Transports": "Bus, voiture nécessaire"}}
    ],
    "Meilleurs quartiers résidentiels": "Notre-Dame, Montreuil",
    "Taxe foncière": "Environ 1400€/an pour un bien moyen, variable selon le quartier",
    "Projets urbains": "Rénovation de quartiers résidentiels, développement des mobilités douces",
    "Potentiel patrimonial": "Bon (marché stable et recherché, rareté du foncier)"
  }}
]

## CONTRAINTES JSON

- Retourne uniquement du JSON, aucun texte hors JSON, aucun bloc ```json, aucun commentaire.
- Aucune clé supplémentaire, aucune clé manquante.
- Respecte exactement l'orthographe et les accents des clés.
- Toutes les valeurs sont des chaînes de caractères, sauf "Quartiers" qui est une liste d'objets avec des valeurs chaînes.
- Échappe correctement les guillemets et caractères spéciaux nécessaires au JSON.
- Le nombre d'objets doit être exactement égal au nombre de villes fournies dans {villes_input}.
- Respecte exactement l'ordre des villes fourni dans {villes_input}.
- N'ajoute aucun classement ou score global qui ne figure pas dans les clés demandées.

## STYLE

Les réponses doivent être synthétiques, factuelles, comparables d'une ville à l'autre, orientées décision immobilière, suffisamment précises pour être utiles à un acheteur ou investisseur, et dépourvues de formulations marketing.

## CONTRÔLE DE COHÉRENCE (à effectuer silencieusement avant de répondre)

1. Toutes les villes de {villes_input} sont présentes, dans le même ordre, sans ajout ni omission.
2. Chaque objet possède exactement les 25 clés demandées, dans le même ordre, sans clé en trop ni manquante.
3. Toutes les valeurs sont des chaînes de caractères, sauf "Quartiers" qui doit être une liste d'objets.
4. Les champs numériques (Population, Prix maison, Prix appartement, Temps vers Paris) ne contiennent que des chiffres, sans unité ni séparateur.
5. Les champs de pourcentage sont au format "XX%" et les paires (Part maisons/Part appartements, Propriétaires/Locataires) somment à 100% sauf "Non disponible".
6. Les champs notés respectent le format "X/10 (justification)" ou l'échelle qualitative prévue pour le Potentiel patrimonial.
7. Aucune donnée n'a été inventée avec une fausse précision : "Non disponible" est utilisé quand la confiance est insuffisante.
8. Les villes homonymes ont été désambiguïsées avec le département.
9. Le JSON produit est syntaxiquement valide et ne contient aucun texte, balise ou commentaire en dehors du tableau JSON.

Génère maintenant la réponse pour les villes suivantes : {villes_input}
                """

                with st.spinner("Gemini analyse le marché immobilier en cours..."):
                    reponse = model.generate_content(
                        prompt,
                        generation_config={"response_mime_type": "application/json"}
                    )
                    try:
                        donnees = json.loads(reponse.text)
                    except json.JSONDecodeError:
                        st.error("❌ Erreur dans le format retourné par l'IA. Veuillez relancer la comparaison.")
                        st.stop()

                    st.session_state["df_villes"] = pd.DataFrame(donnees)

            except Exception as e:
                st.error(f"Une erreur s'est produite lors de la génération. Détails techniques : {e}")

    # Affichage et export pour l'onglet Villes
    if "df_villes" in st.session_state:
        df = st.session_state["df_villes"]
        st.success("Analyse terminée !")
        st.subheader("📊 Résultat de l'analyse :")

        if "Ville" in df.columns and "Quartiers principaux" in df.columns and "Quartiers" in df.columns:
            df_affichage = df.drop(columns=["Quartiers"])
            df_transpose = df_affichage.set_index("Ville").T
            st.table(df_transpose)

            st.subheader("🔍 Détail des quartiers (tableau comparatif)")
            for _, row in df.iterrows():
                ville = row["Ville"]
                quartiers_data = row.get("Quartiers", None)
                if isinstance(quartiers_data, list):
                    df_quartiers = pd.DataFrame(quartiers_data)
                    with st.expander(f"Quartiers - {ville}"):
                        if not df_quartiers.empty:
                            st.dataframe(df_quartiers, use_container_width=True)
                        else:
                            st.write("Aucun détail de quartier disponible.")
                else:
                    with st.expander(f"Quartiers - {ville}"):
                        st.write(quartiers_data if quartiers_data else "Non disponible")
        else:
            st.dataframe(df)

        st.subheader("💾 Exporter les résultats")
        format_export = st.radio("Choisissez le format d'export :", ["Excel", "PDF"], horizontal=True, key="export_villes")
        df_export = df.drop(columns=["Quartiers"]) if "Quartiers" in df.columns else df

        if format_export == "Excel":
            st.download_button(
                label="📥 Télécharger en Excel",
                data=generer_excel(df_export),
                file_name="comparaison_villes.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.download_button(
                label="📥 Télécharger en PDF",
                data=generer_pdf(df_export),
                file_name="comparaison_villes.pdf",
                mime="application/pdf"
            )


# ============================================================
# ONGLET 2 : COMPARAISON DES QUARTIERS D'UNE VILLE
# ============================================================
with tab2:
    st.header("Comparaison des quartiers d'une ville")
    ville_quartiers = st.text_input("Nom de la ville :", key="ville_quartiers")

    if st.button("Analyser les quartiers", key="btn_quartiers"):
        if not ville_quartiers.strip():
            st.warning("⚠️ Veuillez entrer un nom de ville.")
        else:
            try:
                prompt_quartiers = f"""
Tu es un expert en analyse urbaine et immobilière. Pour la ville suivante : {ville_quartiers}, tu dois lister **tous les quartiers** (ou zones cohérentes) avec leurs caractéristiques détaillées.

Retourne EXCLUSIVEMENT un JSON valide, sans aucun texte avant ou après, sans balises markdown, sans commentaire.

La sortie doit être une liste JSON d'objets, chaque objet représentant un quartier. Chaque objet doit contenir EXACTEMENT les clés suivantes, dans cet ordre, avec des valeurs qui sont TOUTES des chaînes de caractères :

[
  {{
    "Nom": "",
    "Caractéristiques": "",
    "Catégorie sociale": "",
    "Sécurité": "",
    "Écoles": "",
    "Transports": ""
  }}
]

Définitions :
- "Nom" : nom du quartier.
- "Caractéristiques" : type d'habitat, ambiance, commodités principales.
- "Catégorie sociale" : catégorie socio-professionnelle dominante.
- "Sécurité" : niveau de sécurité ressenti (ex : Très bonne, Bonne, Correcte, Faible, etc.).
- "Écoles" : écoles de rattachement (noms ou types, séparés par des virgules).
- "Transports" : modes de transport disponibles et accessibilité.

Si une information est inconnue, écris "Non disponible". Assure-toi de couvrir tous les quartiers importants de la ville, y compris les quartiers périphériques.

Exemple de format attendu (ne pas utiliser ces valeurs) :
[
  {{"Nom": "Centre-ville", "Caractéristiques": "Appartements anciens, commerces", "Catégorie sociale": "Mixte", "Sécurité": "Bonne", "Écoles": "Lycée X, Collège Y", "Transports": "Bus, gare"}},
  {{"Nom": "Quartier Nord", "Caractéristiques": "Pavillonnaire, calme", "Catégorie sociale": "Familles", "Sécurité": "Très bonne", "Écoles": "École primaire Z", "Transports": "Bus"}}
]
                """

                with st.spinner("Analyse des quartiers en cours..."):
                    reponse = model.generate_content(
                        prompt_quartiers,
                        generation_config={"response_mime_type": "application/json"}
                    )
                    try:
                        quartiers = json.loads(reponse.text)
                    except json.JSONDecodeError:
                        st.error("❌ Erreur dans le format retourné par l'IA.")
                        st.stop()

                    df_quartiers = pd.DataFrame(quartiers)
                    if not df_quartiers.empty:
                        # Réorganiser les colonnes si nécessaire
                        colonnes = ["Nom", "Caractéristiques", "Catégorie sociale", "Sécurité", "Écoles", "Transports"]
                        colonnes_presentes = [c for c in colonnes if c in df_quartiers.columns]
                        df_quartiers = df_quartiers[colonnes_presentes]
                        st.success(f"✅ {len(df_quartiers)} quartiers trouvés pour {ville_quartiers}.")
                        st.dataframe(df_quartiers, use_container_width=True)

                        # Export des quartiers
                        st.subheader("💾 Exporter les quartiers")
                        format_export_q = st.radio("Format :", ["Excel", "PDF"], horizontal=True, key="export_quartiers")
                        if format_export_q == "Excel":
                            st.download_button(
                                label="📥 Télécharger en Excel",
                                data=generer_excel_simple(df_quartiers, sheet_name="Quartiers"),
                                file_name=f"quartiers_{ville_quartiers}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        else:
                            st.download_button(
                                label="📥 Télécharger en PDF",
                                data=generer_pdf_simple(df_quartiers, title=f"Quartiers de {ville_quartiers}"),
                                file_name=f"quartiers_{ville_quartiers}.pdf",
                                mime="application/pdf"
                            )
                    else:
                        st.warning("Aucun quartier trouvé.")

            except Exception as e:
                st.error(f"Une erreur s'est produite lors de la génération. Détails techniques : {e}")


# ============================================================
# ONGLET 3 : COMPARAISON DES ÉCOLES D'UNE VILLE
# ============================================================
with tab3:
    st.header("Comparaison des écoles d'une ville")
    ville_ecoles = st.text_input("Nom de la ville :", key="ville_ecoles")

    if st.button("Analyser les écoles", key="btn_ecoles"):
        if not ville_ecoles.strip():
            st.warning("⚠️ Veuillez entrer un nom de ville.")
        else:
            try:
                prompt_ecoles = f"""
Tu es un expert en éducation et en analyse territoriale. Pour la ville suivante : {ville_ecoles}, tu dois lister les **établissements scolaires** (écoles maternelles, élémentaires, collèges, lycées) publics et privés sous contrat, avec les indicateurs suivants.

Retourne EXCLUSIVEMENT un JSON valide, sans aucun texte avant ou après, sans balises markdown, sans commentaire.

La sortie doit être une liste JSON d'objets, chaque objet représentant une école. Chaque objet doit contenir EXACTEMENT les clés suivantes, dans cet ordre, avec des valeurs qui sont TOUTES des chaînes de caractères :

[
  {{
    "Nom de l'école": "",
    "Type": "",
    "IPS": "",
    "Qualité de l'enseignement": "",
    "Taux d'absence des professeurs": "",
    "Qualité de l'infrastructure": "",
    "Quartiers rattachés": ""
  }}
]

Définitions :
- "Nom de l'école" : nom officiel de l'établissement.
- "Type" : école maternelle, élémentaire, collège, lycée, etc.
- "IPS" : Indice de Position Sociale (nombre, par exemple "110") ou "Non disponible".
- "Qualité de l'enseignement" : appréciation qualitative (ex : "Excellente", "Bonne", "Moyenne", "Faible") ou note /10.
- "Taux d'absence des professeurs" : pourcentage ou appréciation (ex : "2%", "Faible", "Élevé").
- "Qualité de l'infrastructure" : état des bâtiments, équipements (ex : "Moderne", "Vieillissant", "Bonne").
- "Quartiers rattachés" : liste des quartiers de la ville qui dépendent de cette école (séparés par des virgules).

Si une information est inconnue, écris "Non disponible". Assure-toi de couvrir un échantillon représentatif des écoles de la ville.

Exemple de format attendu (ne pas utiliser ces valeurs) :
[
  {{"Nom de l'école": "École Jean Jaurès", "Type": "Élémentaire", "IPS": "105", "Qualité de l'enseignement": "Bonne", "Taux d'absence des professeurs": "3%", "Qualité de l'infrastructure": "Correcte", "Quartiers rattachés": "Centre-ville, Quartier Nord"}},
  {{"Nom de l'école": "Collège Victor Hugo", "Type": "Collège", "IPS": "120", "Qualité de l'enseignement": "Très bonne", "Taux d'absence des professeurs": "1,5%", "Qualité de l'infrastructure": "Bonne", "Quartiers rattachés": "Centre-ville"}}
]
                """

                with st.spinner("Analyse des écoles en cours..."):
                    reponse = model.generate_content(
                        prompt_ecoles,
                        generation_config={"response_mime_type": "application/json"}
                    )
                    try:
                        ecoles = json.loads(reponse.text)
                    except json.JSONDecodeError:
                        st.error("❌ Erreur dans le format retourné par l'IA.")
                        st.stop()

                    df_ecoles = pd.DataFrame(ecoles)
                    if not df_ecoles.empty:
                        st.success(f"✅ {len(df_ecoles)} écoles trouvées pour {ville_ecoles}.")
                        st.dataframe(df_ecoles, use_container_width=True)

                        # Export des écoles
                        st.subheader("💾 Exporter les écoles")
                        format_export_e = st.radio("Format :", ["Excel", "PDF"], horizontal=True, key="export_ecoles")
                        if format_export_e == "Excel":
                            st.download_button(
                                label="📥 Télécharger en Excel",
                                data=generer_excel_simple(df_ecoles, sheet_name="Ecoles"),
                                file_name=f"ecoles_{ville_ecoles}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        else:
                            st.download_button(
                                label="📥 Télécharger en PDF",
                                data=generer_pdf_simple(df_ecoles, title=f"Écoles de {ville_ecoles}"),
                                file_name=f"ecoles_{ville_ecoles}.pdf",
                                mime="application/pdf"
                            )
                    else:
                        st.warning("Aucune école trouvée.")

            except Exception as e:
                st.error(f"Une erreur s'est produite lors de la génération. Détails techniques : {e}")
