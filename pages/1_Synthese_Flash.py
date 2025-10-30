# -*- coding: utf-8 -*-
"""
v8.0 — Synthèse Flash IA
Base : v7.9.1
Améliorations :
- 🧠 Colonne Décision IA (emoji) basée sur MA20/50/120/240
- 💾 Section "Ajout au portefeuille virtuel" simplifiée (table + bouton unique)
- ✅ Aucune colonne dupliquée / erreur Streamlit
"""

import os, json
import streamlit as st, pandas as pd, numpy as np, altair as alt
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
include_us = st.sidebar.checkbox("🇺🇸 NASDAQ 100 + S&P 500", value=False)

MARKETS = []
if include_eu: MARKETS += [("CAC 40", None), ("DAX", None)]
if include_us: MARKETS += [("NASDAQ 100", None), ("S&P 500", None)]
if not MARKETS:
    st.warning("Aucun marché sélectionné.")
    st.stop()

# ---------------- Données marchés ----------------
data = fetch_all_markets(MARKETS, days_hist=240)
if data.empty:
    st.warning("Aucune donnée disponible.")
    st.stop()

# Colonnes minimales
for c in ["pct_1d","pct_7d","pct_30d","Close","Ticker","name","Indice",
          "MA20","MA50","MA120","MA240","IA_Score"]:
    if c not in data.columns:
        data[c] = np.nan

valid = data.dropna(subset=["Close"]).copy()
valid["Ticker"] = valid["Ticker"].astype(str).str.upper()

# ---------------- Résumé global ----------------
avg = (valid[value_col].dropna().mean() * 100.0)
up = int((valid[value_col] > 0).sum())
down = int((valid[value_col] < 0).sum())

st.markdown(f"### 🧭 Résumé global ({periode})")
st.markdown(f"**Variation moyenne : {avg:+.2f}%** — {up} hausses / {down} baisses")

st.divider()

# ---------------- Top / Flop ----------------
st.subheader(f"🏆 Top 10 hausses & ⛔ Baisses — {periode}")

def prep_table(df, asc=False, n=10):
    if df.empty: return pd.DataFrame()
    cols = ["Ticker","name","Close", value_col,"Indice","IA_Score","MA20","MA50","MA120","MA240"]
    for c in cols:
        if c not in df.columns: df[c] = np.nan
    out = df.sort_values(value_col, ascending=asc).head(n).copy()
    out.rename(columns={"name":"Société","Close":"Cours (€)"}, inplace=True)
    out["Variation %"] = (out[value_col]*100).round(2)
    return out[["Indice","Société","Ticker","Cours (€)","Variation %","IA_Score","MA20","MA50","MA120","MA240"]]

col1, col2 = st.columns(2)
with col1:
    top = prep_table(valid, asc=False)
    st.dataframe(style_variations(top, ["Variation %"]), use_container_width=True, hide_index=True)
with col2:
    flop = prep_table(valid, asc=True)
    st.dataframe(style_variations(flop, ["Variation %"]), use_container_width=True, hide_index=True)

st.divider()

# ---------------- Sélection IA ----------------
st.subheader("🚀 Sélection IA — Opportunités idéales (TOP 10)")
top_actions = select_top_actions(valid, profile=profil, n=10, include_proximity=True)

# Merge Indice
if not top_actions.empty and "Indice" not in top_actions.columns:
    idx_map = valid[["Ticker","Indice"]].drop_duplicates()
    idx_map["Ticker"] = idx_map["Ticker"].astype(str).str.upper()
    if "Symbole" in top_actions.columns:
        top_actions["Symbole"] = top_actions["Symbole"].astype(str).str.upper()
        top_actions = top_actions.merge(idx_map, left_on="Symbole", right_on="Ticker", how="left")
        top_actions.rename(columns={"Symbole":"Ticker"}, inplace=True)
        top_actions.drop(columns=[c for c in top_actions.columns if c.endswith("_y")], errors="ignore", inplace=True)

# Ajout Décision IA
def ia_decision(row):
    ma20, ma50, ma120, ma240 = row.get("MA20"), row.get("MA50"), row.get("MA120"), row.get("MA240")
    if np.all(np.isfinite([ma20, ma50, ma120, ma240])):
        if ma20 > ma50 > ma120 > ma240:
            return "🟢 Acheter"
        elif ma20 < ma50 < ma120 < ma240:
            return "🔴 Éviter"
        else:
            return "🔵 Surveiller"
    return "⚪ Neutre"

top_actions["Décision IA"] = top_actions.apply(ia_decision, axis=1)

# Signal Entrée emoji
def prox_emoji(v):
    if pd.isna(v): return "⚪"
    return "🟢" if abs(v)<=2 else ("⚠️" if abs(v)<=5 else "🔴")
top_actions["Signal Entrée"] = top_actions["Proximité (%)"].apply(prox_emoji)

# Nettoyage des doublons
top_actions = top_actions.loc[:, ~top_actions.columns.duplicated()].copy()

# Affichage complet
show_cols = ["Indice","Société","Ticker","Cours (€)","MA20","MA50","MA120","MA240",
             "IA_Score","Décision IA","Entrée (€)","Objectif (€)","Stop (€)","Proximité (%)","Signal Entrée"]
for c in show_cols:
    if c not in top_actions.columns: top_actions[c] = np.nan

st.dataframe(top_actions[show_cols].style.format(precision=2),
             use_container_width=True, hide_index=True)

# ---------------- Simulation d’investissement simplifiée ----------------
st.divider()
st.subheader("💸 Ajouter directement au portefeuille virtuel")

os.makedirs("data", exist_ok=True)
VFILE = "data/virtual_trades.json"
if not os.path.exists(VFILE):
    json.dump([], open(VFILE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

inv_amount = st.number_input("Montant d’investissement par ligne (€)", 1.0, 10000.0, 20.0, 1.0)
fee_in = st.number_input("Frais entrée (€)", 0.0, 10.0, 1.0, 0.5)
fee_out = st.number_input("Frais sortie (€)", 0.0, 10.0, 1.0, 0.5)
horizon = st.selectbox("Horizon visé", ["1 semaine","2 semaines","1 mois"], index=2)

if not top_actions.empty:
    df_add = top_actions[["Société","Ticker","Cours (€)","Entrée (€)","Objectif (€)","Stop (€)","Décision IA"]].copy()
    df_add["Qté estimée"] = np.floor((inv_amount - fee_in) / df_add["Cours (€)"])
    df_add["Rendement net estimé %"] = ((df_add["Objectif (€)"] - df_add["Cours (€)"]) / df_add["Cours (€)"] * 100 - (fee_in+fee_out)/inv_amount*100).round(2)

    st.dataframe(df_add, use_container_width=True, hide_index=True)

    if st.button("➕ Ajouter la sélection au portefeuille virtuel"):
        try:
            with open(VFILE,"r",encoding="utf-8") as f: cur = json.load(f)
            if not isinstance(cur,list): cur=[]
        except: cur=[]
        for _,r in df_add.iterrows():
            cur.append({
                "date": pd.Timestamp.today().strftime("%Y-%m-%d"),
                "ticker": str(r["Ticker"]),
                "name": str(r["Société"]),
                "price_now": float(r["Cours (€)"]),
                "entry": float(r["Entrée (€)"]) if pd.notna(r["Entrée (€)"]) else None,
                "target": float(r["Objectif (€)"]) if pd.notna(r["Objectif (€)"]) else None,
                "stop": float(r["Stop (€)"]) if pd.notna(r["Stop (€)"]) else None,
                "qty": int(r["Qté estimée"]),
                "invest_eur": float(inv_amount),
                "fee_in": float(fee_in),
                "fee_out": float(fee_out),
                "horizon": horizon,
                "decision": str(r["Décision IA"])
            })
        with open(VFILE,"w",encoding="utf-8") as f:
            json.dump(cur,f,ensure_ascii=False,indent=2)
        st.success(f"✅ {len(df_add)} lignes ajoutées au portefeuille virtuel.")

st.divider()
st.caption("💡 Utilise cette table pour investir virtuellement et observer la performance dans l’onglet 'Suivi Virtuel'.")
