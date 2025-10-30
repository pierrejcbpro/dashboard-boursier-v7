# -*- coding: utf-8 -*-
"""
v7.10.5 — Synthèse Flash IA stable
✅ Corrige KeyError sur top_actions (colonnes manquantes)
✅ Corrige tous les risques de duplication / plantage Streamlit
✅ Stable sur Pandas 2.x / PyArrow 17+
"""

import os, json
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st
from lib import (
    fetch_all_markets, style_variations, load_profile, save_profile,
    news_summary, select_top_actions, fetch_prices
)

# =======================================================
# CONFIGURATION
# =======================================================
st.set_page_config(page_title="Synthèse Flash IA", page_icon="⚡", layout="wide")
st.title("⚡ Synthèse Flash — Marché Global (IA enrichie)")

# =======================================================
# SIDEBAR
# =======================================================
periode = st.sidebar.radio("Période d’analyse", ["Jour", "7 jours", "30 jours"], index=0)
value_col = {"Jour": "pct_1d", "7 jours": "pct_7d", "30 jours": "pct_30d"}[periode]

profil = st.sidebar.radio(
    "Profil IA", ["Prudent", "Neutre", "Agressif"],
    index=["Prudent", "Neutre", "Agressif"].index(load_profile())
)
if st.sidebar.button("💾 Mémoriser le profil"):
    save_profile(profil)
    st.sidebar.success("Profil sauvegardé.")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🌍 Marchés inclus")
include_eu = st.sidebar.checkbox("🇫🇷 CAC 40 + 🇩🇪 DAX", value=True)
include_us = st.sidebar.checkbox("🇺🇸 NASDAQ 100 + S&P 500", value=False)
include_ls = st.sidebar.checkbox("🧠 LS Exchange (perso)", value=False)

# =======================================================
# DONNÉES MARCHÉ
# =======================================================
MARKETS = []
if include_eu: MARKETS += [("CAC 40", None), ("DAX", None)]
if include_us: MARKETS += [("NASDAQ 100", None), ("S&P 500", None)]
if include_ls: MARKETS += [("LS Exchange", None)]

if not MARKETS:
    st.warning("Aucun marché sélectionné.")
    st.stop()

data = fetch_all_markets(MARKETS, days_hist=240)
if data.empty:
    st.warning("Aucune donnée disponible.")
    st.stop()

for c in ["pct_1d","pct_7d","pct_30d"]:
    if c not in data.columns:
        data[c] = np.nan
valid = data.dropna(subset=["Close"]).copy()

# =======================================================
# SYNTHÈSE GLOBALE
# =======================================================
avg = valid[value_col].mean() * 100 if not valid.empty else np.nan
up = (valid[value_col] > 0).sum()
down = (valid[value_col] < 0).sum()
st.markdown(f"### 🧭 Résumé global ({periode})")
if np.isfinite(avg):
    st.markdown(f"**Variation moyenne : {avg:+.2f}%** — {up} hausses / {down} baisses")

disp = valid[value_col].std() * 100 if not valid.empty else np.nan
if np.isfinite(disp):
    if disp < 1: st.caption("Marché calme — consolidation technique.")
    elif disp < 2.5: st.caption("Volatilité modérée — rotations sectorielles.")
    else: st.caption("Marché dispersé — forte volatilité.")
st.divider()

# =======================================================
# TOP / FLOP
# =======================================================
st.subheader(f"🏆 Top 10 hausses & ⛔ Baisses — {periode}")

def prep(df, asc=False):
    if df.empty: return pd.DataFrame()
    out = df.sort_values(value_col, ascending=asc).head(10).copy()
    out["Variation %"] = (out[value_col] * 100).round(2)
    out["Cours (€)"] = out["Close"].round(2)
    out.rename(columns={"name": "Société"}, inplace=True)
    return out[["Indice","Société","Ticker","Cours (€)","Variation %"]]

col1,col2 = st.columns(2)
with col1:
    top = prep(valid, asc=False)
    st.dataframe(style_variations(top, ["Variation %"]), use_container_width=True, hide_index=True)
with col2:
    flop = prep(valid, asc=True)
    st.dataframe(style_variations(flop, ["Variation %"]), use_container_width=True, hide_index=True)

st.divider()

# =======================================================
# 🚀 SÉLECTION IA — Opportunités
# =======================================================
st.subheader("🚀 Sélection IA — Opportunités idéales (TOP 10)")
top_actions = select_top_actions(valid, profile=profil, n=10, include_proximity=True)

if top_actions.empty:
    st.info("Aucune opportunité IA disponible.")
else:
    # ✅ Création sécurisée des colonnes manquantes
    needed_cols = ["name","Ticker","Cours (€)","Entrée (€)","Objectif (€)",
                   "Stop (€)","Proximité (%)","Signal Entrée"]
    for c in needed_cols:
        if c not in top_actions.columns:
            top_actions[c] = np.nan

    # Ajoute Signal Entrée si absent
    if "Signal Entrée" not in top_actions.columns:
        def marker(v):
            if pd.isna(v): return "⚪"
            if abs(v) <= 2: return "🟢"
            elif abs(v) <= 5: return "⚠️"
            return "🔴"
        top_actions["Signal Entrée"] = top_actions["Proximité (%)"].apply(marker)

    # ✅ Nettoie doublons éventuels
    top_actions = top_actions.loc[:, ~top_actions.columns.duplicated()]

    st.dataframe(
        top_actions[needed_cols].round(2),
        use_container_width=True,
        hide_index=True
    )

st.divider()

# =======================================================
# 💸 PORTFEUILLE VIRTUEL — SUIVI
# =======================================================
st.subheader("💸 Portefeuille virtuel — suivi IA")

SUIVI_PATH = "data/suivi_virtuel.json"
os.makedirs("data", exist_ok=True)

def load_suivi():
    try:
        with open(SUIVI_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except:
        return []

def save_suivi(lst):
    with open(SUIVI_PATH, "w", encoding="utf-8") as f:
        json.dump(lst, f, ensure_ascii=False, indent=2)

montant = st.number_input("💶 Montant par ligne (€)",5.0,step=5.0,value=20.0)
horizon = st.selectbox("Horizon cible",["1 semaine","2 semaines","1 mois"],index=2)
st.caption("1€ de frais entrée + 1€ de sortie inclus.")

if not top_actions.empty:
    for i,r in top_actions.iterrows():
        c1,c2,c3,c4,c5,c6=st.columns([3,1,1,1,1,1])
        c1.markdown(f"**{r.get('name','?')}** ({r.get('Ticker','?')})")
        c2.markdown(f"{r.get('Cours (€)',np.nan):.2f} €")
        c3.markdown(f"🎯 {r.get('Objectif (€)',np.nan):.2f} €")
        c4.markdown(f"🛑 {r.get('Stop (€)',np.nan):.2f} €")
        prox=r.get('Proximité (%)',np.nan)
        c5.markdown(f"{prox:+.2f}%" if pd.notna(prox) else "—")
        if c6.button("➕ Ajouter", key=f"a{i}"):
            items=load_suivi()
            entry=float(r.get("Entrée (€)") or r.get("Cours (€)") or np.nan)
            target=float(r.get("Objectif (€)") or np.nan)
            stop=float(r.get("Stop (€)") or np.nan)
            qty=(montant-1)/entry if entry>0 else 0
            rend=((target-entry)/entry*100-2/entry*100) if np.isfinite(entry) and np.isfinite(target) else np.nan
            items.append({
                "ticker":r.get("Ticker"),"name":r.get("name"),
                "entry":entry,"target":target,"stop":stop,
                "amount":montant,"qty":qty,"rendement_estime_pct":rend,
                "added_at":datetime.now(timezone.utc).isoformat(),"horizon":horizon
            })
            save_suivi(items)
            st.success(f"Ajouté : {r.get('name')} ({r.get('Ticker')})")

st.divider()

# =======================================================
# 📊 SUIVI VIRTUEL — AFFICHAGE
# =======================================================
st.subheader("📊 Suivi virtuel & comparaison CAC40")

items=load_suivi()
if not items:
    st.caption("Aucune ligne.")
    st.stop()

df=pd.DataFrame(items)
tickers=df["ticker"].unique().tolist()
px=fetch_prices(tickers+["^FCHI"],days=60)
if px.empty or "Date" not in px.columns:
    st.warning("Pas assez d’historique.")
    st.stop()

last=px.sort_values("Date").groupby("Ticker").tail(1)[["Ticker","Close"]].rename(columns={"Close":"last_close"})
df=df.merge(last,left_on="ticker",right_on="Ticker",how="left")

def perf(r):
    if not np.isfinite(r["last_close"]): return pd.Series({"val":np.nan,"pnl":np.nan})
    val=r["qty"]*r["last_close"]-1
    pnl=(val-r["amount"])/r["amount"]*100 if r["amount"]>0 else np.nan
    return pd.Series({"val":val,"pnl":pnl})
df=pd.concat([df,df.apply(perf,axis=1)],axis=1)

# Nettoie doublons
df=df.loc[:,~df.columns.duplicated()]

show=df.rename(columns={
    "name":"Société","ticker":"Ticker","last_close":"Cours actuel (€)",
    "entry":"Entrée (€)","target":"Objectif (€)","stop":"Stop (€)",
    "rendement_estime_pct":"Rendement estimé (%)","qty":"Qté",
    "amount":"Montant initial (€)","val":"Valeur actuelle (€)","pnl":"P&L (%)"
})
cols=["Société","Ticker","Cours actuel (€)","Entrée (€)","Objectif (€)","Stop (€)",
      "Rendement estimé (%)","Qté","Montant initial (€)","Valeur actuelle (€)","P&L (%)"]
for c in cols:
    if c not in show.columns: show[c]=np.nan

st.dataframe(show[cols].round(2), use_container_width=True, hide_index=True)
