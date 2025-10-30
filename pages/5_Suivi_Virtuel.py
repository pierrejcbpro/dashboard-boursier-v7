# -*- coding: utf-8 -*-
"""
v7.8 — Suivi Virtuel IA
- Ajout automatique depuis Synthèse Flash
- Suppression de lignes
- Comparatif CAC40
"""
import os, json, pandas as pd, numpy as np, streamlit as st, altair as alt
from lib import fetch_prices, compute_metrics, company_name_from_ticker

st.set_page_config(page_title="Suivi Virtuel", page_icon="💰", layout="wide")
st.title("💰 Suivi Virtuel — Portefeuille IA (papier trading)")

DATA_PATH = "data/suivi_virtuel.json"
os.makedirs("data", exist_ok=True)
BASE_COLUMNS = [
    "Société","Ticker","Cours (€)","Entrée (€)","Objectif (€)","Stop (€)",
    "Qté","Montant Initial (€)","Valeur (€)","P&L (%)","Rendement Net Estimé (%)"
]
if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=BASE_COLUMNS).to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
try:
    pf = pd.read_json(DATA_PATH)
except Exception:
    pf = pd.DataFrame(columns=BASE_COLUMNS)

# --- Supprimer / vider
st.subheader("🧹 Gestion du portefeuille virtuel")
if not pf.empty:
    choix_supp = st.multiselect("Sélectionne les lignes à supprimer :", pf["Société"].tolist())
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🗑 Supprimer sélection", key="del_rows"):
            pf = pf[~pf["Société"].isin(choix_supp)]
            pf.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
            st.success("✅ Lignes supprimées."); st.rerun()
    with c2:
        if st.button("♻️ Tout vider", key="wipe_all_rows"):
            pd.DataFrame(columns=BASE_COLUMNS).to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
            st.warning("🧹 Portefeuille vidé."); st.rerun()

st.divider()

if pf.empty:
    st.info("Aucune position virtuelle. Ajoute-en depuis Synthèse Flash.")
    st.stop()

# --- Colonnes manquantes
for col in BASE_COLUMNS:
    if col not in pf.columns:
        pf[col] = np.nan

if "Ticker" not in pf.columns or pf["Ticker"].dropna().empty:
    st.info("Aucune ligne valide (Ticker manquant).")
    st.stop()

tickers = pf["Ticker"].dropna().astype(str).unique().tolist()
hist = fetch_prices(tickers, days=90)
met = compute_metrics(hist)
merged = pf.merge(met, on="Ticker", how="left")

rows=[]
for _, r in merged.iterrows():
    tkr = r["Ticker"]
    px = r.get("Close", np.nan)
    if not np.isfinite(px): continue
    entry = r.get("Entrée (€)", np.nan)
    qte = r.get("Qté", 0)
    init = r.get("Montant Initial (€)", 0)
    if not np.isfinite(entry) or entry==0: continue
    soc = r.get("Société") or company_name_from_ticker(tkr)
    val = px*qte
    pnl = ((px/entry)-1)*100
    rend_est = ((r["Objectif (€)"]/entry)-1)*100 - (2/init)*100
    rows.append({
        "Société": soc, "Ticker": tkr,
        "Cours (€)": round(px,2), "Entrée (€)": round(entry,2),
        "Objectif (€)": round(r["Objectif (€)"],2), "Stop (€)": round(r["Stop (€)"],2),
        "Qté": round(qte,2), "Montant Initial (€)": round(init,2),
        "Valeur (€)": round(val,2), "P&L (%)": round(pnl,2), "Rendement Net Estimé (%)": round(rend_est,2)
    })

out = pd.DataFrame(rows)
if out.empty:
    st.info("Aucune donnée actualisée.")
    st.stop()

# --- Tableau principal
def color_pnl(v):
    if pd.isna(v): return ""
    if v > 0: return "background-color:#e6f4ea; color:#0b8043"
    if v < 0: return "background-color:#ffebee; color:#b71c1c"
    return ""

st.dataframe(out.style.applymap(color_pnl, subset=["P&L (%)","Rendement Net Estimé (%)"]),
             use_container_width=True, hide_index=True)

# --- Synthèse
tot_val = out["Valeur (€)"].sum()
tot_init = out["Montant Initial (€)"].sum()
perf = ((tot_val / tot_init) - 1) * 100 if tot_init else 0
st.markdown(f"""
### 📊 Synthèse
**Investi :** {tot_init:.2f} €  
**Valeur actuelle :** {tot_val:.2f} €  
**Performance :** {perf:+.2f} %
""")

# --- Comparatif CAC40
hist_bmk = fetch_prices(["^FCHI"], days=90)
if not hist_bmk.empty and "Close" in hist_bmk.columns:
    df_bmk = hist_bmk.groupby("Date")["Close"].mean().pct_change().cumsum()*100
    perf_bmk = df_bmk.iloc[-1]
    diff = perf - perf_bmk
    if diff > 0:
        st.success(f"✅ Portefeuille virtuel surperforme le CAC40 de {diff:+.2f}%.")
    else:
        st.warning(f"⚠️ Portefeuille virtuel sous-performe le CAC40 de {abs(diff):.2f}%.")
