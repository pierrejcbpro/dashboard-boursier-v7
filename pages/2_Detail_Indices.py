# -*- coding: utf-8 -*-
import streamlit as st, numpy as np
from lib import fetch_prices, compute_metrics, trend_label_LT

st.set_page_config(page_title="Détail Indice", page_icon="🏦", layout="wide")
st.title("🏦 Détail Indice — Analyse CT & LT")

index = st.selectbox("Indice", ["CAC 40","DAX","NASDAQ 100"], index=0)
symbol = {"CAC 40":"^FCHI","DAX":"^GDAXI","NASDAQ 100":"^NDX"}[index]
data = fetch_prices([symbol], days=360)
metrics = compute_metrics(data)

if metrics.empty:
    st.warning("Aucune donnée disponible.")
    st.stop()

metrics["LT"] = metrics.apply(trend_label_LT, axis=1)
st.subheader(f"{index} — Tendances CT/LT")
st.dataframe(metrics[["Ticker","Close","MA20","MA50","MA120","MA240","ct_trend_score","lt_trend_score","LT"]],
             use_container_width=True, hide_index=True)
