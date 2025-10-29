# -*- coding: utf-8 -*-
import streamlit as st, pandas as pd, numpy as np, altair as alt
from lib import (
    fetch_all_markets, style_variations, load_profile, save_profile,
    news_summary, select_top_actions
)

st.set_page_config(page_title="Synthèse Flash", page_icon="⚡", layout="wide")
st.title("⚡ Synthèse Flash — IA Hybride (CT + LT)")

# ---------------- Sidebar ----------------
periode = st.sidebar.radio("Période d’analyse", ["Jour","7 jours","30 jours"], index=0)
value_col = {"Jour":"pct_1d","7 jours":"pct_7d","30 jours":"pct_30d"}[periode]

profil = st.sidebar.radio("Profil IA", ["Prudent","Neutre","Agressif"], 
                          index=["Prudent","Neutre","Agressif"].index(load_profile()))
if st.sidebar.button("💾 Mémoriser le profil"):
    save_profile(profil)
    st.sidebar.success("Profil sauvegardé.")

markets_selected = st.sidebar.multiselect(
    "Indices analysés",
    ["CAC 40","DAX","NASDAQ 100"],
    default=["CAC 40","DAX","NASDAQ 100"]
)

# ---------------- Données marchés ----------------
MARKETS = [(m, None) for m in markets_selected]
data = fetch_all_markets(MARKETS, days_hist=360)

if data.empty:
    st.warning("Aucune donnée disponible (connectivité ou collecte indices).")
    st.stop()

for c in ["pct_1d","pct_7d","pct_30d"]:
    if c not in data.columns: data[c] = np.nan
valid = data.dropna(subset=["Close"]).copy()

# ---------------- Résumé global multi-marchés ----------------
avg = (valid[value_col].dropna().mean() * 100.0) if not valid.empty else np.nan
up = int((valid[value_col] > 0).sum())
down = int((valid[value_col] < 0).sum())

st.markdown(f"### 🧭 Résumé global ({periode}) — {', '.join(markets_selected)}")
if np.isfinite(avg):
    st.markdown(f"**Variation moyenne : {avg:+.2f}%** — {up} hausses / {down} baisses")
else:
    st.markdown("Variation indisponible pour cette période.")

disp = (valid[value_col].std() * 100.0) if not valid.empty else np.nan
if np.isfinite(disp):
    if disp < 1.0:   st.caption("Marché calme — consolidation technique.")
    elif disp < 2.5: st.caption("Volatilité modérée — quelques leaders sectoriels.")
    else:            st.caption("Marché dispersé — rotation marquée / effets macro.")

st.divider()

# ---------------- Top / Flop (10 + / -) ----------------
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
    # Emojis LT
    def lt_emoji(r):
        if pd.isna(r["MA120"]) or pd.isna(r["MA240"]): return ""
        if r["Close"] > r["MA120"] > r["MA240"]: return "🌱"
        if r["Close"] < r["MA120"] < r["MA240"]: return "🌧"
        return "⚖️"
    out["LT"] = out.apply(lt_emoji, axis=1)
    return out[["Indice","Société","Ticker","Cours (€)","Variation %","LT"]]

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
    # Mise en valeur des proximités
    def color_proximity(v):
        if pd.isna(v): return ""
        if abs(v) <= 2: return "background-color:#e6f4ea; color:#0b8043"  # vert
        if abs(v) <= 5: return "background-color:#fff8e1; color:#a67c00"  # jaune
        return "background-color:#ffebee; color:#b71c1c"                   # rouge
    st.dataframe(
        top_actions.style.applymap(color_proximity, subset=["Proximité (%)"]),
        use_container_width=True, hide_index=True
    )

# ---------------- Chart résumé tops ----------------
st.markdown("### 📊 Visualisation rapide")
def bar_chart(df, title):
    if df.empty: 
        st.caption("—")
        return
    d = df.copy()
    d["Label"] = d["Société"].astype(str) + " (" + d["Ticker"].astype(str) + ")"
    chart = (
        alt.Chart(d)
        .mark_bar()
        .encode(
            x=alt.X("Label:N", sort="-y", title=""),
            y=alt.Y("Variation %:Q", title="Variation (%)"),
            color=alt.Color("Variation %:Q", scale=alt.Scale(scheme="redyellowgreen")),
            tooltip=["Société","Ticker","Variation %","Cours (€)","Indice"]
        )
        .properties(height=320, title=title)
    )
    st.altair_chart(chart, use_container_width=True)

col3, col4 = st.columns(2)
with col3: bar_chart(top, f"Top 10 hausses ({periode})")
with col4: bar_chart(flop, f"Top 10 baisses ({periode})")

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

st.divider()
