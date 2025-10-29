# -*- coding: utf-8 -*-
"""
v7.4 — Recherche Universelle IA
Combine analyse CT (MA20/50) et LT (MA120/240).
"""

import streamlit as st, numpy as np
from lib import fetch_prices, compute_metrics, trend_label_LT, decision_label_from_row

st.set_page_config(page_title="Recherche universelle", page_icon="🔍", layout="wide")
st.title("🔍 Recherche universelle — Analyse IA CT + LT")

ticker = st.text_input("Entrer le ticker Yahoo (ex: AIR.PA, AAPL, NVDA)", "")
if not ticker:
    st.stop()

# Récupération des données
data = fetch_prices([ticker], days=360)
metrics = compute_metrics(data)
if metrics.empty:
    st.warning("Aucune donnée disponible pour ce ticker.")
    st.stop()

row = metrics.iloc[0]
lt = trend_label_LT(row)
decision = decision_label_from_row(row)

st.markdown(f"## {ticker}")
st.metric("Cours actuel", f"{row['Close']:.2f} €")

col1, col2 = st.columns(2)
with col1:
    st.subheader("📈 Court Terme (MA20/MA50)")
    st.write(f"MA20 : {row['MA20']:.2f} € — MA50 : {row['MA50']:.2f} €")
with col2:
    st.subheader("🔭 Long Terme (MA120/MA240)")
    st.write(f"MA120 : {row['MA120']:.2f} € — MA240 : {row['MA240']:.2f} €")
    st.write(f"Tendance LT : **{lt}**")

if lt == "🌱":
    st.success("Tendance long terme haussière — configuration favorable.")
elif lt == "🌧":
    st.error("Tendance long terme baissière — prudence recommandée.")
else:
    st.info("Tendance neutre ou indécise.")

st.divider()
st.markdown(f"### 🧠 Décision IA globale : {decision}")
