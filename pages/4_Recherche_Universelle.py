# -*- coding: utf-8 -*-
"""
v7.2 — Recherche universelle IA Hybride
- Combine MA20/MA50 (trading) et MA120/MA240 (investissement long terme)
- Ajoute analyse double IA (CT / LT)
- Affiche les deux tendances (MA20/50 et MA120/240) sur le graphique
- Donne un score long terme 0–10
- Recommandation combinée IA
"""

import streamlit as st, pandas as pd, numpy as np, altair as alt, requests, html, re, os, json
from datetime import datetime
from lib import (
    fetch_prices, compute_metrics, price_levels_from_row, decision_label_from_row,
    company_name_from_ticker, get_profile_params, resolve_identifier,
    find_ticker_by_name, maybe_guess_yahoo
)

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Recherche universelle", page_icon="🔍", layout="wide")
st.title("🔍 Recherche universelle — Analyse IA Hybride (CT + LT)")

DATA_PATH = "data/portfolio.json"
os.makedirs("data", exist_ok=True)
if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=["Ticker", "Type", "Qty", "PRU", "Name"]).to_json(
        DATA_PATH, orient="records", indent=2, force_ascii=False
    )

# ---------------- HELPERS ----------------
def remember_last_search(symbol=None, query=None, period=None):
    if symbol is not None: st.session_state["ru_symbol"] = symbol
    if query is not None: st.session_state["ru_query"] = query
    if period is not None: st.session_state["ru_period"] = period

def get_last_search(default_period="30 jours"):
    return (
        st.session_state.get("ru_symbol", ""),
        st.session_state.get("ru_query", ""),
        st.session_state.get("ru_period", default_period),
    )

def google_news_titles_and_links(q, lang="fr", limit=6):
    """Mini fetch Google News RSS → [(title, link, pubdate)]."""
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(q)}&hl={lang}-{lang.upper()}&gl={lang.upper()}&ceid={lang.upper()}:{lang.upper()}"
    try:
        xml = requests.get(url, timeout=10).text
        items = re.findall(r"<item>(.*?)</item>", xml, flags=re.S)
        out = []
        for it in items:
            tt = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", it, flags=re.S)
            lk = re.search(r"<link>(.*?)</link>", it, flags=re.S)
            dt = re.search(r"<pubDate>(.*?)</pubDate>", it)
            t = html.unescape((tt.group(1) or tt.group(2) or "").strip()) if tt else ""
            l = (lk.group(1).strip() if lk else "")
            d = ""
            if dt:
                try:
                    d = datetime.strptime(dt.group(1).strip(), "%a, %d %b %Y %H:%M:%S %Z").strftime("%d/%m/%Y")
                except Exception:
                    d = dt.group(1).strip()
            if t and l:
                out.append((t, l, d))
            if len(out) >= limit:
                break
        return out
    except Exception:
        return []

def short_news_summary(titles):
    pos_kw = ["résultats","bénéfice","guidance","relève","contrat","approbation","dividende","rachat","upgrade","partenariat","record"]
    neg_kw = ["profit warning","avertissement","enquête","retard","rappel","amende","downgrade","abaisse","procès","licenciement","chute"]
    if not titles:
        return "Pas d’actualité saillante — mouvement possiblement technique (flux, arbitrages, macro)."
    s = 0
    for t, _, _ in titles:
        low = t.lower()
        if any(k in low for k in pos_kw): s += 1
        if any(k in low for k in neg_kw): s -= 1
    if s >= 1: return "Hausse soutenue par des nouvelles positives (résultats/contrats/relèvements)."
    elif s <= -1: return "Pression liée à des nouvelles défavorables (abaissements, enquêtes, retards)."
    else: return "Actualité mitigée/neutre : mouvement surtout technique."

def pretty_pct(x): return f"{x*100:+.2f}%" if pd.notna(x) else "—"

# ---------------- RECHERCHE ----------------
last_symbol, last_query, last_period = get_last_search()

with st.expander("🔎 Recherche d’une valeur", expanded=True):
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        query = st.text_input("Nom / Ticker / ISIN / WKN / Yahoo", value=last_query)
    with c2:
        period = st.selectbox("Période du graphique", ["Jour","7 jours","30 jours","1 an","5 ans"],
                              index=["Jour","7 jours","30 jours","1 an","5 ans"].index(last_period))
    with c3:
        if st.button("🔍 Lancer la recherche", use_container_width=True):
            if not query.strip():
                st.warning("Entre un terme de recherche.")
            else:
                sym, src = resolve_identifier(query)
                if not sym:
                    results = find_ticker_by_name(query) or []
                    if results: sym = results[0]["symbol"]
                if not sym:
                    sym = maybe_guess_yahoo(query) or query.strip().upper()
                remember_last_search(symbol=sym, query=query, period=period)
                st.rerun()

symbol = st.session_state.get("ru_symbol", "")
if not symbol:
    st.info("🔍 Entre un nom ou ticker ci-dessus pour lancer l’analyse IA complète.")
    st.stop()

# ---------------- DONNÉES ----------------
days_map = {"Jour":5,"7 jours":10,"30 jours":40,"1 an":400,"5 ans":1300}
days_graph = days_map[period]

hist_graph = fetch_prices([symbol], days=days_graph)
hist_full = fetch_prices([symbol], days=360)
metrics = compute_metrics(hist_full)

if metrics.empty:
    st.warning("Impossible de calculer les indicateurs sur cette valeur.")
    st.stop()

row = metrics.iloc[0]
name = company_name_from_ticker(symbol)

# ---------------- ANALYSE HYBRIDE ----------------
st.header(f"{name} ({symbol}) — Analyse IA Hybride")

col1, col2, col3, col4 = st.columns([1.4,1,1,1])
with col1: st.caption("Analyse combinée court / long terme (MA20/50/120/240).")
with col2: st.metric("Cours actuel", f"{row['Close']:.2f} €")
with col3: st.metric("Volatilité (ATR14)", f"{(row['ATR14'] if pd.notna(row['ATR14']) else np.nan):.2f}")
with col4: st.metric("MA20 / MA50 / MA120 / MA240",
                     f"{row.get('MA20',np.nan):.0f} / {row.get('MA50',np.nan):.0f} / {row.get('MA120',np.nan):.0f} / {row.get('MA240',np.nan):.0f}")

# Tendance CT et LT
def tendance(row):
    ma20, ma50, ma120, ma240, px = row["MA20"], row["MA50"], row["MA120"], row["MA240"], row["Close"]
    if pd.isna(ma20) or pd.isna(ma50) or pd.isna(ma120) or pd.isna(ma240): return "❓ Données incomplètes"
    if px > ma120 > ma240:
        lt = "🌱 Long terme : haussier"
    elif px < ma120 < ma240:
        lt = "🌧 Long terme : baissier"
    else:
        lt = "⚖️ Long terme : neutre"

    if px > ma20 > ma50:
        ct = "📈 Court terme : haussier"
    elif px < ma20 < ma50:
        ct = "📉 Court terme : baissier"
    else:
        ct = "⚖️ Court terme : neutre"

    return f"{ct} · {lt}"

st.markdown(f"**Tendance combinée :** {tendance(row)}")

# --- Score LT
score_lt = 5
if row["Close"] > row["MA120"]: score_lt += 2
if row["Close"] > row["MA240"]: score_lt += 3
st.metric("Score LT (0–10)", f"{score_lt}/10", delta=None)

# --- Décision IA
profil = st.session_state.get("profil", "Neutre")
entry, target, stop = price_levels_from_row(row, profil).values()
decision = decision_label_from_row(row, held=False, vol_max=get_profile_params(profil)["vol_max"])
st.subheader("🧠 Recommandation IA")
st.markdown(f"**Décision IA :** {decision}  \n**Entrée :** {entry:.2f} € | **Objectif :** {target:.2f} € | **Stop :** {stop:.2f} €")

# ---------------- GRAPHIQUE ----------------
st.subheader(f"📈 Graphique {period} — avec MA20 / MA50 / MA120 / MA240")

if hist_graph.empty or "Date" not in hist_graph.columns:
    st.caption("Pas assez d'historique.")
else:
    d = hist_graph[hist_graph["Ticker"] == symbol].copy().sort_values("Date")
    base = alt.Chart(d).mark_line(color="#3B82F6", strokeWidth=2).encode(
        x="Date:T", y="Close:Q", tooltip=["Date:T", alt.Tooltip("Close:Q", format=".2f")]
    )
    ma20 = alt.Chart(d).mark_line(color="#22c55e", strokeDash=[3,2]).encode(x="Date:T", y="MA20:Q")
    ma50 = alt.Chart(d).mark_line(color="#16a34a", strokeDash=[4,2]).encode(x="Date:T", y="MA50:Q")
    ma120 = alt.Chart(d).mark_line(color="#fbbf24", strokeDash=[4,2]).encode(x="Date:T", y="MA120:Q")
    ma240 = alt.Chart(d).mark_line(color="#ef4444", strokeDash=[4,2]).encode(x="Date:T", y="MA240:Q")

    chart = (base + ma20 + ma50 + ma120 + ma240).properties(height=420, title=f"{symbol} — Évolution complète")
    st.altair_chart(chart, use_container_width=True)
    st.caption("🟦 Cours | 🟢 MA20/50 (court terme) | 🟠 MA120 (6 mois) | 🔴 MA240 (12 mois)")

# ---------------- NEWS ----------------
st.subheader("📰 Actualités récentes")
news = google_news_titles_and_links(f"{name} {symbol}", lang="fr", limit=6)
if not news: news = google_news_titles_and_links(name, lang="fr", limit=6)

if news:
    st.info(short_news_summary(news))
    for title, link, date in news:
        date_txt = f" *(publié le {date})*" if date else ""
        st.markdown(f"- [{title}]({link}){date_txt}")
else:
    st.caption("Aucune actualité disponible pour cette valeur.")
