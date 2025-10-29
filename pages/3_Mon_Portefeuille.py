# -*- coding: utf-8 -*-
"""
v7.6 — Mon Portefeuille (analyse IA + long terme)
"""

import os, json, numpy as np, pandas as pd, altair as alt, streamlit as st
from lib import (
    fetch_prices, compute_metrics, price_levels_from_row, decision_label_combined,
    style_variations, company_name_from_ticker, get_profile_params,
    resolve_identifier, find_ticker_by_name, load_mapping, save_mapping,
    maybe_guess_yahoo, highlight_near_entry_adaptive, color_proximity_adaptive
)

# --- Config
st.set_page_config(page_title="Mon Portefeuille", page_icon="💼", layout="wide")
st.title("💼 Mon Portefeuille — PEA & CTO")

DATA_PATH = "data/portfolio.json"
os.makedirs("data", exist_ok=True)
if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=["Ticker", "Type", "Qty", "PRU", "Name"]).to_json(DATA_PATH, orient="records", indent=2)

pf = pd.read_json(DATA_PATH)

# --- Éditeur
st.subheader("📝 Composition du portefeuille")
edited = st.data_editor(pf, num_rows="dynamic", use_container_width=True, hide_index=True)
if st.button("💾 Enregistrer"):
    edited.to_json(DATA_PATH, orient="records", indent=2)
    st.success("Sauvegardé."); st.rerun()

if edited.empty:
    st.info("Ajoute une action pour commencer.")
    st.stop()

# --- Analyse IA
tickers = edited["Ticker"].dropna().unique().tolist()
hist = fetch_prices(tickers, days=240)
met = compute_metrics(hist)
merged = edited.merge(met, on="Ticker", how="left")

profil = st.session_state.get("profil", "Neutre")
volmax = get_profile_params(profil)["vol_max"]

rows = []
for _, r in merged.iterrows():
    px = float(r.get("Close", np.nan))
    qty = float(r.get("Qty", 0))
    pru = float(r.get("PRU", np.nan))
    name = r.get("Name") or company_name_from_ticker(r.get("Ticker"))
    val = px * qty if np.isfinite(px) else np.nan
    gain = (px - pru) * qty if np.isfinite(px) and np.isfinite(pru) else np.nan
    perf = ((px / pru) - 1) * 100 if (np.isfinite(px) and pru > 0) else np.nan
    dec = decision_label_combined(r, held=True, vol_max=volmax)
    rows.append({
        "Nom": name, "Ticker": r["Ticker"], "Cours (€)": px, "Qté": qty, "PRU (€)": pru,
        "Valeur (€)": val, "Gain/Perte (€)": gain, "Perf%": perf, "Décision IA": dec
    })

out = pd.DataFrame(rows)
st.dataframe(
    out.style.apply(highlight_near_entry_adaptive, axis=1)
             .applymap(color_proximity_adaptive, subset=["Perf%"]),
    use_container_width=True, hide_index=True
)

st.divider()
st.subheader("📊 Synthèse")
st.metric("Valeur totale (€)", f"{out['Valeur (€)'].sum():,.2f}")
st.metric("Gain/Perte (€)", f"{out['Gain/Perte (€)'].sum():+.2f}")
