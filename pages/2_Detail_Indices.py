# -*- coding: utf-8 -*-
"""
v7.6 — Détail par Indice
Analyse complète d’un indice (ST + LT + IA).
"""

import streamlit as st
import pandas as pd
from lib import (
    members, fetch_prices, compute_metrics, get_profile_params,
    decision_label_combined, style_variations
)

# --- Config
st.set_page_config(page_title="Détail Indice", page_icon="📊", layout="wide")
st.title("📊 Détail par Indice")

indice = st.sidebar.selectbox("Indice", ["CAC 40", "DAX", "NASDAQ 100"], index=0)
profil = st.session_state.get("profil", "Neutre")

mem = members(indice)
if mem.empty:
    st.error("Impossible de charger les constituants.")
    st.stop()

tickers = mem["ticker"].tolist()
data = fetch_prices(tickers, days=240)
if data.empty:
    st.error("Pas de données Yahoo pour cet indice.")
    st.stop()

df = compute_metrics(data).merge(mem, left_on="Ticker", right_on="ticker", how="left")
df["Décision IA"] = df.apply(lambda r: decision_label_combined(r, held=False,
                                  vol_max=get_profile_params(profil)["vol_max"]), axis=1)

# Ajout d'icônes de tendance
df["ST"] = df["trend_score"].apply(lambda v: "📈" if v > 0 else ("📉" if v < 0 else "⚖️"))
df["LT"] = df["lt_trend_score"].apply(lambda v: "🌱" if v > 0 else ("🌧" if v < 0 else "⚖️"))

cols = ["Ticker", "name", "Close", "MA20", "MA50", "MA120", "MA240",
        "ST", "LT", "pct_7d", "pct_30d", "Décision IA"]
st.dataframe(style_variations(df[cols], ["pct_7d", "pct_30d"]), use_container_width=True, hide_index=True)
