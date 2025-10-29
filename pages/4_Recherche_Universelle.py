# -*- coding: utf-8 -*-
"""
v7.0 — Recherche universelle
- Recherche intégrée (Nom / Ticker LS / ISIN / WKN / Yahoo)
- Mémoire de la dernière recherche
- Analyse IA complète (MA20/MA50/ATR, Entrée / Objectif / Stop, Décision IA)
- Graphique avec lignes de niveaux
- Actualités ciblées (liens + dates + résumé IA)
- ➕ Bouton "Ajouter au portefeuille" (sauvegarde directe dans portfolio.json)
"""

import streamlit as st, pandas as pd, numpy as np, altair as alt, requests, html, re, os, json
from datetime import datetime
from lib import (
    fetch_prices, compute_metrics, price_levels_from_row, decision_label_from_row,
    company_name_from_ticker, get_profile_params, resolve_identifier,
    find_ticker_by_name, maybe_guess_yahoo, load_profile   # 👈 profil cohérent
)

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Recherche universelle", page_icon="🔍", layout="wide")
st.title("🔍 Recherche universelle — Analyse IA complète")

DATA_PATH = "data/portfolio.json"
os.makedirs("data", exist_ok=True)
if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=["Ticker", "Type", "Qty", "PRU", "Name"]).to_json(
        DATA_PATH, orient="records", indent=2, force_ascii=False
    )

# ---------------- HELPERS ----------------
def remember_last_search(symbol=None, query=None, period=None):
    if symbol is not None:
        st.session_state["ru_symbol"] = symbol
    if query is not None:
        st.session_state["ru_query"] = query
    if period is not None:
        st.session_state["ru_period"] = period

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
    pos_kw = ["résultats", "bénéfice", "guidance", "relève", "contrat", "approbation", "dividende", "rachat", "upgrade", "partenariat", "record"]
    neg_kw = ["profit warning", "avertissement", "enquête", "retard", "rappel", "amende", "downgrade", "abaisse", "procès", "licenciement", "chute"]
    if not titles:
        return "Pas d’actualité saillante — mouvement possiblement technique (flux, arbitrages, macro)."
    s = 0
    for t, _, _ in titles:
        low = t.lower()
        if any(k in low for k in pos_kw): s += 1
        if any(k in low for k in neg_kw): s -= 1
    if s >= 1:
        return "Hausse soutenue par des nouvelles positives (résultats/contrats/relèvements)."
    elif s <= -1:
        return "Pression liée à des nouvelles défavorables (abaissements, enquêtes, retards)."
    else:
        return "Actualité mitigée/neutre : mouvement surtout technique (rotation sectorielle, macro)."

def pretty_pct(x):
    return f"{x*100:+.2f}%" if pd.notna(x) else "—"

# ---------------- RECHERCHE ----------------
last_symbol, last_query, last_period = get_last_search()

with st.expander("🔎 Recherche d’une valeur", expanded=True):
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        query = st.text_input("Nom / Ticker LS / ISIN / WKN / Yahoo", value=last_query)
    with c2:
        period = st.selectbox("Période du graphique", ["Jour", "7 jours", "30 jours", "1 an", "5 ans"],
                              index=["Jour","7 jours","30 jours","1 an","5 ans"].index(last_period))
    with c3:
        if st.button("🔍 Lancer la recherche", use_container_width=True):
            if not query.strip():
                st.warning("Entre un terme de recherche.")
            else:
                sym, src = resolve_identifier(query)
                if not sym:
                    results = find_ticker_by_name(query) or []
                    if results:
                        sym = results[0]["symbol"]
                if not sym:
                    sym = maybe_guess_yahoo(query) or query.strip().upper()
                remember_last_search(symbol=sym, query=query, period=period)
                st.rerun()

symbol = st.session_state.get("ru_symbol", "")
if not symbol:
    st.info("🔍 Entre un nom ou ticker ci-dessus pour lancer l’analyse IA complète.")
    st.stop()

# ---------------- DONNÉES ----------------
days_map = {"Jour": 5, "7 jours": 10, "30 jours": 40, "1 an": 400, "5 ans": 1300}
days_graph = days_map[period]
hist_graph = fetch_prices([symbol], days=days_graph)
hist_full = fetch_prices([symbol], days=120)
metrics = compute_metrics(hist_full)

if metrics.empty:
    st.warning("Impossible de calculer les indicateurs sur cette valeur.")
    st.stop()

row = metrics.iloc[0]
name = company_name_from_ticker(symbol)

# ---------------- ANALYSE ----------------
col1, col2, col3, col4 = st.columns([1.6, 1, 1, 1])
with col1:
    st.markdown(f"## {name}  \n`{symbol}`")
    st.caption("Analyse IA basée sur MA20/MA50/ATR (120 jours fixes).")
with col2:
    st.metric("Cours", f"{row['Close']:.2f}")
with col3:
    st.metric("MA20 / MA50",
              f"{(row['MA20'] if pd.notna(row['MA20']) else np.nan):.2f} / {(row['MA50'] if pd.notna(row['MA50']) else np.nan):.2f}")
with col4:
    st.metric("ATR14", f"{(row['ATR14'] if pd.notna(row['ATR14']) else np.nan):.2f}")

v1d, v7d, v30 = row.get("pct_1d", np.nan), row.get("pct_7d", np.nan), row.get("pct_30d", np.nan)
st.markdown(f"**Variations** — 1j: {pretty_pct(v1d)} · 7j: {pretty_pct(v7d)} · 30j: {pretty_pct(v30)}")

st.divider()

# 👇 Profil IA cohérent avec lib/load_profile
profil = load_profile()
levels = price_levels_from_row(row, profil)
entry, target, stop = levels["entry"], levels["target"], levels["stop"]
decision = decision_label_from_row(row, held=False, vol_max=get_profile_params(profil)["vol_max"])

cA, cB = st.columns([1.2, 2])

with cA:
    st.subheader("🧠 Synthèse IA")
    vol = (abs(row["MA20"] - row["MA50"]) / row["MA50"] * 100) if (pd.notna(row["MA20"]) and pd.notna(row["MA50"]) and row["MA50"] != 0) else np.nan
    st.markdown(
        f"- **Décision IA** : {decision}\n"
        f"- **Entrée** ≈ **{entry:.2f}** · **Objectif** ≈ **{target:.2f}** · **Stop** ≈ **{stop:.2f}**\n"
        f"- **Volatilité** : {'faible' if vol < 2 else 'modérée' if vol < 5 else 'élevée'} ({vol:.2f}%)"
    )

    # --- Proximité entrée + emoji (dans la même colonne)
    prox = ((row["Close"] / entry) - 1) * 100 if entry and entry > 0 else np.nan
    if np.isfinite(prox):
        emoji = "🟢" if abs(prox) <= 2 else ("⚠️" if abs(prox) <= 5 else "🔴")
        st.markdown(f"- **Proximité de l’entrée** : {prox:+.2f}% {emoji}")
        if abs(prox) <= 2:
            st.success("🟢 Cette valeur est proche du point d’entrée idéal (zone d’achat potentielle).")
        elif abs(prox) <= 5:
            st.warning("⚠️ Cours modérément éloigné de l’entrée idéale.")
        else:
            st.info("🔴 Cours éloigné du point d’entrée — attendre un repli.")
    else:
        st.caption("Proximité non calculable.")

    st.divider()
    st.markdown("### ➕ Ajouter cette valeur au portefeuille")
    type_port = st.selectbox("Type de compte", ["PEA", "CTO"])
    qty = st.number_input("Quantité", min_value=0.0, step=1.0)
    pru = st.number_input("Prix d’achat estimé (PRU €)", min_value=0.0, step=0.01, value=float(row["Close"]))
    if st.button("💼 Ajouter au portefeuille"):
        try:
            pf = pd.read_json(DATA_PATH)
            pf = pd.concat([pf, pd.DataFrame([{
                "Ticker": symbol.upper(),
                "Type": type_port,
                "Qty": qty,
                "PRU": pru,
                "Name": name
            }])], ignore_index=True)
            pf.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
            st.success(f"✅ {name} ({symbol}) ajouté au portefeuille {type_port}.")
        except Exception as e:
            st.error(f"Erreur lors de l’ajout : {e}")

with cB:
    st.subheader(f"📈 Graphique — {period}")
    if hist_graph.empty or "Date" not in hist_graph.columns:
        st.caption("Pas assez d'historique.")
    else:
        d = hist_graph[hist_graph["Ticker"] == symbol].copy().sort_values("Date")
        base = alt.Chart(d).mark_line(color="#3B82F6").encode(
            x=alt.X("Date:T", title=""),
            y=alt.Y("Close:Q", title="Cours"),
            tooltip=["Date:T", alt.Tooltip("Close:Q", format=".2f")]
        ).properties(height=380)
        lv = pd.DataFrame({"y":[entry, target, stop],
                           "label":["Entrée ~","Objectif ~","Stop ~"]})
        rules = alt.Chart(lv).mark_rule(strokeDash=[6,4]).encode(
            y="y:Q", color=alt.value("#888"), tooltip=["label:N","y:Q"]
        )
        st.altair_chart(base + rules, use_container_width=True)

st.divider()

# ---------------- ACTUALITÉS ----------------
st.subheader("📰 Actualités récentes ciblées")
news = google_news_titles_and_links(f"{name} {symbol}", lang="fr", limit=6)
if not news:
    news = google_news_titles_and_links(name, lang="fr", limit=6)

if news:
    st.markdown("**Résumé IA (2–3 lignes)**")
    st.info(short_news_summary(news))
    st.markdown("**Articles**")
    for title, link, date in news:
        date_txt = f" *(publié le {date})*" if date else ""
        st.markdown(f"- [{title}]({link}){date_txt}")
else:
    st.caption("Aucune actualité disponible pour cette valeur.")

# ---------------- MÉMO ----------------
remember_last_search(symbol=symbol, query=query if 'query' in locals() else last_query, period=period)
