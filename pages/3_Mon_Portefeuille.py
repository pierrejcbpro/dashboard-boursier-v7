# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime

from lib import (
    load_profile, get_profile_params,
    fetch_prices, compute_metrics,
    price_levels_from_row, decision_label_strict,
    color_proximity_adaptive, highlight_near_entry_adaptive
)

# =========================
# TITRE & PARAMÈTRES
# =========================
st.set_page_config(page_title="📊 Mon Portefeuille", layout="wide")
st.title("📈 Suivi du Portefeuille")

DATA_DIR = "data"
PORTFOLIO_PATH = os.path.join(DATA_DIR, "portefeuille.csv")
os.makedirs(DATA_DIR, exist_ok=True)

# =========================
# CHARGEMENT PORTFOLIO CSV
# =========================
if os.path.exists(PORTFOLIO_PATH):
    portefeuille = pd.read_csv(PORTFOLIO_PATH)
else:
    portefeuille = pd.DataFrame(columns=["Ticker", "Quantité", "PRU"])

if portefeuille.empty:
    st.info("Aucune ligne dans le portefeuille. Ajoutez vos positions via le menu ⚙️.")
    st.stop()

portefeuille["Ticker"] = portefeuille["Ticker"].astype(str).str.upper()

# =========================
# PROFIL UTILISATEUR
# =========================
profil = load_profile()
params = get_profile_params(profil)
st.sidebar.markdown(f"**Profil IA actif :** `{profil}`  \nVolatilité max tolérée : **{params['vol_max']*100:.1f}%**")

# =========================
# RÉCUPÉRATION DES DONNÉES MARCHÉ
# =========================
tickers = portefeuille["Ticker"].tolist()
data = fetch_prices(tickers, days=240)
if data.empty:
    st.warning("Impossible de récupérer les données Yahoo Finance.")
    st.stop()

met = compute_metrics(data)
if met.empty:
    st.warning("Aucune donnée exploitable pour les tickers du portefeuille.")
    st.stop()

# Fusion
pf = portefeuille.merge(met, left_on="Ticker", right_on="Ticker", how="left")

# =========================
# CALCULS IA & NIVEAUX
# =========================
pf["Décision IA"] = pf.apply(lambda r: decision_label_strict(r, profile=profil, held=True), axis=1)

def _calc_levels(r):
    lev = price_levels_from_row(r, profil)
    if not lev: return pd.Series({"Entrée (€)":np.nan,"Objectif (€)":np.nan,"Stop (€)":np.nan})
    return pd.Series({
        "Entrée (€)": lev["entry"],
        "Objectif (€)": lev["target"],
        "Stop (€)": lev["stop"]
    })

pf = pd.concat([pf, pf.apply(_calc_levels, axis=1)], axis=1)

# P&L, Potentiel, Proximité
pf["Cours (€)"] = pf["Close"].round(2)
pf["Investi (€)"] = pf["Quantité"] * pf["PRU"]
pf["Valeur (€)"] = pf["Quantité"] * pf["Cours (€)"]
pf["P&L (€)"] = pf["Valeur (€)"] - pf["Investi (€)"]
pf["P&L (%)"] = (pf["Valeur (€)"]/pf["Investi (€)"] - 1)*100

pf["Potentiel (€)"] = pf["Objectif (€)"] - pf["Cours (€)"]
pf["Proximité (%)"] = ((pf["Cours (€)"]/pf["Entrée (€)"]) - 1)*100

# =========================
# AFFICHAGE DU PORTEFEUILLE
# =========================
st.subheader("💼 Positions détenues")

cols_aff = [
    "Ticker","Quantité","PRU","Cours (€)","Investi (€)","Valeur (€)","P&L (€)","P&L (%)",
    "MA20","MA50","MA120","MA240","ATR14",
    "Décision IA","Entrée (€)","Objectif (€)","Stop (€)","Proximité (%)","Potentiel (€)"
]

for c in cols_aff:
    if c not in pf.columns: pf[c] = np.nan

view = pf[cols_aff].copy()

# Format
view["P&L (€)"] = view["P&L (€)"].round(2)
view["P&L (%)"] = view["P&L (%)"].round(2)
view["Proximité (%)"] = view["Proximité (%)"].round(2)
view["Potentiel (€)"] = view["Potentiel (€)"].round(2)

# Couleurs et surbrillance
st.dataframe(
    view.style
        .apply(highlight_near_entry_adaptive, axis=1)
        .format({
            "PRU":"{:.2f}","Cours (€)":"{:.2f}",
            "Investi (€)":"{:.0f}","Valeur (€)":"{:.0f}",
            "P&L (€)":"{:.0f}","P&L (%)":"{:.2f}%",
            "Entrée (€)":"{:.2f}","Objectif (€)":"{:.2f}",
            "Stop (€)":"{:.2f}","Proximité (%)":"{:.2f}%",
            "Potentiel (€)":"{:.2f}"
        })
)

# =========================
# SYNTHÈSE GLOBALE
# =========================
col1, col2, col3 = st.columns(3)
val_tot = pf["Valeur (€)"].sum()
inv_tot = pf["Investi (€)"].sum()
pnl_tot = val_tot - inv_tot
perf_tot = (val_tot/inv_tot - 1)*100 if inv_tot>0 else 0

col1.metric("Valeur totale", f"{val_tot:,.0f} €")
col2.metric("P&L total", f"{pnl_tot:,.0f} €", f"{perf_tot:.2f} %")
col3.metric("Nb titres suivis", len(pf))

# =========================
# GRAPHIQUE SIMPLE
# =========================
try:
    import plotly.express as px
    chart = pf.copy()
    chart["P&L (%)"] = chart["P&L (%)"].round(2)
    fig = px.bar(chart, x="Ticker", y="P&L (%)", color="Décision IA",
                 color_discrete_map={
                     "🟢 Acheter":"#34a853",
                     "🟠 Garder":"#fbbc04",
                     "🔴 Vendre":"#ea4335",
                     "👁️ Surveiller":"#999999",
                     "🚫 Éviter":"#666666"
                 },
                 title="Performance % par titre")
    fig.update_layout(showlegend=True, height=400)
    st.plotly_chart(fig, use_container_width=True)
except Exception:
    pass

# =========================
# SAUVEGARDE CSV
# =========================
if st.button("💾 Sauvegarder le portefeuille"):
    pf[["Ticker","Quantité","PRU"]].to_csv(PORTFOLIO_PATH, index=False)
    st.success("Portefeuille mis à jour et sauvegardé.")
