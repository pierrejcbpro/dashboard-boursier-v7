# -*- coding: utf-8 -*-
import streamlit as st, pandas as pd, numpy as np, altair as alt
from lib import fetch_all_markets, select_top_actions, style_variations

st.set_page_config(page_title="Détail Indice", page_icon="🏦", layout="wide")
st.title("🏦 Détail par indice — IA Hybride")

indice = st.sidebar.selectbox("Indice", ["CAC 40","DAX","NASDAQ 100"], index=0)
periode = st.sidebar.radio("Période", ["Jour","7 jours","30 jours"], index=0)
value_col = {"Jour":"pct_1d","7 jours":"pct_7d","30 jours":"pct_30d"}[periode]

MARKETS=[(indice, None)]
data = fetch_all_markets(MARKETS, days_hist=360)
if data.empty:
    st.warning("Données indisponibles pour cet indice.")
    st.stop()

valid = data.dropna(subset=["Close"]).copy()

st.subheader(f"Composants — {indice}")
show_cols = ["Ticker","name","Close","pct_1d","pct_7d","pct_30d","MA20","MA50","MA120","MA240","trend_score","lt_trend_score"]
for c in show_cols:
    if c not in valid.columns: valid[c]=np.nan
tbl = valid[show_cols].copy()
tbl.rename(columns={
    "name":"Société","Close":"Cours (€)",
    "pct_1d":"1j (%)","pct_7d":"7j (%)","pct_30d":"30j (%)",
    "trend_score":"Tendance CT","lt_trend_score":"Tendance LT"
}, inplace=True)
tbl["1j (%)"]= (tbl["1j (%)"]*100).round(2)
tbl["7j (%)"]= (tbl["7j (%)"]*100).round(2)
tbl["30j (%)"]=(tbl["30j (%)"]*100).round(2)
tbl["Cours (€)"]=tbl["Cours (€)"].round(2)

st.dataframe(style_variations(tbl, ["1j (%)","7j (%)","30j (%)"]), use_container_width=True, hide_index=True)

st.divider()

# Top / Flop de l'indice
st.subheader(f"Top/Flop — {indice} ({periode})")
def prep(df, asc=False, n=10):
    if df.empty: return pd.DataFrame()
    cols=["Ticker","name","Close",value_col]
    for c in cols:
        if c not in df.columns: df[c]=np.nan
    out=df.sort_values(value_col, ascending=asc).head(n).copy()
    out.rename(columns={"name":"Société","Close":"Cours (€)"}, inplace=True)
    out["Variation %"]=(out[value_col]*100).round(2)
    out["Cours (€)"]=out["Cours (€)"].round(2)
    return out[["Société","Ticker","Cours (€)","Variation %"]]

c1,c2=st.columns(2)
with c1:
    top=prep(valid, asc=False, n=10)
    st.dataframe(style_variations(top, ["Variation %"]), use_container_width=True, hide_index=True)
with c2:
    flop=prep(valid, asc=True, n=10)
    st.dataframe(style_variations(flop, ["Variation %"]), use_container_width=True, hide_index=True)

st.divider()

# Sélection IA spécifique à l'indice
st.subheader(f"🚀 Sélection IA — {indice}")
top_actions=select_top_actions(valid, n=10)
if top_actions.empty:
    st.info("Aucune opportunité claire sur cet indice.")
else:
    def color_proximity(v):
        if pd.isna(v): return ""
        if abs(v) <= 2: return "background-color:#e6f4ea; color:#0b8043"
        if abs(v) <= 5: return "background-color:#fff8e1; color:#a67c00"
        return "background-color:#ffebee; color:#b71c1c"
    st.dataframe(top_actions.style.applymap(color_proximity, subset=["Proximité (%)"]),
                 use_container_width=True, hide_index=True)
