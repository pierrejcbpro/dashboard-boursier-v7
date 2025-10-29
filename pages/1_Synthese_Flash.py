# -*- coding: utf-8 -*-
import streamlit as st, pandas as pd, numpy as np, altair as alt
from lib import (
    fetch_prices, compute_metrics, style_variations, load_profile, save_profile,
    find_ticker_by_name, yahoo_search, select_top_actions, decision_label_combined
)

st.set_page_config(page_title="Synthèse Flash", page_icon="⚡", layout="wide")
st.title("⚡ Synthèse Flash — Vue Marché (CT + LT)")

# --- Sidebar ---
periode = st.sidebar.radio("Période d’analyse", ["Jour","7 jours","30 jours"], index=0)
value_col = {"Jour":"pct_1d","7 jours":"pct_7d","30 jours":"pct_30d"}[periode]

profil = st.sidebar.radio("Profil IA", ["Prudent","Neutre","Agressif"], 
                          index=["Prudent","Neutre","Agressif"].index(load_profile()))
if st.sidebar.button("💾 Mémoriser le profil"): save_profile(profil); st.sidebar.success("Profil sauvegardé.")

# --- Univers multi-marchés (ex: CAC40 + sélection libre via champ) ---
st.subheader("🌍 Univers analysé")
st.caption("Par défaut CAC 40. Tu peux ajouter des tickers séparés par des virgules (ex: AAPL, MSFT, SAP.DE, AIR.PA)")
free = st.text_input("Ajouter des tickers (optionnel)", "")
base = [m.get("symbol") for m in yahoo_search("CAC 40")] or []
# si la recherche ne marche pas, fallback simple : on ne surcharge pas, on reste CAC40 manuel via Wikipedia indirectement
# Ici on télécharge juste ce qui est fourni
tickers = []
if free.strip():
    tickers = [x.strip() for x in free.replace(";",",").split(",") if x.strip()]
if not tickers:
    # fallback minimal : récupérations de quelques poids lourds CAC
    tickers = ["TTE.PA","AIR.PA","MC.PA","OR.PA","AI.PA","BNP.PA","SU.PA","DG.PA","KER.PA","ORA.PA"]

px = fetch_prices(tickers, days=260)
data = compute_metrics(px)
if data.empty:
    st.warning("Aucune donnée disponible (connectivité ou tickers invalides)."); st.stop()

data["Indice"] = np.where(data["Ticker"].str.endswith(".PA"), "CAC 40 (approx)", "Autres")

# --- Résumé global ---
valid = data.dropna(subset=["Close"]).copy()
avg = (valid[value_col].dropna().mean()*100.0) if not valid.empty else np.nan
up = int((valid[value_col] > 0).sum()); down = int((valid[value_col] < 0).sum())

st.markdown(f"### 🧭 Résumé global ({periode})")
if np.isfinite(avg): st.markdown(f"**Variation moyenne : {avg:+.2f}%** — {up} hausses / {down} baisses")
else: st.markdown("Variation indisponible.")

disp = (valid[value_col].std()*100.0) if not valid.empty else np.nan
if np.isfinite(disp):
    st.caption("Marché calme" if disp<1.0 else "Volatilité modérée" if disp<2.5 else "Marché dispersé")

st.divider()

# --- Top / Flop 10 ---
st.subheader(f"🏆 Top 10 hausses & ⛔ Baisses — {periode}")
def prep_table(df, asc=False, n=10):
    if df.empty: return pd.DataFrame()
    cols = ["Ticker","Close", value_col,"Indice","MA120","MA240","trend_lt","score_ia"]
    for c in cols:
        if c not in df.columns: df[c]=np.nan
    out = df.sort_values(value_col, ascending=asc).head(n).copy()
    out["Variation %"] = (out[value_col]*100).round(2)
    out["Cours (€)"] = out["Close"].astype(float).round(2)
    out["LT"] = out["trend_lt"].apply(lambda v: "🌱" if v>0 else ("🌧" if v<0 else "⚖️"))
    out["Score IA"] = out["score_ia"].round(2)
    return out[["Indice","Ticker","Cours (€)","Variation %","LT","Score IA"]]

col1, col2 = st.columns(2)
with col1:
    top = prep_table(valid, asc=False, n=10)
    st.dataframe(style_variations(top, ["Variation %"]), use_container_width=True, hide_index=True) if not top.empty else st.info("—")
with col2:
    flop = prep_table(valid, asc=True, n=10)
    st.dataframe(style_variations(flop, ["Variation %"]), use_container_width=True, hide_index=True) if not flop.empty else st.info("—")

st.divider()

# --- Sélection IA TOP 10 ---
st.subheader("🚀 Sélection IA — Opportunités idéales (TOP 10)")
sel = select_top_actions(valid, profile=profil, n=10)
if sel.empty: st.info("Aucune opportunité claire détectée aujourd’hui.")
else:
    # couleur proximité & mise en avant
    def prox_style(v):
        from lib import proximity_style
        return proximity_style(v)
    def row_hl(row):
        from lib import highlight_near_entry_row
        return highlight_near_entry_row(row)
    st.dataframe(
        sel.style.apply(row_hl, axis=1).applymap(prox_style, subset=["Proximité (%)"]),
        use_container_width=True, hide_index=True
    )

# --- Mini bar charts ---
st.markdown("### 📊 Visualisation rapide")
def bar_chart(df, title):
    if df.empty: st.caption("—"); return
    d = df.copy(); d["Label"] = d["Ticker"].astype(str)
    chart = alt.Chart(d).mark_bar().encode(
        x=alt.X("Label:N", sort="-y", title=""),
        y=alt.Y("Variation %:Q", title="Variation (%)"),
        color=alt.Color("Variation %:Q", scale=alt.Scale(scheme="redyellowgreen")),
        tooltip=["Ticker","Variation %","Cours (€)","Indice"]
    ).properties(height=300, title=title)
    st.altair_chart(chart, use_container_width=True)

c3,c4 = st.columns(2)
with c3: bar_chart(top, f"Top 10 hausses ({periode})")
with c4: bar_chart(flop, f"Top 10 baisses ({periode})")
