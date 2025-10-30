# -*- coding: utf-8 -*-
"""
v7.7 — Suivi Virtuel IA
- 💹 Suivi du portefeuille simulé
- 📉 Comparaison au CAC 40 (indice réel ^FCHI)
- 🗑 Suppression de lignes interactive
- ✅ Compatible lib v7.6 (IA enrichie)
"""

import streamlit as st, pandas as pd, numpy as np, altair as alt, os
from lib import fetch_prices

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Suivi Virtuel IA", page_icon="💹", layout="wide")
st.title("💹 Suivi Virtuel — Portefeuille IA simulé")

DATA_PATH = "data/suivi_virtuel.json"
os.makedirs("data", exist_ok=True)

# ---------------- CHARGEMENT ----------------
if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=[
        "Ticker","Cours (€)","Entrée (€)","Objectif (€)","Stop (€)",
        "Rendement net estimé (%)","Date ajout"
    ]).to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)

try:
    df = pd.read_json(DATA_PATH)
except Exception:
    df = pd.DataFrame(columns=[
        "Ticker","Cours (€)","Entrée (€)","Objectif (€)","Stop (€)",
        "Rendement net estimé (%)","Date ajout"
    ])

if df.empty:
    st.info("Aucune ligne dans ton portefeuille virtuel. Ajoute depuis la Synthèse Flash 💸.")
    st.stop()

# ---------------- TABLEAU INTERACTIF ----------------
st.subheader("📋 Lignes suivies (modifiables / supprimables)")

edited = st.data_editor(
    df,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "Ticker": st.column_config.TextColumn("Ticker"),
        "Cours (€)": st.column_config.NumberColumn("Cours (€)", format="%.2f"),
        "Entrée (€)": st.column_config.NumberColumn("Entrée (€)", format="%.2f"),
        "Objectif (€)": st.column_config.NumberColumn("Objectif (€)", format="%.2f"),
        "Stop (€)": st.column_config.NumberColumn("Stop (€)", format="%.2f"),
        "Rendement net estimé (%)": st.column_config.NumberColumn("Rendement net estimé (%)", format="%.2f"),
        "Date ajout": st.column_config.TextColumn("Date ajout (auto)")
    }
)

c1, c2, c3 = st.columns(3)
with c1:
    if st.button("💾 Sauvegarder les modifs"):
        edited.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
        st.success("✅ Modifications sauvegardées.")
with c2:
    if st.button("🗑 Supprimer toutes les lignes"):
        os.remove(DATA_PATH)
        st.success("♻️ Suivi virtuel réinitialisé.")
        st.rerun()
with c3:
    if st.button("🔄 Rafraîchir"):
        st.rerun()

st.divider()

# ---------------- MÉTRIQUES ----------------
st.subheader("📊 Synthèse IA")

if "Rendement net estimé (%)" in edited.columns and not edited.empty:
    mean_perf = edited["Rendement net estimé (%)"].mean()
    best = edited.loc[edited["Rendement net estimé (%)"].idxmax()]
    worst = edited.loc[edited["Rendement net estimé (%)"].idxmin()]
else:
    mean_perf, best, worst = np.nan, None, None

col1, col2, col3 = st.columns(3)
col1.metric("Perf. moyenne", f"{mean_perf:+.2f}%" if pd.notna(mean_perf) else "—")
if best is not None:
    col2.metric("Meilleure ligne", f"{best['Ticker']} {best['Rendement net estimé (%)']:+.2f}%")
if worst is not None:
    col3.metric("Pire ligne", f"{worst['Ticker']} {worst['Rendement net estimé (%)']:+.2f}%")

st.divider()

# ---------------- GRAPHE BASE 100 ----------------
st.subheader("📈 Évolution du portefeuille virtuel vs CAC 40")

tickers = edited["Ticker"].dropna().unique().tolist()
if not tickers:
    st.info("Aucun ticker valide à suivre.")
    st.stop()

# Ajout du CAC 40 réel
benchmark_symbol = "^FCHI"
symbols = tickers + [benchmark_symbol]

hist = fetch_prices(symbols, days=90)
if hist.empty or "Date" not in hist.columns:
    st.warning("Impossible de charger les historiques de prix Yahoo Finance.")
    st.stop()

# Normalisation base 100
hist = hist.copy().sort_values(["Ticker","Date"])
hist["Base100"] = hist.groupby("Ticker")["Close"].transform(lambda s: s / s.iloc[0] * 100)

# Portefeuille virtuel = moyenne simple des positions
pf_curve = hist[hist["Ticker"].isin(tickers)].groupby("Date")["Base100"].mean().reset_index()
bmk_curve = hist[hist["Ticker"] == benchmark_symbol][["Date","Base100"]].rename(columns={"Base100":"CAC 40"})

merged = pf_curve.merge(bmk_curve, on="Date", how="inner").rename(columns={"Base100":"Portefeuille"})
merged = merged.melt("Date", var_name="Type", value_name="Valeur")

# Comparaison finale
try:
    perf_port = merged[merged["Type"]=="Portefeuille"]["Valeur"].iloc[-1] - 100
    perf_cac = merged[merged["Type"]=="CAC 40"]["Valeur"].iloc[-1] - 100
    diff = perf_port - perf_cac
    msg = (
        f"✅ Ton portefeuille virtuel surperforme le CAC 40 de {diff:+.2f}%"
        if diff > 0 else
        f"⚠️ Ton portefeuille virtuel sous-performe le CAC 40 de {abs(diff):.2f}%"
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

st.caption("💡 Données CAC 40 en direct (Yahoo Finance : ^FCHI). Les rendements incluent les frais ±1 € simulés.")
