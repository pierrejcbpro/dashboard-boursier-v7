# -*- coding: utf-8 -*-
"""
v7.6 — Synthèse Flash IA (structure V6.9 conservée)
- Score IA combiné (MA20/50 + MA120/240) si dispo, sinon fallback local
- Tendance long terme (LT) 🌱 / 🌧 / ⚖️ dérivée de MA120 vs MA240
- Proximité & signal d’entrée identiques à V6.9
- Compatible lib v7.6 (compute_metrics / select_top_actions / news_summary)
"""
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

profil = st.sidebar.radio(
    "Profil IA", ["Prudent","Neutre","Agressif"],
    index=["Prudent","Neutre","Agressif"].index(load_profile())
)
if st.sidebar.button("💾 Mémoriser le profil"):
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
if include_us: MARKETS += [("NASDAQ 100", None), ("S&P 500", None)]  # S&P 500 ignoré si non supporté par lib
if include_ls: MARKETS += [("LS Exchange", None)]                     # idem

if not MARKETS:
    st.warning("Aucun marché sélectionné. Active au moins un marché dans la barre latérale.")
    st.stop()

# v7.6: on prend 240j pour avoir MA240 disponibles
data = fetch_all_markets(MARKETS, days_hist=240)
if data.empty:
    st.warning("Aucune donnée disponible (vérifie la connectivité ou ta sélection de marchés).")
    st.stop()

# Colonnes variat si absentes
for c in ["pct_1d","pct_7d","pct_30d"]:
    if c not in data.columns:
        data[c] = np.nan

# LT icon (🌱/🌧/⚖️) — robuste même si pas de lt_trend_score
def _lt_icon(row):
    ma120 = row.get("MA120", np.nan)
    ma240 = row.get("MA240", np.nan)
    if np.isfinite(ma120) and np.isfinite(ma240):
        if ma120 > ma240: return "🌱"
        if ma120 < ma240: return "🌧"
        return "⚖️"
    # fallback si la lib expose déjà un score LT signé
    v = row.get("lt_trend_score", np.nan)
    if np.isfinite(v):
        return "🌱" if v > 0 else ("🌧" if v < 0 else "⚖️")
    return "⚪"

valid = data.dropna(subset=["Close"]).copy()
valid["LT"] = valid.apply(_lt_icon, axis=1)

# IA_Score fallback local si absent (pondère LT > ST)
if "IA_Score" not in valid.columns:
    for c in ["trend_score","lt_trend_score","pct_7d","pct_30d","ATR14"]:
        if c not in valid.columns: valid[c] = np.nan
    valid["Volatilité"] = valid["ATR14"] / valid["Close"]
    valid["IA_Score"] = (
        valid["lt_trend_score"].fillna(0)*60
        + valid["trend_score"].fillna(0)*40
        + valid["pct_30d"].fillna(0)*100
        + valid["pct_7d"].fillna(0)*50
        - valid["Volatilité"].fillna(0)*10
    )

# ---------------- Résumé global ----------------
avg = (valid[value_col].dropna().mean() * 100.0) if not valid.empty else np.nan
up = int((valid[value_col] > 0).sum())
down = int((valid[value_col] < 0).sum())

st.markdown(f"### 🧭 Résumé global ({periode})")
if np.isfinite(avg):
    st.markdown(f"**Variation moyenne : {avg:+.2f}%** — {up} hausses / {down} baisses")
else:
    st.markdown("Variation indisponible pour cette période.")

disp = (valid[value_col].std() * 100.0) if not valid.empty else np.nan
if np.isfinite(disp):
    if disp < 1.0:
        st.caption("Marché calme — consolidation technique.")
    elif disp < 2.5:
        st.caption("Volatilité modérée — quelques leaders sectoriels.")
    else:
        st.caption("Marché dispersé — forte rotation / flux macro.")

st.divider()

# ---------------- Top / Flop élargi (10 + / -) ----------------
st.subheader(f"🏆 Top 10 hausses & ⛔ Baisses — {periode}")

def prep_table(df, asc=False, n=10):
    if df.empty: return pd.DataFrame()
    cols = ["Ticker","name","Close", value_col,"Indice","IA_Score","LT"]
    for c in cols:
        if c not in df.columns: df[c] = np.nan
    out = df.sort_values(value_col, ascending=asc).head(n).copy()
    out.rename(columns={"name":"Société","Close":"Cours (€)"}, inplace=True)
    out["Variation %"] = (out[value_col] * 100).round(2)
    out["Cours (€)"] = out["Cours (€)"].round(2)
    return out[["Indice","Société","Ticker","Cours (€)","Variation %","LT","IA_Score"]]

col1, col2 = st.columns(2)
with col1:
    top = prep_table(valid, asc=False, n=10)
    if top.empty: st.info("Pas de hausses.")
    else: st.dataframe(style_variations(top, ["Variation %"]), use_container_width=True, hide_index=True)
with col2:
    flop = prep_table(valid, asc=True, n=10)
    if flop.empty: st.info("Pas de baisses.")
    else: st.dataframe(style_variations(flop, ["Variation %"]), use_container_width=True, hide_index=True)

st.divider()

# ---------------- Sélection IA TOP 10 ----------------
st.subheader("🚀 Sélection IA — Opportunités idéales (TOP 10)")
# select_top_actions de la lib v7.6 renvoie déjà :
# ["Société","Symbole","Cours (€)","Trend ST","Trend LT","Perf 7j (%)",
#  "Perf 30j (%)","Risque","Score IA","Signal","Entrée (€)","Objectif (€)","Stop (€)","Proximité (%)"]
top_actions = select_top_actions(valid, profile=profil, n=10, include_proximity=True)

if top_actions.empty:
    st.info("Aucune opportunité claire détectée aujourd’hui selon l’IA.")
else:
    # Sécurise la Proximité (%) si l’ancienne lib ne la renvoie pas
    def compute_proximity(row):
        e = row.get("Entrée (€)")
        px = row.get("Cours (€)")
        if not np.isfinite(e) or not np.isfinite(px) or e == 0:
            return np.nan
        return ((px / e) - 1) * 100

    if "Proximité (%)" not in top_actions.columns:
        top_actions["Proximité (%)"] = top_actions.apply(compute_proximity, axis=1)

    # Emoji visuel
    def proximity_marker(v):
        if pd.isna(v): return "⚪"
        if abs(v) <= 2: return "🟢"
        elif abs(v) <= 5: return "⚠️"
        else: return "🔴"
    top_actions["Signal Entrée"] = top_actions["Proximité (%)"].apply(proximity_marker)

    # Moyenne de proximité
    prox_mean = top_actions["Proximité (%)"].dropna().mean()
    if pd.notna(prox_mean):
        emoji = "🟢" if abs(prox_mean) <= 2 else ("⚠️" if abs(prox_mean) <= 5 else "🔴")
        st.markdown(f"**📏 Moyenne de proximité IA : {prox_mean:+.2f}% {emoji}**")
        if abs(prox_mean) <= 2:
            st.success("🟢 Marché global proche de zones d’achat idéales — momentum favorable.")
        elif abs(prox_mean) <= 5:
            st.warning("⚠️ Marché modérément éloigné des zones d’achat — à surveiller.")
        else:
            st.info("🔴 Marché éloigné des points d’entrée optimaux — patience recommandée.")

    # Styles
    def style_prox(v):
        if pd.isna(v): return ""
        if abs(v) <= 2:  return "background-color:#e8f5e9; color:#0b8043; font-weight:600;"
        if abs(v) <= 5:  return "background-color:#fff8e1; color:#a67c00;"
        return "background-color:#ffebee; color:#b71c1c;"

    def style_decision(val):
        if pd.isna(val): return ""
        if "Acheter" in val:   return "background-color:rgba(0,200,0,0.15); font-weight:600;"
        if "Éviter" in val:    return "background-color:rgba(255,0,0,0.15); font-weight:600;"
        if "Surveiller" in val:return "background-color:rgba(0,100,255,0.10); font-weight:600;"
        return ""

    styled = (
        top_actions.style
        .applymap(style_prox, subset=["Proximité (%)"])
        .applymap(style_decision, subset=["Signal"])
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

st.divider()

# ---------------- Injection IA — Idées micro-investissement (20 €)
st.divider()
st.subheader("💸 Injection IA — Idées micro-investissement (20 € chacun)")

if top_actions.empty:
    st.caption("Aucune opportunité IA détectée pour injection immédiate.")
else:
    invest_amount = 20.0
    fee_in = 1.0
    fee_out = 1.0
    total_fee = fee_in + fee_out

    micro_rows = []
    for _, r in top_actions.head(15).iterrows():
        entry = float(r.get("Entrée (€)", np.nan))
        target = float(r.get("Objectif (€)", np.nan))
        stop = float(r.get("Stop (€)", np.nan))
        score = float(r.get("Score IA", 50))

        # prix d'achat ajusté par frais
        if not np.isfinite(entry) or not np.isfinite(target) or entry <= 0:
            continue
        buy_price = entry + (fee_in / (invest_amount / entry))  # dilue 1€ dans le ticket
        shares = invest_amount / buy_price
        sell_price = target
        brut_gain = (sell_price - buy_price) * shares
        net_gain = brut_gain - fee_out
        net_return_pct = (net_gain / invest_amount) * 100

        micro_rows.append({
            "Société": r.get("Société") or r.get("name"),
            "Ticker": r.get("Ticker"),
            "Entrée (€)": round(entry, 2),
            "Objectif (€)": round(target, 2),
            "Stop (€)": round(stop, 2),
            "Score IA": round(score, 1),
            "Frais totaux (€)": total_fee,
            "Rendement net estimé (%)": round(net_return_pct, 2),
            "Durée visée": "7–30 j",
            "Décision IA": r.get("Signal") or "Acheter"
        })

    df_inject = pd.DataFrame(micro_rows)
    if df_inject.empty:
        st.info("Aucune action éligible à un micro-investissement rentable actuellement.")
    else:
        df_inject = df_inject.sort_values("Rendement net estimé (%)", ascending=False).head(5)

        def style_gain(v):
            if pd.isna(v): return ""
            if v > 5: return "background-color:#e8f5e9; color:#0b8043; font-weight:600;"
            if v > 0: return "background-color:#fff8e1; color:#a67c00;"
            return "background-color:#ffebee; color:#b71c1c;"

        st.dataframe(
            df_inject.style
                .applymap(style_gain, subset=["Rendement net estimé (%)"])
                .format({
                    "Entrée (€)":"{:.2f}",
                    "Objectif (€)":"{:.2f}",
                    "Stop (€)":"{:.2f}",
                    "Frais totaux (€)":"{:.0f}",
                    "Rendement net estimé (%)":"{:.2f}",
                    "Score IA":"{:.1f}"
                }),
            use_container_width=True, hide_index=True
        )

        best = df_inject.iloc[0]
        st.success(
            f"👉 **Meilleure idée IA : {best['Société']} ({best['Ticker']})** — "
            f"rendement net estimé **{best['Rendement net estimé (%)']:+.2f}%** sur 7–30 jours."
        )


# ---------------- Charts simples ----------------
st.markdown("### 📊 Visualisation rapide")
def bar_chart(df, title):
    if df.empty:
        st.caption("—"); return
    d = df.copy()
    if "Société" not in d.columns and "name" in d.columns:
        d["Société"] = d["name"]
    d["Label"] = d["Société"].astype(str) + " (" + d["Ticker"].astype(str) + ")"
    chart = (
        alt.Chart(d)
        .mark_bar()
        .encode(
            x=alt.X("Label:N", sort="-y", title=""),
            y=alt.Y("Variation %:Q", title="Variation (%)"),
            color=alt.Color("Variation %:Q", scale=alt.Scale(scheme="redyellowgreen")),
            tooltip=[c for c in ["Société","Ticker","Variation %","Cours (€)","Indice","LT","IA_Score"] if c in d.columns]
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
    nm = str(row.get("Société") or row.get("name") or "")
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
st.caption("💡 Active ou désactive les marchés US dans la barre latérale pour ajuster la vision mondiale.")
