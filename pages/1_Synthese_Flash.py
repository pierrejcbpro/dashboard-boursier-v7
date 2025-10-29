# -*- coding: utf-8 -*-
import streamlit as st, pandas as pd, numpy as np, altair as alt
from lib import (
    fetch_all_markets, style_variations, load_profile, save_profile,
    news_summary, select_top_actions, decision_label_from_row
)

st.set_page_config(page_title="Synthèse Flash", page_icon="⚡", layout="wide")
st.title("⚡ Synthèse Flash — Vue IA long terme multi-marchés")

# ---------------- Sidebar ----------------
periode = st.sidebar.radio("Période d’analyse", ["Jour","7 jours","30 jours"], index=0)
value_col = {"Jour":"pct_1d","7 jours":"pct_7d","30 jours":"pct_30d"}[periode]

profil = st.sidebar.radio("Profil IA", ["Prudent","Neutre","Agressif"], 
                          index=["Prudent","Neutre","Agressif"].index(load_profile()))
if st.sidebar.button("💾 Mémoriser le profil"):
    save_profile(profil)
    st.sidebar.success("Profil sauvegardé.")

# ---------------- Marchés ----------------
MARKETS = [("CAC 40", None), ("DAX", None), ("NASDAQ 100", None)]
data = fetch_all_markets(MARKETS, days_hist=240)

if data.empty:
    st.warning("Aucune donnée disponible (vérifie la connectivité).")
    st.stop()

for c in ["pct_1d","pct_7d","pct_30d"]:
    if c not in data.columns:
        data[c] = np.nan
valid = data.dropna(subset=["Close"]).copy()

# ---------------- Résumé global ----------------
avg = (valid[value_col].dropna().mean() * 100.0) if not valid.empty else np.nan
up = int((valid[value_col] > 0).sum())
down = int((valid[value_col] < 0).sum())

st.markdown(f"### 🧭 Résumé global ({periode})")
if np.isfinite(avg):
    st.markdown(f"**Variation moyenne : {avg:+.2f}%** — {up} hausses / {down} baisses")
else:
    st.markdown("Variation indisponible pour cette période.")

# ---------------- Top / Flop élargi ----------------
st.subheader(f"🏆 Top 10 hausses & ⛔ Baisses — {periode}")

def prep_table(df, asc=False, n=10):
    if df.empty: return pd.DataFrame()
    cols = ["Ticker","name","Close", value_col,"Indice","MA120","MA240"]
    for c in cols:
        if c not in df.columns: df[c] = np.nan
    out = df.sort_values(value_col, ascending=asc).head(n).copy()
    out.rename(columns={"name":"Société","Close":"Cours (€)"}, inplace=True)
    out["Variation %"] = (out[value_col] * 100).round(2)
    out["Cours (€)"] = out["Cours (€)"].round(2)

    # 🌱 Indicateur LT
    def trend_lt(row):
        ma120, ma240, close = row["MA120"], row["MA240"], row["Cours (€)"]
        if pd.isna(ma120) or pd.isna(ma240): return "⚖️"
        if close > ma120 > ma240: return "🌱"
        if close < ma120 < ma240: return "🌧"
        return "⚖️"
    out["Tendance LT"] = out.apply(trend_lt, axis=1)
    return out[["Indice","Société","Ticker","Cours (€)","Variation %","Tendance LT"]]

col1, col2 = st.columns(2)
with col1:
    top = prep_table(valid, asc=False, n=10)
    if top.empty: st.info("Pas de hausses.")
    else: st.dataframe(style_variations(top, ["Variation %"]), use_container_width=True, hide_index=True)
with col2:
    flop = prep_table(valid, asc=True, n=10)
    if flop.empty: st.info("Pas de baisses.")
    else: st.dataframe(style_variations(flop, ["Variation %"]), use_container_width=True, hide_index=True)

# ---------------- Sélection IA TOP 10 ----------------
st.subheader("🚀 Sélection IA — Opportunités idéales (TOP 10)")
top_actions = select_top_actions(valid, profile=profil, n=10)
if top_actions.empty:
    st.info("Aucune opportunité claire détectée aujourd’hui selon l’IA.")
else:
    st.dataframe(top_actions, use_container_width=True, hide_index=True)

# ---------------- Graphiques avec MA120/MA240 ----------------
st.markdown("### 📊 Visualisation des tendances (avec MA120 & MA240)")

def line_chart_with_ma(df, title):
    if df.empty or "Date" not in df.columns:
        st.caption("Pas assez d'historique.")
        return
    d = df.copy().dropna(subset=["Close"])
    base = alt.Chart(d).mark_line(color="#3B82F6", strokeWidth=2).encode(
        x=alt.X("Date:T", title=""),
        y=alt.Y("Close:Q", title="Cours (€)"),
        tooltip=["Date:T", alt.Tooltip("Close:Q", format=".2f")]
    )
    ma120 = alt.Chart(d).mark_line(color="#fbbf24", strokeDash=[4,2]).encode(
        x="Date:T", y="MA120:Q", tooltip=["MA120"]
    )
    ma240 = alt.Chart(d).mark_line(color="#ef4444", strokeDash=[4,2]).encode(
        x="Date:T", y="MA240:Q", tooltip=["MA240"]
    )
    chart = (base + ma120 + ma240).properties(height=320, title=title)
    st.altair_chart(chart, use_container_width=True)

col3, col4 = st.columns(2)
with col3:
    if not top.empty:
        sample_ticker = top.iloc[0]["Ticker"]
        sample_df = valid[valid["Ticker"] == sample_ticker]
        line_chart_with_ma(sample_df, f"{sample_ticker} — Top hausses ({periode})")
with col4:
    if not flop.empty:
        sample_ticker = flop.iloc[0]["Ticker"]
        sample_df = valid[valid["Ticker"] == sample_ticker]
        line_chart_with_ma(sample_df, f"{sample_ticker} — Top baisses ({periode})")


# ---------------- Actualités ----------------
st.markdown("### 📰 Actualités principales")
def short_news(row):
    nm = str(row.get("Société") or "")
    tk = str(row.get("Ticker") or "")
    txt, score, items = news_summary(nm, tk, lang="fr")
    return txt

if not top.empty:
    st.markdown("**Top hausses — explication probable :**")
    for _, r in top.iterrows():
        st.markdown(f"- **{r['Société']} ({r['Ticker']})** : {short_news(r)}")
if not flop.empty:
    st.markdown("**Baisses — explication probable :**")
    for _, r in flop.iterrows():
        st.markdown(f"- **{r['Société']} ({r['Ticker']})** : {short_news(r)}")
