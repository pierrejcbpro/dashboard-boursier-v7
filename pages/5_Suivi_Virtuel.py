# -*- coding: utf-8 -*-
"""
v7.6 — Suivi Virtuel IA
Simulateur de portefeuille IA (papier trading)
- Ajout automatique depuis Synthèse Flash
- Montant et frais personnalisés
- Calcul rendement net estimé et P&L %
- Comparaison CAC 40
"""

import os, json, pandas as pd, numpy as np, streamlit as st, altair as alt
from lib import fetch_prices, compute_metrics, company_name_from_ticker

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Suivi Virtuel", page_icon="💰", layout="wide")
st.title("💰 Suivi Virtuel — Portefeuille d’investissement IA")

DATA_PATH = "data/suivi_virtuel.json"
os.makedirs("data", exist_ok=True)

if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=[
        "Société","Ticker","Cours (€)","Entrée (€)","Objectif (€)","Stop (€)",
        "Qté","Montant Initial (€)","Valeur (€)","P&L (%)","Rendement Net Estimé (%)"
    ]).to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)

try:
    pf = pd.read_json(DATA_PATH)
except Exception:
    pf = pd.DataFrame(columns=[
        "Société","Ticker","Cours (€)","Entrée (€)","Objectif (€)","Stop (€)",
        "Qté","Montant Initial (€)","Valeur (€)","P&L (%)","Rendement Net Estimé (%)"
    ])

# ---------------- BARRE D’ACTIONS ----------------
cols = st.columns(4)
with cols[0]:
    if st.button("💾 Sauvegarder", key="save_pf"):
        pf.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
        st.success("✅ Sauvegardé.")
with cols[1]:
    if st.button("🗑 Réinitialiser", key="reset_pf"):
        os.remove(DATA_PATH)
        pd.DataFrame(columns=pf.columns).to_json(DATA_PATH, orient="records", indent=2)
        st.success("♻️ Réinitialisé.")
        st.rerun()
with cols[2]:
    st.download_button("⬇️ Exporter JSON", json.dumps(pf.to_dict(orient="records"), ensure_ascii=False, indent=2),
                       file_name="suivi_virtuel.json", mime="application/json", key="exp_pf")
with cols[3]:
    up = st.file_uploader("📥 Importer JSON", type=["json"], label_visibility="collapsed", key="imp_pf")
    if up:
        try:
            imp = pd.DataFrame(json.load(up))
            imp.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
            st.success("✅ Importé."); st.rerun()
        except Exception as e:
            st.error(f"Erreur import : {e}")

st.divider()

# ---------------- AJOUT MANUEL ----------------
with st.expander("➕ Ajouter une ligne manuellement"):
    c1, c2, c3 = st.columns(3)
    with c1:
        ticker = st.text_input("Ticker", "")
    with c2:
        montant = st.number_input("Montant à investir (€)", min_value=10.0, step=10.0, value=20.0)
    with c3:
        cours = st.number_input("Cours actuel (€)", min_value=0.01, step=0.01)
    if st.button("Ajouter au suivi virtuel", key="add_manual"):
        if ticker and montant and cours:
            soc = company_name_from_ticker(ticker)
            qte = (montant - 1) / cours  # 1€ de frais achat
            pf = pd.concat([
                pf,
                pd.DataFrame([{
                    "Société": soc, "Ticker": ticker, "Cours (€)": cours,
                    "Entrée (€)": cours, "Objectif (€)": cours * 1.07,
                    "Stop (€)": cours * 0.97, "Qté": qte,
                    "Montant Initial (€)": montant, "Valeur (€)": montant,
                    "P&L (%)": 0.0, "Rendement Net Estimé (%)": 0.0
                }])
            ], ignore_index=True)
            pf.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
            st.success(f"Ajouté : {soc} ({ticker})")
            st.rerun()

st.divider()

# ---------------- ANALYSE & MISE À JOUR ----------------
if pf.empty:
    st.info("Aucune position virtuelle. Ajoute une ligne ci-dessus ou depuis Synthèse Flash.")
    st.stop()

tickers = pf["Ticker"].dropna().unique().tolist()
hist = fetch_prices(tickers, days=90)
met = compute_metrics(hist)
merged = pf.merge(met, on="Ticker", how="left")

rows = []
for _, r in merged.iterrows():
    ticker = r["Ticker"]
    px = r.get("Close", np.nan)
    soc = r.get("Société") or company_name_from_ticker(ticker)
    entry = r.get("Entrée (€)", np.nan)
    qte = r.get("Qté", 0)
    if not np.isfinite(px) or not np.isfinite(entry) or entry == 0:
        continue
    val = px * qte
    pnl = ((px / entry) - 1) * 100
    rend_est = ((r["Objectif (€)"] / entry) - 1) * 100 - (2 / entry)  # 1€ achat + 1€ vente
    rows.append({
        "Société": soc, "Ticker": ticker,
        "Cours (€)": round(px, 2),
        "Entrée (€)": round(entry, 2),
        "Objectif (€)": round(r["Objectif (€)"], 2),
        "Stop (€)": round(r["Stop (€)"], 2),
        "Qté": round(qte, 2),
        "Montant Initial (€)": round(r["Montant Initial (€)"], 2),
        "Valeur (€)": round(val, 2),
        "P&L (%)": round(pnl, 2),
        "Rendement Net Estimé (%)": round(rend_est, 2)
    })

out = pd.DataFrame(rows)
if out.empty:
    st.info("Aucune donnée actualisée. Vérifie les tickers.")
    st.stop()

# ---------------- TABLEAU PRINCIPAL ----------------
def color_pnl(v):
    if pd.isna(v): return ""
    if v > 0: return "background-color:#e6f4ea; color:#0b8043"
    if v < 0: return "background-color:#ffebee; color:#b71c1c"
    return ""

st.subheader("📈 Suivi de performance virtuelle")
st.dataframe(
    out.style
        .applymap(color_pnl, subset=["P&L (%)","Rendement Net Estimé (%)"]),
    use_container_width=True, hide_index=True
)

# ---------------- SYNTHÈSE & BENCHMARK ----------------
tot_val = out["Valeur (€)"].sum()
tot_init = out["Montant Initial (€)"].sum()
perf = ((tot_val / tot_init) - 1) * 100 if tot_init else 0

st.markdown(f"""
### 📊 Synthèse
**Investi :** {tot_init:.2f} €  
**Valeur actuelle :** {tot_val:.2f} €  
**Performance globale :** {perf:+.2f} %
""")

st.divider()

# ---------------- COMPARAISON CAC 40 ----------------
st.subheader("📈 Comparatif CAC 40")
hist_bmk = fetch_prices(["^FCHI"], days=90)
if not hist_bmk.empty and "Close" in hist_bmk.columns:
    df_bmk = hist_bmk.groupby("Date")["Close"].mean().pct_change().cumsum() * 100
    perf_bmk = df_bmk.iloc[-1]
    diff = perf - perf_bmk
    if diff > 0:
        st.success(f"✅ Votre portefeuille virtuel surperforme le CAC 40 de {diff:+.2f} %.")
    else:
        st.warning(f"⚠️ Votre portefeuille virtuel sous-performe le CAC 40 de {abs(diff):.2f} %.")
else:
    st.caption("Données CAC 40 non disponibles pour la comparaison.")

chart = alt.Chart(out).mark_bar().encode(
    x="Société:N",
    y="P&L (%):Q",
    color=alt.condition(alt.datum["P&L (%)"] > 0,
                        alt.value("#0b8043"), alt.value("#b71c1c")),
    tooltip=list(out.columns)
).properties(height=320, title="Performance individuelle (%)")
st.altair_chart(chart, use_container_width=True)
