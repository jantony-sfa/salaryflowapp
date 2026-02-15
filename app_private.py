import streamlit as st
import pandas as pd
import math
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def update_revenus_cloud(user_email, df_cleaned):
    """Ecrase les revenus de l'utilisateur avec la version corrigée"""
    sh = get_db_connection()
    ws = sh.worksheet("DATA")
    
    # 1. On récupère TOUT le fichier
    all_records = ws.get_all_records()
    
    # 2. On garde les données des AUTRES utilisateurs (s'il y en a)
    # On filtre pour ne garder que ce qui n'est PAS à toi
    cleaned_data = [r for r in all_records if str(r.get("User")) != str(user_email)]
    
    # 3. On ajoute TES données corrigées
    for _, row in df_cleaned.iterrows():
        r = row.to_dict()
        r["User"] = user_email
        # Sécurisation des dates pour le JSON
        r["Date"] = str(r["Date"])
        r["Date Paiement"] = str(r["Date Paiement"])
        cleaned_data.append(r)
        
    # 4. On écrase le Sheet avec la liste propre
    ws.clear()
    if cleaned_data:
        headers = list(cleaned_data[0].keys())
        ws.update([headers] + [list(d.values()) for d in cleaned_data])
    else:
        # Si tout est vide, on remet les titres
        ws.append_row(["User", "Date", "Mois", "Source", "Type", "Détails", "Montant Net", "Date Paiement", "Mois Paiement"])
        
# --- 1. CONFIGURATION ---
st.set_page_config(page_title="SalaryFlow SaaS", page_icon="🚀", layout="wide")

# --- 2. CSS ---
st.markdown("""
    <style>
    /* 1. Masquer le menu Hamburger (les 3 traits) */
    #MainMenu {visibility: hidden;}
    
    /* 2. Masquer le bouton 'Deploy' et les décorations du haut */
    .stDeployButton {display:none;}
    header {visibility: hidden;}
    
    /* 3. Masquer le footer 'Made with Streamlit' */
    footer {visibility: hidden;}

    /* 4. Masquer la barre d'outils si elle apparait encore */
    [data-testid="stToolbar"] {visibility: hidden;}

    /* TES STYLES PERSO */
    .status-banner { padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px; color: white; font-weight: bold; font-size: 1.2rem; }
    .status-ok { background-color: #00E676; }
    .status-warn { background-color: #FFA726; }
    .status-bad { background-color: #EF5350; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. CONNEXION DATABASE (GOOGLE SHEETS) ---
@st.cache_resource
def get_db_connection():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    return client.open("SalaryFlow_DB")

def load_user_data(user_email):
    sh = get_db_connection()
    
    # --- 1. CHARGEMENT REVENUS ---
    try:
        ws_r = sh.worksheet("DATA")
        data_r = ws_r.get_all_records()
        df_r = pd.DataFrame(data_r)
        
        if not df_r.empty:
            # Filtrage par utilisateur
            df_r = df_r[df_r["User"] == user_email]
            
            # Correction virgule -> point (Sécurité)
            if "Montant Net" in df_r.columns:
                df_r["Montant Net"] = df_r["Montant Net"].astype(str).str.replace(",", ".", regex=False)
                df_r["Montant Net"] = pd.to_numeric(df_r["Montant Net"], errors='coerce').fillna(0.0)
            
            # --- NETTOYAGE LIGHT (Permissif) ---
            # On ne supprime PLUS les doublons (drop_duplicates retiré)
            # On garde juste ce qui est "réel" (Montant > 0)
            df_r = df_r[df_r["Montant Net"] > 0]
            
        else:
            # Structure vide par défaut
            df_r = pd.DataFrame(columns=["User", "Date", "Mois", "Source", "Type", "Détails", "Montant Net", "Date Paiement", "Mois Paiement"])
    except:
        df_r = pd.DataFrame(columns=["User", "Date", "Mois", "Source", "Type", "Détails", "Montant Net", "Date Paiement", "Mois Paiement"])

    # --- 2. CHARGEMENT CHARGES ---
    try:
        ws_c = sh.worksheet("CHARGES")
        data_c = ws_c.get_all_records()
        df_c = pd.DataFrame(data_c)
        
        if not df_c.empty:
            df_c = df_c[df_c["User"] == user_email]

            if "Montant" in df_c.columns:
                df_c["Montant"] = df_c["Montant"].astype(str).str.replace(",", ".", regex=False)
                df_c["Montant"] = pd.to_numeric(df_c["Montant"], errors='coerce').fillna(0.0)
            
            # Pour les charges, on évite quand même les doublons stricts (car c'est mensuel)
            # Mais si vous voulez pouvoir mettre 2 fois "Loyer", enlevez la ligne ci-dessous :
            df_c = df_c.drop_duplicates() 
            df_c = df_c[df_c["Montant"] > 0]
            
        if df_c.empty:
            default_charges = [
                ("EPARGNE", "Court Terme", "Livret A", 0, 1),
                ("FIXES", "Logement", "Loyer", 0, 5),
                ("FIXES", "Logement", "Energie/Eau", 0, 15),
                ("FIXES", "Logement", "Internet", 0, 10),
                ("FIXES", "Transport", "Abonnement TBM", 0, 5),
                ("FIXES", "Abonnements", "Spotify", 0, 10),
                ("FIXES", "Abonnements", "Téléphone", 0, 10),
                ("FIXES", "Banque", "Frais Bancaires", 0, 1),
                ("VARIABLES", "Plaisir", "Restos / Sorties", 0, 20),
                ("VARIABLES", "Beauté", "Ongles / Esthétique", 0, 15),
                ("VARIABLES", "Animaux", "Véto / Croquettes", 0, 20),
            ]
            df_c = pd.DataFrame(default_charges, columns=["Groupe", "Sous-Groupe", "Intitule", "Montant", "Jour"])
            df_c["User"] = user_email
    except:
        df_c = pd.DataFrame()

    return df_r, df_c
    
def save_revenu_cloud(user_email, row_dict):
    sh = get_db_connection()
    ws = sh.worksheet("DATA")
    # Ordre des colonnes correspondant au Sheet
    row = [
        user_email, 
        row_dict["Date"], 
        row_dict["Mois"], 
        row_dict["Source"], 
        row_dict["Type"], 
        row_dict["Détails"], 
        row_dict["Montant Net"], 
        row_dict["Date Paiement"], 
        row_dict["Mois Paiement"]
    ]
    ws.append_row(row)

def save_charges_cloud(user_email, df_charges):
    sh = get_db_connection()
    ws = sh.worksheet("CHARGES")
    
    # 1. Lire tout le sheet
    all_data = ws.get_all_records()
    
    # 2. Garder tout ce qui n'est PAS à l'utilisateur actuel
    new_data = [row for row in all_data if row['User'] != user_email]
    
    # 3. Ajouter les nouvelles charges de l'utilisateur
    for _, row in df_charges.iterrows():
        r = row.to_dict()
        r['User'] = user_email
        new_data.append(r)
        
    # 4. Tout réécrire (Nettoyage + Mise à jour)
    ws.clear()
    if new_data:
        # Réécrire l'en-tête + les données
        headers = list(new_data[0].keys())
        ws.update([headers] + [list(d.values()) for d in new_data])
    else:
        # Juste l'en-tête si vide
        ws.append_row(["User", "Groupe", "Sous-Groupe", "Intitule", "Montant", "Jour"])

def update_user_revenus_cloud(user_email, df_revenus):
    """Met à jour TOUS les revenus de l'utilisateur (Correction/Suppression)"""
    sh = get_db_connection()
    ws = sh.worksheet("DATA")
    
    # 1. Récupérer toutes les données du Sheet
    all_data = ws.get_all_records()
    
    # 2. Garder tout ce qui n'est PAS à l'utilisateur actuel (les autres clients)
    # Si le sheet est vide ou n'a pas de colonne User, on gère l'erreur
    try:
        other_users_data = [row for row in all_data if str(row.get('User')) != str(user_email)]
    except:
        other_users_data = []

    # 3. Préparer les nouvelles données de l'utilisateur
    new_user_data = []
    for _, row in df_revenus.iterrows():
        r = row.to_dict()
        r['User'] = user_email # On s'assure que le mail est bien là
        # On force la conversion en string pour éviter les bugs JSON
        r['Date'] = str(r['Date'])
        r['Date Paiement'] = str(r['Date Paiement'])
        new_user_data.append(r)
        
    # 4. Fusionner et Réécrire
    final_data = other_users_data + new_user_data
    
    ws.clear()
    if final_data:
        headers = list(final_data[0].keys())
        # Astuce : on réécrit tout
        ws.update([headers] + [list(d.values()) for d in final_data])
    else:
        # Remettre les en-têtes si tout est vide
        ws.append_row(["User", "Date", "Mois", "Source", "Type", "Détails", "Montant Net", "Date Paiement", "Mois Paiement"])
        
# --- 4. LOGIN SYSTEM (Email = ID) ---
if 'user_email' not in st.session_state:
    col_log1, col_log2, col_log3 = st.columns([1,2,1])
    with col_log2:
        st.markdown("## 👋 Bienvenue sur SalaryFlow")
        st.info("Version Cloud Sécurisée")
        email = st.text_input("📧 Entrez votre email pour accéder à votre espace :")
        if st.button("🚀 Accéder à mon Dashboard", type="primary"):
            if "@" in email and "." in email:
                st.session_state['user_email'] = email.strip().lower()
                st.rerun()
            else:
                st.error("Format d'email invalide")
    st.stop()

# --- 5. INITIALISATION SESSION ---
user = st.session_state['user_email']

# Cette condition est CRUCIALE : elle empêche de recharger si c'est déjà fait
if 'data_loaded' not in st.session_state:
    with st.spinner('Synchronisation Cloud...'):
        # On charge depuis le Cloud
        df_cloud_r, df_cloud_c = load_user_data(user)
        
        # On ÉCRASE ce qu'il y a en mémoire (au lieu d'ajouter)
        st.session_state['data_revenus'] = df_cloud_r
        st.session_state['data_charges'] = df_cloud_c
        
        # On marque comme chargé pour ne plus y toucher
        st.session_state['data_loaded'] = True

# --- 6. MOTEUR & INTELLIGENCE ---
def calculer_net(type_c, taux, heures, paniers, charges_pct):
    try:
        t, h = float(taux), float(heures)
        p = float(paniers) if paniers else 0.0
        pct = float(charges_pct) / 100.0 if charges_pct else 0.0
        if type_c == "Intérim": return round(((t * h * 1.21) * 0.78) + p, 2)
        else: return round(((t * h) * (1 - pct)) + p, 2)
    except: return 0.0

def analyser_situation(solde, score, timeline_df):
    tension_date = None
    if not timeline_df.empty:
        for _, row in timeline_df.iterrows():
            if row['Cumul'] < 0:
                tension_date = row['Jour']
                break
    if score < 1 or solde < 0:
        msg = f"Tension le {tension_date}" if tension_date else "Déficit prévu"
        return "🔴 RISQUE DÉTECTÉ", "status-bad", msg, [f"❌ Manque : {abs(solde):.0f}€", "💪 Action : Travaillez plus", "✂️ Action : Coupez les variables"]
    elif score < 1.5 or solde < 200:
        return "🟠 SITUATION FRAGILE", "status-warn", f"Marge faible ({solde:.0f}€)", ["⚠️ Attention aux imprévus", "🎯 Zéro écart ce mois-ci"]
    else:
        return "🟢 SITUATION STABLE", "status-ok", f"Marge : {solde:.0f}€", ["✅ Tout est vert", f"💰 Epargnez {solde*0.5:.0f}€"]

# --- 7. NAVIGATION ---
with st.sidebar:
    st.markdown("## 🚀 Cockpit")
    st.caption(f"👤 Compte : {user}")
    
    if st.button("Déconnexion"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
        
    st.markdown("---")
    menu = st.radio("Menu", ["🔮 Tableau de Bord", "➕ Ajouter un revenu", "💳 Charges & Budgets"])
    
    st.markdown("---")
    val_sim = st.number_input("Simuler entrée (€)", value=float(st.session_state['sim_val']), step=50.0)
    if val_sim != st.session_state['sim_val']:
        st.session_state['sim_val'] = val_sim
        st.rerun()

# --- PAGE 1 : DASHBOARD ---
if menu == "🔮 Tableau de Bord":
    c1, c2, c3 = st.columns([1, 6, 1])
    if c1.button("◀"):
        st.session_state['view_date'] = (st.session_state['view_date'] - timedelta(days=1)).replace(day=1)
        st.rerun()
    
    mois_str = st.session_state['view_date'].strftime("%Y-%m")
    c2.markdown(f"<h2 style='text-align: center; margin:0;'>{st.session_state['view_date'].strftime('%B %Y').capitalize()}</h2>", unsafe_allow_html=True)
    
    if c3.button("▶"):
        st.session_state['view_date'] = (st.session_state['view_date'] + timedelta(days=32)).replace(day=1)
        st.rerun()

    df_r, df_c = st.session_state['data_revenus'], st.session_state['data_charges']
    
    # Calculs
    in_month = 0.0
    revenus_du_mois = pd.DataFrame()
    if not df_r.empty:
        revenus_du_mois = df_r[df_r["Mois Paiement"] == mois_str]
        in_month = revenus_du_mois["Montant Net"].sum()

    entree_totale = in_month + st.session_state['sim_val']
    fixes = df_c[df_c["Groupe"]=="FIXES"]["Montant"].sum()
    total_sorties = fixes + df_c[df_c["Groupe"]=="EPARGNE"]["Montant"].sum() + df_c[df_c["Groupe"]=="VARIABLES"]["Montant"].sum()
    solde = entree_totale - total_sorties
    score = (entree_totale / fixes) if fixes > 0 else 0
    
    # Timeline
    tl_data = []
    for _, r in df_c.iterrows():
        if r['Montant'] > 0: tl_data.append({"Jour": int(r['Jour']), "Nom": r['Intitule'], "Type": "Charge", "Montant": -r['Montant']})
    if not revenus_du_mois.empty:
        for _, r in revenus_du_mois.iterrows():
            try: d = pd.to_datetime(r["Date Paiement"]).day
            except: d = 1
            tl_data.append({"Jour": d, "Nom": r["Source"], "Type": r["Type"], "Montant": r["Montant Net"]})
    if st.session_state['sim_val'] > 0: 
        tl_data.append({"Jour": 15, "Nom": "Simulation", "Type": "Sim", "Montant": st.session_state['sim_val']})
            
    df_tl = pd.DataFrame(tl_data)
    if not df_tl.empty:
        df_tl = df_tl.sort_values("Jour")
        df_tl["Cumul"] = df_tl["Montant"].cumsum()

    etat, css, desc, conseils = analyser_situation(solde, score, df_tl)

    st.markdown(f"""<div class="status-banner {css}"> {etat} <br> <span style="font-size:0.9rem;">{desc}</span></div>""", unsafe_allow_html=True)
    
    col_g, col_k = st.columns([1, 2])
    with col_g:
        st.markdown("### Stabilité")
        st.progress(min(score/3, 1.0))
        st.caption(f"Score : {score:.2f} / 3.0")
        if fixes == 0: st.info("Ajoutez des charges.")

    with col_k:
        k1, k2, k3 = st.columns(3)
        k1.metric("Entrées", f"{entree_totale:,.0f} €")
        k2.metric("Sorties", f"{total_sorties:,.0f} €")
        k3.metric("Solde", f"{solde:,.0f} €")
        st.markdown("### 🧠 Coach")
        for c in conseils: st.markdown(f"<div class='coach-text'>{c}</div>", unsafe_allow_html=True)

    st.markdown("### 🗓️ Timeline")
    if not df_tl.empty:
        st.dataframe(df_tl[["Jour", "Nom", "Type", "Montant", "Cumul"]].style.map(lambda x: 'color:#EF5350;font-weight:bold' if x<0 else 'color:#00E676;font-weight:bold', subset=['Cumul', 'Montant']).format("{:.2f} €", subset=['Montant', 'Cumul']), use_container_width=True, hide_index=True)
    else: st.info("Rien ce mois-ci.")

# ... (Le code de ta Timeline existante est juste au dessus) ...

   # --- NOUVELLE SECTION : GESTIONNAIRE D'HISTORIQUE ---
    st.markdown("---")
    st.subheader("🛠 Gestion & Corrections")
    
    with st.expander("📝 Modifier, Supprimer ou Nettoyer", expanded=True):
        
        # --- 1. GESTION DE LA SIMULATION (INTEGRÉE ICI) ---
        if st.session_state['sim_val'] > 0:
            st.warning(f"⚠️ **Une simulation est active : {st.session_state['sim_val']} €**")
            col_sim_txt, col_sim_btn = st.columns([3, 1])
            col_sim_txt.info("Ce montant s'ajoute à vos calculs mais n'est pas enregistré.")
            if col_sim_btn.button("🗑️ Supprimer la simulation", type="primary"):
                st.session_state['sim_val'] = 0.0
                st.rerun()
            st.markdown("---") # Séparateur visuel
        # --------------------------------------------------

        st.info("Cochez les lignes du tableau ci-dessous pour les supprimer définitivement.")
        
        # SÉCURISATION DES DONNÉES AVANT AFFICHAGE
        df_to_edit = st.session_state['data_revenus'].copy()
        
        if not df_to_edit.empty:
            # Conversion forcée en DATE et NOMBRE pour éviter les bugs
            df_to_edit["Date Paiement"] = pd.to_datetime(df_to_edit["Date Paiement"], dayfirst=True, errors='coerce')
            
            if df_to_edit["Montant Net"].dtype == object:
                df_to_edit["Montant Net"] = df_to_edit["Montant Net"].astype(str).str.replace(",", ".", regex=False)
                df_to_edit["Montant Net"] = pd.to_numeric(df_to_edit["Montant Net"], errors='coerce')

        # TABLEAU ÉDITABLE
        edited_history = st.data_editor(
            df_to_edit,
            num_rows="dynamic",
            use_container_width=True,
            key="history_editor",
            column_config={
                "User": None, 
                "Montant Net": st.column_config.NumberColumn("Net (€)", format="%.2f €", step=0.01),
                "Date Paiement": st.column_config.DateColumn("Date Paiement", format="DD/MM/YYYY"),
                "Source": st.column_config.TextColumn("Source (Client)"),
            },
            hide_index=True
        )

        col_save, col_info = st.columns([1, 3])
        
        if col_save.button("💾 Valider les corrections", type="primary"):
            try:
                # Mise à jour Session
                st.session_state['data_revenus'] = edited_history
                # Mise à jour Cloud
                update_revenus_cloud(user, edited_history)
                
                st.success("✅ Données mises à jour !")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur de sauvegarde : {e}")

# --- PAGE 2 : AJOUT ---
elif menu == "➕ Ajouter un revenu":
    st.header("Nouvelle Rentrée")
    c1, c2 = st.columns(2)
    source = c1.text_input("Source")
    typ = c2.selectbox("Type", ["Intérim", "Micro-Entreprise", "Salaire", "Chomâge", "APL", "Prime d'activité", "Remboursements", "Autre"])
    
    label_date = "Date de la mission" if typ in ["Intérim", "Micro-Entreprise"] else "Date de versement"
    date_mission = st.date_input(label_date, datetime.now())
    
    montant_final = 0.0
    d_pay = date_mission
    st.markdown("---")
    
    if typ == "Intérim":
        cc1, cc2, cc3 = st.columns(3)
        taux = cc1.number_input("Taux", 0.0)
        heures = cc2.number_input("Heures", 0.0)
        paniers = cc3.number_input("Paniers (€)", 0.0)
        montant_final = calculer_net("Intérim", taux, heures, paniers, 0)
        st.write(f"**Net : {montant_final:.2f} €**")
        if date_mission.month == 12: d_pay = datetime(date_mission.year + 1, 1, 12)
        else: d_pay = datetime(date_mission.year, date_mission.month + 1, 12)
        st.caption(f"Paiement auto : {d_pay.strftime('%d/%m/%Y')}")
        
    elif typ == "Micro-Entreprise":
        cc1, cc2, cc3, cc4 = st.columns(4)
        taux = cc1.number_input("Taux/CA", 0.0)
        heures = cc2.number_input("Qté/Jours", 1.0)
        paniers = cc3.number_input("Frais (€)", 0.0)
        charges = cc4.number_input("% Charges", 21.2)
        d_pay = st.date_input("Date Paiement", value=date_mission + timedelta(days=30))
        montant_final = calculer_net("Autre", taux, heures, paniers, charges)
        st.write(f"**Net : {montant_final:.2f} €**")
        
    else:
        montant_final = st.number_input("Net (€)", 0.0)

    if st.button("Valider et Sauvegarder", type="primary"):
        new = {"Date": date_mission.strftime("%d/%m/%Y"), "Mois": date_mission.strftime("%Y-%m"), "Source": source, "Type": typ, "Détails": "App", "Montant Net": montant_final, "Date Paiement": d_pay.strftime("%Y-%m-%d"), "Mois Paiement": d_pay.strftime("%Y-%m")}
        
        # SAUVEGARDE GOOGLE SHEETS
        try:
            save_revenu_cloud(user, new)
            st.session_state['data_revenus'] = pd.concat([st.session_state['data_revenus'], pd.DataFrame([new])], ignore_index=True)
            st.success("✅ Sauvegardé dans le Cloud !")
            st.rerun()
        except Exception as e:
            st.error(f"Erreur de sauvegarde : {e}")

# --- PAGE 3 : CHARGES ---
elif menu == "💳 Charges & Budgets":
    st.header("Mes Charges")
    st.info("Chaque modification est sauvegardée dans votre espace Cloud.")
    
    edited = st.data_editor(
        st.session_state['data_charges'],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "User": None,  # <--- 1. ON CACHE LA COLONNE USER ICI
            "Montant": st.column_config.NumberColumn(
                "Montant (€)",
                min_value=0.0,
                max_value=10000.0,
                step=0.01,
                format="%.2f €"
            ),
            "Jour": st.column_config.NumberColumn(
                "Jour du mois",
                min_value=1,
                max_value=31,
                step=1
            ),
            "Groupe": st.column_config.SelectboxColumn(
                "Type",
                options=["FIXES", "VARIABLES", "EPARGNE"]
            )
        }
    )
    
    if st.button("☁️ Mettre à jour le Cloud", type="primary"):
        try:
            # Nettoyage des virgules (12,50 -> 12.50)
            if "Montant" in edited.columns:
                edited["Montant"] = edited["Montant"].astype(str).str.replace(",", ".", regex=False)
                edited["Montant"] = pd.to_numeric(edited["Montant"], errors='coerce').fillna(0.0)

            # Sauvegarde
            save_charges_cloud(user, edited)
            st.session_state['data_charges'] = edited
            st.success("✅ Vos charges sont à jour !")
            st.rerun()
            
        except Exception as e:
            st.error(f"Erreur : {e}")
