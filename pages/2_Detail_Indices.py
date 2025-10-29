# -*- coding: utf-8 -*-
import streamlit as st, pandas as pd, numpy as np
from lib import members, fetch_prices, compute_metrics, style_variations, decision_label_combined, get_profile_params, load_profile, save_profile

st.set_page_config(page_title="Détail Indice", page_icon="🧩", layout="wide")
st.title("🧩 Détail par indice — CT & LT")

indice = st.selectbox("Indice", ["CAC 40"], index=0)
profil = st.sidebar.radio("Profil IA", ["Prudent","Neutre","Agressif"], 
                          index=["Prudent","Neutre","Agressif"].index(load_profile()))
if st.sidebar.button("💾 Mémoriser le profil"): save_profile(profil); st.sidebar.success("Profil sauvegardé.")

mem = members(indice)
if mem.empty:
    st.warning("Impossible de charger la composition de l'indice."); st.stop()

tickers = mem["ticker"].dropna().unique().tolist()
px = fetch_prices(tickers, days=260)
met = compute_metrics(px)
df = met.merge(mem, left_on="Ticker", right_on="ticker", how="left")

if df.empty:
    st.warning("Données indisponibles."); st.stop()

# Décision combinée
volmax = get_profile_params(profil)["vol_max"]
df["Décision IA"] = df.apply(lambda r: decision_label_combined(r, held=False, vol_max=volmax), axis=1)
df["LT"] = df["trend_lt"].apply(lambda v: "🌱" if v>0 else ("🌧" if v<0 else "⚖️"))
df["Cours (€)"] = df["Close"].astype(float).round(2)
for c in ["pct_1d","pct_7d","pct_30d"]: 
    df[c] = (df[c]*100).round(2)

cols = ["name","ticker","Cours (€)","pct_1d","pct_7d","pct_30d","LT","score_ia","Décision IA"]
df = df[cols].rename(columns={"name":"Société","ticker":"Ticker","pct_1d":"1j %","pct_7d":"7j %","pct_30d":"30j %","score_ia":"Score IA"})

st.dataframe(
    style_variations(df, ["1j %","7j %","30j %"]),
    use_container_width=True, hide_index=True
)
