# -*- coding: utf-8 -*-
"""
v7.4 — Synthèse Flash IA (CT+LT)
Affiche : MA20/50/120/240, tendance CT/LT, décision IA.
"""

import streamlit as st, pandas as pd, numpy as np
from lib import fetch_all_markets, trend_label_LT, decision_label_from_row

st.set_page_config(page_title="Synthèse Flash", page_icon="⚡", layout="wide")
st.title("⚡ Synthèse Flash — Vue globale IA (CT + LT)")

# Choix multi-marchés
markets = [
    ("CAC 40", None),
    ("DAX", None),
    ("NASDAQ 100", None),
    ("LS Exchange", None)
]

# Chargement
data = fetch_all_markets(markets, days_hist=360)
if data.empty:
    st.warning("Aucune donnée disponible (vérifie la connexion Internet).")
    st.stop()

# Calcul LT
data["LT"] = data.apply(trend_label_LT, axis=1)
data["Décision IA"] = data.apply(decision_label_from_row, axis=1)

# Nettoyage
cols = ["Indice", "name", "Ticker", "Close", "MA20", "MA50", "MA120", "MA240", "ct_trend_score", "lt_trend_score", "LT", "Décision IA"]
data = data[cols].rename(columns={
    "name": "Nom",
    "Close": "Cours (€)",
    "ct_trend_score": "Score CT",
    "lt_trend_score": "Score LT"
})

# Affichage
st.markdown("### 🔍 Analyse multi-marchés (CAC40, DAX, NASDAQ, LS Exchange)")
st.dataframe(data.sort_values("Indice"), use_container_width=True, hide_index=True)

# Analyse visuelle des tendances globales
nb_haussier = (data["LT"] == "🌱").sum()
nb_baissier = (data["LT"] == "🌧").sum()
nb_neutre = (data["LT"] == "⚖️").sum()
st.markdown(f"**🌱 Haussières : {nb_haussier}** · **⚖️ Neutres : {nb_neutre}** · **🌧 Baissières : {nb_baissier}**")
