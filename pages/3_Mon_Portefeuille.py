# -*- coding: utf-8 -*-
import os, json, numpy as np, pandas as pd, altair as alt, streamlit as st
from lib import (
    fetch_prices, compute_metrics, price_levels_from_row, decision_label_from_row,
    style_variations, company_name_from_ticker, get_profile_params
)

st.set_page_config(page_title="Mon Portefeuille", page_icon="💼", layout="wide")
st.title("💼 Mon Portefeuille — IA Long Terme")

# ---------------- Chargement du portefeuille ----------------
DATA_PATH = "data/portfolio.json"
os.makedirs("data", exist_ok=True)
if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=["Ticker", "Type", "Qty", "PRU", "Name"]).to_json(DATA_PATH, orient="records", indent=2)

try:
    pf = pd.read_json(DATA_PATH)
except Exception:
    pf = pd.DataFrame(columns=["Ticker","Type","Qty","PRU","Name"])

# ---------------- Analyse IA ----------------
if pf.empty:
    st.info("Ajoute des valeurs à ton portefeuille pour commencer.")
    st.stop()

tickers = pf["Ticker"].dropna().unique().tolist()
hist_full = fetch_prices(tickers, days=240)
met = compute_metrics(hist_full)
merged = pf.merge(met, on="Ticker", how="left")

profil = "Neutre"
volmax = get_profile_params(profil)["vol_max"]

# ---------------- Construction du tableau ----------------
rows = []
for _, r in merged.iterrows():
    px = float(r.get("Close", np.nan))
    qty = float(r.get("Qty", 0))
    pru = float(r.get("PRU", np.nan))
    name = r.get("Name") or company_name_from_ticker(r.get("Ticker"))
    ma120, ma240 = float(r.get("MA120", np.nan)), float(r.get("MA240", np.nan))

    levels = price_levels_from_row(r, profil)
    dec = decision_label_from_row(r, held=True, vol_max=volmax)

    # 🌱 Indicateur LT
    if np.isfinite(ma120) and np.isfinite(ma240):
        if px > ma120 > ma240:
            cap = "🌱"
        elif px < ma120 < ma240:
            cap = "🌧"
        else:
            cap = "⚖️"
    else:
        cap = "⚖️"

    val = px * qty if np.isfinite(px) else np.nan
    gain = (px - pru) * qty if np.isfinite(px) and np.isfinite(pru) else np.nan

    rows.append({
        "Type": r["Type"], "Nom": name, "Ticker": r["Ticker"],
        "Cours (€)": round(px,2) if np.isfinite(px) else None,
        "Qté": qty, "PRU (€)": round(pru,2) if np.isfinite(pru) else None,
        "Valeur (€)": round(val,2) if np.isfinite(val) else None,
        "Gain/Perte (€)": round(gain,2) if np.isfinite(gain) else None,
        "Tendance LT": cap,
        "Entrée (€)": levels["entry"], "Objectif (€)": levels["target"], "Stop (€)": levels["stop"],
        "Décision IA": dec
    })

out = pd.DataFrame(rows)
st.dataframe(style_variations(out, ["Gain/Perte (€)"]), use_container_width=True, hide_index=True)

# ---------------- Synthèse ----------------
total_gain = out["Gain/Perte (€)"].sum()
total_val = out["Valeur (€)"].sum()
perf_pct = (total_gain / (total_val - total_gain) * 100) if total_val > 0 else 0

st.markdown(f"""
### 📊 Synthèse
**Gain total :** {total_gain:+.2f} € ({perf_pct:+.2f}%)  
**Portefeuille global :** {total_val:.2f} €
""")
