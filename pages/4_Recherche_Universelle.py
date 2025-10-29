# -*- coding: utf-8 -*-
"""
Recherche universelle — v7.6 (base V6 + IA CT/LT)
"""
import streamlit as st, pandas as pd, numpy as np, altair as alt, requests, html, re, os, json
from datetime import datetime
from lib import (
    fetch_prices, compute_metrics, price_levels_from_row, decision_label_combined,
    company_name_from_ticker, get_profile_params, resolve_identifier,
    find_ticker_by_name, maybe_guess_yahoo, google_news_titles, filter_company_news
)

st.set_page_config(page_title="Recherche universelle", page_icon="🔍", layout="wide")
st.title("🔍 Recherche universelle — Analyse IA (CT + LT)")

DATA_PATH = "data/portfolio.json"
os.makedirs("data", exist_ok=True)
if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=["Ticker","Type","Qty","PRU","Name"]).to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)

# Mémoire session
if "ru_symbol" not in st.session_state: st.session_state["ru_symbol"] = ""
if "ru_query" not in st.session_state:  st.session_state["ru_query"]  = ""
if "ru_period" not in st.session_state: st.session_state["ru_period"] = "30 jours"

with st.expander("🔎 Recherche d’une valeur", expanded=True):
    c1, c2, c3 = st.columns([2,1,1])
    with c1:
        query = st.text_input("Nom / Ticker LS / ISIN / WKN / Yahoo", value=st.session_state["ru_query"])
    with c2:
        period = st.selectbox("Période du graphique", ["Jour","7 jours","30 jours","1 an","5 ans"],
                              index=["Jour","7 jours","30 jours","1 an","5 ans"].index(st.session_state["ru_period"]))
    with c3:
        if st.button("🔍 Lancer", use_container_width=True):
            if not query.strip(): st.warning("Entre un terme.")
            else:
                sym,_ = resolve_identifier(query)
                if not sym:
                    res=find_ticker_by_name(query) or []
                    if res: sym=res[0]["symbol"]
                if not sym: sym = maybe_guess_yahoo(query) or query.strip().upper()
                st.session_state["ru_symbol"]=sym; st.session_state["ru_query"]=query; st.session_state["ru_period"]=period
                st.rerun()

symbol = st.session_state.get("ru_symbol","")
if not symbol:
    st.info("🔍 Entre un nom ou ticker ci-dessus pour lancer l’analyse."); st.stop()

# Données
days_map = {"Jour":5,"7 jours":10,"30 jours":40,"1 an":400,"5 ans":1300}
days_graph = days_map[st.session_state["ru_period"]]
hist_graph = fetch_prices([symbol], days=days_graph)
hist_full  = fetch_prices([symbol], days=260)
metrics = compute_metrics(hist_full)
if metrics.empty: st.warning("Impossible de calculer les indicateurs."); st.stop()

row = metrics.iloc[0]
name = company_name_from_ticker(symbol)
profil = st.session_state.get("profil", "Neutre")
entry, target, stop = price_levels_from_row(row, profil).values()
decision = decision_label_combined(row, held=False, vol_max=get_profile_params(profil)["vol_max"])

# Header metrics
c1,c2,c3,c4,c5 = st.columns([1.6,1,1,1,1])
with c1:
    st.markdown(f"## {name}  \n`{symbol}`")
    st.caption("CT : MA20/MA50 • LT : MA120/MA240 • Score IA combiné.")
with c2: st.metric("Cours", f"{row['Close']:.2f}")
with c3: st.metric("MA20 / MA50", f"{(row['MA20'] or np.nan):.2f} / {(row['MA50'] or np.nan):.2f}")
with c4: st.metric("MA120 / MA240", f"{(row['MA120'] or np.nan):.2f} / {(row['MA240'] or np.nan):.2f}")
with c5: st.metric("Score IA", f"{row['score_ia']:.2f}")

v1d,v7d,v30 = row.get("pct_1d",np.nan), row.get("pct_7d",np.nan), row.get("pct_30d",np.nan)
pp = lambda x: f"{x*100:+.2f}%" if pd.notna(x) else "—"
st.markdown(f"**Variations** — 1j: {pp(v1d)} · 7j: {pp(v7d)} · 30j: {pp(v30)}")

st.divider()

# Synthèse IA & bouton ajout
cA,cB = st.columns([1.2,2])
with cA:
    st.subheader("🧠 Synthèse IA")
    lt = "🌱 LT haussier" if int(row.get("trend_lt",0))>0 else ("🌧 LT baissier" if int(row.get("trend_lt",0))<0 else "⚖️ LT neutre")
    st.markdown(
        f"- **Décision combinée** : {decision}\n"
        f"- **Entrée** ≈ **{entry:.2f}** · **Objectif** ≈ **{target:.2f}** · **Stop** ≈ **{stop:.2f}**\n"
        f"- **Tendance** : {lt}"
    )
    prox = ((row["Close"]/entry)-1)*100 if (entry and entry>0) else np.nan
    if pd.notna(prox):
        emo = "🟢" if abs(prox)<=2 else ("⚠️" if abs(prox)<=5 else "🔴")
        st.markdown(f"- **Proximité entrée** : {prox:+.2f}% {emo}")
        if abs(prox)<=2: st.success("🟢 Zone d’achat potentielle.")
        elif abs(prox)<=5: st.warning("⚠️ Proche de l’entrée.")
        else: st.info("🔴 Éloigné — attendre un repli.")

    st.divider()
    st.markdown("### ➕ Ajouter au portefeuille")
    type_port = st.selectbox("Type de compte", ["PEA","CTO"])
    qty = st.number_input("Quantité", min_value=0.0, step=1.0)
    pru = st.number_input("PRU (€)", min_value=0.0, step=0.01, value=float(row["Close"]))
    if st.button("💼 Ajouter"):
        try:
            pf=pd.read_json(DATA_PATH)
            pf=pd.concat([pf, pd.DataFrame([{"Ticker":symbol.upper(),"Type":type_port,"Qty":qty,"PRU":pru,"Name":name}])], ignore_index=True)
            pf.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
            st.success(f"✅ {name} ({symbol}) ajouté.")
        except Exception as e:
            st.error(f"Erreur : {e}")

with cB:
    st.subheader(f"📈 Graphique — {st.session_state['ru_period']}")
    if hist_graph.empty or "Date" not in hist_graph.columns: st.caption("Pas assez d'historique.")
    else:
        d=hist_graph[hist_graph["Ticker"]==symbol].copy().sort_values("Date")
        base=alt.Chart(d).mark_line(color="#3B82F6").encode(
            x=alt.X("Date:T", title=""), y=alt.Y("Close:Q", title="Cours"),
            tooltip=["Date:T", alt.Tooltip("Close:Q", format=".2f")]
        ).properties(height=380)
        lv=pd.DataFrame({"y":[entry,target,stop],"label":["Entrée ~","Objectif ~","Stop ~"]})
        rules=alt.Chart(lv).mark_rule(strokeDash=[6,4]).encode(y="y:Q", color=alt.value("#888"), tooltip=["label:N","y:Q"])
        st.altair_chart(base+rules, use_container_width=True)

st.divider()

# Actualités
st.subheader("📰 Actualités récentes")
items = google_news_titles(f"{name} {symbol}", "fr")
items = filter_company_news(symbol, name, items)
if not items: items = google_news_titles(name, "fr")
if items:
    for t,link,pub in items:
        dt=""
        try:
            if pub and "," in pub:
                dt=datetime.strptime(pub.split(",")[1].strip(), "%d %b %Y %H:%M:%S %Z").strftime("%d/%m/%Y")
        except Exception:
            dt = pub or ""
        st.markdown(f"- [{t}]({link})  — *{dt}*")
else:
    st.caption("Aucune actualité disponible.")
