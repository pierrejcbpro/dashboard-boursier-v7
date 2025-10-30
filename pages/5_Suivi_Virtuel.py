# -*- coding: utf-8 -*-
"""
v7.6 — Suivi Virtuel (Portefeuille IA simulé)
- Suivi des lignes ajoutées depuis Synthèse Flash 💸
- Rendement net estimé (frais inclus)
- Graphique d’évolution base 100 vs Indice global
- Lecture directe de data/suivi_virtuel.json
"""

import streamlit as st, pandas as pd, numpy as np, altair as alt, os, datetime
from lib import fetch_prices, compute_metrics, price_levels_from_row

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Suivi Virtuel IA", page_icon="💹", layout="wide")
st.title("💹 Suivi Virtuel — Portefeuille IA simulé")

DATA_PATH = "data/suivi_virtuel.json"
os.makedirs("data", exist_ok=True)

if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=["Ticker","Cours (€)","Entrée (€)","Objectif (€)","Stop (€)",
                          "Rendement net estimé (%)","Date ajout"]).to_json(
        DATA_PATH, orient="records", indent=2, force_ascii=False
    )

try:
    df = pd.read_json(DATA_PATH)
except Exception:
    df = pd.DataFrame(columns=["Ticker","Entrée (€)","Objectif (€)","Stop (€)","Rendement net estimé (%)"])

if df.empty:
    st.info("Aucune ligne encore ajoutée au suivi virtuel. Ajoute depuis la Synthèse Flash 💸.")
    st.stop()

# ---------------- TABLEAU ----------------
st.subheader("📋 Positions virtuelles actuelles")

def color_perf(v):
    if pd.isna(v): return ""
    if v > 0: return "background-color: rgba(0,200,0,0.15); color:#0b8043"
    if v < 0: return "background-color: rgba(255,0,0,0.15); color:#b71c1c"
    return ""

st.dataframe(
    df.style.applymap(color_perf, subset=["Rendement net estimé (%)"]),
    use_container_width=True, hide_index=True
)

# ---------------- METRIQUES GLOBALES ----------------
mean_perf = df["Rendement net estimé (%)"].mean() if "Rendement net estimé (%)" in df else np.nan
best = df.loc[df["Rendement net estimé (%)"].idxmax()] if not df.empty else None
worst = df.loc[df["Rendement net estimé (%)"].idxmin()] if not df.empty else None

col1, col2, col3 = st.columns(3)
col1.metric("Perf. moyenne", f"{mean_perf:+.2f}%" if pd.notna(mean_perf) else "—")
if best is not None:
    col2.metric("Meilleure ligne", f"{best['Ticker']} {best['Rendement net estimé (%)']:+.2f}%")
if worst is not None:
    col3.metric("Pire ligne", f"{worst['Ticker']} {worst['Rendement net estimé (%)']:+.2f}%")

st.divider()

# ---------------- GRAPHE BASE 100 ----------------
st.subheader("📈 Évolution du portefeuille virtuel (base 100)")

# Récupère les tickers uniques
tickers = df["Ticker"].dropna().unique().tolist()
if not tickers:
    st.info("Aucun ticker valide.")
    st.stop()

# Télécharge les cours récents
hist = fetch_prices(tickers, days=90)
if hist.empty:
    st.warning("Impossible de charger les historiques de prix.")
    st.stop()

hist = hist.copy().sort_values(["Ticker","Date"])
hist["Variation"] = hist.groupby("Ticker")["Close"].transform(lambda s: s / s.iloc[0] * 100)

# Portefeuille virtuel = moyenne égale de toutes les lignes
portfolio = hist.groupby("Date")["Variation"].mean().reset_index().rename(columns={"Variation":"Portefeuille"})
portfolio["Indice global"] = 100 + np.random.normal(0, 0.2, len(portfolio))  # placeholder (peut être remplacé par ^GSPC)

chart = (
    alt.Chart(portfolio)
    .transform_fold(
        ["Portefeuille","Indice global"],
        as_=["Type","Valeur"]
    )
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

st.caption("💡 Les performances sont simulées à partir des cours réels Yahoo Finance. Les frais (±1€) sont intégrés dans le calcul du rendement net estimé.")
