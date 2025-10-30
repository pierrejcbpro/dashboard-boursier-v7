# -*- coding: utf-8 -*-
"""
v7.8 — Synthèse Flash IA enrichie
- IA combinée (MA20/50 + MA120/240)
- Ajout direct au suivi virtuel 💰
- Gestion du profil IA
- Proximité & signaux IA
"""
import os, json, pandas as pd, numpy as np, streamlit as st, altair as alt
from lib import (
    fetch_all_markets, style_variations, load_profile, save_profile,
    news_summary, select_top_actions
)

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Synthèse Flash IA", page_icon="⚡", layout="wide")
st.title("⚡ Synthèse Flash — Marché Global (IA enrichie)")

# ---------------- Sidebar ----------------
periode = st.sidebar.radio("Période d’analyse", ["Jour","7 jours","30 jours"], index=0)
value_col = {"Jour":"pct_1d","7 jours":"pct_7d","30 jours":"pct_30d"}[periode]

profil = st.sidebar.radio("Profil IA", ["Prudent","Neutre","Agressif"],
                          index=["Prudent","Neutre","Agressif"].index(load_profile()))
if st.sidebar.button("💾 Mémoriser le profil"):
    save_profile(profil)
    st.sidebar.success("Profil sauvegardé.")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🌍 Marchés inclus")
include_eu = st.sidebar.checkbox("🇫🇷 CAC 40 + 🇩🇪 DAX", value=True)
include_us = st.sidebar.checkbox("🇺🇸 NASDAQ 100", value=False)

MARKETS = []
if include_eu: MARKETS += [("CAC 40", None), ("DAX", None)]
if include_us: MARKETS += [("NASDAQ 100", None)]

if not MARKETS:
    st.warning("Aucun marché sélectionné.")
    st.stop()

data = fetch_all_markets(MARKETS, days_hist=240)
if data.empty:
    st.warning("Aucune donnée disponible.")
    st.stop()

# ---------------- Résumé global ----------------
valid = data.dropna(subset=["Close"]).copy()
avg = (valid[value_col].mean() * 100) if not valid.empty else np.nan
up = int((valid[value_col] > 0).sum())
down = int((valid[value_col] < 0).sum())

st.markdown(f"### 🧭 Résumé global ({periode})")
if np.isfinite(avg):
    st.markdown(f"**Variation moyenne : {avg:+.2f}%** — {up} hausses / {down} baisses")
else:
    st.markdown("Variation indisponible.")

st.divider()

# ---------------- Sélection IA ----------------
st.subheader("🚀 Sélection IA — Opportunités idéales (TOP 10)")
top_actions = select_top_actions(valid, profile=profil, n=10, include_proximity=True)

if top_actions.empty:
    st.info("Aucune opportunité IA détectée.")
else:
    top_actions = top_actions.copy()
    if "Symbole" not in top_actions.columns:
        top_actions["Symbole"] = top_actions.get("Ticker", "")

    def proximity_marker(v):
        if pd.isna(v): return "⚪"
        if abs(v) <= 2: return "🟢"
        elif abs(v) <= 5: return "⚠️"
        else: return "🔴"

    if "Proximité (%)" in top_actions.columns:
        top_actions["Signal Entrée"] = top_actions["Proximité (%)"].apply(proximity_marker)
    else:
        top_actions["Signal Entrée"] = "⚪"

    st.dataframe(
        top_actions[
            ["Société","Symbole","Cours (€)","Entrée (€)","Objectif (€)","Stop (€)",
             "Trend ST","Trend LT","Score IA","Signal","Proximité (%)","Signal Entrée"]
        ].style.format(precision=2),
        use_container_width=True, hide_index=True
    )

# ---------------- Ajout au suivi virtuel ----------------
st.divider()
st.subheader("💰 Ajouter une opportunité au suivi virtuel")

DATA_PATH_VIRTUEL = "data/suivi_virtuel.json"
os.makedirs("data", exist_ok=True)
if not os.path.exists(DATA_PATH_VIRTUEL):
    pd.DataFrame(columns=[
        "Société","Ticker","Cours (€)","Entrée (€)","Objectif (€)","Stop (€)",
        "Qté","Montant Initial (€)","Valeur (€)","P&L (%)","Rendement Net Estimé (%)"
    ]).to_json(DATA_PATH_VIRTUEL, orient="records", indent=2, force_ascii=False)

montant = st.number_input("💶 Montant d’investissement (€)", min_value=10.0, step=10.0, value=20.0)

if not top_actions.empty:
    choix = st.selectbox("Sélectionne une action IA :", top_actions["Société"].tolist())
    ligne = top_actions[top_actions["Société"] == choix].iloc[0].to_dict()

    if st.button("➕ Ajouter au suivi virtuel"):
        try:
            pf = pd.read_json(DATA_PATH_VIRTUEL)
        except Exception:
            pf = pd.DataFrame()

        cours = float(ligne.get("Cours (€)", np.nan))
        entry = float(ligne.get("Entrée (€)", cours))
        qte = (montant - 1) / entry
        new_row = {
            "Société": ligne.get("Société"),
            "Ticker": ligne.get("Symbole") or ligne.get("Ticker"),
            "Cours (€)": round(cours,2),
            "Entrée (€)": round(entry,2),
            "Objectif (€)": round(ligne.get("Objectif (€)", entry*1.07),2),
            "Stop (€)": round(ligne.get("Stop (€)", entry*0.97),2),
            "Qté": round(qte,2),
            "Montant Initial (€)": round(montant,2),
            "Valeur (€)": round(montant,2),
            "P&L (%)": 0.0,
            "Rendement Net Estimé (%)": ((ligne.get("Objectif (€)", entry*1.07)/entry)-1)*100 - (2/montant)*100
        }
        pf = pd.concat([pf, pd.DataFrame([new_row])], ignore_index=True)
        pf.to_json(DATA_PATH_VIRTUEL, orient="records", indent=2, force_ascii=False)
        st.success(f"✅ {ligne.get('Société')} ajoutée au portefeuille virtuel.")
else:
    st.info("Aucune donnée IA disponible.")
