# -*- coding: utf-8 -*-
"""
v2 — Suivi Virtuel IA
Compatible Synthèse Flash v7.8
Fonctionnalités :
- 📊 Lecture du portefeuille virtuel (data/suivi_virtuel.json)
- 🧮 Calcul P&L%, valeur actuelle estimée
- 🔁 Suppression de lignes (sélective)
- 📈 Comparaison avec CAC 40 (indice global)
"""

import os, json
import streamlit as st, pandas as pd, numpy as np, altair as alt
from lib import fetch_all_markets

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Suivi Virtuel IA", page_icon="💹", layout="wide")
st.title("💹 Suivi Virtuel — Portefeuille IA")

save_path = "data/suivi_virtuel.json"
os.makedirs("data", exist_ok=True)

# ---------------- CHARGEMENT ----------------
if not os.path.exists(save_path):
    json.dump([], open(save_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

try:
    pf = pd.read_json(save_path)
except Exception:
    pf = pd.DataFrame()

if pf.empty:
    st.info("Aucune ligne dans le portefeuille virtuel. Ajoute des positions depuis la page *Synthèse Flash IA*.")
    st.stop()

# ---------------- MISE EN FORME ----------------
pf = pf.copy()
expected_cols = ["Société","Ticker","Entrée (€)","Objectif (€)","Stop (€)","Score IA","Durée visée","Rendement net estimé (%)"]
for c in expected_cols:
    if c not in pf.columns:
        pf[c] = np.nan

pf["Ticker"] = pf["Ticker"].astype(str)
pf["Société"] = pf["Société"].astype(str)

st.subheader("📘 Portefeuille Virtuel actuel")

# Simulation du cours actuel (fetch marchés principaux)
st.caption("Les cours sont actualisés via les marchés sélectionnés (CAC 40 + DAX + NASDAQ + S&P 500).")

MARKETS = [("CAC 40", None), ("DAX", None), ("NASDAQ 100", None), ("S&P 500", None)]
data = fetch_all_markets(MARKETS, days_hist=30)
for c in ["Ticker","Close"]:
    if c not in data.columns: data[c] = np.nan

# Cours actuel
tickers = pf["Ticker"].dropna().unique().tolist()
current = data[data["Ticker"].isin(tickers)][["Ticker","Close"]].rename(columns={"Close":"Cours actuel (€)"})
merged = pf.merge(current, on="Ticker", how="left")

# Calculs rendement réel
merged["Entrée (€)"] = pd.to_numeric(merged["Entrée (€)"], errors="coerce")
merged["Cours actuel (€)"] = pd.to_numeric(merged["Cours actuel (€)"], errors="coerce")

merged["P&L (%)"] = ((merged["Cours actuel (€)"] - merged["Entrée (€)"]) / merged["Entrée (€)"] * 100).round(2)
merged["Valeur actuelle (€)"] = (merged["Cours actuel (€)"] / merged["Entrée (€)"] * 20).round(2)  # ticket de 20€ par défaut

# Mise en forme
cols_display = [
    "Société","Ticker","Entrée (€)","Cours actuel (€)","Objectif (€)","Stop (€)",
    "P&L (%)","Score IA","Durée visée","Rendement net estimé (%)"
]

for c in cols_display:
    if c not in merged.columns:
        merged[c] = np.nan

def color_pl(v):
    if pd.isna(v): return ""
    if v > 5: return "background-color:#e8f5e9; color:#0b8043; font-weight:600;"
    if v > 0: return "background-color:#fff8e1; color:#a67c00;"
    return "background-color:#ffebee; color:#b71c1c;"

styled = merged[cols_display].style.applymap(color_pl, subset=["P&L (%)"])
st.dataframe(styled, use_container_width=True, hide_index=True)

# ---------------- SUPPRESSION ----------------
st.divider()
st.subheader("🗑️ Gérer le portefeuille")

merged["Supprimer"] = False
edited = st.data_editor(
    merged[["Société","Ticker","Entrée (€)","Objectif (€)","Stop (€)","Supprimer"]],
    use_container_width=True,
    hide_index=True,
    key="delete_editor",
    num_rows="fixed",
    column_config={
        "Supprimer": st.column_config.CheckboxColumn("Supprimer"),
    },
)

if st.button("❌ Supprimer les lignes cochées"):
    to_delete = edited[edited["Supprimer"]==True]
    if to_delete.empty:
        st.warning("Aucune ligne cochée à supprimer.")
    else:
        remaining = pf[~pf["Ticker"].isin(to_delete["Ticker"])]
        remaining.to_json(save_path, orient="records", indent=2, force_ascii=False)
        st.success(f"🗑️ {len(to_delete)} ligne(s) supprimée(s). Recharge la page pour voir la mise à jour.")

# ---------------- COMPARAISON CAC 40 ----------------
st.divider()
st.subheader("📈 Comparatif performance vs CAC 40")

# Performance portefeuille
perf_pf = merged["P&L (%)"].mean(skipna=True)

# Performance CAC40
cac = data[data["Indice"]=="CAC 40"].copy()
if not cac.empty:
    cac["Var%"] = (cac["pct_7d"]*100).round(2)
    perf_cac = cac["Var%"].mean(skipna=True)
else:
    perf_cac = np.nan

col1, col2 = st.columns(2)
with col1:
    st.metric("Portefeuille IA (moyenne)", f"{perf_pf:+.2f} %", delta=None)
with col2:
    if np.isfinite(perf_cac):
        st.metric("CAC 40 (7 jours)", f"{perf_cac:+.2f} %", delta=perf_pf - perf_cac)
    else:
        st.metric("CAC 40 (7 jours)", "N/A")

# ---------------- VISUALISATION ----------------
st.divider()
st.subheader("📊 Répartition et P&L")

if merged.empty:
    st.caption("Aucune donnée à visualiser.")
else:
    c1, c2 = st.columns(2)
    with c1:
        chart = (
            alt.Chart(merged)
            .mark_bar()
            .encode(
                x=alt.X("Ticker:N", sort="-y", title="Ticker"),
                y=alt.Y("P&L (%):Q", title="P&L (%)"),
                color=alt.condition(
                    alt.datum["P&L (%)"] > 0,
                    alt.value("#0b8043"),
                    alt.value("#c62828")
                ),
                tooltip=["Société","Ticker","P&L (%)","Entrée (€)","Cours actuel (€)","Rendement net estimé (%)"]
            )
            .properties(height=320, title="Performance par action")
        )
        st.altair_chart(chart, use_container_width=True)

    with c2:
        pie_data = merged.groupby(pd.cut(merged["P&L (%)"], bins=[-999,-5,0,5,999])).size().reset_index(name="count")
        pie_data["category"] = pie_data["P&L (%)"].astype(str)
        chart2 = (
            alt.Chart(pie_data)
            .mark_arc()
            .encode(
                theta="count",
                color="category",
                tooltip=["category","count"]
            )
            .properties(title="Répartition des gains / pertes")
        )
        st.altair_chart(chart2, use_container_width=True)

st.caption("💡 Tu peux gérer ici ton portefeuille virtuel et comparer tes performances à celles du CAC 40.")
