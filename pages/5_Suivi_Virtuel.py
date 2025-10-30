# -*- coding: utf-8 -*-
"""
v7.8 — Suivi Virtuel IA
- 💹 Portefeuille simulé comparé au CAC 40
- ✏️ Suppression ligne par ligne
- ✅ Données réelles Yahoo Finance (^FCHI)
"""

import streamlit as st, pandas as pd, numpy as np, altair as alt, os
from lib import fetch_prices

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Suivi Virtuel IA", page_icon="💹", layout="wide")
st.title("💹 Suivi Virtuel — Portefeuille IA simulé")

DATA_PATH = "data/suivi_virtuel.json"
os.makedirs("data", exist_ok=True)

if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=[
        "Ticker","Cours (€)","Entrée (€)","Objectif (€)","Stop (€)",
        "Rendement net estimé (%)","Date ajout"
    ]).to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)

try:
    df = pd.read_json(DATA_PATH)
    if not isinstance(df, pd.DataFrame): df = pd.DataFrame()
except Exception:
    df = pd.DataFrame()

if df.empty:
    st.info("Aucune ligne dans ton portefeuille virtuel.")
    st.stop()

# ---------------- TABLEAU INTERACTIF ----------------
st.subheader("📋 Lignes suivies (supprimables)")

# Ajout bouton suppression ligne par ligne
delete_options = st.multiselect("🗑 Sélectionne les lignes à supprimer :", df["Ticker"].tolist())
if st.button("Supprimer la sélection"):
    df = df[~df["Ticker"].isin(delete_options)]
    df.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
    st.success(f"✅ Lignes supprimées : {', '.join(delete_options)}")
    st.rerun()

st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()

# ---------------- MÉTRIQUES ----------------
mean_perf = df["Rendement net estimé (%)"].mean()
best = df.loc[df["Rendement net estimé (%)"].idxmax()]
worst = df.loc[df["Rendement net estimé (%)"].idxmin()]

col1, col2, col3 = st.columns(3)
col1.metric("Perf. moyenne", f"{mean_perf:+.2f}%")
col2.metric("Meilleure ligne", f"{best['Ticker']} {best['Rendement net estimé (%)']:+.2f}%")
col3.metric("Pire ligne", f"{worst['Ticker']} {worst['Rendement net estimé (%)']:+.2f}%")

st.divider()

# ---------------- GRAPHE ----------------
st.subheader("📈 Évolution du portefeuille virtuel vs CAC 40")

tickers = df["Ticker"].dropna().unique().tolist()
if not tickers:
    st.info("Aucun ticker valide à suivre.")
    st.stop()

benchmark = "^FCHI"
symbols = tickers + [benchmark]

hist = fetch_prices(symbols, days=90)
if hist.empty or "Date" not in hist.columns:
    st.warning("Impossible de charger les historiques de prix.")
    st.stop()

hist = hist.copy().sort_values(["Ticker","Date"])
hist["Base100"] = hist.groupby("Ticker")["Close"].transform(lambda s: s / s.iloc[0] * 100)

pf_curve = hist[hist["Ticker"].isin(tickers)].groupby("Date")["Base100"].mean().reset_index()
bmk_curve = hist[hist["Ticker"] == benchmark][["Date","Base100"]].rename(columns={"Base100":"CAC 40"})

merged = pf_curve.merge(bmk_curve, on="Date", how="inner").rename(columns={"Base100":"Portefeuille"})
merged = merged.melt("Date", var_name="Type", value_name="Valeur")

try:
    perf_port = merged[merged["Type"]=="Portefeuille"]["Valeur"].iloc[-1] - 100
    perf_cac = merged[merged["Type"]=="CAC 40"]["Valeur"].iloc[-1] - 100
    diff = perf_port - perf_cac
    msg = (
        f"✅ Surperformance : {diff:+.2f}% au-dessus du CAC 40"
        if diff > 0 else
        f"⚠️ Sous-performance : {abs(diff):.2f}% en dessous du CAC 40"
    )
    st.markdown(f"**{msg}**")
except Exception:
    pass

chart = (
    alt.Chart(merged)
    .mark_line()
    .encode(
        x="Date:T",
        y=alt.Y("Valeur:Q", title="Base 100"),
        color=alt.Color("Type:N", scale=alt.Scale(scheme="category10")),
        tooltip=["Date:T","Type:N","Valeur:Q"]
    )
    .properties(height=400)
)
st.altair_chart(chart, use_container_width=True)
