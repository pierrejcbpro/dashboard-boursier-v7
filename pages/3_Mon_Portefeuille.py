# -*- coding: utf-8 -*-
import streamlit as st, pandas as pd, numpy as np, os, json
from lib import fetch_prices, compute_metrics, trend_label_LT

st.set_page_config(page_title="Mon Portefeuille", page_icon="💼", layout="wide")
st.title("💼 Mon Portefeuille — IA Hybride CT + LT")

DATA_PATH = "data/portfolio.json"
if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=["Ticker","Type","Qty","PRU","Name"]).to_json(DATA_PATH, orient="records")

try:
    pf = pd.read_json(DATA_PATH)
except Exception:
    st.warning("Portefeuille vide.")
    pf = pd.DataFrame(columns=["Ticker","Type","Qty","PRU","Name"])

if pf.empty:
    st.info("Ajoute des actions dans ton portefeuille.")
    st.stop()

tickers = pf["Ticker"].dropna().unique().tolist()
data = fetch_prices(tickers, days=360)
metrics = compute_metrics(data)
if metrics.empty:
    st.warning("Données introuvables.")
    st.stop()

merged = pf.merge(metrics, on="Ticker", how="left")
merged["LT"] = merged.apply(trend_label_LT, axis=1)

st.dataframe(
    merged[["Type","Name","Ticker","Close","MA20","MA50","MA120","MA240","ct_trend_score","lt_trend_score","LT"]]
        .rename(columns={"Close":"Cours (€)","Name":"Nom"}),
    use_container_width=True, hide_index=True
)
