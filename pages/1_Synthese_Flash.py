# -*- coding: utf-8 -*-
"""
v7.9 — Synthèse Flash IA (complète)
Base v6.9 conservée :
- Résumé global
- Top/Flop
- Sélection IA (avec proximité + signal)
- Graphiques
- Actualités
Ajouts v7.9 :
- Onglet "💸 Portefeuille virtuel (suivi)" :
  * Montant paramétrable, frais (1€ entrée + 1€ sortie) pris en compte
  * Ajout direct depuis la Sélection IA
  * Rendement net estimé, stop/objectif, qty théorique
  * Comparaison vs CAC 40 (^FCHI)
  * Suppression de lignes
"""

import os, json, time
import streamlit as st, pandas as pd, numpy as np, altair as alt
from datetime import datetime, timezone
from lib import (
    fetch_all_markets, style_variations, load_profile, save_profile,
    news_summary, select_top_actions, price_levels_from_row, fetch_prices
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
if include_us: MARKETS += [("NASDAQ 100", None), ("S&P 500", None)]
if include_ls: MARKETS += [("LS Exchange", None)]

if not MARKETS:
    st.warning("Aucun marché sélectionné. Active au moins un marché dans la barre latérale.")
    st.stop()

data = fetch_all_markets(MARKETS, days_hist=240)
if data.empty:
    st.warning("Aucune donnée disponible (vérifie la connectivité ou ta sélection de marchés).")
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
    cols = ["Ticker","name","Close", value_col,"Indice","lt_trend_score","MA120","MA240"]
    for c in cols:
        if c not in df.columns: df[c] = np.nan
    out = df.sort_values(value_col, ascending=asc).head(n).copy()
    out.rename(columns={"name":"Société","Close":"Cours (€)"}, inplace=True)
    out["Variation %"] = (out[value_col] * 100).round(2)
    out["Cours (€)"] = out["Cours (€)"].round(2)
    # LT icon : si MA120/MA240 présents on les utilise, sinon signe de lt_trend_score
    def lt_icon(row):
        m120, m240 = row.get("MA120"), row.get("MA240")
        if pd.notna(m120) and pd.notna(m240):
            return "🌱" if m120 > m240 else ("🌧" if m120 < m240 else "⚖️")
        v = row.get("lt_trend_score", np.nan)
        return "🌱" if pd.notna(v) and v>0 else ("🌧" if pd.notna(v) and v<0 else "⚖️")
    out["LT"] = out.apply(lt_icon, axis=1)
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

st.divider()

# ---------------- Sélection IA TOP 10 ----------------
st.subheader("🚀 Sélection IA — Opportunités idéales (TOP 10)")
top_actions = select_top_actions(valid, profile=profil, n=10, include_proximity=True)

if top_actions.empty:
    st.info("Aucune opportunité claire détectée aujourd’hui selon l’IA.")
else:
    # Proximité % & balise visuelle
    def compute_proximity(row):
        e = row.get("Entrée (€)")
        px = row.get("Cours (€)")
        if not np.isfinite(e) or not np.isfinite(px) or e == 0:
            return np.nan
        return ((px / e) - 1) * 100

    if "Proximité (%)" not in top_actions.columns:
        top_actions["Proximité (%)"] = top_actions.apply(compute_proximity, axis=1)

    def proximity_marker(v):
        if pd.isna(v): return "⚪"
        if abs(v) <= 2: return "🟢"
        elif abs(v) <= 5: return "⚠️"
        else: return "🔴"

    top_actions["Signal Entrée"] = top_actions["Proximité (%)"].apply(proximity_marker)

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

    def style_prox(v):
        if pd.isna(v): return ""
        if abs(v) <= 2:  return "background-color:#e8f5e9; color:#0b8043; font-weight:600;"
        if abs(v) <= 5:  return "background-color:#fff8e1; color:#a67c00;"
        return "background-color:#ffebee; color:#b71c1c;"

    def style_decision(val):
        if pd.isna(val): return ""
        if "Acheter" in val: return "background-color:rgba(0,200,0,0.15); font-weight:600;"
        if "Éviter" in val:  return "background-color:rgba(255,0,0,0.15); font-weight:600;"
        if "Surveiller" in val: return "background-color:rgba(0,100,255,0.1); font-weight:600;"
        return ""

    styled = (
        top_actions.style
        .applymap(style_prox, subset=["Proximité (%)"])
        .applymap(style_decision, subset=["Signal"])
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

st.divider()

# ---------------- 📊 Graphiques Top/Flop ----------------
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
            tooltip=["Société","Ticker","Variation %","Cours (€)","Indice","LT"]
        )
        .properties(height=320, title=title)
    )
    st.altair_chart(chart, use_container_width=True)

col3, col4 = st.columns(2)
with col3: bar_chart(top, f"Top 10 hausses ({periode})")
with col4: bar_chart(flop, f"Top 10 baisses ({periode})")

# ---------------- 📰 Actualités ----------------
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

# =========================
# 💸 Onglet — Portefeuille virtuel (suivi)
# =========================
st.subheader("💸 Portefeuille virtuel (suivi)")

# Fichier de suivi
SUIVI_PATH = "data/suivi_virtuel.json"
os.makedirs("data", exist_ok=True)

def _load_suivi():
    if not os.path.exists(SUIVI_PATH):
        return []
    try:
        obj = json.load(open(SUIVI_PATH, "r", encoding="utf-8"))
        # tolérant : dict -> list
        if isinstance(obj, dict):
            # ancienne forme, on le transforme en liste d'items
            items = obj.get("items") or []
            return items if isinstance(items, list) else []
        if isinstance(obj, list):
            return obj
        return []
    except Exception:
        return []

def _save_suivi(items):
    # format liste propre
    with open(SUIVI_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

# Paramètres d'injection
c1, c2, c3 = st.columns([1,1,2])
with c1:
    montant = st.number_input("Montant par ligne (€)", min_value=5.0, step=5.0, value=20.0)
with c2:
    horizon_txt = st.selectbox("Horizon cible", ["1 semaine", "2 semaines", "1 mois"], index=2)
with c3:
    st.caption("Frais pris en compte automatiquement : **1€ entrée + 1€ sortie**.")

st.markdown("**Sélection IA (ajout au suivi)**")
if top_actions.empty:
    st.info("Aucune proposition IA disponible pour ajout.")
else:
    # On montre un mini tableau avec bouton d'ajout par ligne
    mini = top_actions[["Société","Symbole","Cours (€)","Entrée (€)","Objectif (€)","Stop (€)","Proximité (%)","Signal"]].copy()
    mini.rename(columns={"Symbole":"Ticker"}, inplace=True)

    # Pour chaque ligne, bouton d'ajout
    for i, r in mini.iterrows():
        with st.container():
            cols = st.columns([3,2,2,2,2,2,2,2])
            cols[0].markdown(f"**{r['Société']}**")
            cols[1].markdown(f"`{r['Ticker']}`")
            cols[2].markdown(f"📈 Cours: **{r['Cours (€)']:.2f}**")
            cols[3].markdown(f"🎯 Entrée: **{r['Entrée (€)']:.2f}**")
            cols[4].markdown(f"🎯 Obj.: **{r['Objectif (€)']:.2f}**")
            cols[5].markdown(f"🛑 Stop: **{r['Stop (€)']:.2f}**")
            prox = r.get("Proximité (%)", np.nan)
            if pd.notna(prox):
                emoji = "🟢" if abs(prox)<=2 else ("⚠️" if abs(prox)<=5 else "🔴")
                cols[6].markdown(f"📏 Prox: **{prox:+.2f}%** {emoji}")
            else:
                cols[6].markdown("📏 Prox: —")
            # Bouton
            if cols[7].button("➕ Ajouter", key=f"add_{i}"):
                try:
                    items = _load_suivi()
                    entry = float(r["Entrée (€)"]) if pd.notna(r["Entrée (€)"]) else float(r["Cours (€)"])
                    fees_in = 1.0
                    fees_out = 1.0
                    net_capital = max(montant - fees_in, 0.0)
                    qty = net_capital / entry if entry>0 else 0.0
                    items.append({
                        "ticker": str(r["Ticker"]),
                        "name": str(r["Société"]),
                        "entry": round(entry, 4),
                        "target": float(r["Objectif (€)"]) if pd.notna(r["Objectif (€)"]) else None,
                        "stop": float(r["Stop (€)"]) if pd.notna(r["Stop (€)"]) else None,
                        "amount": float(montant),
                        "fees_in": fees_in,
                        "fees_out": fees_out,
                        "qty": round(qty, 6),
                        "profile": profil,
                        "added_at": datetime.now(timezone.utc).isoformat(),
                        "horizon": horizon_txt
                    })
                    _save_suivi(items)
                    st.success(f"Ajouté au suivi virtuel : {r['Société']} ({r['Ticker']}) — {montant:.2f} €")
                except Exception as e:
                    st.error(f"Erreur lors de l’ajout : {e}")

st.divider()
st.markdown("### 📒 Suivi virtuel — performance & comparaison CAC 40")

items = _load_suivi()
if not items:
    st.caption("Aucune ligne dans le suivi virtuel pour le moment.")
else:
    df = pd.DataFrame(items)
    # Récup prix actuels
    tickers = df["ticker"].dropna().unique().tolist()
    px = fetch_prices(tickers + ["^FCHI"], days=60)
    if px.empty or "Date" not in px.columns:
        st.warning("Données insuffisantes pour l’évaluation en temps réel.")
    else:
        last = px.sort_values("Date").groupby("Ticker").tail(1)[["Ticker","Close"]].rename(columns={"Close":"last_close"})
        df = df.merge(last, left_on="ticker", right_on="Ticker", how="left")
        df.drop(columns=["Ticker"], inplace=True, errors="ignore")

        # PnL par ligne (avec frais sortie inclus au moment de l'exit => on estime net en retranchant fees_out de la valeur finale)
        def compute_line(row):
            entry = float(row.get("entry") or np.nan)
            qty   = float(row.get("qty") or 0.0)
            amt   = float(row.get("amount") or 0.0)
            fees_in  = float(row.get("fees_in") or 0.0)
            fees_out = float(row.get("fees_out") or 0.0)
            last_p = float(row.get("last_close") or np.nan)
            cur_val = qty * last_p if np.isfinite(last_p) else np.nan
            # Net aujourd'hui si on sortait : valeur - frais de sortie
            cur_val_net = cur_val - fees_out if np.isfinite(cur_val) else np.nan
            invested_net = amt  # on a déjà soustrait fees_in dans qty; amt inclut tout cash déboursé
            pnl = cur_val_net - invested_net if (np.isfinite(cur_val_net)) else np.nan
            pnl_pct = (pnl / invested_net * 100.0) if (invested_net>0 and np.isfinite(pnl)) else np.nan
            return pd.Series({"current_value_net": cur_val_net, "pnl_eur": pnl, "pnl_pct": pnl_pct})

        res = df.apply(compute_line, axis=1)
        df = pd.concat([df, res], axis=1)

        # Bench CAC40 depuis la date d’ajout (approx : on prend le % variation sur 30 jours si date trop récente indispo)
        bmk = px[px["Ticker"]=="^FCHI"].sort_values("Date")[["Date","Close"]].rename(columns={"Close":"bmk_close"})
        bmk_first = bmk["bmk_close"].iloc[0] if not bmk.empty else np.nan
        bmk_last  = bmk["bmk_close"].iloc[-1] if not bmk.empty else np.nan
        bmk_pct = ((bmk_last/bmk_first - 1)*100.0) if (pd.notna(bmk_first) and pd.notna(bmk_last) and bmk_first>0) else np.nan

        # Aggrégat portefeuille
        tot_invest = df["amount"].sum()
        tot_cur    = df["current_value_net"].sum()
        tot_pnl    = tot_cur - tot_invest if (pd.notna(tot_cur) and pd.notna(tot_invest)) else np.nan
        tot_pct    = (tot_pnl / tot_invest * 100.0) if (tot_invest>0 and pd.notna(tot_pnl)) else np.nan

        cA, cB, cC = st.columns(3)
        with cA: st.metric("Portefeuille virtuel (P&L €)", f"{tot_pnl:+.2f} €")
        with cB: st.metric("Portefeuille virtuel (P&L %)", f"{tot_pct:+.2f}%")
        with cC:
            if pd.notna(bmk_pct):
                delta = tot_pct - bmk_pct if pd.notna(tot_pct) else np.nan
                st.metric("vs CAC 40 (depuis période comparable)", f"{bmk_pct:+.2f}%", delta=None)
                if pd.notna(delta):
                    st.caption(("✅ Surperformance " if delta>0 else "⚠️ Sous-performance ") + f"de {abs(delta):.2f} pts")

        # Tableau + suppression
        def prox_marker(row):
            e = row.get("entry")
            last_p = row.get("last_close")
            if not (np.isfinite(e) and np.isfinite(last_p) and e>0): return ""
            prox = (last_p/e - 1)*100
            return "🟢" if abs(prox)<=2 else ("⚠️" if abs(prox)<=5 else "🔴")

        show = df.copy()
        show["Prox. entrée"] = show.apply(prox_marker, axis=1)
        show.rename(columns={
            "name":"Société","ticker":"Ticker","entry":"Entrée (€)","target":"Objectif (€)","stop":"Stop (€)",
            "qty":"Qté (théorique)","amount":"Montant (€)","current_value_net":"Valeur nette (€)",
            "pnl_eur":"P&L (€)","pnl_pct":"P&L (%)","last_close":"Cours actuel (€)","horizon":"Horizon"
        }, inplace=True)
        # tri par P&L %
        if "P&L (%)" in show.columns:
            show["P&L (%)"] = show["P&L (%)"].round(2)
            show = show.sort_values("P&L (%)", ascending=False)

        st.dataframe(
            show[[
                "Société","Ticker","Cours actuel (€)","Entrée (€)","Objectif (€)","Stop (€)",
                "Qté (théorique)","Montant (€)","Valeur nette (€)","P&L (€)","P&L (%)","Prox. entrée","Horizon","profile","added_at"
            ]].style.format(precision=2),
            use_container_width=True, hide_index=True
        )

        # Suppression ciblée
        st.markdown("#### 🗑 Retirer une ligne")
        tickers_del = show["Ticker"].tolist()
        if tickers_del:
            colD1, colD2 = st.columns([3,1])
            with colD1:
                del_sel = st.selectbox("Sélectionne une ligne à retirer (par Ticker — supprime la plus récente si plusieurs)", tickers_del)
            with colD2:
                if st.button("Supprimer"):
                    # On supprime la dernière occurrence de ce ticker (la plus récente)
                    items = _load_suivi()
                    idxs = [i for i, it in enumerate(items) if it.get("ticker")==del_sel]
                    if idxs:
                        # trouve la plus récente
                        latest_idx = max(idxs, key=lambda k: items[k].get("added_at",""))
                        it = items.pop(latest_idx)
                        _save_suivi(items)
                        st.success(f"Ligne retirée : {it.get('name')} ({del_sel})")
                        time.sleep(0.6)
                        st.rerun()

# Pied de page
st.divider()
st.caption("💡 Active/désactive les marchés US dans la barre latérale. Le suivi virtuel est indépendant du portefeuille réel.")
