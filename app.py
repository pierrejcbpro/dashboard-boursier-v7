# -*- coding: utf-8 -*-
"""
app.py — v7.2 IA Hybride (CT + LT)
Application principale Streamlit
- Barre latérale profil & résumé
- Navigation vers les 4 pages principales
- Affichage synthétique du profil et du marché
"""

import streamlit as st
from lib import load_profile, save_profile, fetch_all_markets
import pandas as pd
import numpy as np
import datetime

st.set_page_config(page_title="Dashboard IA Hybride", page_icon="🤖", layout="wide")

# =========================
# HEADER
# =========================
st.markdown("""
# 🤖 Dashboard IA Hybride
Bienvenue dans votre assistant d’investissement — version **v7.2 IA Hybride**  
Combinant **analyse court terme (MA20/50)** et **vision long terme (MA120/240)**.
""")

# =========================
# PROFIL
# =========================
with st.sidebar:
    st.markdown("## 👤 Profil IA")
    current = load_profile()
    profil = st.radio(
        "Profil d'investisseur",
        ["Prudent","Neutre","Agressif"],
        index=["Prudent","Neutre","Agressif"].index(current)
    )
    if st.button("💾 Sauvegarder le profil"):
        save_profile(profil)
        st.success("✅ Profil enregistré")

    st.divider()
    st.markdown("### ⚙️ Navigation")
    st.page_link("pages/1_Synthese_Flash.py", label="⚡ Synthèse Flash")
    st.page_link("pages/2_Detail_Indice.py", label="🏦 Détail Indice")
    st.page_link("pages/3_Mon_Portefeuille.py", label="💼 Mon Portefeuille")
    st.page_link("pages/4_Recherche_Universelle.py", label="🔍 Recherche universelle")

    st.divider()
    st.caption("v7.2 — IA Hybride (MA20/50/120/240) © 2025")

# =========================
# SECTION ACCUEIL RAPIDE
# =========================
st.markdown("## 🌐 Aperçu rapide des marchés")

try:
    data = fetch_all_markets(
        [("CAC 40", None), ("DAX", None), ("NASDAQ 100", None)],
        days_hist=360
    )
except Exception:
    data = None

if data is None or data.empty:
    st.warning("Impossible de récupérer les données des indices (connectivité Yahoo Finance).")
else:
    valid = data.dropna(subset=["Close"]).copy()
    for c in ["pct_1d","pct_7d","pct_30d"]:
        if c not in valid.columns: valid[c] = np.nan

    def summary(df, label):
        if df.empty:
            return "—", "—", "—"
        avg = (df["pct_7d"].mean() * 100)
        up = int((df["pct_7d"] > 0).sum())
        down = int((df["pct_7d"] < 0).sum())
        return f"{avg:+.2f}%", up, down

    col1, col2, col3 = st.columns(3)
    for idx, col in zip(["CAC 40","DAX","NASDAQ 100"], [col1,col2,col3]):
        df = valid[valid["Indice"] == idx]
        avg, up, down = summary(df, idx)
        col.metric(f"{idx}", avg, help=f"{up} hausses / {down} baisses")

st.divider()

# =========================
# RAPPEL DES PAGES
# =========================
st.markdown("""
### 📘 Navigation rapide :
| Page | Description |
|------|--------------|
| ⚡ **Synthèse Flash** | Vue d’ensemble multi-marchés (CAC40, DAX, NASDAQ100) avec les meilleures opportunités IA. |
| 🏦 **Détail Indice** | Analyse détaillée par indice, avec IA court/long terme et variations. |
| 💼 **Mon Portefeuille** | Suivi complet de ton portefeuille (PEA / CTO), décisions IA et comparatif benchmark. |
| 🔍 **Recherche universelle** | Recherche libre avec graphique complet (MA20/50/120/240) et actualités. |
""")

st.divider()

st.markdown("""
### 🧠 Ce que fait l’IA v7.2 :
- Combine les signaux **trading** (MA20/50) et **investissement long terme** (MA120/240)  
- Génère une **recommandation IA mixte** :  
  > 📈 Court terme : signal technique  
  > 🌱 Long terme : tendance structurelle  
- Évalue la **proximité d’entrée** avec des repères visuels :
  - 🟢 proche du point d’entrée idéal  
  - ⚠️ à surveiller  
  - 🔴 éloigné / trop cher  
""")

st.info("👉 Clique sur une page dans la barre latérale pour commencer ton analyse.")
