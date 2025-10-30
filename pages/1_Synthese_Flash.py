# -*- coding: utf-8 -*-
"""
v7.9.1 — Synthèse Flash IA complète et stable
Basée sur V6.9 + corrections robustes :
- Score IA combiné (MA20/50 + MA120/240)
- Indicateurs LT 🌱/🌧/⚖️
- Proximité entrée, emoji Signal
- Ajout direct au Portefeuille Virtuel (data/virtual_trades.json)
- Suppression automatique des colonnes dupliquées
- Compatible lib v7.6
"""

import os, json
import streamlit as st, pandas as pd, numpy as np, altair as alt

from lib import (
    fetch_all_markets, style_variations, load_profile, save_profile,
    news_summary, select_top_actions, get_profile_params
)

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Synthèse Flash IA", page_icon="⚡", layout="wide")
st.title("⚡ Synthèse Flash — Marché Global (IA enrichie)")

# ---------------- Sidebar ----------------
periode = st.sidebar.radio("Période d’analyse", ["Jour","7 jours","30 jours"], index=0)
value_col = {"Jour":"pct_1d","7 jours":"pct_7d","30 jours":"pct_30d"}[periode]

# Profil IA
cur_profile = load_profile()
profil = st.sidebar.radio("Profil IA", ["Prudent","Neutre","Agressif"],
                          index=["Prudent","Neutre","Agressif"].index(cur_profile))
if st.sidebar.button("💾 Mémoriser le profil", key="save_profile_btn"):
    save_profile(profil)
    st.sidebar.success("Profil sauvegardé.")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🌍 Marchés inclus")
include_eu = st.sidebar.checkbox("🇫🇷 CAC 40 + 🇩🇪 DAX", value=True)
include_us = st.sidebar.checkbox("🇺🇸 NASDAQ 100 + S&P 500", value=False)
include_ls = st.sidebar.checkbox("🧠 LS Exchange (perso)", value=False)

# ---------------- Données marchés ----------------
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

# Colonnes minimales
for c in ["pct_1d","pct_7d","pct_30d","Close","Ticker","name","Indice",
          "MA20","MA50","MA120","MA240","IA_Score","trend_lt"]:
    if c not in data.columns:
        data[c] = np.nan

valid = data.dropna(subset=["Close"]).copy()
valid["Ticker"] = valid["Ticker"].astype(str).str.upper()

# ---------------- Résumé global ----------------
avg = (valid[value_col].dropna().mean() * 100.0) if not valid.empty else np.nan
up = int((valid[value_col] > 0).sum())
down = int((valid[value_col] < 0).sum())

st.markdown(f"### 🧭 Résumé global ({periode})")
if np.isfinite(avg):
    st.markdown(f"**Variation moyenne : {avg:+.2f}%** — {up} hausses / {down} baisses")
else:
    st.markdown("Variation indisponible.")

disp = (valid[value_col].std() * 100.0) if not valid.empty else np.nan
if np.isfinite(disp):
    if disp < 1.0:
        st.caption("Marché calme — consolidation technique.")
    elif disp < 2.5:
        st.caption("Volatilité modérée — quelques leaders sectoriels.")
    else:
        st.caption("Marché dispersé — forte rotation / flux macro.")

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
    def lt_emoji(row):
        m120, m240 = row.get("MA120"), row.get("MA240")
        if np.isfinite(m120) and np.isfinite(m240):
            return "🌱" if m120>m240 else ("🌧" if m120<m240 else "⚖️")
        return "⚖️"
    out["LT"] = out.apply(lt_emoji, axis=1)
    return out[["Indice","Société","Ticker","Cours (€)","Variation %","LT","IA_Score"]]

col1, col2 = st.columns(2)
with col1:
    top = prep_table(valid, asc=False)
    if top.empty: st.info("Pas de hausses.")
    else: st.dataframe(style_variations(top, ["Variation %"]), use_container_width=True, hide_index=True)
with col2:
    flop = prep_table(valid, asc=True)
    if flop.empty: st.info("Pas de baisses.")
    else: st.dataframe(style_variations(flop, ["Variation %"]), use_container_width=True, hide_index=True)

st.divider()

# ---------------- Sélection IA ----------------
st.subheader("🚀 Sélection IA — Opportunités idéales (TOP 10)")
top_actions = select_top_actions(valid, profile=profil, n=10, include_proximity=True)

# Merge indice
if not top_actions.empty and "Indice" not in top_actions.columns:
    idx_map = valid[["Ticker","Indice"]].drop_duplicates()
    idx_map["Ticker"] = idx_map["Ticker"].astype(str).str.upper()
    if "Symbole" in top_actions.columns:
        top_actions["Symbole"] = top_actions["Symbole"].astype(str).str.upper()
        top_actions = top_actions.merge(idx_map, left_on="Symbole", right_on="Ticker", how="left")
        top_actions.rename(columns={"Symbole":"Ticker"}, inplace=True)
        top_actions.drop(columns=[c for c in top_actions.columns if c.endswith("_y")], errors="ignore", inplace=True)
        if "Ticker_x" in top_actions.columns:
            top_actions.rename(columns={"Ticker_x":"Ticker"}, inplace=True)
    else:
        top_actions = top_actions.merge(idx_map, on="Ticker", how="left")

# --- Affichage complet sans doublons ---
if top_actions.empty:
    st.info("Aucune opportunité claire détectée selon l’IA.")
else:
    for c in ["MA20","MA50","MA120","MA240","Entrée (€)","Objectif (€)","Stop (€)",
              "Proximité (%)","Score IA","Indice","Société","Ticker"]:
        if c not in top_actions.columns: top_actions[c] = np.nan

    def prox_emoji(v):
        if pd.isna(v): return "⚪"
        return "🟢" if abs(v)<=2 else ("⚠️" if abs(v)<=5 else "🔴")
    top_actions["Signal Entrée"] = top_actions["Proximité (%)"].apply(prox_emoji)

    want_cols = ["Indice","Société","Ticker","Cours (€)","MA20","MA50","MA120","MA240",
                 "Score IA","Entrée (€)","Objectif (€)","Stop (€)","Proximité (%)","Signal Entrée"]
    top_actions = top_actions.loc[:, ~top_actions.columns.duplicated()].copy()

    # Nettoyage des types non scalaires
    for c in want_cols:
        if c in top_actions.columns:
            top_actions[c] = top_actions[c].apply(lambda x: x if np.isscalar(x) or pd.isna(x) else str(x))

    st.dataframe(top_actions[want_cols].style.format(precision=2),
                 use_container_width=True, hide_index=True)

# ---------------- Simulation d’investissement ----------------
st.divider()
st.subheader("💸 Simulation d’investissement — Portefeuille virtuel")

os.makedirs("data", exist_ok=True)
VFILE = "data/virtual_trades.json"
if not os.path.exists(VFILE):
    json.dump([], open(VFILE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

c1, c2, c3, c4 = st.columns([1,1,1,2])
with c1: inv_default = st.number_input("Montant (€)", 1.0, 10000.0, 20.0, 1.0)
with c2: fee_in = st.number_input("Frais entrée (€)", 0.0, 10.0, 1.0, 0.5)
with c3: fee_out = st.number_input("Frais sortie (€)", 0.0, 10.0, 1.0, 0.5)
with c4: horizon = st.selectbox("Horizon", ["1 semaine","2 semaines","1 mois"], index=2)

if not top_actions.empty:
    st.markdown("#### ➕ Ajouter au portefeuille virtuel")
    mini_cols = ["Société","Ticker","Cours (€)","Entrée (€)","Objectif (€)","Stop (€)","Proximité (%)","Signal Entrée","Score IA","Indice"]
    for c in mini_cols:
        if c not in top_actions.columns: top_actions[c] = np.nan
    mini = top_actions[mini_cols].copy().reset_index(drop=True)

    for i, r in mini.iterrows():
        with st.container(border=True):
            cA, cB, cC, cD, cE, cF = st.columns([2,1.2,1.2,1.2,1.2,1.2])
            with cA:
                st.markdown(f"**{r['Société']}**  \n`{r['Ticker']}`  \n_{r.get('Indice','')}_")
            with cB: st.metric("Cours", f"{r['Cours (€)']:.2f}" if pd.notna(r["Cours (€)"]) else "—")
            with cC: st.metric("Entrée", f"{r['Entrée (€)']:.2f}" if pd.notna(r["Entrée (€)"]) else "—")
            with cD: st.metric("Objectif", f"{r['Objectif (€)']:.2f}" if pd.notna(r["Objectif (€)"]) else "—")
            with cE: st.metric("Stop", f"{r['Stop (€)']:.2f}" if pd.notna(r["Stop (€)"]) else "—")
            with cF: st.metric("Proximité", f"{r['Proximité (%)']:.2f}%" if pd.notna(r["Proximité (%)"]) else "—")

            c1a, c1b, c1c, c1d = st.columns([1.2,1,1,1.5])
            with c1a: inv = st.number_input("Montant", 1.0, 10000.0, inv_default, 1.0, key=f"inv_{i}")
            with c1b:
                px = float(r["Cours (€)"]) if pd.notna(r["Cours (€)"]) else np.nan
                qty = np.floor(max(inv-fee_in,0)/px) if np.isfinite(px) and px>0 else 0
                st.metric("Qté", f"{int(qty)}")
            with c1c:
                rn_pct = np.nan
                if np.isfinite(px) and qty>0:
                    obj = float(r["Objectif (€)"]) if pd.notna(r["Objectif (€)"]) else np.nan
                    if np.isfinite(obj):
                        pnl = (obj - px) * qty - fee_out
                        rn_pct = pnl/inv*100 if inv>0 else np.nan
                st.metric("Rendement net", f"{rn_pct:.2f}%" if np.isfinite(rn_pct) else "—")
            with c1d:
                if st.button("➕ Ajouter", key=f"addvirt_{i}"):
                    try:
                        with open(VFILE,"r",encoding="utf-8") as f: cur=json.load(f)
                        if not isinstance(cur,list): cur=[]
                    except: cur=[]
                    rec={
                        "date": pd.Timestamp.today().strftime("%Y-%m-%d"),
                        "ticker": r["Ticker"], "name": r["Société"],
                        "indice": r.get("Indice",""),
                        "price_now": float(px) if np.isfinite(px) else None,
                        "entry": float(r["Entrée (€)"]) if pd.notna(r["Entrée (€)"]) else None,
                        "target": float(r["Objectif (€)"]) if pd.notna(r["Objectif (€)"]) else None,
                        "stop": float(r["Stop (€)"]) if pd.notna(r["Stop (€)"]) else None,
                        "qty": int(qty), "invest_eur": float(inv),
                        "fee_in": float(fee_in), "fee_out": float(fee_out),
                        "horizon": horizon,
                        "ia_score": float(r["Score IA"]) if pd.notna(r["Score IA"]) else None,
                        "signal": str(r["Signal Entrée"] or "")
                    }
                    cur.append(rec)
                    with open(VFILE,"w",encoding="utf-8") as f: json.dump(cur,f,ensure_ascii=False,indent=2)
                    st.success(f"✅ {r['Société']} ajouté au portefeuille virtuel.")

st.divider()

# ---------------- Graphiques ----------------
st.markdown("### 📊 Visualisation rapide")
def bar_chart(df, title):
    if df.empty: 
        st.caption("—"); return
    d=df.copy()
    if "Variation %" not in d.columns and value_col in d.columns:
        d["Variation %"]=(d[value_col]*100).round(2)
    if "Société" not in d.columns and "name" in d.columns:
        d["Société"]=d["name"]
    d["Label"]=d["Société"]+" ("+d["Ticker"]+")"
    chart=alt.Chart(d).mark_bar().encode(
        x=alt.X("Label:N",sort="-y",title=""),
        y=alt.Y("Variation %:Q",title="Variation (%)"),
        color=alt.Color("Variation %:Q",scale=alt.Scale(scheme="redyellowgreen")),
        tooltip=["Société","Ticker","Variation %","Indice","IA_Score"]
    ).properties(height=320,title=title)
    st.altair_chart(chart,use_container_width=True)

c3,c4=st.columns(2)
with c3: bar_chart(top,f"Top 10 hausses ({periode})")
with c4: bar_chart(flop,f"Top 10 baisses ({periode})")

# ---------------- Actualités ----------------
st.markdown("### 📰 Actualités principales")
def short_news(row):
    nm=str(row.get("Société") or row.get("name") or "")
    tk=str(row.get("Ticker") or "")
    txt,_,_=news_summary(nm,tk,lang="fr")
    return txt

if not top.empty:
    st.markdown("**Top hausses — explication probable :**")
    for _,r in top.iterrows():
        st.markdown(f"- **{r['Société']} ({r['Ticker']})** : {short_news(r)}")
if not flop.empty:
    st.markdown("**Baisses — explication probable :**")
    for _,r in flop.iterrows():
        st.markdown(f"- **{r['Société']} ({r['Ticker']})** : {short_news(r)}")

st.caption("💡 Utilise la section 'Simulation d’investissement' pour tester des positions virtuelles.")
