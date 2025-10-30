# -*- coding: utf-8 -*-
"""
v7.7 — Suivi virtuel IA
- Simulation des investissements IA depuis l’onglet Injection
- Calculs en temps réel : perf réelle vs perf estimée
- Stop, Objectif, Score IA conservés
"""

import os, pandas as pd, numpy as np, streamlit as st
from lib import fetch_prices, company_name_from_ticker

st.set_page_config(page_title="Suivi virtuel IA", page_icon="💹", layout="wide")
st.title("💹 Suivi virtuel des micro-investissements IA")

SAVE_PATH = "data/suivi_virtuel.json"
os.makedirs("data", exist_ok=True)

if not os.path.exists(SAVE_PATH):
    st.info("Aucune donnée de suivi virtuel pour l’instant.")
    st.stop()

try:
    df = pd.read_json(SAVE_PATH)
except Exception:
    st.error("Erreur lors du chargement du fichier de suivi.")
    st.stop()

if df.empty:
    st.info("Aucune ligne à afficher.")
    st.stop()

# Nettoyage des colonnes
for c in ["Ticker", "Entrée (€)", "Objectif (€)", "Stop (€)", "Score IA", "Rendement net estimé (%)"]:
    if c not in df.columns: df[c] = np.nan

tickers = df["Ticker"].dropna().unique().tolist()
hist = fetch_prices(tickers, days=90)
if hist.empty:
    st.warning("Données marché indisponibles pour le moment.")
    st.stop()

# Derniers cours
last = hist.sort_values("Date").groupby("Ticker").tail(1)[["Ticker","Close"]].rename(columns={"Close":"Cours actuel (€)"})
merged = df.merge(last, on="Ticker", how="left")

# Calculs de performance réelle
perf_rows = []
for _, r in merged.iterrows():
    entry, target, stop, score = r["Entrée (€)"], r["Objectif (€)"], r["Stop (€)"], r["Score IA"]
    px = r["Cours actuel (€)"]
    if np.isfinite(entry) and np.isfinite(px) and entry != 0:
        perf_pct = (px / entry - 1) * 100
        reached_stop = np.isfinite(stop) and px <= stop
        reached_target = np.isfinite(target) and px >= target
    else:
        perf_pct, reached_stop, reached_target = np.nan, False, False

    status = "✅ Objectif atteint" if reached_target else ("⛔ Stop touché" if reached_stop else "⏳ En cours")
    perf_rows.append({
        "Société": r.get("Société"),
        "Ticker": r["Ticker"],
        "Entrée (€)": entry,
        "Objectif (€)": target,
        "Stop (€)": stop,
        "Cours actuel (€)": px,
        "Score IA": score,
        "Rendement net estimé (%)": r["Rendement net estimé (%)"],
        "Perf réelle (%)": round(perf_pct, 2) if np.isfinite(perf_pct) else np.nan,
        "Statut": status,
        "Durée visée": r.get("Durée visée", "—")
    })

out = pd.DataFrame(perf_rows)

# Styles
def style_status(v):
    if "Objectif" in v: return "background-color:#e8f5e9; color:#0b8043; font-weight:600;"
    if "Stop" in v: return "background-color:#ffebee; color:#b71c1c; font-weight:600;"
    return "background-color:#fff8e1; color:#a67c00;"

def style_perf(v):
    if pd.isna(v): return ""
    if v > 5: return "background-color:#e8f5e9; color:#0b8043;"
    if v > 0: return "background-color:#fff8e1; color:#a67c00;"
    return "background-color:#ffebee; color:#b71c1c;"

st.dataframe(
    out.style
        .applymap(style_status, subset=["Statut"])
        .applymap(style_perf, subset=["Perf réelle (%)"]),
    use_container_width=True, hide_index=True
)

# Synthèse
avg_real = out["Perf réelle (%)"].mean()
avg_est = out["Rendement net estimé (%)"].mean()
diff = avg_real - avg_est

st.markdown(f"""
### 📊 Synthèse du suivi
**Perf estimée moyenne** : {avg_est:+.2f}%  
**Perf réelle moyenne** : {avg_real:+.2f}%  
**Écart IA vs marché** : {diff:+.2f}%  
""")

if diff > 0:
    st.success("L’IA surperforme ses prévisions initiales 💪")
else:
    st.warning("Les résultats réels sont inférieurs aux prévisions IA ⚠️")

# Suppression / reset
st.divider()
if st.button("🗑 Réinitialiser le suivi virtuel"):
    os.remove(SAVE_PATH)
    st.success("Données effacées."); st.rerun()
