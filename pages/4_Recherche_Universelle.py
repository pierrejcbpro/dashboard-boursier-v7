# -*- coding: utf-8 -*-
"""
v7.6 — Recherche Universelle
Analyse complète d’une valeur (IA ST+LT, Score IA, News)
"""

import streamlit as st, pandas as pd, numpy as np, altair as alt
from lib import (
    fetch_prices, compute_metrics, price_levels_from_row, decision_label_combined,
    company_name_from_ticker, get_profile_params, resolve_identifier,
    find_ticker_by_name, maybe_guess_yahoo, news_summary
)

# --- Config
st.set_page_config(page_title="Recherche Universelle", page_icon="🔍", layout="wide")
st.title("🔍 Recherche Universelle — Analyse IA complète")

# --- Entrée utilisateur
query = st.text_input("Nom / Ticker", value="")
if not query.strip():
    st.stop()

sym, _ = resolve_identifier(query)
if not sym:
    res = find_ticker_by_name(query)
    sym = res[0]["symbol"] if res else maybe_guess_yahoo(query)
if not sym:
    st.error("Aucun symbole valide trouvé.")
    st.stop()

# --- Données
hist = fetch_prices([sym], days=240)
met = compute_metrics(hist)
if met.empty:
    st.error("Impossible de calculer les métriques.")
    st.stop()

row = met.iloc[0]
name = company_name_from_ticker(sym)
profil = st.session_state.get("profil", "Neutre")
volmax = get_profile_params(profil)["vol_max"]

st.subheader(f"{name} ({sym})")

c1, c2, c3, c4, c5 = st.columns(5)
with c1: st.metric("Cours", f"{row['Close']:.2f}")
with c2: st.metric("MA20 / MA50", f"{row['MA20']:.2f} / {row['MA50']:.2f}")
with c3: st.metric("MA120 / MA240", f"{row['MA120']:.2f} / {row['MA240']:.2f}")
with c4: st.metric("ATR14", f"{row['ATR14']:.2f}")
with c5: st.metric("Score IA", f"{row.get('IA_Score', np.nan):.2f}")

# --- Décision IA
dec = decision_label_combined(row, held=False, vol_max=volmax)
levels = price_levels_from_row(row, profil)
st.info(f"🧠 **Décision IA :** {dec}\n\n🎯 **Entrée** {levels['entry']} · **Objectif** {levels['target']} · **Stop** {levels['stop']}")

# --- Graphique
if not hist.empty:
    chart = alt.Chart(hist).mark_line(color="#3b82f6").encode(
        x="Date:T", y="Close:Q", tooltip=["Date:T", "Close:Q"]
    ).properties(height=380)
    st.altair_chart(chart, use_container_width=True)

# --- Actualités
st.divider()
st.subheader("📰 Actualités récentes")
txt, score, news = news_summary(name, sym)
st.info(txt)
for t, l, d in news:
    st.markdown(f"- [{t}]({l}) *(publié le {d})*")
