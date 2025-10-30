# -*- coding: utf-8 -*-
"""
v8.1 — Synthèse Flash IA (version complète et homogène)
- Table IA identique à "Classement IA des actions" (Détails Indices)
- Sélection manuelle avant ajout au portefeuille virtuel
- Compatible lib v7.6
"""

import os, json
import streamlit as st, pandas as pd, numpy as np, altair as alt
from lib import (
    fetch_all_markets, style_variations, load_profile, save_profile,
    select_top_actions, news_summary, price_levels_from_row, decision_label_from_row, get_profile_params
)

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Synthèse Flash IA", page_icon="⚡", layout="wide")
st.title("⚡ Synthèse Flash — Marché Global (IA enrichie)")

# ---------------- Sidebar ----------------
periode = st.sidebar.radio("Période d’analyse", ["Jour","7 jours","30 jours"], index=1)
value_col = {"Jour":"pct_1d","7 jours":"pct_7d","30 jours":"pct_30d"}[periode]

profil = st.sidebar.radio("Profil IA", ["Prudent","Neutre","Agressif"],
                          index=["Prudent","Neutre","Agressif"].index(load_profile()))
if st.sidebar.button("💾 Mémoriser le profil"):
    save_profile(profil)
    st.sidebar.success("Profil sauvegardé.")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🌍 Marchés inclus")
include_eu = st.sidebar.checkbox("🇫🇷 CAC 40 + 🇩🇪 DAX", value=True)
include_us = st.sidebar.checkbox("🇺🇸 NASDAQ 100 + S&P 500", value=False)

MARKETS = []
if include_eu: MARKETS += [("CAC 40", None), ("DAX", None)]
if include_us: MARKETS += [("NASDAQ 100", None), ("S&P 500", None)]
if not MARKETS:
    st.warning("Aucun marché sélectionné.")
    st.stop()

# ---------------- Données ----------------
data = fetch_all_markets(MARKETS, days_hist=240)
if data.empty:
    st.warning("Aucune donnée disponible.")
    st.stop()

for c in ["pct_1d","pct_7d","pct_30d","Close","Ticker","name"]:
    if c not in data.columns:
        data[c] = np.nan
valid = data.dropna(subset=["Close"]).copy()

# ---------------- Sélection IA ----------------
st.subheader("🚀 Sélection IA — Opportunités idéales (TOP 10)")

top_actions = select_top_actions(valid, profile=profil, n=10, include_proximity=True)
if top_actions.empty:
    st.info("Aucune opportunité claire détectée aujourd’hui selon l’IA.")
    st.stop()

volmax = get_profile_params(profil)["vol_max"]

# Applique la logique identique à "Détails Indices"
rows = []
for _, r in top_actions.iterrows():
    levels = price_levels_from_row(r, profil)
    dec = decision_label_from_row(r, held=False, vol_max=volmax)
    entry, target, stop = levels["entry"], levels["target"], levels["stop"]
    px = r.get("Close", np.nan)
    prox = ((px / entry) - 1) * 100 if np.isfinite(px) and np.isfinite(entry) and entry > 0 else np.nan
    emoji = "🟢" if abs(prox) <= 2 else ("⚠️" if abs(prox) <= 5 else "🔴")
    rows.append({
        "Indice": r.get("Indice", ""),
        "Société": r.get("name", ""),
        "Ticker": r.get("Ticker", ""),
        "Cours (€)": round(px, 2) if np.isfinite(px) else None,
        "Variation (%)": round(r[value_col]*100, 2) if np.isfinite(r[value_col]) else None,
        "Entrée (€)": entry,
        "Objectif (€)": target,
        "Stop (€)": stop,
        "Décision IA": dec,
        "Proximité (%)": round(prox, 2) if np.isfinite(prox) else np.nan,
        "Signal": emoji
    })

out = pd.DataFrame(rows)
if out.empty:
    st.info("Aucune donnée exploitable.")
    st.stop()

# Tri identique : Acheter > Surveiller > Vendre
def sort_key(v):
    if "Acheter" in v: return 0
    if "Surveiller" in v: return 1
    if "Vendre" in v: return 2
    return 3

out["sort"] = out["Décision IA"].apply(sort_key)
out = out.sort_values(["sort","Proximité (%)"], ascending=[True,True]).drop(columns="sort")

# Style identique à Détails Indices
def color_decision(v):
    if pd.isna(v): return ""
    if "Acheter" in v: return "background-color: rgba(0,200,0,0.15);"
    if "Vendre" in v: return "background-color: rgba(255,0,0,0.15);"
    if "Surveiller" in v: return "background-color: rgba(0,100,255,0.15);"
    return ""

def color_proximity(v):
    if pd.isna(v): return ""
    if abs(v) <= 2: return "background-color: rgba(0,200,0,0.10); color:#0b8043"
    if abs(v) <= 5: return "background-color: rgba(255,200,0,0.15); color:#a67c00"
    return "background-color: rgba(255,0,0,0.12); color:#b71c1c"

# Affichage principal
st.dataframe(
    out.style
        .applymap(color_decision, subset=["Décision IA"])
        .applymap(color_proximity, subset=["Proximité (%)"]),
    use_container_width=True, hide_index=True
)

# ---------------- Sélection et ajout au portefeuille virtuel ----------------
st.divider()
st.subheader("💸 Ajouter au portefeuille virtuel (sélection manuelle)")

os.makedirs("data", exist_ok=True)
VFILE = "data/virtual_trades.json"
if not os.path.exists(VFILE):
    json.dump([], open(VFILE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

# Sélection
out["Sélection"] = False
selected = st.data_editor(
    out,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    column_config={
        "Sélection": st.column_config.CheckboxColumn("Sélection", help="Cocher pour ajouter au portefeuille virtuel"),
    },
)

# Entrées globales
c1, c2, c3, c4 = st.columns(4)
with c1: inv_amount = st.number_input("Montant d’investissement (€)", 1.0, 10000.0, 20.0, 1.0)
with c2: fee_in = st.number_input("Frais entrée (€)", 0.0, 10.0, 1.0, 0.5)
with c3: fee_out = st.number_input("Frais sortie (€)", 0.0, 10.0, 1.0, 0.5)
with c4: horizon = st.selectbox("Horizon", ["1 semaine","2 semaines","1 mois"], index=2)

# Ajouter les lignes cochées
to_add = selected[selected["Sélection"]==True]
if not to_add.empty and st.button("➕ Ajouter les lignes sélectionnées au portefeuille virtuel"):
    try:
        with open(VFILE,"r",encoding="utf-8") as f: cur = json.load(f)
        if not isinstance(cur,list): cur=[]
    except: cur=[]
    for _,r in to_add.iterrows():
        cur.append({
            "date": pd.Timestamp.today().strftime("%Y-%m-%d"),
            "ticker": str(r["Ticker"]),
            "name": str(r["Société"]),
            "indice": str(r["Indice"]),
            "price_now": float(r["Cours (€)"]) if pd.notna(r["Cours (€)"]) else None,
            "entry": float(r["Entrée (€)"]) if pd.notna(r["Entrée (€)"]) else None,
            "target": float(r["Objectif (€)"]) if pd.notna(r["Objectif (€)"]) else None,
            "stop": float(r["Stop (€)"]) if pd.notna(r["Stop (€)"]) else None,
            "decision": str(r["Décision IA"]),
            "proximity": float(r["Proximité (%)"]) if pd.notna(r["Proximité (%)"]) else None,
            "signal": str(r["Signal"]),
            "invest_eur": float(inv_amount),
            "fee_in": float(fee_in),
            "fee_out": float(fee_out),
            "horizon": horizon
        })
    with open(VFILE,"w",encoding="utf-8") as f:
        json.dump(cur,f,ensure_ascii=False,indent=2)
    st.success(f"✅ {len(to_add)} ligne(s) ajoutée(s) au portefeuille virtuel.")

st.caption("💡 Coche uniquement les actions que tu souhaites ajouter à ton portefeuille virtuel.")
