# -*- coding: utf-8 -*-
"""
v7.11 — Synthèse Flash IA
- ✅ Ticker garanti dans “Sélection IA”
- ✅ Ajout + suivi Portefeuille Virtuel (onglet dédié)
- ✅ Colonnes demandées : Société / Ticker / Cours / Entrée / Objectif / Stop / Rendement estimé / Qté / Montant / Valeur / P&L%
- ✅ Suppression de lignes
- ⓘ Mini-benchmark CAC40 optionnel
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
    st.warning("Aucune donnée disponible (connectivité / marchés).")
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
    cols = ["Ticker","name","Close", value_col,"Indice","IA_Score","trend_lt"]
    for c in cols:
        if c not in df.columns: df[c] = np.nan
    out = df.sort_values(value_col, ascending=asc).head(n).copy()
    out.rename(columns={"name":"Société","Close":"Cours (€)"}, inplace=True)
    out["Variation %"] = (out[value_col] * 100).round(2)
    out["Cours (€)"] = out["Cours (€)"].round(2)
    out["LT"] = out["trend_lt"].apply(lambda v: "🌱" if v > 0 else ("🌧" if v < 0 else "⚖️"))
    return out[["Indice","Société","Ticker","Cours (€)","Variation %","LT","IA_Score"]]

col1, col2 = st.columns(2)
with col1:
    top = prep_table(valid, asc=False, n=10)
    st.dataframe(style_variations(top, ["Variation %"]), use_container_width=True, hide_index=True)
with col2:
    flop = prep_table(valid, asc=True, n=10)
    st.dataframe(style_variations(flop, ["Variation %"]), use_container_width=True, hide_index=True)

st.divider()

# =======================================================
# 🚀 SÉLECTION IA — Opportunités (TOP 10)
# =======================================================
st.subheader("🚀 Sélection IA — Opportunités idéales (TOP 10)")

top_actions = select_top_actions(valid, profile=profil, n=10, include_proximity=True)

if top_actions.empty:
    st.info("Aucune opportunité claire détectée aujourd’hui selon l’IA.")
else:
    df = top_actions.copy()

    # --- Normalisation et nettoyage complet
    # 1️⃣ Assure la présence de Société / Ticker / Indice / Cours (€)
    rename_map = {
        "symbol": "Ticker", "ticker": "Ticker", "Symbole": "Ticker",
        "name": "Société", "shortname": "Société",
        "Close": "Cours (€)"
    }
    for old, new in rename_map.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]

    # Si aucune colonne ticker trouvée
    if "Ticker" not in df.columns:
        df["Ticker"] = df.index.astype(str)

    # Si aucune colonne Indice trouvée
    if "Indice" not in df.columns:
        for k in ["index", "Market", "Indice"]:
            if k in df.columns:
                df["Indice"] = df[k]
                break
        else:
            df["Indice"] = "—"

    # Nettoyage None / NaN texte
    df["Société"] = df["Société"].fillna("—").astype(str)
    df["Ticker"] = df["Ticker"].fillna("—").astype(str)
    df["Indice"] = df["Indice"].fillna("—").astype(str)

    # --- Ajoute les colonnes techniques manquantes
    for ma in ["MA20","MA50","MA120","MA240"]:
        if ma not in df.columns: df[ma] = np.nan
    for col in ["Entrée (€)","Objectif (€)","Stop (€)","Cours (€)"]:
        if col not in df.columns: df[col] = np.nan

    # --- Calcul des tendances et du Score IA
    df["Tendance MT"] = np.where(df["MA20"] > df["MA50"], "🌱",
                          np.where(df["MA20"] < df["MA50"], "🌧", "⚖️"))
    df["Tendance LT"] = np.where(df["MA120"] > df["MA240"], "🌱",
                          np.where(df["MA120"] < df["MA240"], "🌧", "⚖️"))

    df["Score IA"] = np.nan
    cond = df[["MA20","MA50","MA120","MA240"]].notna().all(axis=1)
    df.loc[cond, "Score IA"] = 100 - ((abs(df["MA20"]-df["MA50"]) + abs(df["MA120"]-df["MA240"])) * 10).clip(0,100)

    # --- Décision IA simulée si manquante
    if "Décision IA" not in df.columns:
        def decision_from_ma(r):
            if r["MA20"] > r["MA50"] and r["MA120"] > r["MA240"]: return "Acheter"
            if r["MA20"] < r["MA50"] and r["MA120"] < r["MA240"]: return "Vendre"
            return "Surveiller"
        df["Décision IA"] = df.apply(decision_from_ma, axis=1)

    # --- Proximité + signal emoji
    if "Proximité (%)" not in df.columns:
        df["Proximité (%)"] = np.nan
        mask = df[["Cours (€)","Entrée (€)"]].notna().all(axis=1)
        df.loc[mask,"Proximité (%)"] = ((df.loc[mask,"Cours (€)"]/df.loc[mask,"Entrée (€)"])-1)*100

    def proximity_marker(v):
        if pd.isna(v): return "⚪"
        if abs(v) <= 2: return "🟢"
        elif abs(v) <= 5: return "⚠️"
        else: return "🔴"
    df["Signal Entrée"] = df["Proximité (%)"].apply(proximity_marker)

    # --- Ordonne les colonnes pour affichage clair
    disp_cols = [
        "Indice","Société","Ticker","Cours (€)","Entrée (€)","Objectif (€)","Stop (€)",
        "MA20","MA50","MA120","MA240",
        "Tendance MT","Tendance LT","Score IA","Décision IA","Proximité (%)","Signal Entrée"
    ]
    for c in disp_cols:
        if c not in df.columns: df[c] = np.nan

    # --- Mise en forme
    def style_dec(v):
        if pd.isna(v): return ""
        if "Acheter" in v: return "background-color:rgba(0,200,0,0.15); font-weight:600;"
        if "Vendre" in v: return "background-color:rgba(255,0,0,0.15); font-weight:600;"
        if "Surveiller" in v: return "background-color:rgba(0,100,255,0.1); font-weight:600;"
        return ""
    def style_prox(v):
        if pd.isna(v): return ""
        if abs(v) <= 2:  return "background-color:#e8f5e9; color:#0b8043; font-weight:600;"
        if abs(v) <= 5:  return "background-color:#fff8e1; color:#a67c00;"
        return "background-color:#ffebee; color:#b71c1c;"

    st.dataframe(
        df[disp_cols].style
            .applymap(style_dec, subset=["Décision IA"])
            .applymap(style_prox, subset=["Proximité (%)"]),
        use_container_width=True, hide_index=True
    )

    st.markdown(
        f"📊 **Moyenne Score IA :** {df['Score IA'].mean():.1f}/100 — "
        f"**Actions proches des entrées idéales :** {(df['Signal Entrée']=='🟢').sum()} / {len(df)}"
    )


st.divider()

# =======================================================
# 💸 PORTFEUILLE VIRTUEL — Onglet dédié
# =======================================================
st.subheader("💸 Portefeuille virtuel — suivi IA")

SUIVI_PATH = "data/suivi_virtuel.json"
os.makedirs("data", exist_ok=True)

def load_suivi():
    try:
        with open(SUIVI_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def save_suivi(lst):
    with open(SUIVI_PATH, "w", encoding="utf-8") as f:
        json.dump(lst, f, ensure_ascii=False, indent=2)

tabs = st.tabs(["📋 Propositions IA (ajout rapide)", "📈 Suivi virtuel"])

with tabs[0]:
    montant = st.number_input("💶 Montant par ligne (€)", min_value=5.0, step=5.0, value=20.0)
    horizon = st.selectbox("Horizon cible", ["1 semaine","2 semaines","1 mois"], index=2)
    st.caption("Hypothèse de frais : 1€ à l’achat + 1€ à la vente (déduits du rendement estimé).")

    if top_actions.empty:
        st.info("Aucune proposition IA pour le moment.")
    else:
        df_add = df.copy()  # df établi ci-dessus
        for i, r in df_add.iterrows():
            c1, c2, c3, c4, c5, c6, c7 = st.columns([3,1,1,1,1,1,1])
            name = str(r.get("Société") or "")
            tkr  = str(r.get("Ticker") or "")
            px   = float(r.get("Cours (€)") or np.nan)
            ent  = float(r.get("Entrée (€)") or (px if np.isfinite(px) else np.nan))
            tgt  = float(r.get("Objectif (€)") or np.nan)
            stp  = float(r.get("Stop (€)") or np.nan)
            prox = r.get("Proximité (%)", np.nan)

            c1.markdown(f"**{name}** (`{tkr}`)")
            c2.markdown(f"{px:.2f} €" if np.isfinite(px) else "—")
            c3.markdown(f"🎯 {tgt:.2f} €" if np.isfinite(tgt) else "🎯 —")
            c4.markdown(f"🛑 {stp:.2f} €" if np.isfinite(stp) else "🛑 —")
            c5.markdown(f"{prox:+.2f}%" if pd.notna(prox) else "—")
            qty = (montant - 1.0) / ent if (np.isfinite(ent) and ent > 0) else 0.0
            c6.markdown(f"Qté~ {qty:.2f}" if qty>0 else "Qté —")
            if c7.button("➕ Ajouter", key=f"add_{i}"):
                items = load_suivi()
                # Rendement estimé net (objectif) = (tgt/ent -1) *100 - (2/ent *100) en % du PRU
                rend_est = np.nan
                if np.isfinite(ent) and np.isfinite(tgt) and ent > 0:
                    rend_est = (tgt/ent - 1.0) * 100.0 - (2.0/ent)*100.0
                items.append({
                    "ticker": tkr,
                    "name": name,
                    "entry": ent if np.isfinite(ent) else None,
                    "target": tgt if np.isfinite(tgt) else None,
                    "stop": stp if np.isfinite(stp) else None,
                    "amount": float(montant),
                    "qty": float(qty) if np.isfinite(qty) else 0.0,
                    "added_at": datetime.now(timezone.utc).isoformat(),
                    "horizon": horizon
                })
                save_suivi(items)
                st.success(f"Ajouté : {name} ({tkr})")

with tabs[1]:
    items = load_suivi()
    if not items:
        st.info("Aucune ligne dans le suivi virtuel. Ajoute des idées depuis l’onglet précédent.")
    else:
        sv = pd.DataFrame(items)
        # Nettoyage basique
        for col in ["entry","target","stop","amount","qty"]:
            if col in sv.columns:
                sv[col] = pd.to_numeric(sv[col], errors="coerce")

        tickers = sv["ticker"].dropna().astype(str).unique().tolist()
        # Récupère cours actuels
        px_now = {}
        if tickers:
            px_df = fetch_prices(tickers, days=10)
            if not px_df.empty:
                last = px_df.sort_values("Date").groupby("Ticker").tail(1)[["Ticker","Close"]]
                px_now = {str(k): float(v) for k, v in zip(last["Ticker"], last["Close"])}

        def current_price(tkr):
            return px_now.get(str(tkr), np.nan)

        sv["Cours (€)"]       = sv["ticker"].apply(current_price)
        sv["Montant initial"] = sv["amount"]
        sv["Valeur (€)"]      = sv["qty"] * sv["Cours (€)"]
        # P&L% basé sur entry (PRU + frais achat 1€ déjà déduit dans qty)
        sv["P&L%"] = np.where(
            np.isfinite(sv["entry"]) & (sv["entry"] > 0) & np.isfinite(sv["Cours (€)"]),
            (sv["Cours (€)"]/sv["entry"] - 1.0) * 100.0 - (1.0/sv["entry"])*100.0,  # –1€ de frais sortie “virtuel” si tu veux, ajoute-le ici
            np.nan
        )
        # Rendement estimé (vers objectif), net 2€ (achat+vente)
        sv["Rendement estimé (%)"] = np.where(
            np.isfinite(sv["entry"]) & (sv["entry"] > 0) & np.isfinite(sv["target"]),
            (sv["target"]/sv["entry"] - 1.0) * 100.0 - (2.0/sv["entry"])*100.0,
            np.nan
        )

        # Ordre des colonnes demandées
        show_cols = [
            "name","ticker","Cours (€)","entry","target","stop",
            "Rendement estimé (%)","qty","Montant initial","Valeur (€)","P&L%"
        ]
        for c in show_cols:
            if c not in sv.columns: sv[c] = np.nan
        show = sv[show_cols].copy()
        show.rename(columns={
            "name":"Société","ticker":"Ticker","entry":"Montant à l’entrée",
            "target":"Objectif (€)","stop":"Stop (€)","qty":"Qté","Montant initial":"Montant€ initial d’investissement"
        }, inplace=True)

        # Style simple
        def col_pl(v):
            if pd.isna(v): return ""
            if v >= 0: return "background-color:#e8f5e9; color:#0b8f3a;"
            return "background-color:#ffebee; color:#d5353a;"

        st.dataframe(
            show.style
                .format({
                    "Cours (€)":"{:.2f}",
                    "Montant à l’entrée":"{:.2f}",
                    "Objectif (€)":"{:.2f}",
                    "Stop (€)":"{:.2f}",
                    "Rendement estimé (%)":"{:+.2f}",
                    "Qté":"{:.2f}",
                    "Montant€ initial d’investissement":"{:.2f}",
                    "Valeur (€)":"{:.2f}",
                    "P&L%":"{:+.2f}",
                })
                .applymap(col_pl, subset=["P&L%"]),
            use_container_width=True, hide_index=True
        )

               # Suppression de lignes
        st.markdown("### 🧹 Gérer les lignes")
        for i, r in sv.reset_index().iterrows():
            c1, c2 = st.columns([8,2])
            c1.caption(f"{r.get('name','?')} ({r.get('ticker','?')}) — Ajouté le {r.get('added_at','')[:10]}")
            if c2.button("🗑 Supprimer", key=f"del_{i}"):
                lst = load_suivi()
                if 0 <= i < len(lst):
                    lst.pop(i)
                    save_suivi(lst)
                    st.success(f"Ligne supprimée : {r.get('name')} ({r.get('ticker')})")
                    st.experimental_rerun()

        # ✅ Bouton “Vider tout” déplacé en dehors de la boucle
        st.markdown("---")
        if st.button("♻️ Vider tout le suivi virtuel", key="wipe_all_global"):
            save_suivi([])
            st.success("Tout le suivi virtuel a été vidé.")
            st.experimental_rerun()


st.divider()

# ---------------- Actualités ----------------
st.markdown("### 📰 Actualités principales")
def short_news(row):
    nm = str(row.get("Société") or row.get("name") or "")
    tk = str(row.get("Ticker") or row.get("ticker") or "")
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

st.caption("💡 Utilise l’onglet “Suivi virtuel” pour tester la stratégie avant de l’appliquer au portefeuille réel.")
