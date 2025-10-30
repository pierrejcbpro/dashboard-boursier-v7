# -*- coding: utf-8 -*-
"""
v7.8 — Synthèse Flash IA enrichie
- IA combinée (MA20/50 + MA120/240)
- Ajout direct au suivi virtuel 💰
- Gestion du profil IA
- Proximité & signaux IA
"""
import os, json, pandas as pd, numpy as np, streamlit as st, altair as alt
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

profil = st.sidebar.radio("Profil IA", ["Prudent","Neutre","Agressif"],
                          index=["Prudent","Neutre","Agressif"].index(load_profile()))
if st.sidebar.button("💾 Mémoriser le profil"):
    save_profile(profil)
    st.sidebar.success("Profil sauvegardé.")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🌍 Marchés inclus")
include_eu = st.sidebar.checkbox("🇫🇷 CAC 40 + 🇩🇪 DAX", value=True)
include_us = st.sidebar.checkbox("🇺🇸 NASDAQ 100", value=False)

MARKETS = []
if include_eu: MARKETS += [("CAC 40", None), ("DAX", None)]
if include_us: MARKETS += [("NASDAQ 100", None)]

if not MARKETS:
    st.warning("Aucun marché sélectionné.")
    st.stop()

data = fetch_all_markets(MARKETS, days_hist=240)
if data.empty:
    st.warning("Aucune donnée disponible.")
    st.stop()

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

    # --- Normalisation des colonnes
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

    # ✅ Récupère les indices depuis les données complètes “valid”
    idx_map = valid[["Ticker", "Indice"]].drop_duplicates()
    df = df.merge(idx_map, on="Ticker", how="left")
    df["Indice"] = df["Indice"].fillna("—")

    # Nettoyage des valeurs texte
    df["Société"] = df["Société"].fillna("—").astype(str)
    df["Ticker"] = df["Ticker"].fillna("—").astype(str)

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
            if r["MA20"] > r["MA50"] and r["MA120"] > r["MA240"]: return "🟢 Acheter"
            if r["MA20"] < r["MA50"] and r["MA120"] < r["MA240"]: return "🔴 Vendre"
            return "⚠️ Surveiller"
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

# ---------------- Ajout au suivi virtuel ----------------
st.divider()
st.subheader("💰 Ajouter une opportunité au suivi virtuel")

DATA_PATH_VIRTUEL = "data/suivi_virtuel.json"
os.makedirs("data", exist_ok=True)
if not os.path.exists(DATA_PATH_VIRTUEL):
    pd.DataFrame(columns=[
        "Société","Ticker","Cours (€)","Entrée (€)","Objectif (€)","Stop (€)",
        "Qté","Montant Initial (€)","Valeur (€)","P&L (%)","Rendement Net Estimé (%)"
    ]).to_json(DATA_PATH_VIRTUEL, orient="records", indent=2, force_ascii=False)

montant = st.number_input("💶 Montant d’investissement (€)", min_value=10.0, step=10.0, value=20.0)

if not top_actions.empty:
    choix = st.selectbox("Sélectionne une action IA :", top_actions["Société"].tolist())
    ligne = top_actions[top_actions["Société"] == choix].iloc[0].to_dict()

    if st.button("➕ Ajouter au suivi virtuel"):
        try:
            pf = pd.read_json(DATA_PATH_VIRTUEL)
        except Exception:
            pf = pd.DataFrame()

        cours = float(ligne.get("Cours (€)", np.nan))
        entry = float(ligne.get("Entrée (€)", cours))
        qte = (montant - 1) / entry
        new_row = {
            "Société": ligne.get("Société"),
            "Ticker": ligne.get("Symbole") or ligne.get("Ticker"),
            "Cours (€)": round(cours,2),
            "Entrée (€)": round(entry,2),
            "Objectif (€)": round(ligne.get("Objectif (€)", entry*1.07),2),
            "Stop (€)": round(ligne.get("Stop (€)", entry*0.97),2),
            "Qté": round(qte,2),
            "Montant Initial (€)": round(montant,2),
            "Valeur (€)": round(montant,2),
            "P&L (%)": 0.0,
            "Rendement Net Estimé (%)": ((ligne.get("Objectif (€)", entry*1.07)/entry)-1)*100 - (2/montant)*100
        }
        pf = pd.concat([pf, pd.DataFrame([new_row])], ignore_index=True)
        pf.to_json(DATA_PATH_VIRTUEL, orient="records", indent=2, force_ascii=False)
        st.success(f"✅ {ligne.get('Société')} ajoutée au portefeuille virtuel.")
else:
    st.info("Aucune donnée IA disponible.")
