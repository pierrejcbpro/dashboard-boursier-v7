# -*- coding: utf-8 -*-
"""
v8.1 — Mon Portefeuille IA stricte & Bench Total/PEA/CTO (ROBUSTE Yahoo)
- Structure type V6.9 conservée (recherche, convertisseur, tableau éditable)
- IA stricte (held=True)
- Décision IA + 🎯 Priorité + Proximité + emojis + Tendance LT
- Résout/valide les tickers Yahoo (fallback PEA -> .PA + test fetch 2j)
- Diagnostic des tickers KO + tickers manquants après download
- Synthèse PEA/CTO/Total
- Benchmark comparatif (3 messages: Total, PEA, CTO) + chart
- Styles sûrs (pas de crash pandas styler)
"""

import os, json, numpy as np, pandas as pd, altair as alt, streamlit as st
from lib import (
    fetch_prices, compute_metrics, price_levels_from_row, decision_label_from_row,
    company_name_from_ticker, get_profile_params, load_profile,
    resolve_identifier, find_ticker_by_name, load_mapping, save_mapping, maybe_guess_yahoo
)

# ==============================
# CONFIG APP
# ==============================
st.set_page_config(page_title="Mon Portefeuille", page_icon="💼", layout="wide")
st.title("💼 Mon Portefeuille — IA stricte & benchmark (robuste Yahoo)")

DATA_PATH = "data/portfolio.json"
os.makedirs("data", exist_ok=True)

# ==============================
# CHARGEMENT / INIT FICHIER
# ==============================
if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=["Ticker", "Type", "Qty", "PRU", "Name"]).to_json(
        DATA_PATH, orient="records", indent=2, force_ascii=False
    )

try:
    pf = pd.read_json(DATA_PATH)
except Exception:
    pf = pd.DataFrame(columns=["Ticker", "Type", "Qty", "PRU", "Name"])

for c in ["Ticker", "Type", "Qty", "PRU", "Name"]:
    if c not in pf.columns:
        pf[c] = "" if c in ("Ticker", "Type", "Name") else 0.0

# ==============================
# SIDEBAR : Période & Benchmark
# ==============================
periode = st.sidebar.radio("Période graphique", ["1 jour", "7 jours", "30 jours"], index=0)
days = {"1 jour": 2, "7 jours": 10, "30 jours": 35}[periode]

bench_name = st.sidebar.selectbox("Indice de comparaison", ["CAC 40", "DAX", "S&P 500", "NASDAQ 100"], index=0)
bench_map = {"CAC 40": "^FCHI", "DAX": "^GDAXI", "S&P 500": "^GSPC", "NASDAQ 100": "^NDX"}
bench = bench_map[bench_name]

st.sidebar.markdown("---")
st.sidebar.caption("Profil IA chargé automatiquement via lib.load_profile().")

# ==============================
# BARRE D’ACTIONS : Sauvegarde / Reset / Import/Export
# ==============================
c1, c2, c3, c4 = st.columns(4)
with c1:
    if st.button("💾 Sauvegarder"):
        pf.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
        st.success("✅ Sauvegardé.")

with c2:
    if st.button("♻️ Réinitialiser"):
        try:
            os.remove(DATA_PATH)
        except FileNotFoundError:
            pass
        pd.DataFrame(columns=["Ticker", "Type", "Qty", "PRU", "Name"]).to_json(
            DATA_PATH, orient="records", indent=2, force_ascii=False
        )
        st.success("Fichier réinitialisé.")
        st.rerun()

with c3:
    st.download_button(
        "⬇️ Exporter JSON",
        json.dumps(pf.to_dict(orient="records"), ensure_ascii=False, indent=2),
        file_name="portfolio.json",
        mime="application/json",
    )

with c4:
    up = st.file_uploader("📥 Importer JSON", type=["json"], label_visibility="collapsed")
    if up:
        try:
            imp = pd.DataFrame(json.load(up))
            for c in ["Ticker", "Type", "Qty", "PRU", "Name"]:
                if c not in imp.columns:
                    imp[c] = "" if c in ("Ticker", "Type", "Name") else 0.0
            imp.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
            st.success("✅ Importé.")
            st.rerun()
        except Exception as e:
            st.error(f"Import impossible : {e}")

st.divider()

# ==============================
# CONVERTISSEUR LS → Yahoo
# ==============================
with st.expander("🔁 Convertisseur LS Exchange → Yahoo"):
    cA, cB, cC = st.columns(3)
    with cA:
        ls = st.text_input("Ticker LS Exchange (ex: TOTB)", "")
    with cB:
        if st.button("🔍 Convertir", key="convert_ls"):
            if not ls.strip():
                st.warning("Indique un ticker.")
            else:
                y = maybe_guess_yahoo(ls)
                if y:
                    st.session_state["conv_pair"] = (ls.upper(), y)
                    st.success(f"{ls.upper()} → {y}")
                else:
                    st.warning("Aucune correspondance trouvée.")
    with cC:
        if st.button("✅ Enregistrer mapping", key="save_map"):
            pair = st.session_state.get("conv_pair")
            if not pair:
                st.warning("Aucune conversion active.")
            else:
                src, dst = pair
                m = load_mapping()
                m[src] = dst
                save_mapping(m)
                st.success(f"Ajout mapping : {src} → {dst}")

st.divider()

# ==============================
# RECHERCHE / AJOUT RAPIDE
# ==============================
with st.expander("🔎 Recherche par nom / ISIN / WKN / Ticker"):
    q = st.text_input("Nom ou identifiant", "")
    t = st.selectbox("Type", ["PEA", "CTO"])
    qty = st.number_input("Qté", min_value=0.0, step=1.0)
    if st.button("Rechercher", key="search_add"):
        if not q.strip():
            st.warning("Entre un terme.")
        else:
            sym, _meta = resolve_identifier(q)
            if sym:
                st.session_state["search_res"] = [{"symbol": sym, "shortname": company_name_from_ticker(sym)}]
            else:
                st.session_state["search_res"] = find_ticker_by_name(q) or []

    res = st.session_state.get("search_res", [])
    if res:
        labels = [f"{r['symbol']} — {r.get('shortname','')}" for r in res]
        sel = st.selectbox("Résultats", labels)
        if st.button("➕ Ajouter", key="add_from_search"):
            i = labels.index(sel)
            sym = res[i]["symbol"]
            nm = res[i].get("shortname", sym)
            pf = pd.concat([pf, pd.DataFrame([{
                "Ticker": sym.upper(), "Type": t, "Qty": qty, "PRU": 0.0, "Name": nm
            }])], ignore_index=True)
            pf.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
            st.success(f"Ajouté : {nm} ({sym})")
            st.rerun()

st.divider()

# ==============================
# TABLEAU PRINCIPAL (éditable)
# ==============================
st.subheader("📝 Mon Portefeuille")
edited = st.data_editor(
    pf, num_rows="dynamic", use_container_width=True, hide_index=True,
    column_config={
        "Ticker": st.column_config.TextColumn("Ticker"),
        "Type": st.column_config.SelectboxColumn("Type", options=["PEA", "CTO"]),
        "Qty": st.column_config.NumberColumn("Qté"),
        "PRU": st.column_config.NumberColumn("PRU (€)", format="%.2f"),
        "Name": st.column_config.TextColumn("Nom"),
    },
    key="portfolio_editor",
)

cS1, cS2 = st.columns(2)
with cS1:
    if st.button("💾 Enregistrer Modifs", key="save_edits"):
        edited2 = edited.copy()
        edited2["Ticker"] = edited2["Ticker"].astype(str).str.upper()
        edited2.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
        st.success("✅ Sauvegardé.")
        st.rerun()
with cS2:
    if st.button("🔄 Rafraîchir", key="refresh_all"):
        st.cache_data.clear()
        st.rerun()

if edited.empty:
    st.info("Ajoute des actions pour commencer.")
    st.stop()

# ==============================
# ANALYSE IA (strict) + METRICS  — ROBUSTE Yahoo
# ==============================

edited = edited.copy()
edited["Ticker"] = edited["Ticker"].astype(str).str.strip().str.upper()
edited["Type"] = edited["Type"].astype(str).str.strip().str.upper()
edited = edited[edited["Ticker"] != ""]  # retire les tickers vides

if edited.empty:
    st.info("Aucun ticker valide dans le portefeuille (lignes vides).")
    st.stop()

def resolve_yahoo(row) -> str | None:
    tkr = str(row.get("Ticker", "")).strip().upper()
    if not tkr:
        return None

    # 1) heuristique principale
    y = None
    try:
        y = maybe_guess_yahoo(tkr)
    except Exception:
        y = None
    y = y.strip() if isinstance(y, str) else ""

    # 2) candidats fallback
    cands = []
    if y:
        cands.append(y)

    if "." in tkr or "^" in tkr:
        cands.append(tkr)
    else:
        tp = str(row.get("Type", "")).upper()
        if tp == "PEA":
            cands.append(f"{tkr}.PA")  # fallback simple PEA
        cands.append(tkr)

    # dédoublonnage
    seen = set()
    cands = [x for x in cands if x and not (x in seen or seen.add(x))]

    # 3) validation rapide : un fetch 2 jours (évite les faux tickers)
    for cand in cands:
        try:
            tmp = fetch_prices([cand], days=2)
            if isinstance(tmp, pd.DataFrame) and (not tmp.empty) and ("Close" in tmp.columns):
                if tmp["Close"].dropna().shape[0] > 0:
                    return cand
        except Exception:
            pass

    return None

edited["Yahoo"] = edited.apply(resolve_yahoo, axis=1)

bad_rows = edited[edited["Yahoo"].isna()][["Ticker", "Type", "Name"]].copy()
if not bad_rows.empty:
    st.warning("⚠️ Yahoo introuvable pour ces lignes (à corriger / mapper LS→Yahoo) :")
    st.dataframe(bad_rows, use_container_width=True, hide_index=True)

tickers = edited["Yahoo"].dropna().astype(str).unique().tolist()
if not tickers:
    st.error("Aucun ticker Yahoo valide après normalisation.")
    st.stop()

# 4) Téléchargement robuste (240j pour LT)
hist_full = fetch_prices(tickers, days=240)
if not isinstance(hist_full, pd.DataFrame) or hist_full.empty:
    st.error("Téléchargement des prix vide. Vérifie la connectivité et/ou les tickers.")
    st.stop()

# Diagnostic : tickers manquants dans le download
if "Ticker" in hist_full.columns:
    got = set(hist_full["Ticker"].astype(str).unique().tolist())
    missing = sorted(list(set(tickers) - got))
    if missing:
        st.warning("⚠️ Yahoo n’a pas renvoyé de données pour : " + ", ".join(missing))

# 5) Calcul métriques sur ces tickers Yahoo
met = compute_metrics(hist_full)
if not isinstance(met, pd.DataFrame) or met.empty:
    st.error("Métriques vides après téléchargement. Possible blocage Yahoo temporaire.")
    st.stop()

# 6) Merge propre
met = met.copy()
met["Ticker"] = met["Ticker"].astype(str).str.strip()
edited["Yahoo"] = edited["Yahoo"].astype(str).str.strip()

merged = edited.merge(met, left_on="Yahoo", right_on="Ticker", how="left", suffixes=("", "_px"))

profil = load_profile()
volmax = get_profile_params(profil)["vol_max"]

rows = []
for _, r in merged.iterrows():
    tkr_orig = r.get("Ticker_x") if "Ticker_x" in r else r.get("Ticker")
    if pd.isna(tkr_orig):
        tkr_orig = r.get("Ticker") or r.get("Yahoo")
    tkr_orig = str(tkr_orig)

    name = r.get("Name") or company_name_from_ticker(r.get("Yahoo"))
    px = float(r.get("Close", np.nan))
    qty = float(r.get("Qty", 0))
    pru = float(r.get("PRU", np.nan))

    levels = price_levels_from_row(r, profil)
    dec = decision_label_from_row(r, held=True, vol_max=volmax)

    val = px * qty if np.isfinite(px) else np.nan
    gain = (px - pru) * qty if (np.isfinite(px) and np.isfinite(pru)) else np.nan
    perf = ((px / pru) - 1) * 100 if (np.isfinite(px) and np.isfinite(pru) and pru > 0) else np.nan

    # LT trend (MA120 vs MA240)
    ma120, ma240 = float(r.get("MA120", np.nan)), float(r.get("MA240", np.nan))
    trend_icon = "🌱" if (np.isfinite(ma120) and np.isfinite(ma240) and ma120 > ma240) else (
        "🌧" if (np.isfinite(ma120) and np.isfinite(ma240) and ma120 < ma240) else "⚖️"
    )

    entry, target, stop = levels.get("entry", np.nan), levels.get("target", np.nan), levels.get("stop", np.nan)

    prox = ((px / entry) - 1) * 100 if (np.isfinite(px) and np.isfinite(entry) and entry > 0) else np.nan
    if pd.isna(prox):
        emoji = "⚪"
    else:
        emoji = "🟢" if abs(prox) <= 2 else ("⚠️" if abs(prox) <= 5 else "🔴")

    # 🎯 Priorité d'action
    if np.isfinite(px) and np.isfinite(target) and px >= target:
        priority = "🎯 Vendre"
    elif np.isfinite(perf) and perf > 12 and trend_icon != "🌱":
        priority = "⚖️ Alléger"
    elif np.isfinite(px) and np.isfinite(stop) and px <= stop:
        priority = "🚨 Couper"
    else:
        priority = "✅ Conserver"

    rows.append({
        "Nom": name,
        "Ticker": tkr_orig,              # saisi
        "Yahoo": r.get("Yahoo"),         # debug
        "Type": r.get("Type"),
        "Décision IA": dec,
        "🎯 Priorité": priority,
        "Cours (€)": round(px, 2) if np.isfinite(px) else None,
        "Qté": qty,
        "PRU (€)": round(pru, 2) if np.isfinite(pru) else None,
        "Valeur (€)": round(val, 2) if np.isfinite(val) else None,
        "Gain (€)": round(gain, 2) if np.isfinite(gain) else None,
        "Perf%": round(perf, 2) if np.isfinite(perf) else None,
        "Entrée (€)": entry,
        "Objectif (€)": target,
        "Stop (€)": stop,
        "Proximité (%)": round(prox, 2) if np.isfinite(prox) else None,
        "Signal Entrée": emoji,
        "Tendance LT": trend_icon,
    })

out = pd.DataFrame(rows)

# ==============================
# STYLES SÛRS
# ==============================
def sty_dec(v):
    s = str(v)
    if "Acheter" in s:
        return "background-color:rgba(0,180,0,0.18);font-weight:600;"
    if "Vendre" in s:
        return "background-color:rgba(255,0,0,0.18);font-weight:600;"
    if "Surveiller" in s:
        return "background-color:rgba(0,90,255,0.18);font-weight:600;"
    if "Garder" in s:
        return "background-color:rgba(0,120,255,0.12);"
    return ""

def sty_priority(v):
    s = str(v)
    if "Vendre" in s:
        return "background-color:#ffebee;color:#b71c1c;font-weight:600;"
    if "Alléger" in s:
        return "background-color:#fff8e1;color:#a67c00;font-weight:600;"
    if "Couper" in s:
        return "background-color:#ffe0e0;color:#a80000;font-weight:600;"
    return "background-color:#e8f5e9;color:#0b8043;font-weight:600;"

def sty_prox(v):
    if pd.isna(v):
        return ""
    try:
        x = float(v)
    except Exception:
        return ""
    if abs(x) <= 2:
        return "background-color:#e8f5e9;color:#0b8043;font-weight:600;"
    if abs(x) <= 5:
        return "background-color:#fff8e1;color:#a67c00;"
    return "background-color:#ffebee;color:#b71c1c;"

styler = out.style
if "Décision IA" in out.columns:
    styler = styler.applymap(sty_dec, subset=["Décision IA"])
if "🎯 Priorité" in out.columns:
    styler = styler.applymap(sty_priority, subset=["🎯 Priorité"])
if "Proximité (%)" in out.columns:
    styler = styler.applymap(sty_prox, subset=["Proximité (%)"])

st.dataframe(styler, use_container_width=True, hide_index=True)

# ==============================
# SYNTHÈSE PERFORMANCE
# ==============================
def synthese_perf(df, t):
    sub = df[df["Type"] == t]
    if sub.empty:
        return 0.0, 0.0
    val = float(sub["Valeur (€)"].sum())
    gain = float(sub["Gain (€)"].sum())
    pct = (gain / (val - gain) * 100) if (val - gain) != 0 else 0.0
    return gain, float(pct)

pea_gain, pea_pct = synthese_perf(out, "PEA")
cto_gain, cto_pct = synthese_perf(out, "CTO")
tot_gain = float(out["Gain (€)"].sum())
tot_val = float(out["Valeur (€)"].sum())
tot_pct = (tot_gain / (tot_val - tot_gain) * 100) if tot_val > 0 else 0.0

st.markdown(f"""
### 📊 Synthèse {periode}
**PEA** : {pea_gain:+.2f} € ({pea_pct:+.2f}%)  
**CTO** : {cto_gain:+.2f} € ({cto_pct:+.2f}%)  
**Total** : {tot_gain:+.2f} € ({tot_pct:+.2f}%)
""")

st.divider()

# ==============================
# BENCHMARK : Total + PEA + CTO (3 messages)
# ==============================
st.subheader(f"📈 Portefeuille vs {bench_name} ({periode})")

# On benchmarke sur les tickers Yahoo valides
bench_tickers = edited["Yahoo"].dropna().astype(str).unique().tolist()
hist_graph = fetch_prices(bench_tickers + [bench], days=days)

if not isinstance(hist_graph, pd.DataFrame) or hist_graph.empty or "Date" not in hist_graph.columns:
    st.caption("Pas assez d'historique.")
else:
    df_val = []
    # On calcule les valeurs à partir des tickers Yahoo (et non le ticker original)
    for _, r in edited.iterrows():
        y = str(r.get("Yahoo") or "").strip()
        if not y:
            continue
        q = float(r.get("Qty", 0))
        tp = str(r.get("Type", "")).strip().upper()

        d = hist_graph[hist_graph["Ticker"] == y].copy()
        if d.empty:
            continue
        d["Valeur"] = d["Close"] * q
        d["Type"] = tp  # PEA / CTO
        df_val.append(d[["Date", "Valeur", "Type"]])

    if df_val:
        D = pd.concat(df_val, ignore_index=True)
        agg = D.groupby(["Date", "Type"]).agg({"Valeur": "sum"}).reset_index()  # PEA / CTO
        tot = agg.groupby("Date")["Valeur"].sum().reset_index().assign(Type="Total")  # TOTAL

        bmk = hist_graph[hist_graph["Ticker"] == bench].copy()
        base_val = float(tot["Valeur"].iloc[0]) if not tot.empty else 1.0
        bmk = bmk.assign(Type=bench_name, Valeur=bmk["Close"] / bmk["Close"].iloc[0] * base_val)

        full = pd.concat([agg, tot, bmk], ignore_index=True)
        base = full.groupby("Type").apply(
            lambda g: g.assign(Pct=(g["Valeur"] / g["Valeur"].iloc[0] - 1) * 100)
        ).reset_index(drop=True)

        def perf_of(t):
            try:
                return float(base[base["Type"] == t]["Pct"].iloc[-1])
            except Exception:
                return np.nan

        perf_total = perf_of("Total")
        perf_pea = perf_of("PEA")
        perf_cto = perf_of("CTO")
        perf_bmk = perf_of(bench_name)

        def compare_msg(name, perf):
            if np.isnan(perf) or np.isnan(perf_bmk):
                return ""
            diff = perf - perf_bmk
            if diff > 0:
                return f"✅ **{name} surperforme** {bench_name} de **{diff:+.2f}%**."
            return f"⚠️ **{name} sous-performe** {bench_name} de **{abs(diff):.2f}%**."

        st.markdown(compare_msg("Portefeuille TOTAL", perf_total))
        st.markdown(compare_msg("PEA", perf_pea))
        st.markdown(compare_msg("CTO", perf_cto))

        chart = alt.Chart(base).mark_line().encode(
            x="Date:T",
            y=alt.Y("Pct:Q", title="Variation (%)"),
            color=alt.Color("Type:N", title=""),
            tooltip=["Date:T", "Type:N", "Pct:Q"],
        ).properties(height=380)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.caption("Portefeuille vide côté historique (ou tickers Yahoo non résolus).")

st.divider()

# ==============================
# RÉPARTITION PORTFOLIO (camembert)
# ==============================
st.subheader("📊 Répartition du portefeuille")
repart = out.groupby("Nom").agg({"Valeur (€)": "sum"}).reset_index()
if not repart.empty:
    chart = alt.Chart(repart).mark_arc(outerRadius=120).encode(
        theta="Valeur (€):Q",
        color=alt.Color("Nom:N", legend=None),
        tooltip=["Nom:N", "Valeur (€):Q"],
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.caption("Aucune donnée pour le camembert (valeurs nulles ?).")

st.caption("💡 Les décisions IA sont **strictes** (mode ‘held=True’).")
