# -*- coding: utf-8 -*-
import streamlit as st, numpy as np
from lib import fetch_prices, compute_metrics, trend_label_LT

st.set_page_config(page_title="Recherche universelle", page_icon="🔍", layout="wide")
st.title("🔍 Recherche universelle — IA Court & Long Terme")

query = st.text_input("Nom ou Ticker Yahoo (ex: AIR.PA, AAPL, NVDA)", "")
if not query:
    st.stop()

data = fetch_prices([query], days=360)
metrics = compute_metrics(data)
if metrics.empty:
    st.warning("Aucune donnée disponible.")
    st.stop()

row = metrics.iloc[0]
lt = trend_label_LT(row)
st.markdown(f"## {query}")
st.metric("Cours", f"{row['Close']:.2f} €")

# --- Nouvelle section LT ---
st.subheader("🔭 Analyse long terme (MA120 / MA240)")
st.write(f"MA120 : {row['MA120']:.2f} € — MA240 : {row['MA240']:.2f} €")
st.write(f"Tendance long terme : **{lt}**")

if lt == "🌱":
    st.success("Tendance long terme haussière — configuration favorable à l’investissement.")
elif lt == "🌧":
    st.error("Tendance long terme baissière — prudence recommandée.")
else:
    st.info("Tendance neutre ou indécise.")
