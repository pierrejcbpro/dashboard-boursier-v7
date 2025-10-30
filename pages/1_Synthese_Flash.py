# -*- coding: utf-8 -*-
"""
v7.10.2 — Synthèse Flash IA complète
- Basée sur v6.9 + IA combinée MA20/50/120/240
- Ajout d’un module de suivi virtuel d’investissement 💸
- Colonne Rendement estimé (%) + P&L réel
- Corrige les doublons de colonnes Streamlit
"""

import os, json
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st
from lib import (
    fetch_all_markets, style_variations, load_profile, save_profile,
    news_summary, select_top_actions, fetch_prices
)

# =======================================================
# CONFIGURATION GÉNÉRALE
# =======================================================
st.set_page_config(page_title="Synthèse Flash IA", page_icon="⚡", layout="wide")
st.title("⚡ Synthèse Flash — Marché Global (IA enrichie)")

# =======================================================
# SIDEBAR
# =======================================================
periode = st.sidebar.radio("Période d’analyse", ["Jour", "7 jours", "30 jours"], index=0)
value_col = {"Jour": "pct_1d", "7 jours": "pct_7d", "30 jours": "pct_30d"}[periode]

profil = st.sidebar.radio(
    "Profil IA", ["Prudent", "Neutre", "Agressif"],
    index=["Prudent", "Neutre", "Agressif"].index(load_profile())
)
if st.sidebar.button("💾 Mémoriser le profil"):
    save_profile(profil)
    st.sidebar.success("Profil sauvegardé.")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🌍 Marchés inclus")
include_eu = st.sidebar.checkbox("🇫🇷 CAC 40 + 🇩🇪 DAX", value=True)
include_us = st.sidebar.checkbox("🇺🇸 NASDAQ 100 + S&P 500", value=False)
include_ls = st.sidebar.checkbox("🧠 LS Exchange (perso)", value=False)

# =======================================================
# CHARGEMENT DES MARCHÉS
# =======================================================
MARKETS = []
if include_eu:
    MARKETS += [("CAC 40", None), ("DAX", None)]
if include_us:
    MARKETS += [("NASDAQ 100", None), ("S&P 500", None)]
if include_ls:
    MARKETS += [("LS Exchange", None)]

if not MARKETS:
    st.warning("Aucun marché sélectionné. Active au moins un marché.")
    st.stop()

data = fetch_all_markets(MARKETS, days_hist=240)
if data.empty:
    st.warning("Aucune donnée disponible (vérifie la connectivité).")
    st.stop()

for c in ["pct_1d", "pct_7d", "pct_30d"]:
    if c not in data.columns:
        data[c] = np.nan
valid = data.dropna(subset=["Close"]).copy()

# =======================================================
# SYNTHÈSE GLOBALE
# =======================================================
avg = (valid[value_col].mean() * 100.0) if not valid.empty else np.nan
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
        st.caption("Volatilité modérée — rotations sectorielles.")
    else:
        st.caption("Marché dispersé — forte volatilité.")
st.divider()

# =======================================================
# TOP / FLOP
# =======================================================
st.subheader(f"🏆 Top 10 hausses & ⛔ Baisses — {periode}")

def prep_table(df, asc=False, n=10):
    if df.empty:
        return pd.DataFrame()
    cols = ["Ticker", "name", "Close", value_col, "Indice", "trend_score", "lt_trend_score"]
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
    out = df.sort_values(value_col, ascending=asc).head(n).copy()
    out.rename(columns={"name": "Société", "Close": "Cours (€)"}, inplace=True)
    out["Variation %"] = (out[value_col] * 100).round(2)
    out["Cours (€)"] = out["Cours (€)"].round(2)
    out["LT"] = out["lt_trend_score"].apply(lambda v: "🌱" if v > 0 else ("🌧" if v < 0 else "⚖️"))
    return out[["Indice", "Société", "Ticker", "Cours (€)", "Variation %", "LT"]]

col1, col2 = st.columns(2)
with col1:
    top = prep_table(valid, asc=False)
    st.dataframe(style_variations(top, ["Variation %"]), use_container_width=True, hide_index=True)
with col2:
    flop = prep_table(valid, asc=True)
    st.dataframe(style_variations(flop, ["Variation %"]), use_container_width=True, hide_index=True)

st.divider()

# =======================================================
# SÉLECTION IA — OPPORTUNITÉS
# =======================================================
st.subheader("🚀 Sélection IA — Opportunités idéales (TOP 10)")
top_actions = select_top_actions(valid, profile=profil, n=10, include_proximity=True)

if top_actions.empty:
    st.info("Aucune opportunité détectée aujourd’hui selon l’IA.")
else:
    # Ajout du signal de proximité
    def proximity_marker(v):
        if pd.isna(v):
            return "⚪"
        if abs(v) <= 2:
            return "🟢"
        elif abs(v) <= 5:
            return "⚠️"
        else:
            return "🔴"
    top_actions["Signal Entrée"] = top_actions["Proximité (%)"].apply(proximity_marker)

    # Style tableau IA
    def style_prox(v):
        if pd.isna(v):
            return ""
        if abs(v) <= 2:
            return "background-color:#e8f5e9; color:#0b8043;"
        if abs(v) <= 5:
            return "background-color:#fff8e1; color:#a67c00;"
        return "background-color:#ffebee; color:#b71c1c;"

    def style_decision(v):
        if pd.isna(v):
            return ""
        if "Acheter" in v:
            return "background-color:rgba(0,200,0,0.15);"
        if "Éviter" in v:
            return "background-color:rgba(255,0,0,0.15);"
        if "Surveiller" in v:
            return "background-color:rgba(0,100,255,0.1);"
        return ""

    styled = (
        top_actions.style
        .applymap(style_prox, subset=["Proximité (%)"])
        .applymap(style_decision, subset=["Signal"])
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

st.divider()

# =======================================================
# 💸 PORTFEUILLE VIRTUEL
# =======================================================
st.subheader("💸 Portefeuille virtuel (suivi IA)")

# ---------- Fichiers ----------
SUIVI_PATH = "data/suivi_virtuel.json"
os.makedirs("data", exist_ok=True)

def _load_suivi():
    if not os.path.exists(SUIVI_PATH):
        return []
    try:
        data = json.load(open(SUIVI_PATH, "r", encoding="utf-8"))
        return data if isinstance(data, list) else data.get("items", [])
    except Exception:
        return []

def _save_suivi(items):
    with open(SUIVI_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

# ---------- Paramètres ----------
colA, colB, colC = st.columns([1, 1, 2])
with colA:
    montant = st.number_input("💶 Montant par ligne (€)", min_value=5.0, step=5.0, value=20.0)
with colB:
    horizon_txt = st.selectbox("Horizon cible", ["1 semaine", "2 semaines", "1 mois"], index=2)
with colC:
    st.caption("Les calculs incluent 1 € de frais d’entrée et 1 € de sortie.")

# ---------- Liste d’opportunités ----------
st.markdown("### 🧠 Sélection IA — Ajout au suivi virtuel")

if top_actions.empty:
    st.info("Aucune opportunité IA disponible.")
else:
    # Renommage compatible
    df_cols = list(top_actions.columns)
    rename_map = {}
    if "name" in df_cols:
        rename_map["name"] = "Société"
    if "Ticker" in df_cols:
        rename_map["Ticker"] = "Symbole"
    if "Symbol" in df_cols:
        rename_map["Symbol"] = "Symbole"
    top_actions = top_actions.rename(columns=rename_map)
    if "IA_Score" not in top_actions.columns:
        top_actions["IA_Score"] = np.nan

    keep_cols = [
        c for c in [
            "Société", "Symbole", "Cours (€)", "Entrée (€)", "Objectif (€)", "Stop (€)",
            "Proximité (%)", "Signal", "IA_Score"
        ] if c in top_actions.columns
    ]
    mini = top_actions[keep_cols].copy()

    for i, r in mini.iterrows():
        with st.container():
            cols = st.columns([3, 1.2, 1.2, 1.2, 1.2, 1, 1, 1])
            cols[0].markdown(f"**{r.get('Société','?')}** (`{r.get('Symbole','?')}`)")
            cols[1].markdown(f"💶 {r.get('Cours (€)', np.nan):.2f} €" if pd.notna(r.get("Cours (€)")) else "—")
            cols[2].markdown(f"🎯 Entrée : {r.get('Entrée (€)', np.nan):.2f} €" if pd.notna(r.get("Entrée (€)")) else "—")
            cols[3].markdown(f"🎯 Objectif : {r.get('Objectif (€)', np.nan):.2f} €" if pd.notna(r.get("Objectif (€)")) else "—")
            cols[4].markdown(f"🛑 Stop : {r.get('Stop (€)', np.nan):.2f} €" if pd.notna(r.get("Stop (€)")) else "—")

            prox = r.get("Proximité (%)", np.nan)
            emoji = "🟢" if pd.notna(prox) and abs(prox) <= 2 else ("⚠️" if abs(prox) <= 5 else "🔴")
            cols[5].markdown(f"📏 {prox:+.2f}% {emoji}" if pd.notna(prox) else "📏 —")

            score = r.get("IA_Score", np.nan)
            cols[6].markdown(f"🧮 Score IA : {score:.1f}/100" if pd.notna(score) else "—")

            if cols[7].button("➕ Ajouter", key=f"add_{i}"):
                try:
                    items = _load_suivi()
                    entry = float(r.get("Entrée (€)") or r.get("Cours (€)") or np.nan)
                    target = float(r.get("Objectif (€)") or np.nan)
                    stop = float(r.get("Stop (€)") or np.nan)
                    fees_in, fees_out = 1.0, 1.0
                    net_capital = max(montant - fees_in, 0.0)
                    qty = net_capital / entry if entry > 0 else 0.0
                    rend_net = ((target - entry) / entry * 100) - (2 / entry * 100) if np.isfinite(entry) and np.isfinite(target) else np.nan

                    items.append({
                        "ticker": str(r.get("Symbole")),
                        "name": str(r.get("Société")),
                        "entry": round(entry, 4),
                        "target": target,
                        "stop": stop,
                        "amount": float(montant),
                        "fees_in": fees_in,
                        "fees_out": fees_out,
                        "qty": round(qty, 6),
                        "rendement_estime_pct": rend_net,
                        "score_ia": float(score) if pd.notna(score) else None,
                        "profile": profil,
                        "added_at": datetime.now(timezone.utc).isoformat(),
                        "horizon": horizon_txt
                    })
                    _save_suivi(items)
                    st.success(f"Ajouté au suivi virtuel : {r.get('Société')} ({r.get('Symbole')}) — {montant:.2f} €")
                except Exception as e:
                    st.error(f"Erreur lors de l’ajout : {e}")

st.divider()
st.markdown("### 📊 Suivi virtuel — performance & comparaison CAC 40")

# ---------- Lecture ----------
items = _load_suivi()
if not items:
    st.caption("Aucune ligne dans le suivi virtuel.")
else:
    df = pd.DataFrame(items)
    tickers = df["ticker"].dropna().unique().tolist()
    px = fetch_prices(tickers + ["^FCHI"], days=60)
    if px.empty or "Date" not in px.columns:
        st.warning("Pas assez d’historique pour évaluer les performances.")
    else:
        last = px.sort_values("Date").groupby("Ticker").tail(1)[["Ticker", "Close"]].rename(columns={"Close": "last_close"})
        df = df.merge(last, left_on="ticker", right_on="Ticker", how="left")

        def compute_perf(row):
            entry, qty, amt, fees_out = float(row["entry"]), float(row["qty"]), float(row["amount"]), float(row["fees_out"])
            last_p = row["last_close"]
            if not np.isfinite(last_p):
                return pd.Series({"valeur_actuelle": np.nan, "pnl_pct": np.nan})
            cur_val = qty * last_p - fees_out
            pnl_pct = ((cur_val - amt) / amt * 100) if amt > 0 else np.nan
            return pd.Series({"valeur_actuelle": cur_val, "pnl_pct": pnl_pct})

        res = df.apply(compute_perf, axis=1)
        df = pd.concat([df, res], axis=1)

        tot_val = df["valeur_actuelle"].sum()
        tot_invest = df["amount"].sum()
        tot_pct = ((tot_val - tot_invest) / tot_invest * 100) if tot_invest > 0 else np.nan

        c1, c2 = st.columns(2)
        c1.metric("Performance globale", f"{tot_pct:+.2f}%")
        c2.metric("Capital virtuel", f"{tot_val:,.2f} €")

        show = df.copy()
        show.rename(columns={
            "name": "Société",
            "ticker": "Ticker",
            "last_close": "Cours actuel (€)",
            "entry": "Entrée (€)",
            "target": "Objectif (€)",
            "stop": "Stop (€)",
            "rendement_estime_pct": "Rendement estimé (%)",
            "qty": "Qté",
            "amount": "Montant initial (€)",
            "valeur_actuelle": "Valeur actuelle (€)",
            "pnl_pct": "P&L (%)"
        }, inplace=True)

        # 🔧 Supprime doublons de colonnes
        show.columns = pd.io.parsers.ParserBase({'names': show.columns})._maybe_dedup_names(show.columns)

        # 🔧 Vérifie colonnes manquantes
        expected_cols = [
            "Société", "Ticker", "Cours actuel (€)", "Entrée (€)", "Objectif (€)", "Stop (€)",
            "Rendement estimé (%)", "Qté", "Montant initial (€)", "Valeur actuelle (€)", "P&L (%)"
        ]
        for c in expected_cols:
            if c not in show.columns:
                show[c] = np.nan

        st.dataframe(
            show[expected_cols].style.format(precision=2),
            use_container_width=True, hide_index=True
        )

        # ---------- Suppression d’une ligne ----------
        st.markdown("#### 🗑 Retirer une ligne")
        tickers_del = show["Ticker"].unique().tolist()
        colA, colB = st.columns([3, 1])
        with colA:
            del_sel = st.selectbox("Sélectionner une ligne à retirer", tickers_del)
        with colB:
            if st.button("Supprimer"):
                items = _load_suivi()
                items = [x for x in items if x["ticker"] != del_sel]
                _save_suivi(items)
                st.success(f"Ligne supprimée : {del_sel}")
                st.rerun()


st.divider()

# Pied de page
st.divider()
st.caption("💡 Active/désactive les marchés US dans la barre latérale. Le suivi virtuel est indépendant du portefeuille réel.")
