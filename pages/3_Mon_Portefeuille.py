# -*- coding: utf-8 -*-
"""
v7.4 — Mon Portefeuille
Intègre les tendances CT+LT et la décision IA combinée.
"""

import os, json, numpy as np, pandas as pd, streamlit as st
from lib import fetch_prices, compute_metrics, trend_label_LT, decision_label_from_row

st.set_page_config(page_title="Mon Portefeuille", page_icon="💼", layout="wide")
st.title("💼 Mon Portefeuille — Analyse CT + LT")

DATA_PATH = "data/portfolio.json"
os.makedirs("data", exist_ok=True)
if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=["Ticker", "Type", "Qty", "PRU", "Name"]).to_json(DATA_PATH, orient="records", indent=2)

try:
    pf = pd.read_json(DATA_PATH)
except Exception:
    pf = pd.DataFrame(columns=["Ticker", "Type", "Qty", "PRU", "Name"])

if pf.empty:
    st.info("Ajoute des actions dans ton portefeuille pour commencer.")
    st.stop()

# Récupération des prix
tickers = pf["Ticker"].dropna().unique().tolist()
data = fetch_prices(tickers, days=360)
metrics = compute_metrics(data)
if metrics.empty:
    st.warning("Impossible de récupérer les données de marché.")
    st.stop()

merged = pf.merge(metrics, on="Ticker", how="left")
merged["LT"] = merged.apply(trend_label_LT, axis=1)
merged["Décision IA"] = merged.apply(decision_label_from_row, axis=1)

# Table principale
out = merged.rename(columns={
    "Name": "Nom",
    "Close": "Cours (€)",
    "ct_trend_score": "Score CT",
    "lt_trend_score": "Score LT"
})[
    ["Type", "Nom", "Ticker", "Cours (€)", "Qty", "PRU", "MA20", "MA50", "MA120", "MA240", "Score CT", "Score LT", "LT", "Décision IA"]
]

st.dataframe(out, use_container_width=True, hide_index=True)

# Synthèse globale
gain_total = (out["Cours (€)"] - out["PRU"]).fillna(0) * out["Qty"]
st.markdown(f"### 💰 Synthèse Globale")
st.write(f"Valeur totale estimée : **{(out['Cours (€)'] * out['Qty']).sum():,.2f} €**")
st.write(f"Gain latent : **{gain_total.sum():+.2f} €**")
