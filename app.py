import io
import json
import pandas as pd
import streamlit as st
import google.generativeai as genai
import difflib

from openpyxl.styles import Font, PatternFill
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

# Configuration de la page web
st.set_page_config(page_title="Comparateur Pour Achat Immobilier", page_icon="🏡", layout="wide")

st.title("🏡 Comparateur Pour Achat Immobilier")
st.write("Analysez et comparez des villes, leurs quartiers et leurs écoles.")

# Vérification préalable de la clé API
if "GEMINI_API_KEY" not in st.secrets:
    st.error("⚠️ La clé API `GEMINI_API_KEY` est manquante dans les secrets Streamlit.")
    st.stop()

api_key = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-3.6-flash')


# --- FONCTIONS D'EXPORT ---

def generer_excel_simple(df, sheet_name="Données"):
    """Exporte un DataFrame vers Excel sans transposition."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        feuille = writer.sheets[sheet_name]

        for cellule in feuille[1]:
            cellule.font = Font(bold=True, color="FFFFFF")
            cellule.fill = PatternFill(start_color="FF4B4B", end_color="FF4B4B", fill_type="solid")

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


def wrap_text(text, max_chars=50):
    """Insère des retours à la ligne dans une chaîne pour améliorer l'affichage."""
    if not isinstance(text, str):
        return text
    if "\n" in text:
        return text
    words = text.split(", ")
    result = []
    current_line = ""
    for word in words:
        if len(current_line) + len(word) + 2 > max_chars:
            result.append(current_line)
            current_line = word
        else:
            if current_line:
                current_line += ", " + word
            else:
                current_line = word
    if current_line:
        result.append(current_line)
    return "\n".join(result)


def normalize_columns(df, expected_columns):
    """
    Renomme les colonnes du DataFrame pour correspondre aux noms attendus,
    en utilisant une correspondance approximative si nécessaire.
    """
    actual_columns = list(df.columns)
    if len(actual_columns) == len(expected_columns):
        df.columns = expected_columns
    else:
        new_columns = []
        for col in actual_columns:
            best_match = difflib.get_close_matches(col, expected_columns, n=1, cutoff=0.6)
            if best_match:
                new_columns.append(best_match[0])
            else:
                new_columns.append(col)
        df.columns = new_columns
    return df


def extract_json_from_response(response):
    """
    Extrait le texte JSON d'une réponse Gemini en ignorant les appels de fonction.
    """
    texte_json = ""
    if response.parts:
        for part in response.parts:
            if hasattr(part, 'text') and part.text:
                texte_json += part.text
    if not texte_json.strip():
        # fallback
        texte_json = response.text
    return texte_json


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
Tu es un expert senior de l'immobilier résidentiel en France, spécialisé dans l'analyse des marchés locaux, de l'attractivité territoriale, du cadre de vie, des quartiers et du potentiel patrimonial.

Ta mission est de réaliser une analyse comparative rigoureuse, factuelle, actualisée et homogène des communes suivantes :

{villes_input}

# 1. OBJECTIF

Pour chaque commune, évalue simultanément :
- le marché immobilier et l'évolution des prix ;
- la structure du parc de logements et le statut d'occupation ;
- le profil démographique et socio-économique des habitants ;
- la sécurité ;
- l'offre scolaire et son accessibilité ;
- les infrastructures sportives ;
- la nature, les espaces verts et les cheminements ;
- les commerces et services du quotidien ;
- les transports et l'accessibilité à Paris ;
- les activités culturelles ;
- l'ambiance et le cadre de vie quotidien ;
- **l'ensemble des quartiers et secteurs locaux identifiés dans la commune**, sans se limiter à une sélection de quartiers principaux ;
- les secteurs résidentiels particulièrement recherchés pour les maisons individuelles ;
- la taxe foncière ;
- les projets urbains documentés ;
- le potentiel patrimonial à moyen/long terme.

L'objectif est de permettre à un particulier ou à un investisseur de comparer objectivement les communes, leurs forces, leurs faiblesses, leurs différences internes et leur potentiel immobilier.

# 2. PRINCIPES NON NÉGOCIABLES

1. **Exactitude avant apparence de complétude :** n'invente jamais une donnée, un quartier, une école de rattachement, une statistique locale ou une source pour remplir une cellule.
2. **Exhaustivité des quartiers :** le champ `Quartiers` doit recenser tous les quartiers et secteurs locaux reconnus ou nommés de façon fiable dans la commune. Ne renvoie jamais uniquement les quartiers les plus connus ou les plus importants.
3. **Comparabilité :** utilise autant que possible la même source, la même période, la même définition, la même unité et la même granularité pour toutes les communes.
4. **Traçabilité interne :** toute donnée chiffrée importante ou appréciation fondée sur une source doit pouvoir être retrouvée et vérifiée pendant la recherche. Les références détaillées restent dans ton processus de travail et ne sont pas affichées dans le JSON final.
5. **Transparence :** distingue les données officielles, les calculs effectués, les estimations et les appréciations qualitatives.
6. **Neutralité :** ne présente pas une commune ou un quartier de manière promotionnelle, caricaturale ou stigmatisante.
7. **Prudence :** une corrélation, une tendance passée ou un projet annoncé ne constitue pas une garantie de prix futurs.
8. **Pas de fausse précision :** arrondis raisonnablement et qualifie les estimations fragiles.
9. **Échelle géographique correcte :** n'attribue jamais à une commune une donnée provenant en réalité de son intercommunalité, de son département ou d'une aire urbaine, sans le préciser explicitement.
10. **Pas de classement global :** ne crée aucun score global ou classement des communes qui ne figure pas dans le schéma JSON.

# 3. ENTRÉE ET IDENTIFICATION DES COMMUNES

- La liste des communes à analyser est celle fournie dans `{villes_input}`.
- Conserve strictement le nombre, l'ordre et l'orthographe des entrées, sauf correction évidente d'une faute de frappe.
- N'ajoute aucune commune et n'en supprime aucune.
- Identifie chaque commune avec son code postal et/ou son département lorsque cela permet de lever une ambiguïté.
- **N'identifie pas automatiquement un nom homonyme comme étant la commune la plus peuplée.** Utilise le contexte déjà fourni et les informations géographiques explicites. Si plusieurs communes restent plausibles, ne choisis pas arbitrairement : conserve l'entrée dans le résultat et indique que l'identification est ambiguë dans `Ville`; remplis les autres champs avec `Non disponible` tant que l'identité n'est pas établie et utilise une liste vide `[]` pour `Quartiers`.
- Corrige silencieusement une faute d'orthographe évidente lorsque la commune visée ne fait aucun doute.
- Si une commune est réellement introuvable, conserve son entrée dans `Ville`, indique `Non disponible` pour les autres champs de type chaîne et utilise une liste vide `[]` pour `Quartiers`.
- Si l'utilisateur a donné une priorité (maison, écoles, transports, sécurité, rendement, etc.), fais-la ressortir dans les champs concernés sans modifier la structure ni l'ordre des clés.

# 4. MÉTHODE DE TRAVAIL OBLIGATOIRE EN SIX PHASES

Effectue les six phases avant de produire le JSON. Ne rédige pas le résultat à partir de connaissances générales seules lorsque des données actuelles peuvent être recherchées.

## Phase 1 — Identifier et cadrer

- Identifie précisément chaque commune et son département.
- Détermine la date de recherche et les millésimes les plus récents disponibles pour les données utilisées.
- Repère les différences de couverture géographique, de définition et de disponibilité entre les communes.
- Pour les transports vers Paris, applique le protocole commun de la section 10, sauf destination différente explicitement demandée.
- Prépare une liste de contrôle distincte des quartiers et secteurs à recenser pour chaque commune.

## Phase 2 — Collecter les données

Effectue des recherches Internet et privilégie les sources institutionnelles, les jeux de données originaux et les documents officiels plutôt que les articles qui les commentent.

Hiérarchie indicative des sources :

1. **Démographie, logements, revenus et structure sociale :** INSEE, notamment recensement de la population, dossiers complets et données locales.
2. **Prix et transactions :** DVF (Demandes de valeurs foncières), Etalab et données/indices des Notaires de France.
3. **Sécurité :** Service statistique ministériel de la sécurité intérieure (SSMSI), ministère de l'Intérieur et données publiques officielles.
4. **Écoles :** annuaires et jeux de données du ministère de l'Éducation nationale, académies, collectivités et cartes officielles de sectorisation.
5. **Équipements sportifs :** Recensement des équipements sportifs (RES), ministère chargé des Sports et collectivités.
6. **Nature et espaces verts :** collectivités, IGN, INPN, gestionnaires d'espaces naturels et organismes publics compétents.
7. **Commerces, équipements et culture :** Base permanente des équipements (BPE) de l'INSEE, données SIRENE en complément, collectivités et établissements culturels officiels.
8. **Transports :** Île-de-France Mobilités, SNCF, RATP, opérateurs régionaux ou locaux et calculateurs d'itinéraires reconnus.
9. **Taxe foncière :** DGFiP, collectivités et délibérations fiscales officielles.
10. **Projets urbains :** communes, intercommunalités, préfectures, aménageurs publics, opérateurs institutionnels et documents d'urbanisme.
11. **Noms et périmètres des quartiers :** sites officiels des communes et intercommunalités, cartes municipales, conseils ou comités de quartier, documents d'urbanisme, projets de rénovation urbaine et publications institutionnelles locales.

Les sites d'estimation immobilière (MeilleursAgents, SeLoger, etc.) peuvent servir de contrôle secondaire ou de repère complémentaire, mais ne remplacent pas les transactions officielles lorsqu'elles sont disponibles. Signale en interne toute divergence importante et évite de mélanger ces estimations avec des prix DVF dans une même série.

## Phase 3 — Harmoniser et contrôler

Pour chaque indicateur :
- vérifie que les données portent sur la bonne commune ;
- vérifie la définition, l'unité, la période, la couverture géographique et la date de publication ;
- utilise la même période de référence pour toutes les communes lorsque les sources le permettent ;
- ne mélange pas des millésimes différents sans le signaler dans la valeur concernée ;
- ne compare pas directement des indicateurs qui n'ont pas la même définition ou granularité ;
- si une donnée n'est disponible qu'à une échelle supérieure, indique explicitement cette échelle dans la valeur ;
- si les données sont trop rares, trop anciennes, contradictoires ou non comparables, indique `Non disponible` ou qualifie explicitement l'estimation comme fragile ;
- ne transforme pas une donnée départementale en donnée communale ou de quartier.

## Phase 4 — Calculer et analyser

- Effectue les calculs uniquement à partir de données identifiées et vérifiables.
- Distingue les constats mesurés des appréciations qualitatives.
- Applique les grilles de notation de la section 11. N'attribue aucune note intuitive.
- Ne déduis jamais une caractéristique d'un quartier à partir de sa réputation seule.
- N'extrapole pas au quartier une statistique disponible uniquement à l'échelle communale.

## Phase 5 — Rédiger les objets JSON

- Respecte exactement les 25 clés et leur ordre définis dans le schéma de sortie.
- Conserve l'ordre des communes fourni par l'utilisateur.
- Utilise des formulations courtes, factuelles et comparables.
- Le champ `Quartiers` est une liste exhaustive des quartiers et secteurs identifiés selon la méthode de la section 9.
- N'ajoute ni champ `Quartiers principaux`, ni champ `Sources et méthode`, ni aucun autre champ.

## Phase 6 — Contrôler silencieusement la réponse

Effectue tous les contrôles de la section 15 avant de répondre. Ne prétends pas avoir effectué une vérification ou un calcul qui n'a pas réellement été réalisé.

# 5. PÉRIODES, COMPARABILITÉ ET QUALITÉ DES DONNÉES

## 5.1 Règle générale

- Privilégie la dernière donnée officielle publiée.
- Affiche l'année ou la période de référence lorsqu'elle change l'interprétation du résultat.
- La date de consultation ne remplace jamais l'année de la donnée.
- Pour chaque famille d'indicateurs, utilise le millésime le plus récent disponible pour toutes les communes. Si un millésime commun n'existe pas, indique la différence dans la valeur concernée.

## 5.2 Prix immobiliers et transactions

- Utilise en priorité les transactions DVF, lorsque leur couverture géographique et leur disponibilité le permettent.
- Distingue strictement les maisons des appartements.
- Privilégie une période commune de **24 mois de transactions récentes entièrement disponibles**. Si cette fenêtre n'est pas suffisamment renseignée, étends-la jusqu'à 36 mois et indique-le.
- N'utilise pas arbitrairement des fenêtres différentes entre communes.
- Indique le nombre de transactions utilisé si la source permet de le déterminer.
- Un échantillon inférieur à **10 transactions comparables** pour un type de bien est insuffisant pour présenter une médiane comme robuste. Indique alors `Non disponible (échantillon insuffisant)` ou, seulement si cela apporte une information utile, une estimation explicitement qualifiée de fragile.
- Exclue des ventes atypiques uniquement si la méthode d'exclusion est explicite et reproductible. N'écarte pas des transactions parce qu'elles ne correspondent pas à la tendance attendue.
- Ne mélange pas prix affichés, estimations d'agences, prix notariaux et médianes DVF dans une même série.
- Les indices Notaires de France peuvent servir à analyser une évolution temporelle, mais précise leur périmètre et ne les présente pas comme un prix médian communal s'ils ne le sont pas.
- Signale les limites de couverture des données DVF.
- Les prix sont nominaux, sauf si une correction de l'inflation est explicitement calculée et expliquée.

## 5.3 Seuils internes de fiabilité

- **Fiabilité élevée :** donnée officielle directement disponible, définition claire, période connue et échantillon suffisant.
- **Fiabilité moyenne :** estimation calculée à partir de données officielles ou donnée indirecte cohérente dont les limites sont explicites.
- **Fiabilité faible :** données anciennes, échantillon trop réduit, sources contradictoires ou extrapolation importante. Préfère alors `Non disponible` à un chiffre trompeur.

Ces niveaux servent à contrôler la qualité de l'information. Ne les transforme pas en notes de qualité de ville.

# 6. DÉFINITIONS ET CALCUL DES DONNÉES DÉMOGRAPHIQUES ET DU LOGEMENT

## Population

- Utilise la **population municipale** de l'INSEE, et non la population totale ou celle de l'intercommunalité.
- Indique l'année de référence dans la valeur `Population`.
- Ne mélange pas population municipale, population légale totale et population de l'aire d'attraction.

## Part des maisons et des appartements

- Utilise une seule définition INSEE et un seul millésime pour toutes les communes.
- Exprime les parts en pourcentage de l'ensemble des logements et précise le dénominateur dans la valeur.
- **Ne force jamais la somme à 100 %.** Les maisons et les appartements ne représentent pas nécessairement tous les logements : d'autres catégories peuvent exister.

## Propriétaires et locataires

- Calcule les parts parmi les **résidences principales**, à partir d'une même définition et d'un même millésime INSEE.
- Distingue propriétaires, locataires et personnes logées gratuitement lorsque les données le permettent.
- Les parts propriétaires, locataires et logés gratuitement doivent être cohérentes et totaliser environ 100 %, sous réserve des arrondis.
- Dans `Locataires`, précise si possible la part du parc social, sans la confondre avec l'ensemble des locataires. La part des personnes logées gratuitement peut également être indiquée à titre distinct.
- **Ne force pas `Propriétaires` et `Locataires` à totaliser 100 %** si les personnes logées gratuitement constituent une catégorie séparée.
- Ne présente pas ces parts comme des pourcentages de l'ensemble des logements lorsqu'elles portent sur les seules résidences principales.

## Profil socio-économique

Appuie-toi notamment sur des indicateurs INSEE comparables : revenu disponible médian, taux de pauvreté, taux d'emploi ou de chômage, catégories socioprofessionnelles et composition des ménages.
- Donne les millésimes utiles.
- Ne résume pas la commune par une étiquette sociale réductrice.
- Ne déduis pas son profil d'une réputation ou d'une impression.

## Moyenne d'âge des résidents

- N'assimile pas âge moyen et âge médian.
- Si l'âge moyen n'est pas publié, tu peux le calculer approximativement à partir des classes d'âge INSEE, en utilisant une moyenne pondérée des milieux de classes et en indiquant qu'il s'agit d'une estimation.
- Si les classes disponibles ne permettent pas un calcul raisonnable, indique `Non disponible`.
- Tu peux ajouter l'âge médian à titre complémentaire, mais identifie-le explicitement comme médian.

# 7. RÈGLES PAR INDICATEUR SENSIBLE

## Sécurité

- Privilégie les statistiques communales du SSMSI ou du ministère de l'Intérieur.
- Utilise des taux rapportés à la population lorsque la comparaison est pertinente, pas uniquement des nombres bruts.
- Distingue les catégories d'infractions, notamment atteintes aux biens et atteintes aux personnes, et précise les années étudiées.
- Lorsque c'est possible, observe plusieurs années pour limiter l'effet d'une variation ponctuelle ou d'un faible nombre de faits.
- Rappelle que les faits enregistrés dépendent aussi des dépôts de plainte, de l'activité des services et des flux de population.
- Ne transforme pas un taux global en affirmation absolue sur la sécurité vécue.
- Ne présente pas des données départementales comme des données communales.
- N'attribue pas de note si les données sont trop limitées ou non comparables.
- À l'échelle d'un quartier, n'invente pas un niveau de sécurité si aucune statistique locale fiable n'existe. Indique `Données de sécurité par quartier non disponibles`.

## Écoles

- Évalue l'offre et l'accessibilité : présence et diversité des écoles maternelles, élémentaires, collèges et lycées, secteurs de recrutement lorsqu'ils sont officiellement disponibles, temps d'accès et capacité lorsqu'elle est documentée.
- Les résultats aux examens ne sont utilisables que s'ils sont pertinents et comparables. Ne les présente pas comme une mesure complète de la qualité pédagogique.
- Ne déduis pas la qualité d'un établissement de sa réputation ou d'un classement commercial non vérifié.
- À l'échelle d'un quartier, ne donne le nom d'une école de rattachement que si la carte ou la sectorisation officielle confirme cette affectation. Sinon, cite éventuellement des établissements proches en précisant que le rattachement n'est pas confirmé.
- La note évalue l'offre et l'accessibilité scolaires, pas la qualité individuelle des enseignants ou des élèves.

## Infrastructures sportives

- Utilise en priorité le Recensement des équipements sportifs et les données des collectivités.
- Prends en compte le nombre et la diversité des équipements, leur accessibilité et, lorsque possible, leur disponibilité pour le public.
- Rapporte les quantités à la population lorsque c'est pertinent.
- Ne confonds pas présence d'un équipement, qualité de l'équipement et accès effectif à une activité encadrée.

## Nature

- Évalue l'accès réel aux espaces verts, parcs, forêts, berges, espaces naturels et cheminements publics.
- Prends en compte leur proximité, leur accessibilité et leur diversité.
- Ne déduis pas une bonne accessibilité à la nature du seul pourcentage de surface boisée ou agricole de la commune.

## Commerces

- Évalue la diversité et la densité des commerces et services du quotidien, ainsi que leur accessibilité.
- Utilise la BPE de l'INSEE et les données locales, avec SIRENE en complément si utile.
- Vérifie la date des données et les ouvertures/fermetures récentes lorsque c'est possible.
- Distingue les commerces présents dans la commune de ceux accessibles dans une commune voisine.

## Activités culturelles

- Évalue la diversité et l'accessibilité des équipements et activités : médiathèques, cinémas, théâtres, salles de spectacle, conservatoires, musées et programmation locale.
- Distingue les équipements permanents des événements ponctuels.
- N'attribue pas une note élevée sur la seule base d'un festival ou d'un événement annuel.

## Taxe foncière

- Privilégie les taux officiels de la DGFiP et les délibérations des collectivités, en indiquant l'année.
- Distingue les taux communal et intercommunal lorsqu'ils sont disponibles, ainsi que les autres composantes pertinentes.
- Rappelle que le montant payé dépend notamment de la valeur locative cadastrale, des taux applicables et des exonérations ou dispositifs éventuels.
- Ne déduis pas un montant annuel standard d'un taux communal seul.
- Ne donne un exemple en euros que si le bien et sa base fiscale sont précisément documentés. Décris alors le type de bien, l'année et le périmètre fiscal.
- Si seul le taux est fiable, donne le taux et précise que le montant varie selon le bien ; n'invente pas de montant moyen.

## Projets urbains

Pour chaque projet mentionné, vérifie qu'il est officiellement documenté et précise son niveau d'avancement :
1. annoncé ou à l'étude ;
2. voté, autorisé ou financé ;
3. travaux engagés ;
4. livré ou en service.

Indique le calendrier annoncé et l'effet plausible sur les transports, le logement, les équipements ou l'attractivité. Distingue l'effet attendu de l'effet déjà constaté. Ne présente pas un projet simplement évoqué comme certain ou financé.

# 8. TRANSPORT VERS PARIS : PROTOCOLE COMMUN

- Si l'utilisateur indique une destination précise à Paris, utilise cette destination.
- Sinon, prends **Châtelet–Les Halles** comme destination de référence.
- Pour chaque commune, identifie la gare principale qui dessert son secteur résidentiel central. S'il n'existe pas de gare dans la commune, identifie la gare réellement utilisée la plus pertinente et indique son nom ainsi que le trajet d'accès nécessaire.
- Compare des trajets en transports collectifs dans des conditions similaires : jour ouvré, arrivée cible à Paris vers **8 h 30**, avec les horaires disponibles au moment de la recherche.
- Indique le temps **gare à gare**, les correspondances et les modes utilisés. Ne présente pas ce temps comme un temps porte-à-porte.
- Mentionne les fréquences ou contraintes particulières uniquement si elles sont vérifiées.
- Signale la marche, le bus d'approche ou le rabattement vers une gare extérieure à la commune.
- Si aucun horaire fiable ne peut être consulté, indique `Non disponible` plutôt que d'inventer une durée.
- Les temps réels varient selon le quartier de départ, l'heure, les perturbations et les correspondances.

# 9. QUARTIERS — EXHAUSTIVITÉ OBLIGATOIRE

Le champ `Quartiers` est particulièrement important. Il doit contenir **tous les quartiers et secteurs locaux identifiables de la commune**, et non une sélection des quartiers principaux.

## 9.1 Recherche exhaustive à effectuer

Pour chaque commune, mène une recherche spécifique et systématique :
1. Consulte le site officiel de la mairie et recherche ses pages, cartes, annuaires ou publications consacrés aux quartiers.
2. Recherche les conseils de quartier, comités de quartier, secteurs municipaux, quartiers administratifs, villages, hameaux et lieux-dits habités lorsqu'ils sont reconnus localement.
3. Consulte les documents d'urbanisme, plans locaux d'urbanisme, projets d'aménagement, opérations de rénovation urbaine et documents institutionnels cartographiant les secteurs.
4. Consulte l'intercommunalité et les autres organismes publics locaux lorsque leurs documents complètent la nomenclature municipale.
5. Effectue des recherches complémentaires avec des formulations telles que `quartiers de [commune]`, `carte des quartiers [commune]`, `conseils de quartier [commune]`, `secteurs [commune]`, `hameaux [commune]` et `plan [commune] quartiers`.
6. Croise les listes et cartes obtenues pour repérer les quartiers omis, les sous-quartiers ayant un nom propre, les variantes de nom et les doublons.
7. Vérifie que chaque secteur retenu se situe bien à l'intérieur de la commune. Ne transforme pas un quartier d'une commune voisine en quartier de la commune analysée.
8. Réalise un dernier contrôle de couverture : chaque quartier officiellement nommé dans les sources locales consultées doit apparaître dans la liste finale, sauf doublon évident ou appellation obsolète clairement remplacée.

## 9.2 Définition opérationnelle d'un quartier

- Inclue tous les quartiers officiellement nommés ou reconnus par la commune ou l'intercommunalité.
- Ajoute les secteurs résidentiels, villages, hameaux ou sous-quartiers qui disposent d'une appellation locale stable et sont reconnus par plusieurs sources fiables, même s'ils ne constituent pas des quartiers administratifs.
- Préserve les appellations locales usuelles et les noms officiels lorsqu'ils diffèrent.
- Les IRIS de l'INSEE peuvent servir de contrôle géographique ou statistique, mais **ne sont pas automatiquement des quartiers**. Ne les présente pas comme tels sans preuve de reconnaissance locale.
- Ne crée jamais de sous-quartiers uniquement pour augmenter le nombre d'entrées.
- Déduplique les variantes manifestes d'un même quartier, sans fusionner deux secteurs réellement distincts.
- Ne limite pas artificiellement le nombre d'entrées à 5, 10 ou 15 : la taille de la liste doit dépendre du nombre réel de quartiers et secteurs identifiés.

## 9.3 Contenu de chaque objet quartier

Chaque objet de `Quartiers` doit contenir exactement les six clés suivantes, dans cet ordre :
- `Nom` : nom du quartier ou secteur ;
- `Caractéristiques` : type de tissu urbain, habitat, densité, environnement, commerces ou éléments distinctifs vérifiés ;
- `Catégorie sociale` : profil socio-économique uniquement si des données locales fiables le permettent ;
- `Sécurité` : appréciation uniquement si des données fiables existent à cette échelle ;
- `Écoles` : écoles et établissements accessibles ; précise le rattachement officiel uniquement s'il est confirmé ;
- `Transports` : gare, lignes, bus, tram, métro, temps d'accès ou contraintes de mobilité vérifiés.

Règles supplémentaires :
- Toutes les valeurs sont des chaînes de caractères.
- Si une information n'est pas disponible à cette échelle, écris `Non disponible` ou une précision honnête telle que `Données de sécurité par quartier non disponibles`.
- Ne transpose pas les statistiques de la commune à un quartier.
- Ne déduis pas la catégorie sociale, la sécurité, la qualité des écoles ou la desserte d'une simple réputation.
- Distingue les équipements situés dans le quartier de ceux qui sont simplement à proximité.
- N'affirme pas qu'un établissement est l'école de rattachement sans carte scolaire ou source officielle.
- Ne regroupe pas plusieurs quartiers distincts dans un seul objet pour raccourcir la réponse.
- Si les sources consultées ne permettent pas de confirmer que l'inventaire est exhaustif, n'invente pas les quartiers manquants et signale explicitement cette limite dans `Cadre de vie et Quotidien`. La recherche doit néanmoins avoir été poursuivie jusqu'à vérification des principales sources municipales et institutionnelles disponibles.

# 10. TRANSPORTS ET TEMPS VERS PARIS

Dans `Transport vers Paris` : indique la gare de départ, les modes disponibles et les correspondances utiles. Mentionne les modes locaux pertinents (train, RER, Transilien, métro, tram, bus, voiture, autoroute) sans lister des modes qui ne desservent pas réellement la commune.

Dans `Temps vers Paris (min)` :
- indique un temps gare à gare, en minutes ;
- précise la gare de départ, la destination et le mode ;
- indique les correspondances si elles sont significatives ;
- ne donne pas un temps porte-à-porte sous cette clé ;
- n'invente pas un temps si les horaires n'ont pas été vérifiés.

# 11. MÉTHODOLOGIE DES NOTES SUR 10

Les critères notés sont : `Sécurité`, `Qualité des écoles`, `Infrastructures sportives`, `Nature`, `Commerces` et `Activités culturelles`.

## 11.1 Règles générales

- Une note doit être fondée sur des indicateurs observables, des sources identifiées et la grille propre au critère.
- Utilise la même méthode pour toutes les communes.
- Évalue chaque commune indépendamment sur une échelle de référence commune. Ne distribue pas les notes en fonction du seul classement des communes demandées.
- Ne donne pas automatiquement une note moyenne lorsqu'une donnée manque.
- Si les données sont insuffisantes, trop anciennes ou non comparables, écris `Non disponible (données insuffisantes)`.
- Les notes synthétisent des indicateurs et ne sont pas des mesures scientifiques absolues.
- La justification dans la valeur JSON doit comporter **5 à 8 mots**, hors note et éventuelle référence temporelle.

## 11.2 Échelle commune

- **1–2/10 :** offre très faible, difficulté importante ou indicateurs nettement défavorables.
- **3–4/10 :** offre limitée ou situation plutôt défavorable.
- **5–6/10 :** situation moyenne, offre correcte ou contrastée.
- **7–8/10 :** situation favorable, offre riche ou bonne accessibilité.
- **9–10/10 :** situation particulièrement favorable, offre très complète et largement accessible, étayée par plusieurs indicateurs.

## 11.3 Grilles spécifiques

**Sécurité**
- Compare les taux d'infractions disponibles par grandes catégories à des références territoriales pertinentes (département et/ou France), sur des périodes cohérentes.
- Prends en compte plusieurs années si possible et distingue les atteintes aux biens des atteintes aux personnes.
- Une situation nettement plus favorable et stable que les références peut soutenir une note élevée ; des taux nettement supérieurs et persistants peuvent soutenir une note basse.
- Ne calcule pas de note synthétique si les catégories disponibles ou les volumes ne permettent pas une comparaison raisonnable.

**Qualité des écoles — offre et accessibilité scolaires**
- Prends en compte la présence des niveaux scolaires, la diversité des établissements, les temps d'accès et la capacité lorsqu'elle est connue.
- Ajoute des indicateurs officiels de résultats uniquement lorsqu'ils sont pertinents et comparables.
- Une offre complète, accessible et documentée peut justifier une note élevée ; une offre rare ou nécessitant de longs déplacements peut justifier une note faible.

**Infrastructures sportives**
- Prends en compte le nombre d'équipements rapporté à la population, la diversité des disciplines, la répartition géographique et l'accès public connu.
- Une offre nombreuse, diversifiée et accessible peut justifier une note élevée.

**Nature**
- Prends en compte les espaces verts publics accessibles, les grands espaces naturels proches, les cheminements et la facilité d'accès depuis les secteurs habités.
- Une offre variée, proche et accessible peut justifier une note élevée.

**Commerces**
- Prends en compte la diversité des commerces du quotidien, leur densité, leur répartition et leur accessibilité à pied ou en transport.
- Une offre diversifiée et répartie dans les secteurs habités peut justifier une note élevée.

**Activités culturelles**
- Prends en compte la variété des équipements permanents, la programmation régulière, leur accessibilité et, si disponible, leur fréquentation.
- Une offre permanente, diversifiée et accessible peut justifier une note élevée.

Ne fais pas la moyenne mécanique de sous-indicateurs si leurs définitions ou leur importance ne sont pas comparables. Le fondement de chaque note doit être vérifiable en interne.

# 12. DÉFINITIONS ET FORMAT ATTENDU PAR CHAMP JSON

Toutes les valeurs sont des chaînes de caractères, sauf `Quartiers` qui est une liste d'objets. Les unités et les périodes peuvent être intégrées dans les chaînes afin de ne pas perdre le contexte des données.

## Champs démographiques et immobiliers

- `Ville` : nom officiel de la commune, suivi du département entre parenthèses si utile pour lever toute ambiguïté. Exemple : `Saint-Denis (93)`.
- `Population` : population municipale INSEE la plus récente disponible, sous forme de chiffres lisibles, avec l'année de référence. Exemple : `42 000 (population municipale INSEE, 2022)`.
- `Prix maison (€/m²)` : médiane des prix de vente des maisons lorsque l'échantillon est suffisant ; indique la valeur, la période DVF et le nombre de transactions si disponible. Exemple : `3 200 €/m² (médiane DVF, 2024-2025, 18 ventes)`. Si l'échantillon est insuffisant : `Non disponible (moins de 10 transactions comparables)`.
- `Prix appartement (€/m²)` : même méthode que pour les maisons, en distinguant strictement les appartements. Exemple : `4 100 €/m² (médiane DVF, 2024-2025, 32 ventes)`.
- `Évolution des prix (Tendance)` : commence exactement par l'une des expressions suivantes : `Forte hausse`, `Hausse modérée`, `Stable`, `Baisse modérée`, `Forte baisse`, `Évolution contrastée` ou `Non disponible`. Compare des périodes et types de biens comparables. Indique l'ordre de grandeur et la période si les données sont robustes.
- `Part maisons` : pourcentage des maisons parmi l'ensemble des logements, avec année de référence. Exemple : `32 % des logements (INSEE, 2022)`. Ne force pas la somme avec les appartements à 100 %.
- `Part appartements` : pourcentage des appartements parmi l'ensemble des logements, avec année de référence. Exemple : `66 % des logements (INSEE, 2022)`. D'autres types de logements peuvent expliquer que les deux parts ne totalisent pas 100 %.
- `Propriétaires` : part des propriétaires occupants parmi les résidences principales, avec année. Exemple : `58 % des résidences principales (INSEE, 2022)`.
- `Locataires` : part des locataires parmi les résidences principales, avec année ; ajoute si disponible la part du parc social et la part des personnes logées gratuitement en les distinguant. Exemple : `39 % des résidences principales, dont 12 % en logement social ; logés gratuitement : 3 % (INSEE, 2022)`.
- `Profil socio-économique` : 1 à 3 phrases courtes fondées sur les revenus, la pauvreté, l'emploi, les CSP et la composition des ménages. Indique les millésimes utiles. Évite les étiquettes simplificatrices.
- `Moyenne d'âge des résidents` : moyenne en années uniquement si publiée ou calculable de façon raisonnable. Indique si elle est estimée à partir des classes d'âge. Ne substitue pas silencieusement la médiane à la moyenne. Exemple : `41 ans (moyenne estimée à partir des classes INSEE, 2022)`.

## Champs notés

Format : `X/10 (justification factuelle de 5 à 8 mots)`. Les 5 à 8 mots correspondent à la justification, pas à la note.
- `Sécurité` : niveau de sécurité et principales caractéristiques locales, sans sensationnalisme ; respecte les limites des statistiques disponibles.
- `Qualité des écoles` : offre scolaire, diversité, accessibilité et résultats officiels pertinents ; ne te fonde pas sur la seule réputation.
- `Infrastructures sportives` : quantité, diversité et accessibilité des équipements.
- `Nature` : accès aux parcs, forêts, cours d'eau, espaces naturels et sentiers.
- `Commerces` : diversité et accessibilité des commerces et services du quotidien.
- `Activités culturelles` : équipements permanents, programmation et accessibilité.
- `Potentiel patrimonial` : utilise exclusivement l'une des appréciations `Faible`, `Modéré`, `Bon`, `Très bon`, `Exceptionnel`, suivie d'une justification concise. Prends en compte la demande résidentielle, l'économie et l'emploi, la démographie, l'accessibilité, les projets réellement engagés, la rareté foncière, le niveau et l'évolution des prix. Évalue un potentiel indicatif à 5–10 ans sans promettre une plus-value ni garantir un rendement.

## Champs descriptifs

- `Transport vers Paris` : gares de départ, modes effectivement disponibles et correspondances utiles ; précise si la gare est hors commune et si un rabattement est nécessaire.
- `Temps vers Paris (min)` : temps gare à gare vérifié, avec mode, gare de départ et destination. Exemple : `35 min (train, gare de X → Châtelet–Les Halles, 1 correspondance)`.
- `Ambiance` : atmosphère urbaine, densité, rythme et usages dominants lorsque les informations le permettent. Évite les stéréotypes sur les habitants. Mentionne les contrastes internes importants.
- `Cadre de vie et Quotidien` : 1 à 3 phrases concrètes sur la vie quotidienne : densité, circulation, stationnement, services, espaces publics, nuisances documentées et praticité. Si l'exhaustivité de l'inventaire des quartiers n'a pas pu être confirmée après recherches, mentionne explicitement cette limite ici.
- `Quartiers` : liste exhaustive selon les règles de la section 9 ; chaque élément doit être un objet ayant exactement les six clés et toutes les valeurs sous forme de chaînes.
- `Meilleurs quartiers résidentiels` : identifie, si les éléments le permettent, deux secteurs recherchés pour les maisons individuelles. Justifie brièvement par des éléments concrets : présence de maisons, environnement résidentiel, accès aux services, transports ou transactions observées. Ne présente pas cette sélection comme un classement officiel. Si les données ne permettent pas de l'étayer, indique `Non disponible`.
- `Taxe foncière` : indique les taux officiels et leur année, en distinguant les niveaux fiscaux lorsqu'ils sont disponibles. Donne un montant annuel uniquement si un exemple de bien et sa base fiscale sont documentés. Sinon, précise que le montant varie selon la valeur locative cadastrale et les caractéristiques du bien.
- `Projets urbains` : présente uniquement les projets officiellement documentés ; précise statut, calendrier connu et effet plausible ; distingue les projets annoncés, financés, en travaux et livrés.

# 13. FORMAT DE SORTIE — CONTRAINTE ABSOLUE

Retourne **EXCLUSIVEMENT un JSON valide**, sans texte avant ou après, sans balises Markdown, sans commentaire et sans bloc de code. N'utilise jamais d'appel de fonction.

La sortie doit être une liste JSON contenant exactement un objet par commune d'entrée. Chaque objet doit contenir exactement les 25 clés suivantes, dans cet ordre, avec des valeurs qui sont toutes des chaînes de caractères, sauf `Quartiers` qui doit être une liste d'objets :

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
    "Moyenne d'âge des résidents": "",
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
    "Quartiers": [
      {{
        "Nom": "",
        "Caractéristiques": "",
        "Catégorie sociale": "",
        "Sécurité": "",
        "Écoles": "",
        "Transports": ""
      }}
    ],
    "Meilleurs quartiers résidentiels": "",
    "Taxe foncière": "",
    "Projets urbains": "",
    "Potentiel patrimonial": ""
  }}
]

Aucun champ `Quartiers principaux` ne doit apparaître. Aucune section `Sources et méthode` ne doit être ajoutée au JSON.

# 14. RÈGLES JSON ET STYLE

- Retourne uniquement du JSON, aucun texte hors JSON, aucun bloc Markdown et aucun commentaire.
- Aucune clé supplémentaire, aucune clé manquante.
- Respecte exactement l'orthographe, les accents et l'ordre des clés.
- Toutes les valeurs sont des chaînes de caractères, sauf `Quartiers`, qui est une liste d'objets.
- Chaque objet de `Quartiers` contient exactement les clés `Nom`, `Caractéristiques`, `Catégorie sociale`, `Sécurité`, `Écoles`, `Transports`, dans cet ordre.
- Toutes les valeurs à l'intérieur des objets quartier sont des chaînes de caractères ; utilise `Non disponible` si nécessaire.
- Échappe correctement les guillemets, antislashs et caractères spéciaux nécessaires au JSON.
- Le nombre d'objets de premier niveau doit être exactement égal au nombre de communes fournies.
- Respecte exactement l'ordre des communes fourni.
- N'ajoute aucun classement ou score global.
- Le style doit être synthétique, factuel, comparable d'une commune à l'autre, orienté décision immobilière et dépourvu de formulations marketing.
- Ne raccourcis pas artificiellement la liste `Quartiers` pour économiser des tokens. L'exhaustivité des quartiers est une exigence prioritaire. Si la taille de la réponse devient importante, conserve tous les quartiers et reste concis dans les autres champs.

# 15. CONTRÔLE DE COHÉRENCE — À EFFECTUER SILENCIEUSEMENT

Avant de répondre, vérifie les points suivants :

## Structure et ordre
1. Toutes les communes de `{villes_input}` sont présentes, dans le même ordre, sans ajout ni omission.
2. Chaque objet de premier niveau possède exactement les 25 clés demandées, dans le même ordre.
3. La clé `Quartiers principaux` est absente.
4. Aucune section ni clé `Sources et méthode` n'est présente.
5. Toutes les valeurs sont des chaînes, sauf `Quartiers`, qui est une liste d'objets.
6. Chaque objet quartier possède exactement les six clés prévues, dans le bon ordre.
7. Le JSON est syntaxiquement valide et ne contient aucun texte hors JSON.

## Données et comparabilité
8. Chaque chiffre important possède une source réellement consultée et une année ou période de référence, même si les références détaillées ne sont pas montrées dans le résultat final.
9. Les données communales ne sont pas confondues avec celles de l'intercommunalité ou du département.
10. Les prix maison et appartement reposent sur des définitions, périodes et méthodes comparables.
11. Les volumes de transactions sont suffisants ou la fragilité de l'estimation est clairement signalée.
12. Les tendances de prix reposent sur des périodes comparables et des données réellement disponibles.
13. Les parts de logements et les statuts d'occupation utilisent les bons dénominateurs ; aucune somme à 100 % n'est imposée à tort.
14. La moyenne d'âge n'est pas confondue avec l'âge médian.
15. Les taux de sécurité, chiffres par quartier et évaluations scolaires ne sont pas extrapolés sans preuve.
16. La taxe foncière n'est pas convertie en montant annuel sans base fiscale suffisante.
17. Les projets urbains sont associés à un statut et un calendrier vérifiés.

## Exhaustivité des quartiers
18. Le champ `Quartiers` ne contient pas seulement les quartiers principaux ou les plus connus.
19. Les sources municipales, cartes, conseils de quartier, documents d'urbanisme et sources institutionnelles locales disponibles ont été recherchés.
20. Tous les quartiers et secteurs officiellement nommés identifiés dans les sources consultées sont présents.
21. Les secteurs reconnus localement (y compris villages, hameaux ou sous-quartiers nommés) sont inclus lorsqu'ils sont attestés par des sources fiables.
22. Aucun quartier d'une commune voisine n'est attribué à la commune analysée.
23. Les IRIS ne sont pas présentés automatiquement comme des quartiers.
24. Les doublons et variantes de noms ont été traités sans fusionner des quartiers distincts.
25. Chaque quartier est décrit avec les six champs requis et aucune information locale n'est inventée.
26. Si l'exhaustivité ne peut pas être confirmée, la limite est explicitement indiquée dans `Cadre de vie et Quotidien` ; ne prétends jamais à une exhaustivité non vérifiée.

## Notes et appréciations
27. Chaque note sur 10 respecte la grille propre à son critère et repose sur des indicateurs documentés.
28. Chaque justification de note compte entre 5 et 8 mots, hors note.
29. Aucune note n'est inventée lorsque les données sont insuffisantes.
30. Le potentiel patrimonial est argumenté, nuancé et ne constitue pas une promesse de rendement ou de plus-value.
31. Les appréciations sur les quartiers restent à la bonne échelle géographique et ne reposent pas sur des réputations non vérifiées.

Si un point ne peut pas être validé, corrige la valeur concernée ou indique `Non disponible`. Ne masque jamais une incertitude pour donner un résultat qui paraît plus complet.

Génère maintenant la réponse pour les communes suivantes : {villes_input}
                """


                with st.spinner("Gemini analyse le marché immobilier en cours..."):
                    reponse = model.generate_content(
                        prompt,
                        generation_config={"response_mime_type": "application/json", "temperature": 0}
                    )
                    texte_json = extract_json_from_response(reponse)
                    try:
                        donnees = json.loads(texte_json)
                    except json.JSONDecodeError:
                        st.error("❌ Erreur dans le format retourné par l'IA. Veuillez relancer la comparaison.")
                        st.stop()

                    st.session_state["df_villes"] = pd.DataFrame(donnees)

            except Exception as e:
                st.error(f"Une erreur s'est produite lors de la génération. Détails techniques : {e}")

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
                            df_quartiers = normalize_columns(df_quartiers, ["Nom", "Caractéristiques", "Catégorie sociale", "Sécurité", "Écoles", "Transports"])
                            df_quartiers_wrapped = df_quartiers.map(lambda x: wrap_text(x, max_chars=40))
                            df_quartiers_wrapped = df_quartiers_wrapped.fillna("")
                            st.table(df_quartiers_wrapped.set_index("Nom").T)
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
                data=generer_excel_simple(df_export),
                file_name="comparaison_villes.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.download_button(
                label="📥 Télécharger en PDF",
                data=generer_pdf_simple(df_export, title="Comparaison de villes"),
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

**Important : ne jamais utiliser d'appel de fonction. Retourne uniquement du JSON pur.**

Retourne EXCLUSIVEMENT un JSON valide, sans aucun texte avant ou après, sans balises markdown, sans commentaire.

La sortie doit être une liste JSON d'objets, chaque objet représentant un quartier. Chaque objet doit contenir EXACTEMENT les clés suivantes, dans cet ordre, avec des valeurs qui sont TOUTES des chaînes de caractères :

[
  {{
    "Nom": "",
    "Caractéristiques": "",
    "Catégorie sociale": "",
    "Moyenne d'âge des résidents": "",
    "Sécurité": "",
    "Écoles": "",
    "Transports": ""
  }}
]

Définitions :
- "Nom" : nom du quartier.
- "Caractéristiques" : type d'habitat, ambiance, commodités principales.
- "Catégorie sociale" : catégorie socio-professionnelle dominante.
- "Moyenne d'âge des résidents" : âge moyen estimé des habitants du quartier, en années, et ajouter "ans" à la fin. Ex : "37 ans".
- "Sécurité" : niveau de sécurité ressenti (ex : Très bonne, Bonne, Correcte, Faible, etc.).
- "Écoles" : écoles de rattachement (noms ou types, séparés par des virgules).
- "Transports" : modes de transport disponibles et accessibilité.

Si une information est inconnue, écris "Non disponible". Assure-toi de couvrir tous les quartiers importants de la ville, y compris les quartiers périphériques.

Exemple de format attendu (ne pas utiliser ces valeurs) :
[
  {{"Nom": "Centre-ville", "Caractéristiques": "Appartements anciens, commerces", "Catégorie sociale": "Mixte", "Moyenne d'âge des résidents": "42 ans", "Sécurité": "Bonne", "Écoles": "Lycée X, Collège Y", "Transports": "Bus, gare"}},
  {{"Nom": "Quartier Nord", "Caractéristiques": "Pavillonnaire, calme", "Catégorie sociale": "Familles", "Moyenne d'âge des résidents": "36 ans", "Sécurité": "Très bonne", "Écoles": "École primaire Z", "Transports": "Bus"}}
]
                """

                with st.spinner("Analyse des quartiers en cours..."):
                    reponse = model.generate_content(
                        prompt_quartiers,
                        generation_config={"response_mime_type": "application/json", "temperature": 0}
                    )
                    texte_json = extract_json_from_response(reponse)
                    try:
                        quartiers = json.loads(texte_json)
                    except json.JSONDecodeError:
                        st.error("❌ Erreur dans le format retourné par l'IA.")
                        st.stop()

                    df_quartiers = pd.DataFrame(quartiers)
                    if not df_quartiers.empty:
                        # Normaliser les colonnes
                        df_quartiers = normalize_columns(df_quartiers, ["Nom", "Caractéristiques", "Catégorie sociale", "Moyenne d'âge des résidents", "Sécurité", "Écoles", "Transports"])

                        df_quartiers_wrapped = df_quartiers.map(lambda x: wrap_text(x, max_chars=40))
                        df_quartiers_wrapped = df_quartiers_wrapped.fillna("")

                        df_quartiers_display = df_quartiers_wrapped.set_index("Nom").T

                        st.success(f"✅ {len(df_quartiers)} quartiers trouvés pour {ville_quartiers}.")
                        st.table(df_quartiers_display)

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
Tu es un expert senior de l'éducation nationale et de l'analyse territoriale en France. Tu maîtrises l'organisation des établissements scolaires, les données statistiques de la DEPP, l'Indice de Position Sociale (IPS), les indicateurs de résultats des collèges et lycées, ainsi que les règles de sectorisation scolaire.

Ta mission est de produire un inventaire aussi exhaustif que possible, rigoureux, actualisé et vérifiable des établissements scolaires situés dans la commune suivante :

{ville_ecoles}

L'analyse doit permettre de comprendre l'offre scolaire locale et, lorsque les informations officielles le permettent, d'identifier précisément les établissements publics de rattachement des différents quartiers de la commune.

## 1. OBJECTIFS

Pour la commune demandée :
- recenser tous les établissements scolaires du premier et du second degré physiquement implantés dans la commune ;
- distinguer les établissements publics, privés sous contrat et privés hors contrat ;
- identifier leur niveau d'enseignement et leur statut exact ;
- récupérer le dernier IPS officiel disponible pour chaque établissement lorsque cet indicateur existe ;
- analyser les résultats scolaires publiés officiellement, sans les confondre avec la qualité globale de l'enseignement ;
- documenter les caractéristiques des infrastructures uniquement à partir d'informations vérifiables ;
- identifier les quartiers effectivement rattachés à chaque établissement public selon la carte scolaire applicable ;
- signaler les limites des données lorsque le rattachement ne peut pas être établi avec précision.

L'exhaustivité du recensement est une exigence forte : ne te limite jamais aux établissements les plus connus, les mieux classés ou les mieux référencés par les sites privés.

## 2. IDENTIFICATION DE LA COMMUNE ET PÉRIMÈTRE

- Identifie précisément la commune correspondant à `{ville_ecoles}`, avec son département et son code postal lorsque nécessaire.
- Si le nom est ambigu et que le contexte ne permet pas d'identifier la commune avec une confiance suffisante, ne choisis pas automatiquement la commune la plus peuplée : demande une précision. Si le format d'exécution impose malgré tout une sortie JSON, n'invente pas de commune ni d'établissements.
- Corrige silencieusement une faute d'orthographe évidente si la commune visée ne fait aucun doute.
- Le périmètre principal comprend les établissements scolaires dont l'adresse physique se trouve à l'intérieur des limites administratives de la commune.
- N'ajoute pas les écoles des communes voisines à l'inventaire principal, même si elles sont proches ou fréquentées par des habitants de la commune.
- Tu peux toutefois signaler, dans le champ `Quartiers rattachés`, qu'un quartier dépend officiellement d'un établissement situé hors de la commune, en précisant le nom de cet établissement et sa commune, si cette information est vérifiée.
- N'inclus pas les crèches, garderies, accueils périscolaires, organismes de soutien scolaire, établissements d'enseignement supérieur, écoles de conduite ou simples centres de formation pour adultes.
- Inclus les écoles maternelles, écoles élémentaires, écoles primaires, collèges, lycées généraux et technologiques, lycées professionnels et polyvalents, ainsi que les établissements scolaires spécialisés ou agricoles lorsqu'ils relèvent bien du périmètre scolaire et sont officiellement recensés.

## 3. MÉTHODOLOGIE OBLIGATOIRE EN SIX PHASES

Effectue les recherches et contrôles dans l'ordre. Ne produis pas le JSON avant d'avoir terminé les vérifications possibles.

### Phase 1 — Établir le périmètre et la liste de référence

1. Identifie la commune, son code INSEE, son département et son académie.
2. Consulte l'Annuaire de l'Éducation nationale et les jeux de données officiels recensant les établissements.
3. Recherche également les annuaires de l'académie, de la DSDEN, de la mairie et, selon le niveau, du conseil départemental ou régional.
4. Recherche spécifiquement les établissements privés sous contrat et hors contrat ; ne suppose pas que l'annuaire principal les recense tous.
5. Utilise le code UAI/RNE comme identifiant de référence pour dédoublonner les établissements lorsque cette donnée est disponible.
6. Vérifie les adresses pour exclure les établissements situés dans une commune voisine.
7. Prends en compte les ouvertures, fermetures, changements de nom, fusions, déménagements et changements de statut récents.

### Phase 2 — Garantir l'exhaustivité du recensement

Croise au minimum les sources pertinentes suivantes :
- Annuaire officiel de l'Éducation nationale et jeux de données ouverts associés ;
- site de l'académie et de la DSDEN compétente ;
- annuaire ou pages Éducation de la mairie ;
- listes officielles des établissements privés sous contrat ;
- informations officielles relatives aux établissements privés hors contrat déclarés ;
- annuaires des établissements agricoles ou spécialisés, lorsqu'ils sont concernés.

Contrôles obligatoires :
- compare les listes obtenues et recherche les établissements présents dans une source mais absents des autres ;
- vérifie chaque établissement par son nom, son adresse, son niveau et, si possible, son code UAI ;
- ne considère pas deux lignes de sources différentes comme deux établissements distincts si elles correspondent au même code UAI ;
- si une même entité administrative comporte plusieurs niveaux dans un même établissement, indique les niveaux dans un seul objet lorsque le code UAI est identique ;
- si plusieurs établissements distincts ont des codes UAI différents, crée un objet distinct pour chacun, même s'ils partagent une adresse ou un groupe scolaire ;
- ne crée jamais un établissement à partir d'une simple mention non confirmée ou d'un résultat de moteur de recherche.

N'affirme pas que l'inventaire est exhaustif si les sources officielles se contredisent ou si une partie du secteur privé hors contrat n'a pas pu être contrôlée. Dans ce cas, retourne tous les établissements confirmés et utilise les champs concernés pour signaler les informations non vérifiées, sans inventer d'entrée.

### Phase 3 — Déterminer le statut et le type exacts

Pour chaque établissement :
- récupère son nom officiel ;
- détermine son niveau exact : `Maternelle`, `Élémentaire`, `Maternelle et élémentaire`, `Collège`, `Lycée général et technologique`, `Lycée professionnel`, `Lycée polyvalent`, `Établissement spécialisé`, `Établissement agricole` ou une désignation officielle plus précise ;
- utilise exclusivement l'un des statuts suivants : `Public`, `Privé sous contrat`, `Privé hors contrat` ;
- ne déduis jamais le statut à partir du nom, du caractère religieux, de la réputation ou du site Internet de l'établissement ;
- si le statut juridique ne peut pas être établi de manière fiable, indique `Non disponible` dans `Statut`.

### Phase 4 — Récupérer et interpréter l'IPS

Utilise en priorité les jeux de données officiels de la DEPP et de data.education.gouv.fr :
- IPS des écoles ;
- IPS des collèges ;
- IPS des lycées.

Règles impératives :
- recherche le dernier millésime officiel disponible pour chaque établissement ;
- associe l'IPS au bon établissement en vérifiant le nom, la commune, le niveau et le code UAI lorsque disponible ;
- indique le millésime ou l'année scolaire avec la valeur, par exemple `112 (rentrée 2025)` ;
- si la donnée est absente, non publiée, masquée, indiquée `NS` ou impossible à rattacher avec certitude à l'établissement, écris `Non disponible` ;
- n'estime jamais un IPS à partir du quartier, des revenus des habitants, de la réputation de l'établissement ou de l'IPS d'un établissement voisin ;
- ne calcule pas un IPS de quartier en faisant la moyenne des IPS des écoles, sauf demande explicite et méthode statistique appropriée ;
- ne compare pas directement des IPS issus de niveaux scolaires ou de millésimes différents sans précaution explicite ;
- ne surinterprète pas les écarts de 3 points ou moins entre IPS moyens ;
- rappelle dans l'interprétation interne que l'IPS décrit le profil social moyen des élèves et non leur niveau scolaire, leur capacité, la qualité des enseignants ou la performance pédagogique.

Pour les établissements privés hors contrat, n'attribue aucun IPS en l'absence de publication officielle spécifique et vérifiable.

### Phase 5 — Évaluer les résultats, les absences et les infrastructures

#### Qualité de l'enseignement

Le champ `Qualité de l'enseignement` ne doit jamais devenir une note de réputation ou un jugement subjectif.

- Pour les collèges, consulte les indicateurs officiels IVAC de la DEPP lorsque disponibles.
- Pour les lycées, consulte les indicateurs officiels IVAL de la DEPP lorsque disponibles.
- Privilégie l'analyse de la valeur ajoutée, des taux d'accès, des taux de réussite et des résultats attendus/constatés, en tenant compte de la méthodologie officielle.
- Ne classe pas un établissement à partir du seul taux brut de réussite au brevet ou au baccalauréat.
- Ne confonds pas IPS élevé et qualité de l'enseignement élevée.
- Ne déduis pas la qualité pédagogique de commentaires d'internautes, de palmarès commerciaux ou de la réputation locale.
- Pour les écoles maternelles et élémentaires, ne fabrique pas de note si aucun indicateur public comparable n'existe.
- Pour les établissements privés hors contrat, ne transpose pas les résultats d'un autre établissement ni ceux d'un établissement sous contrat.
- Résume uniquement les éléments officiels pertinents et leur année. Si aucun indicateur fiable et comparable n'est disponible, écris `Non disponible (pas d'indicateur public comparable)`.

Les IVAC et IVAL sont des indicateurs d'analyse des résultats et de la valeur ajoutée ; ils ne constituent pas à eux seuls une mesure exhaustive de la qualité pédagogique ou de l'expérience des élèves.

#### Taux d'absence des professeurs

- Recherche uniquement une donnée publique, identifiable, récente et portant bien sur l'absence des enseignants de l'établissement concerné.
- Ne confonds jamais absence des professeurs, absentéisme des élèves, taux de remplacement, postes vacants ou absentéisme moyen du département.
- N'extrapole pas un taux national, académique ou départemental à un établissement précis.
- Si aucune donnée d'établissement fiable n'est publiée, écris `Non disponible`.

#### Qualité de l'infrastructure

- Décris uniquement des caractéristiques factuelles et documentées : état signalé des bâtiments, rénovations, travaux, accessibilité, équipements sportifs ou numériques, restauration, espaces extérieurs, performance énergétique ou capacité d'accueil.
- Privilégie les documents de la mairie, de la collectivité propriétaire, les délibérations, les programmes de travaux et les pages officielles de l'établissement.
- Distingue un projet annoncé, un chantier en cours et des travaux livrés.
- Ne juge pas l'état d'un bâtiment à partir de photographies seules, d'avis en ligne ou d'impressions.
- N'assimile pas l'absence d'information à une infrastructure médiocre ou excellente.
- Si aucune information fiable n'est disponible, écris `Non disponible`.

### Phase 6 — Cartographier la sectorisation et les quartiers rattachés

Cette phase est essentielle et nécessite une vigilance particulière : un établissement proche d'un quartier n'est pas nécessairement son établissement de rattachement.

#### A. Constituer la liste des quartiers

- Établis d'abord l'inventaire le plus exhaustif possible des quartiers et secteurs locaux de la commune.
- Utilise en priorité les cartes et documents officiels de la mairie, le PLU/PLUi, les documents d'urbanisme, les conseils de quartier et les publications institutionnelles.
- Complète avec les appellations locales établies et utilisées de manière cohérente par plusieurs sources fiables.
- Ne confonds pas automatiquement les IRIS de l'INSEE, les secteurs administratifs, les quartiers vécus et les quartiers utilisés dans le langage courant.
- Ne crée pas de nouveaux quartiers à partir de simples rues ou d'ensembles immobiliers, sauf si une source locale les identifie comme un secteur reconnu.
- N'oublie aucun quartier identifié dans les sources retenues. Si les limites d'un quartier ne sont pas officiellement définies, traite son appellation comme un secteur local et ne lui attribue pas une frontière artificielle.

#### B. Comprendre les règles de sectorisation selon le niveau

- Pour les écoles maternelles et élémentaires publiques, utilise la sectorisation arrêtée par la commune. Les secteurs peuvent être définis par rue, numéro, adresse ou portion de quartier.
- Pour les collèges publics, utilise la carte scolaire officielle établie par l'autorité compétente, généralement le conseil départemental.
- Pour les lycées publics, utilise la sectorisation et les règles d'affectation publiées par l'autorité académique compétente.
- Vérifie le millésime de la carte scolaire et son application pour l'année scolaire en cours.
- Ne suppose jamais que le secteur d'un collège ou d'un lycée est identique au secteur de l'école primaire.
- Ne transpose pas les règles de sectorisation publique aux établissements privés : ceux-ci ne disposent pas d'un secteur public de rattachement obligatoire comparable.

#### C. Associer précisément les quartiers aux établissements

- Utilise les cartes scolaires officielles, les fichiers géographiques publiés, les outils officiels de recherche par adresse et les listes de rues ou numéros lorsqu'ils existent.
- Lorsque la sectorisation est disponible uniquement par adresse, ne transforme pas cette information en rattachement de quartier entier sans preuve géographique.
- Lorsqu'un quartier est traversé par plusieurs secteurs, précise `partie du quartier` ou `selon l'adresse`.
- Lorsqu'un secteur couvre plusieurs quartiers entiers, indique chacun des quartiers concernés.
- Lorsqu'une seule partie d'un quartier est affectée à un établissement, ne présente pas le quartier entier comme rattaché à cet établissement.
- Lorsqu'un même quartier dépend de plusieurs établissements selon la rue ou le numéro, indique cette nuance explicitement.
- Si la carte scolaire est disponible mais que la correspondance entre ses limites et les quartiers ne peut pas être vérifiée, indique `Non disponible (correspondance quartier-secteur non vérifiable)`.
- Si aucune carte scolaire officielle n'est accessible, indique `Non disponible (carte scolaire officielle non trouvée)`.
- Ne déduis jamais le rattachement du seul établissement le plus proche, d'une distance à vol d'oiseau, d'un annuaire commercial ou de la réputation du quartier.
- Pour une école privée, indique `Non applicable (pas de sectorisation publique)` ; si ses critères d'admission sont officiellement publiés, tu peux les résumer dans un autre champ pertinent, mais ne les présente pas comme une sectorisation.
- Si un quartier dépend d'un établissement public situé dans une commune voisine, signale le nom de cet établissement et sa commune dans `Quartiers rattachés`, en précisant qu'il est hors du périmètre de l'inventaire principal.

## 4. HIÉRARCHIE DES SOURCES

Privilégie les données originales et les sources institutionnelles, dans l'ordre suivant selon le sujet :

1. **Identification des établissements :** Annuaire de l'Éducation nationale, Répertoire national des établissements (UAI/RNE), jeux de données ouverts du ministère.
2. **Statut public/privé :** ministère de l'Éducation nationale, rectorat, DSDEN et listes officielles des établissements privés sous contrat ou hors contrat.
3. **IPS :** DEPP et data.education.gouv.fr, jeux de données IPS écoles, collèges et lycées.
4. **Résultats scolaires :** DEPP, IVAC, IVAL et indicateurs officiels de résultats des collèges et lycées.
5. **Sectorisation primaire :** mairie, service Éducation de la commune, carte scolaire municipale, délibérations et outils officiels de recherche par adresse.
6. **Sectorisation collèges :** conseil départemental, DSDEN et carte scolaire officielle.
7. **Sectorisation lycées :** rectorat, académie, DSDEN et documents officiels de l'autorité compétente.
8. **Infrastructures :** mairie, collectivité propriétaire, délibérations, marchés ou programmes de travaux publics, documents officiels des établissements.
9. **Établissements agricoles ou spécialisés :** ministère ou administration de tutelle compétente et annuaires officiels associés.

Les sites privés, annuaires commerciaux, palmarès, forums et avis d'internautes peuvent uniquement servir à repérer une piste à vérifier. Ils ne constituent jamais la preuve finale d'un statut, d'un rattachement scolaire, d'un IPS ou d'une performance.

## 5. RÈGLES DE QUALITÉ ET DE PRUDENCE

- Utilise les données les plus récentes disponibles, mais indique leur année ou rentrée scolaire dans le champ concerné.
- Compare des informations portant sur la même période, le même niveau scolaire et la même définition.
- Distingue toujours les données directement publiées, les informations calculées et les appréciations qualitatives.
- Ne présente jamais une donnée communale, départementale ou académique comme une donnée propre à un établissement.
- N'invente aucun IPS, taux d'absence, résultat, équipement ou rattachement de quartier.
- Ne déduis pas la qualité de l'enseignement du niveau social des familles ou du quartier.
- Ne transforme pas un classement commercial en évaluation officielle.
- Si plusieurs sources officielles divergent, privilégie la source de l'autorité compétente pour le sujet et la période considérés ; ne masque pas une divergence importante.
- Si une donnée est inconnue, utilise `Non disponible` avec une raison concise lorsque cela aide à comprendre la limite.
- N'utilise pas `Non disponible` par facilité lorsqu'une recherche ciblée dans les sources officielles permet de retrouver l'information.
- Ne prétends pas avoir consulté une carte, une base ou une source que tu n'as pas réellement vérifiée.

## 6. FORMAT DE SORTIE — CONTRAINTE ABSOLUE

Retourne EXCLUSIVEMENT un JSON valide, sans aucun texte avant ou après, sans balises Markdown, sans commentaire et sans bloc de code.

La sortie doit être une liste JSON d'objets. Chaque objet représente un établissement scolaire distinct et contient EXACTEMENT les huit clés suivantes, dans cet ordre. Toutes les valeurs sont des chaînes de caractères :

[
  {{
    "Nom de l'école": "",
    "Type": "",
    "Statut": "",
    "IPS": "",
    "Qualité de l'enseignement": "",
    "Taux d'absence des professeurs": "",
    "Qualité de l'infrastructure": "",
    "Quartiers rattachés": ""
  }}
]

## 7. DÉFINITIONS ET FORMAT DE CHAQUE CHAMP

- `Nom de l'école` : nom officiel complet de l'établissement, tel qu'il apparaît dans l'annuaire officiel. N'utilise pas un nom commercial ou un surnom non officiel.
- `Type` : niveau ou combinaison de niveaux réellement proposés, avec une formulation précise. Exemples : `Maternelle`, `Élémentaire`, `Maternelle et élémentaire`, `Collège`, `Lycée général et technologique`, `Lycée professionnel`, `Lycée polyvalent`, `Établissement spécialisé`.
- `Statut` : uniquement `Public`, `Privé sous contrat`, `Privé hors contrat` ou `Non disponible`.
- `IPS` : valeur officielle accompagnée de son millésime, par exemple `112 (rentrée 2025)`, ou `Non disponible`.
- `Qualité de l'enseignement` : résumé court d'indicateurs officiels de résultats et de valeur ajoutée, avec leur année. Ne donne aucune note intuitive et n'utilise pas les adjectifs `Bonne`, `Très bonne` ou `Excellente` sans indicateur officiel explicite et contextualisé. Si aucun indicateur comparable n'existe, indique `Non disponible (pas d'indicateur public comparable)`.
- `Taux d'absence des professeurs` : pourcentage uniquement si une donnée officielle portant exactement sur les absences des enseignants de cet établissement est disponible, avec sa période. Sinon `Non disponible`.
- `Qualité de l'infrastructure` : description factuelle des équipements, travaux, rénovations, accessibilité ou état du bâtiment lorsqu'ils sont documentés. Sinon `Non disponible`.
- `Quartiers rattachés` : liste des quartiers ou portions de quartiers officiellement rattachés à cet établissement, séparés par des virgules. Ajoute les nuances `partie du quartier` ou `selon l'adresse` dès que nécessaire. Pour le privé, indique `Non applicable (pas de sectorisation publique)`. Si le rattachement est inconnu, indique la raison précise.

## 8. ORDRE DES ÉTABLISSEMENTS

Trie les établissements de façon stable et lisible :
1. écoles maternelles et élémentaires ;
2. collèges ;
3. lycées généraux et technologiques ;
4. lycées professionnels et polyvalents ;
5. établissements scolaires spécialisés ou agricoles.

À l'intérieur de chaque catégorie, trie par nom officiel dans l'ordre alphabétique. Ne crée pas de classement qualitatif entre les établissements.

## 9. CONTRÔLE FINAL SILENCIEUX

Avant de répondre, vérifie obligatoirement :

1. La commune analysée est bien celle demandée et le périmètre administratif est exact.
2. Tous les établissements scolaires identifiés dans les sources officielles pertinentes ont été examinés.
3. Les établissements publics, privés sous contrat et privés hors contrat ont été recherchés séparément.
4. Les établissements des communes voisines n'ont pas été ajoutés à l'inventaire principal.
5. Les doublons ont été éliminés à l'aide du code UAI lorsque disponible.
6. Les établissements multi-niveaux et les groupes scolaires sont traités sans doublon artificiel.
7. Le nom, le type et le statut correspondent aux informations officielles les plus récentes.
8. Chaque IPS correspond au bon établissement, au bon niveau et au bon millésime.
9. L'IPS n'est jamais interprété comme une mesure de qualité pédagogique.
10. Les résultats IVAC/IVAL sont interprétés selon leur méthodologie et ne sont pas réduits au taux brut de réussite.
11. Les absences des enseignants ne sont pas confondues avec celles des élèves ou avec les taux de remplacement.
12. Les appréciations sur les infrastructures reposent sur des éléments vérifiables.
13. Les secteurs scolaires sont ceux de l'année scolaire en cours.
14. Les quartiers rattachés reposent sur une carte, une liste de rues, un outil officiel par adresse ou une preuve géographique suffisante.
15. Aucun quartier entier n'est rattaché à un établissement lorsque seule une partie du quartier est concernée.
16. Les écoles privées ne se voient pas attribuer artificiellement une sectorisation publique.
17. Les valeurs inconnues sont indiquées comme `Non disponible` ou `Non applicable` selon le cas.
18. Chaque objet possède exactement les huit clés demandées et toutes les valeurs sont des chaînes de caractères.
19. Le JSON est syntaxiquement valide, sans texte, commentaire ou balise hors du JSON.
20. Aucun établissement, indicateur ou rattachement n'a été inventé pour compléter artificiellement la réponse.

## 10. EXEMPLE DE FORMAT (ILLUSTRATIF UNIQUEMENT)

Ne réutilise pas les noms, les valeurs ni les rattachements ci-dessous. Cet exemple sert uniquement à illustrer la syntaxe :

[
  {{
    "Nom de l'école": "École élémentaire Exemple",
    "Type": "Élémentaire",
    "Statut": "Public",
    "IPS": "108 (rentrée 2025)",
    "Qualité de l'enseignement": "Non disponible (pas d'indicateur public comparable)",
    "Taux d'absence des professeurs": "Non disponible",
    "Qualité de l'infrastructure": "Rénovation énergétique livrée en 2024, selon la mairie",
    "Quartiers rattachés": "Centre-ville (selon l'adresse), Quartier Nord (partie du quartier)"
  }},
  {{
    "Nom de l'école": "Collège Exemple",
    "Type": "Collège",
    "Statut": "Public",
    "IPS": "116 (rentrée 2025)",
    "Qualité de l'enseignement": "IVAC 2025 : valeur ajoutée positive au DNB, à interpréter avec le profil des élèves",
    "Taux d'absence des professeurs": "Non disponible",
    "Qualité de l'infrastructure": "Extension livrée en 2023, équipements sportifs documentés par le département",
    "Quartiers rattachés": "Centre-ville, Quartier Nord (selon l'adresse)"
  }},
  {{
    "Nom de l'école": "Établissement privé Exemple",
    "Type": "Maternelle et élémentaire",
    "Statut": "Privé sous contrat",
    "IPS": "Non disponible",
    "Qualité de l'enseignement": "Non disponible (pas d'indicateur public comparable)",
    "Taux d'absence des professeurs": "Non disponible",
    "Qualité de l'infrastructure": "Non disponible",
    "Quartiers rattachés": "Non applicable (pas de sectorisation publique)"
  }}
]

Génère maintenant l'inventaire pour la commune suivante : {ville_ecoles}
                """


                with st.spinner("Analyse des écoles en cours..."):
                    reponse = model.generate_content(
                        prompt_ecoles,
                        generation_config={"response_mime_type": "application/json", "temperature": 0}
                    )
                    texte_json = extract_json_from_response(reponse)
                    try:
                        ecoles = json.loads(texte_json)
                    except json.JSONDecodeError:
                        st.error("❌ Erreur dans le format retourné par l'IA.")
                        st.stop()

                    df_ecoles = pd.DataFrame(ecoles)
                    if not df_ecoles.empty:
                        # Normaliser les colonnes
                        expected_ecoles_columns = ["Nom de l'école", "Type", "Statut", "IPS", "Qualité de l'enseignement", "Taux d'absence des professeurs", "Qualité de l'infrastructure", "Quartiers rattachés"]
                        df_ecoles = normalize_columns(df_ecoles, expected_ecoles_columns)

                        # Remplir les NaN de Type avec "Non spécifié"
                        df_ecoles["Type"] = df_ecoles["Type"].fillna("Non spécifié")

                        # Tri par type
                        ordre_types = {
                            "École maternelle": 0,
                            "École élémentaire": 1,
                            "Collège": 2,
                            "Lycée": 3,
                            "Autre": 4,
                            "Non spécifié": 5
                        }

                        def get_ordre_type(type_ecole):
                            return ordre_types.get(type_ecole, ordre_types["Autre"])

                        df_ecoles["_ordre"] = df_ecoles["Type"].apply(get_ordre_type)
                        df_ecoles = df_ecoles.sort_values("_ordre")
                        df_ecoles = df_ecoles.drop(columns=["_ordre"])

                        df_ecoles_wrapped = df_ecoles.map(lambda x: wrap_text(x, max_chars=40))
                        df_ecoles_wrapped = df_ecoles_wrapped.fillna("")

                        df_ecoles_display = df_ecoles_wrapped.set_index("Nom de l'école").T

                        st.success(f"✅ {len(df_ecoles)} écoles trouvées pour {ville_ecoles}.")
                        st.table(df_ecoles_display)

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