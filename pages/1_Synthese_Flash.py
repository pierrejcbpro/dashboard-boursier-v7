# -*- coding: utf-8 -*-
"""
v7.9 — Synthèse Flash IA (full)
Base V6.9 conservée + enrichissements :
- Score IA (MA20/50 + MA120/240) via lib.select_top_actions
- Indicateurs LT 🌱/🌧/⚖️
- Proximité entrée, emoji Signal
- Ajout direct au Portefeuille Virtuel (data/virtual_trades.json)
- Protection colonnes manquantes / dupliquées
- Merge de l’Indice dans le tableau IA
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
include_ls = st.sidebar.checkbox("🧠 LS Exchange (perso)", value=False)  # placeholder, non utilisé par lib.fetch_all_markets

# ---------------- Données marchés ----------------
MARKETS = []
if include_eu: MARKETS += [("CAC 40", None), ("DAX", None)]
if include_us: MARKETS += [("NASDAQ 100", None), ("S&P 500", None)]
# NOTE : la lib actuelle supporte CAC40 / DAX / NASDAQ 100. S&P 500 est ignoré si non supporté.
#       On le garde pour UI cohérente ; lib.fetch_all_markets filtrera.
if include_ls:  # si tu ajoutes la logique LS dans lib, ça se branchera ici
    MARKETS += [("LS Exchange", None)]

if not MARKETS:
    st.warning("Aucun marché sélectionné. Active au moins un marché dans la barre latérale.")
    st.stop()

data = fetch_all_markets(MARKETS, days_hist=240)

if data.empty:
    st.warning("Aucune donnée disponible (vérifie la connectivité ou ta sélection de marchés).")
    st.stop()

# Colonnes minimales nécessaires
for c in ["pct_1d","pct_7d","pct_30d","Close","Ticker","name","Indice",
          "MA20","MA50","MA120","MA240","lt_trend_score","trend_score","IA_Score","trend_lt"]:
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
    cols = ["Ticker","name","Close", value_col,"Indice","IA_Score","trend_lt","MA20","MA50","MA120","MA240"]
    for c in cols:
        if c not in df.columns: df[c] = np.nan
    out = df.sort_values(value_col, ascending=asc).head(n).copy()
    out.rename(columns={"name":"Société","Close":"Cours (€)"}, inplace=True)
    out["Variation %"] = (out[value_col] * 100).round(2)
    out["Cours (€)"] = out["Cours (€)"].round(2)
    # LT emoji (si lib a rempli trend_lt comme -1/0/1 ; sinon on calcule vite fait via MA120/MA240)
    def lt_emoji(row):
        v = row.get("trend_lt", np.nan)
        if pd.notna(v):
            return "🌱" if v > 0 else ("🌧" if v < 0 else "⚖️")
        m120, m240 = row.get("MA120", np.nan), row.get("MA240", np.nan)
        if np.isfinite(m120) and np.isfinite(m240):
            return "🌱" if m120 > m240 else ("🌧" if m120 < m240 else "⚖️")
        return "⚖️"
    out["LT"] = out.apply(lt_emoji, axis=1)
    # Colonnes finales
    return out[["Indice","Société","Ticker","Cours (€)","Variation %","LT","IA_Score","MA20","MA50","MA120","MA240"]]

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

# On calcule une table IA complète à partir de valid
top_actions = select_top_actions(valid, profile=profil, n=10, include_proximity=True)

# select_top_actions renomme 'Ticker' en 'Symbole' et 'name' en 'Société'
# Il ne renvoie pas 'Indice' : on le merge depuis valid
if not top_actions.empty:
    if "Indice" not in top_actions.columns:
        idx_map = valid[["Ticker","Indice"]].drop_duplicates().copy()
        idx_map["Ticker"] = idx_map["Ticker"].astype(str).str.upper()
        # rattacher via Symbole -> Ticker
        if "Symbole" in top_actions.columns:
            tmp = top_actions.copy()
            tmp["Symbole"] = tmp["Symbole"].astype(str).str.upper()
            top_actions = tmp.merge(idx_map, left_on="Symbole", right_on="Ticker", how="left")
            # garde une seule colonne de code
            if "Ticker_y" in top_actions.columns: top_actions.drop(columns=[c for c in ["Ticker_y"] if c in top_actions.columns], inplace=True)
            if "Ticker_x" in top_actions.columns:
                top_actions.rename(columns={"Ticker_x":"Ticker"}, inplace=True)
            else:
                top_actions.rename(columns={"Symbole":"Ticker"}, inplace=True)
        else:
            # fallback rare : si pas de Symbole, essaye 'Ticker'
            top_actions = top_actions.merge(idx_map, on="Ticker", how="left")

    # Ajoute un LT emoji s'il n'existe pas
    if "LT" not in top_actions.columns:
        def lt_from_ma(row):
            m120, m240 = row.get("MA120", np.nan), row.get("MA240", np.nan)
            if np.isfinite(m120) and np.isfinite(m240):
                return "🌱" if m120 > m240 else ("🌧" if m120 < m240 else "⚖️")
            return "⚖️"
        top_actions["LT"] = top_actions.apply(lt_from_ma, axis=1)

# Affichage tableau IA avec toutes les colonnes utiles
if top_actions.empty:
    st.info("Aucune opportunité claire détectée aujourd’hui selon l’IA.")
else:
    # Colonnes cibles (on tolère les absences)
    want_cols = [
        "Indice", "Société", "Ticker",
        "Cours (€)", "MA20", "MA50", "MA120", "MA240",
        "Trend ST", "Trend LT", "Score IA",
        "Entrée (€)", "Objectif (€)", "Stop (€)",
        "Proximité (%)", "Signal", "LT"
    ]
    for c in want_cols:
        if c not in top_actions.columns:
            top_actions[c] = np.nan

    # Proximité -> emoji entrée si besoin
    def prox_emoji(v):
        if pd.isna(v): return "⚪"
        return "🟢" if abs(v) <= 2 else ("⚠️" if abs(v) <= 5 else "🔴")
    if "Signal Entrée" not in top_actions.columns:
        top_actions["Signal Entrée"] = top_actions["Proximité (%)"].apply(prox_emoji)

    # Affichage
    show_cols = [c for c in want_cols if c in top_actions.columns] + (["Signal Entrée"] if "Signal Entrée" in top_actions.columns else [])
    # évite colonnes dupliquées
    show_cols_unique = []
    seen = set()
    for c in show_cols:
        if c not in seen:
            show_cols_unique.append(c); seen.add(c)

    st.dataframe(
        top_actions[show_cols_unique].style.format(precision=2),
        use_container_width=True, hide_index=True
    )

# ---------------- Paramètres d’investissement virtuel ----------------
st.divider()
st.subheader("💸 Simulation d’investissement — Ajout direct au Portefeuille Virtuel")

# Prépare stockage
os.makedirs("data", exist_ok=True)
VFILE = "data/virtual_trades.json"
if not os.path.exists(VFILE):
    with open(VFILE, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)

# Contrôles globaux
c1, c2, c3, c4 = st.columns([1,1,1,2])
with c1:
    inv_default = st.number_input("Montant par ligne (€)", min_value=1.0, value=20.0, step=1.0, key="inv_default")
with c2:
    fee_in = st.number_input("Frais entrée (€)", min_value=0.0, value=1.0, step=0.5, key="fee_in")
with c3:
    fee_out = st.number_input("Frais sortie (€)", min_value=0.0, value=1.0, step=0.5, key="fee_out")
with c4:
    horizon = st.selectbox("Horizon visé", ["1 semaine", "2 semaines", "1 mois"], index=2, key="horizon_sel")

st.caption("Le nombre de titres est calculé comme ⌊(Montant - Frais entrée) / Cours⌋.")

# Bloc d’ajout par ligne (sur base du tableau IA)
if not top_actions.empty:
    st.markdown("#### ➕ Ajouter des lignes depuis la sélection IA")
    # On fabrique un mini tableau avec les colonnes demandées + bouton par ligne
    mini_cols = ["Société","Ticker","Cours (€)","Entrée (€)","Objectif (€)","Stop (€)","Proximité (%)","Signal Entrée","Score IA","Indice"]
    for c in mini_cols:
        if c not in top_actions.columns: top_actions[c] = np.nan
    mini = top_actions[mini_cols].copy()
    mini.reset_index(drop=True, inplace=True)

    for i, row in mini.iterrows():
        with st.container(border=True):
            colA, colB, colC, colD, colE, colF = st.columns([2,1.2,1.2,1.2,1.2,1.2])
            with colA:
                st.markdown(f"**{row['Société']}**  \n`{row['Ticker']}`  \n_{row.get('Indice','')}_")
            with colB:
                st.metric("Cours", f"{row['Cours (€)']:.2f}" if pd.notna(row['Cours (€)']) else "—")
            with colC:
                st.metric("Entrée", f"{row['Entrée (€)']:.2f}" if pd.notna(row['Entrée (€)']) else "—")
            with colD:
                st.metric("Objectif", f"{row['Objectif (€)']:.2f}" if pd.notna(row['Objectif (€)']) else "—")
            with colE:
                st.metric("Stop", f"{row['Stop (€)']:.2f}" if pd.notna(row['Stop (€)']) else "—")
            with colF:
                st.metric("Proximité", f"{row['Proximité (%)']:.2f}%" if pd.notna(row['Proximité (%)']) else "—")

            c1a, c1b, c1c, c1d = st.columns([1.2,1,1,1.5])
            with c1a:
                inv = st.number_input("Montant (€)", min_value=1.0, value=float(inv_default), step=1.0, key=f"inv_{i}")
            with c1b:
                qty = 0.0
                px = float(row["Cours (€)"]) if pd.notna(row["Cours (€)"]) else np.nan
                if np.isfinite(px) and px > 0:
                    qty = np.floor(max(inv - fee_in, 0)/px)
                st.metric("Qté", f"{int(qty)}")
            with c1c:
                # Rendement net estimé = (Objectif - Cours) * qté - frais sortie -> en %
                rn_pct = np.nan
                if np.isfinite(px) and np.isfinite(qty) and qty > 0:
                    obj = float(row["Objectif (€)"]) if pd.notna(row["Objectif (€)"]) else np.nan
                    if np.isfinite(obj):
                        pnl_eur = (obj - px) * qty - fee_out
                        base = inv
                        rn_pct = (pnl_eur / base * 100.0) if base > 0 else np.nan
                st.metric("Rendement net estimé", f"{rn_pct:.2f}%" if np.isfinite(rn_pct) else "—")
            with c1d:
                # Ajout dans virtual_trades.json
                if st.button("➕ Ajouter au portefeuille virtuel", key=f"addvirt_{i}"):
                    try:
                        with open(VFILE, "r", encoding="utf-8") as f:
                            cur = json.load(f)
                            if not isinstance(cur, list):
                                cur = []
                    except Exception:
                        cur = []

                    entry = float(row["Entrée (€)"]) if pd.notna(row["Entrée (€)"]) else (px if np.isfinite(px) else None)
                    obj   = float(row["Objectif (€)"]) if pd.notna(row["Objectif (€)"]) else None
                    stp   = float(row["Stop (€)"]) if pd.notna(row["Stop (€)"]) else None
                    rec = {
                        "date": pd.Timestamp.today().strftime("%Y-%m-%d"),
                        "indice": row.get("Indice", ""),
                        "ticker": str(row.get("Ticker") or ""),
                        "name": str(row.get("Société") or ""),
                        "price_now": float(px) if np.isfinite(px) else None,
                        "entry": entry,
                        "target": obj,
                        "stop": stp,
                        "qty": int(qty),
                        "invest_eur": float(inv),
                        "fee_in": float(fee_in),
                        "fee_out": float(fee_out),
                        "horizon": horizon,
                        "ia_score": float(row.get("Score IA")) if pd.notna(row.get("Score IA")) else None,
                        "proximity_pct": float(row.get("Proximité (%)")) if pd.notna(row.get("Proximité (%)")) else None,
                        "signal": str(row.get("Signal Entrée") or "")
                    }
                    cur.append(rec)
                    with open(VFILE, "w", encoding="utf-8") as f:
                        json.dump(cur, f, ensure_ascii=False, indent=2)
                    st.success(f"✅ Ajouté au portefeuille virtuel : {rec['name']} ({rec['ticker']})")

st.divider()

# ---------------- Charts simples ----------------
st.markdown("### 📊 Visualisation rapide")
def bar_chart(df, title):
    if df.empty:
        st.caption("—")
        return
    d = df.copy()
    # Fabrique une colonne Variation % si absente
    if "Variation %" not in d.columns:
        if value_col in d.columns:
            d["Variation %"] = (d[value_col]*100).round(2)
        else:
            d["Variation %"] = np.nan
    # Label
    if "Société" not in d.columns:
        if "name" in d.columns: d["Société"] = d["name"]
        else: d["Société"] = ""
    d["Label"] = d["Société"].astype(str) + " (" + d["Ticker"].astype(str) + ")"
    chart = (
        alt.Chart(d)
        .mark_bar()
        .encode(
            x=alt.X("Label:N", sort="-y", title=""),
            y=alt.Y("Variation %:Q", title="Variation (%)"),
            color=alt.Color("Variation %:Q", scale=alt.Scale(scheme="redyellowgreen")),
            tooltip=["Société","Ticker","Variation %","Indice","IA_Score","MA20","MA50","MA120","MA240"]
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
st.caption("💡 Utilise la section 'Simulation d’investissement' pour ajouter rapidement des lignes à suivre dans le portefeuille virtuel (onglet dédié).")
