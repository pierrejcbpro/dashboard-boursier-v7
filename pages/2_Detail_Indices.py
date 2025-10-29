# -*- coding: utf-8 -*-
"""
v7.4 — Détail Indice
Affiche les moyennes MA20/50/120/240, la tendance CT & LT et la décision IA.
"""

import streamlit as st, pandas as pd
from lib import fetch_all_markets, trend_label_LT, decision_label_from_row

st.set_page_config(page_title="Détail Indice", page_icon="🏦", layout="wide")
st.title("🏦 Détail par Indice — IA complète CT + LT")

indice = st.selectbox("Choisis un indice :", ["CAC 40", "DAX", "NASDAQ 100"], index=0)
markets = [(indice, None)]
data = fetch_all_markets(markets, days_hist=360)

if data.empty:
    st.warning("Aucune donnée disponible pour cet indice.")
    st.stop()

data["LT"] = data.apply(trend_label_LT, axis=1)
data["Décision IA"] = data.apply(decision_label_from_row, axis=1)

data = data.rename(columns={
    "name": "Nom",
    "Close": "Cours (€)",
    "ct_trend_score": "Score CT",
    "lt_trend_score": "Score LT"
})

st.markdown(f"### {indice} — Détail complet IA")
st.dataframe(
    data[["Nom", "Ticker", "Cours (€)", "MA20", "MA50", "MA120", "MA240", "Score CT", "Score LT", "LT", "Décision IA"]],
    use_container_width=True,
    hide_index=True
)
