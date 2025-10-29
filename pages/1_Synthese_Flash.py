# -*- coding: utf-8 -*-
import streamlit as st, pandas as pd, numpy as np
from lib import fetch_prices, compute_metrics, trend_label_LT

st.set_page_config(page_title="Synthèse Flash", page_icon="⚡", layout="wide")
st.title("⚡ Synthèse Flash — IA Court & Long Terme")

MARKETS = {
    "CAC 40": "^FCHI",
    "DAX": "^GDAXI",
    "NASDAQ 100": "^NDX"
}

st.sidebar.markdown("### Indice à afficher")
index = st.sidebar.selectbox("Indice", list(MARKETS.keys()), index=0)

tickers = [MARKETS[index]]
data = fetch_prices(tickers, days=360)
metrics = compute_metrics(data)

if metrics.empty:
    st.warning("Aucune donnée disponible.")
    st.stop()

metrics["LT"] = metrics.apply(trend_label_LT, axis=1)

st.markdown(f"### {index} — Indicateurs CT/LT")
st.dataframe(
    metrics[["Ticker","Close","MA20","MA50","MA120","MA240","ct_trend_score","lt_trend_score","LT"]]
        .rename(columns={
            "Ticker":"Symbole","Close":"Cours (€)",
            "ct_trend_score":"Tendance CT","lt_trend_score":"Tendance LT"
        }),
    use_container_width=True, hide_index=True
)
