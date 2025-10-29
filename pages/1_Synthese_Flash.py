# -*- coding: utf-8 -*-
"""
v7.6 — Synthèse Flash IA
Vue globale multi-marchés (CAC40, DAX, NASDAQ100)
avec calculs IA combinés (MA20/50 + MA120/240).
"""

import streamlit as st
import pandas as pd
from lib import (
    fetch_all_markets, get_profile_params, select_top_actions,
    highlight_near_entry_adaptive, color_proximity_adaptive
)

# --- Config
st.set_page_config(page_title="Synthèse Flash IA", page_icon="🌍", layout="wide")
st.title("🌍 Synthèse Flash IA — Multi Marchés")

# --- Choix de l’utilisateur
profil = st.session_state.get("profil", "Neutre")
params = get_profile_params(profil)

st.sidebar.header("⚙️ Paramètres")
indices = st.sidebar.multiselect(
    "Indices à inclure",
    ["CAC 40", "DAX", "NASDAQ 100"],
    default=["CAC 40", "DAX", "NASDAQ 100"]
)
nb_top = st.sidebar.slider("Nombre de valeurs à afficher (TOP N)", 5, 30, 10)

# --- Chargement
st.info("Chargement des marchés…")
data = fetch_all_markets([(i, "") for i in indices], days_hist=240)

if data.empty:
    st.error("Aucune donnée disponible (vérifie la connectivité Yahoo).")
    st.stop()

# --- Sélection IA
st.divider()
st.header("🚀 Sélection IA — Opportunités idéales (TOP 10)")
sel = select_top_actions(data, profile=profil, n=nb_top, include_proximity=True)

if sel.empty:
    st.warning("Aucune action répondant aux critères IA.")
    st.stop()

# --- Affichage
st.dataframe(
    sel.style.apply(highlight_near_entry_adaptive, axis=1)
             .applymap(color_proximity_adaptive, subset=["Proximité (%)"]),
    use_container_width=True,
    hide_index=True
)

# --- Téléchargement
csv = sel.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Exporter les résultats", csv, "synthese_flash.csv", "text/csv")
