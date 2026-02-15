import streamlit as st
import pandas as pd
import math
from datetime import datetime, timedelta
import io
import os

# --- 1. CONFIGURATION DE LA PAGE --- #BETA2024
st.set_page_config(
    page_title="SalaryFlow Copilot",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SYSTEME DE LOGIN MULTI-CLIENTS ---
def check_login():
    """Retourne True si l'utilisateur est connecté."""
    
    # Si déjà connecté, on laisse passer
    if st.session_state.get("authenticated", False):
        return True

    # Interface de connexion propre
    st.markdown("## 🔒 Accès Client SalaryFlow")
    
    # Création de deux colonnes pour centrer ou juste un formulaire simple
    with st.form("login_form"):
        email = st.text_input("Email Client")
        password = st.text_input("Mot de passe", type="password")
        submit = st.form_submit_button("Se connecter 🚀")
        
        if submit:
            # On va chercher les mots de passe dans les secrets de Streamlit
            secrets = st.secrets["passwords"]
            
            # Vérification
            if email in secrets and secrets[email] == password:
                st.session_state["authenticated"] = True
                st.session_state["user"] = email
                st.success("Connexion réussie !")
                st.rerun()
            else:
                st.error("Email ou mot de passe incorrect.")
                
    return False

# --- VERROUILLAGE ---
if not check_login():
    st.stop() # Arrête tout si pas connecté

# --- MESSAGE DE BIENVENUE ---
st.sidebar.info(f"Connecté en tant que : {st.session_state.get('user')}")
if st.sidebar.button("Déconnexion"):
    st.session_state["authenticated"] = False
    st.rerun()

# ---------------------------------------------------------
# ICI COMMENCE TON VRAI CODE (Styles CSS, etc.)
# ---------------------------------------------------------

# --- 2. STYLES CSS (MODIFIÉ POUR CACHER LE CODE) ---
st.markdown("""
    <style>
    /* Masquer le menu Streamlit (Hamburger) et le bouton 'Deploy' */
    #MainMenu {visibility: hidden;}
    .stDeployButton {display:none;}
    footer {visibility: hidden;}
    /* header {visibility: hidden;}  <-- Décommente si tu veux aussi cacher la barre colorée en haut */

    /* Tes styles existants */
    .status-banner { padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px; color: white; font-weight: bold; font-size: 1.2rem; }
    .status-ok { background-color: #00E676; }
    .status-warn { background-color: #FFA726; }
    .status-bad { background-color: #EF5350; }
    .coach-text { font-size: 1.1rem; margin-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. MOTEUR DE CALCULS & DONNEES ---

# Fonction pour calculer le net (inchangée de ta V10)
def calculer_net(type_c, taux, heures, paniers, charges_pct):
    try:
        t, h = float(taux), float(heures)
        p = float(paniers) if paniers else 0.0
        pct = float(charges_pct) / 100.0 if charges_pct else 0.0
        if type_c == "Intérim": return round(((t * h * 1.21) * 0.78) + p, 2)
        else: return round(((t * h) * (1 - pct)) + p, 2)
    except: return 0.0

# Initialisation des données (Session State pour persistance web)
if 'data_revenus' not in st.session_state:
    # Structure vide pour les revenus
    st.session_state['data_revenus'] = pd.DataFrame(columns=["Date", "Mois", "Source", "Type", "Détails", "Montant Net", "Date Paiement", "Mois Paiement"])

if 'data_charges' not in st.session_state:
    # Charges par défaut (Ta liste)
    data_charges = [
        ("EPARGNE", "Court Terme", "Livret A", 0, 1),
        ("FIXES", "Logement", "Loyer", 0, 5),
        ("FIXES", "Logement", "Energie/Eau", 0, 15),
        ("FIXES", "Logement", "Internet", 0, 10),
        ("FIXES", "Crédits", "Prêt", 0, 5),
        ("FIXES", "Alim", "Courses (Fixe)", 0, 1),
        ("FIXES", "Transport", "Assurance Auto", 0, 10),
        ("FIXES", "Transport", "Carburant", 0, 1),
        ("FIXES", "Santé", "Mutuelle", 0, 5),
        ("FIXES", "Abonnements", "Téléphone", 0, 10),
        ("FIXES", "Abonnements", "Spotify/Netflix", 0, 10),
        ("FIXES", "Banque", "Frais Bancaires", 0, 1),
        ("VARIABLES", "Plaisir", "Restos / Sorties", 0, 20),
        ("VARIABLES", "Divers", "Imprévus", 0, 15),
    ]
    st.session_state['data_charges'] = pd.DataFrame(data_charges, columns=["Groupe", "Sous-Groupe", "Intitule", "Montant", "Jour"])

# Gestion de la date de vue
if 'view_date' not in st.session_state:
    now = datetime.now()
    if now.month == 12: st.session_state['view_date'] = datetime(now.year + 1, 1, 1)
    else: st.session_state['view_date'] = datetime(now.year, now.month + 1, 1)

# Gestion simulation
if 'sim_val' not in st.session_state: st.session_state['sim_val'] = 0.0


# --- 4. INTELLIGENCE V11 (COACH & ANALYSE) ---

def analyser_situation(solde, score, timeline_df):
    # 1. État Global
    tension_date = None
    if not timeline_df.empty:
        # Trouver le premier jour où le cumul passe en négatif
        for _, row in timeline_df.iterrows():
            if row['Cumul'] < 0:
                tension_date = row['Jour']
                break
            
    if score < 1 or solde < 0:
        etat = "🔴 RISQUE DÉTECTÉ"
        css = "status-bad"
        if tension_date: desc = f"Attention : Trésorerie sous tension le {tension_date}."
        else: desc = "Déficit structurel prévu ce mois-ci."
        
        conseils = [
            f"❌ **Manque à gagner : {abs(solde):.0f} €**",
            f"💪 **Action Coach :** Il vous manque environ {math.ceil(abs(solde)/12.02)}h de travail (base 12.02€/h).",
            "✂️ **Action Coach :** Réduisez les dépenses variables (Restos, Sorties)."
        ]
        
    elif score < 1.5 or solde < 200:
        etat = "🟠 SITUATION FRAGILE"
        css = "status-warn"
        desc = f"Vos charges sont couvertes, mais la marge est faible ({solde:.0f}€)."
        conseils = [
            "⚠️ Marge de sécurité trop faible pour gérer un imprévu.",
            "🎯 **Objectif :** Ne faites aucune dépense 'Plaisir' ce mois-ci.",
            "💡 Une petite mission supplémentaire vous sécuriserait."
        ]
        
    else:
        etat = "🟢 SITUATION STABLE"
        css = "status-ok"
        desc = f"Tout va bien ! Marge confortable de {solde:.0f}€."
        conseils = [
            "✅ Tous les voyants sont au vert.",
            f"💰 **Conseil Coach :** Virez {solde*0.5:.0f}€ sur votre épargne dès maintenant."
        ]
        
    return etat, css, desc, conseils


# --- 5. INTERFACE UTILISATEUR (STREAMLIT) ---

# Sidebar Navigation
with st.sidebar:
    st.markdown("## ⚡ SalaryFlowApp")
    menu = st.radio("Menu", ["🚀 Cockpit", "➕ Ajouter un revenu", "💳 Charges & Budgets"])
    
    st.markdown("---")
    st.markdown("### 🚀 Simulateur Rapide")
    val_sim = st.number_input("Simuler une entrée (€)", value=float(st.session_state['sim_val']), step=50.0)
    if val_sim != st.session_state['sim_val']:
        st.session_state['sim_val'] = val_sim
        st.rerun() # Rafraichir auto

# --- AJOUTER CECI A LA FIN DU BLOC "with st.sidebar:" ---
    
    st.markdown("---")
    st.markdown("### 💾 Sauvegarde")
    
    # Création du fichier Excel en mémoire virtuelle
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        # Onglet 1 : Revenus
        st.session_state['data_revenus'].to_excel(writer, sheet_name='DATA', index=False)
        # Onglet 2 : Charges
        st.session_state['data_charges'].to_excel(writer, sheet_name='CHARGES', index=False)
        
    # Le bouton de téléchargement
    st.download_button(
        label="📥 Télécharger mon Excel",
        data=buffer,
        file_name="Mes_Finances_SalaryFlow.xlsx",
        mime="application/vnd.ms-excel"
    )

# PAGE 1: DASHBOARD / PILOTAGE
if menu == "🚀 Cockpit":
    
    # Sélecteur de mois
    col_nav1, col_nav2, col_nav3 = st.columns([1, 6, 1])
    if col_nav1.button("◀"):
        d = st.session_state['view_date']
        if d.month == 1: st.session_state['view_date'] = datetime(d.year - 1, 12, 1)
        else: st.session_state['view_date'] = datetime(d.year, d.month - 1, 1)
        st.rerun()
        
    mois_str = st.session_state['view_date'].strftime("%Y-%m")
    nom_mois = st.session_state['view_date'].strftime("%B %Y").capitalize()
    col_nav2.markdown(f"<h2 style='text-align: center; margin:0;'>{nom_mois}</h2>", unsafe_allow_html=True)
    
    if col_nav3.button("▶"):
        d = st.session_state['view_date']
        if d.month == 12: st.session_state['view_date'] = datetime(d.year + 1, 1, 1)
        else: st.session_state['view_date'] = datetime(d.year, d.month + 1, 1)
        st.rerun()

    # --- CALCULS ---
    df_r = st.session_state['data_revenus']
    df_c = st.session_state['data_charges']
    
    # Revenus du mois
    if not df_r.empty:
        in_month = df_r[df_r["Mois Paiement"] == mois_str]["Montant Net"].sum()
    else: in_month = 0.0
    
    entree_totale = in_month + st.session_state['sim_val']
    
    # Charges
    fixes = df_c[df_c["Groupe"]=="FIXES"]["Montant"].sum()
    epargne = df_c[df_c["Groupe"]=="EPARGNE"]["Montant"].sum()
    var = df_c[df_c["Groupe"]=="VARIABLES"]["Montant"].sum()
    total_sorties = fixes + epargne + var
    
    solde = entree_totale - total_sorties
    
    # Score
    if fixes > 0: score = entree_totale / fixes
    else: score = 0 # Pas de charges = pas de score calculable
    
    # Timeline Data Construction
    tl_data = []
    # Charges
    for _, r in df_c.iterrows():
        if r['Montant'] > 0:
            tl_data.append({"Jour": int(r['Jour']), "Type": "Charge", "Nom": r['Intitule'], "Montant": -r['Montant']})
    # Revenus
    if not df_r.empty:
        rev_mois = df_r[df_r["Mois Paiement"] == mois_str]
        for _, r in rev_mois.iterrows():
            try: d = pd.to_datetime(r["Date Paiement"]).day
            except: d = 1
            tl_data.append({"Jour": d, "Type": "Revenu", "Nom": r["Source"], "Montant": r["Montant Net"]})
    # Sim
    if st.session_state['sim_val'] > 0:
        tl_data.append({"Jour": 15, "Type": "Sim", "Nom": "Simulation", "Montant": st.session_state['sim_val']})
            
    df_tl = pd.DataFrame(tl_data)
    if not df_tl.empty:
        df_tl = df_tl.sort_values("Jour")
        df_tl["Cumul"] = df_tl["Montant"].cumsum() # Solde progressif
        
    # ANALYSE INTELLIGENTE
    etat, css, desc, conseils = analyser_situation(solde, score, df_tl)

    # --- AFFICHAGE ---
    
    # 1. BANDEAU D'ÉTAT (GLOBAL)
    st.markdown(f"""
        <div class="status-banner {css}">
            {etat} <br>
            <span style="font-size:0.9rem; font-weight:normal;">{desc}</span>
        </div>
        """, unsafe_allow_html=True)
        
    col_kpi_g, col_kpi_d = st.columns([1, 2])
    
    with col_kpi_g:
        st.markdown("### Stabilité")
        # On plafonne la barre à 100% (1.0) pour ne pas que ça plante si le score dépasse 3
        bar_value = min(score / 3, 1.0)
        st.progress(bar_value)
        
        # On affiche le chiffre en gros juste en dessous
        if score < 1:
            st.error(f"Score : {score:.2f} / 3.0 (Risque)")
        elif score < 1.5:
            st.warning(f"Score : {score:.2f} / 3.0 (Fragile)")
        else:
            st.success(f"Score : {score:.2f} / 3.0 (Solide)")
            
        if fixes == 0: 
            st.info("Ajoutez des charges fixes pour calculer le score.")

    with col_kpi_d:
        # Métriques
        k1, k2, k3 = st.columns(3)
        k1.metric("Revenus Attendus", f"{entree_totale:,.2f} €", delta=f"Dont Simu: {st.session_state['sim_val']}€" if st.session_state['sim_val']>0 else None)
        k2.metric("Charges Totales", f"{total_sorties:,.2f} €", delta="-Sorties", delta_color="inverse")
        k3.metric("SOLDE PRÉVISIONNEL", f"{solde:,.2f} €", delta="Reste à vivre")
        
        st.divider()
        
        # Coach
        st.subheader("💡 Analyse du Coach")
        for c in conseils:
            st.markdown(f"<div class='coach-text'>{c}</div>", unsafe_allow_html=True)

    st.markdown("---")
    
    # 2. TIMELINE STRATÉGIQUE
    st.subheader("🗓️ Timeline de Trésorerie")
    if not df_tl.empty:
        # On prépare un tableau stylisé
        st.dataframe(
            df_tl[["Jour", "Type", "Nom", "Montant", "Cumul"]].style.map(
                lambda x: 'color: #EF5350; font-weight: bold;' if x < 0 else 'color: #00E676;', subset=['Cumul']
            ).format("{:.2f} €", subset=["Montant", "Cumul"]),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Aucune transaction prévue pour ce mois.")


# PAGE 2: AJOUT REVENU AVEC BOUTON ANNULER
# --- PAGE 2 : AJOUT REVENU ---
elif menu == "➕ Ajouter un revenu":
    st.header("Rentrée d'argent")
    
    # 1. On demande d'abord la SOURCE et le TYPE (pour adapter la suite)
    c1, c2 = st.columns(2)
    source = c1.text_input("Source")
    typ = c2.selectbox("Type", ["Intérim", "Micro-Entreprise", "Salaire", "APL", "Prime d'activité", "Chômage", "Remboursements", "Autre"])
    
    # 2. On adapte le libellé de la date en fonction du type choisi
    if typ in ["Intérim", "Micro-Entreprise"]:
        label_date = "Date de la mission"
    else:
        label_date = "Date de versement"
        
    date_mission = st.date_input(label_date, datetime.now())
    
    montant_final = 0.0
    d_pay = date_mission # Par défaut, paiement le jour même (sauf écrasé plus bas)

    st.markdown("---")
    
    # --- CAS 1 : INTÉRIM ---
    if typ == "Intérim":
        cc1, cc2, cc3 = st.columns(3)
        taux = cc1.number_input("Taux", 0.0)
        heures = cc2.number_input("Heures", 0.0)
        paniers = cc3.number_input("Paniers (€)", 0.0)
        montant_final = calculer_net("Intérim", taux, heures, paniers, 0)
        st.write(f"**Net estimé : {montant_final:.2f} €**")
        
        # Calcul automatique date paiement Intérim (M+1 le 12)
        if date_mission.month == 12:
            d_pay = datetime(date_mission.year + 1, 1, 12)
        else:
            d_pay = datetime(date_mission.year, date_mission.month + 1, 12)
        st.caption(f"📅 Paiement prévu automatiquement le : {d_pay.strftime('%d/%m/%Y')}")
        
    # --- CAS 2 : MICRO-ENTREPRISE ---
    elif typ == "Micro-Entreprise":
        # Ligne 1 : Calculs
        cc1, cc2, cc3, cc4 = st.columns(4)
        taux = cc1.number_input("Taux/CA", 0.0)
        heures = cc2.number_input("Qté/Jours", 1.0)
        paniers = cc3.number_input("Frais (€)", 0.0)
        charges = cc4.number_input("% Charges", 21.2)
        
        # Ligne 2 : Date de paiement manuelle (TA DEMANDE)
        st.write("") # Petit espace
        d_pay = st.date_input("📅 Date de paiement prévue", value=date_mission + timedelta(days=30))
        
        montant_final = calculer_net("Autre", taux, heures, paniers, charges)
        st.write(f"**Net estimé : {montant_final:.2f} €**")
        
    # --- CAS 3 : AUTRES ---
    else:
        montant_final = st.number_input("Net (€)", 0.0)
        # Pour salaire/autre, la date de paiement reste la date de versement saisie en haut

    # VALIDATION
    if st.button("Valider", type="primary"):
        new = {
            "Date": date_mission.strftime("%d/%m/%Y"), 
            "Mois": date_mission.strftime("%Y-%m"), 
            "Source": source, 
            "Type": typ, 
            "Détails": "App", 
            "Montant Net": montant_final, 
            "Date Paiement": d_pay.strftime("%Y-%m-%d"), 
            "Mois Paiement": d_pay.strftime("%Y-%m")
        }
        st.session_state['data_revenus'] = pd.concat([st.session_state['data_revenus'], pd.DataFrame([new])], ignore_index=True)
        st.success("Ajouté !")
        st.rerun()

    st.markdown("---")
    st.subheader("Historique récent")
    if not st.session_state['data_revenus'].empty:
        st.dataframe(st.session_state['data_revenus'].tail(3), use_container_width=True)
        if st.button("🗑️ Supprimer dernier ajout"):
            st.session_state['data_revenus'] = st.session_state['data_revenus'].iloc[:-1]
            st.warning("Supprimé !")
            st.rerun()
    else:
        st.info("Aucun revenu enregistré pour le moment.")


# PAGE 3: CHARGES
elif menu == "💳 Charges & Budgets":
    st.header("Mes Charges Mensuelles")
    st.info("Modifiez vos charges ici. Elles s'appliquent automatiquement à tous les mois futurs.")
    
    # Editeur de données interactif
    edited_df = st.data_editor(
        st.session_state['data_charges'],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Montant": st.column_config.NumberColumn("Montant (€)", min_value=0, format="%.2f €"),
            "Jour": st.column_config.NumberColumn("Jour du mois", min_value=1, max_value=31),
            "Groupe": st.column_config.SelectboxColumn("Groupe", options=["FIXES", "VARIABLES", "EPARGNE"])
        }
    )
    
    if st.button("Sauvegarder les modifications"):
        st.session_state['data_charges'] = edited_df
        st.success("Charges mises à jour !")
        
    # Export Excel (Optionnel)
    st.markdown("---")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        st.session_state['data_revenus'].to_excel(writer, sheet_name='DATA', index=False)
        st.session_state['data_charges'].to_excel(writer, sheet_name='CHARGES', index=False)
        
    st.download_button(
        label="💾 Sauvegarder mon Excel",
        data=buffer,
        file_name="Mes_Finances_SalaryFlow.xlsx",
        mime="application/vnd.ms-excel"
    )