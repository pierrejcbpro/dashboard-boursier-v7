# -*- coding: utf-8 -*-
"""
lib.py — v7.4
Module central du Dash Boursier IA
- Ajout MA120 / MA240 (vision long terme)
- Intégration tendance LT 🌱⚖️🌧 sur tous les marchés
- fetch_all_markets mis à jour (CAC40 + DAX + NASDAQ + LS)
"""

import os, json, math, requests, numpy as np, pandas as pd, yfinance as yf
from functools import lru_cache

# =========================
# CONFIGURATION & DOSSIERS
# =========================
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}

# =========================
# PROFIL IA
# =========================
PROFILE_PARAMS = {
    "Agressif": {"vol_max": 0.08, "target_mult": 1.10, "stop_mult": 0.92, "entry_mult": 0.990},
    "Neutre":   {"vol_max": 0.05, "target_mult": 1.07, "stop_mult": 0.95, "entry_mult": 0.990},
    "Prudent":  {"vol_max": 0.03, "target_mult": 1.05, "stop_mult": 0.97, "entry_mult": 0.995},
}
def get_profile_params(profile: str):
    return PROFILE_PARAMS.get(profile or "Neutre", PROFILE_PARAMS["Neutre"])

# =========================
# FONCTIONS PRIX
# =========================
@lru_cache(maxsize=64)
def fetch_prices_cached(tickers_tuple, period="240d"):
    tickers=list(tickers_tuple)
    if not tickers: return pd.DataFrame()
    try:
        data=yf.download(
            tickers, period=period, interval="1d",
            auto_adjust=True, group_by="ticker",
            threads=False, progress=False
        )
    except Exception:
        return pd.DataFrame()
    if data is None or len(data)==0: return pd.DataFrame()
    frames=[]
    if {"Open","High","Low","Close"}.issubset(data.columns):
        df=data.copy(); df["Ticker"]=tickers[0]; frames.append(df)
    else:
        for t in tickers:
            if t in data and isinstance(data[t],pd.DataFrame):
                df=data[t].copy(); df["Ticker"]=t; frames.append(df)
    out=pd.concat(frames)
    out.reset_index(inplace=True)
    return out

def fetch_prices(tickers, days=240):
    return fetch_prices_cached(tuple(tickers), period=f"{days}d")

# =========================
# MÉTRIQUES TECHNIQUES (MA20 / MA50 / MA120 / MA240)
# =========================
def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule les indicateurs CT/LT et renvoie 1 ligne par ticker"""
    if df is None or df.empty:
        return pd.DataFrame(columns=[
            "Ticker","Date","Close","MA20","MA50","MA120","MA240",
            "ct_trend_score","lt_trend_score","pct_1d","pct_7d","pct_30d"
        ])
    df=df.copy()
    if "Date" not in df.columns:
        df=df.reset_index().rename(columns={df.index.name or "index":"Date"})
    df["Ticker"]=df["Ticker"].astype(str).str.upper()
    df=df.sort_values(["Ticker","Date"])
    for n in [20,50,120,240]:
        df[f"MA{n}"]=df.groupby("Ticker")["Close"].transform(lambda s:s.rolling(n,min_periods=5).mean())

    last=df.groupby("Ticker").tail(1)[["Ticker","Date","Close","MA20","MA50","MA120","MA240"]].copy()

    # Gaps CT et LT
    for n in [20,50,120,240]:
        last[f"gap{n}"]=np.where(np.isfinite(last[f"MA{n}"]) & (last[f"MA{n}"]!=0),
                                 last["Close"]/last[f"MA{n}"]-1,np.nan)
    last["ct_trend_score"]=0.6*last["gap20"]+0.4*last["gap50"]
    last["lt_trend_score"]=0.5*last["gap120"]+0.5*last["gap240"]

    return last.reset_index(drop=True)

# =========================
# TENDANCE LONG TERME (LT)
# =========================
def trend_label_LT(row):
    """Renvoie 🌱 (haussière), ⚖️ (neutre), 🌧 (baissière) selon MA120/MA240"""
    ma120, ma240, px = row.get("MA120"), row.get("MA240"), row.get("Close")
    if not all(map(np.isfinite,[ma120,ma240,px])): return "⚪️"
    if px>ma120>ma240: return "🌱"
    if px<ma120<ma240: return "🌧"
    return "⚖️"

# =========================
# INFOS BOURSIÈRES & UTILITAIRES
# =========================
@lru_cache(maxsize=512)
def company_name_from_ticker(ticker: str) -> str:
    try:
        t=yf.Ticker(ticker)
        info=t.get_info()
        return info.get("shortName") or info.get("longName") or ticker
    except Exception:
        return ticker

# =========================
# MEMBRES INDICES
# =========================
@lru_cache(maxsize=32)
def _read_tables(url: str):
    html = requests.get(url, headers=UA, timeout=15).text
    return pd.read_html(html)

def _extract_name_ticker(tables):
    table=None
    for df in tables:
        cols={str(c).lower() for c in df.columns}
        if (("company" in cols or "name" in cols) and ("ticker" in cols or "symbol" in cols)):
            table=df.copy(); break
    if table is None: table=tables[0].copy()
    table.rename(columns={c:str(c).lower() for c in table.columns}, inplace=True)
    tcol=next((c for c in table.columns if "ticker" in c or "symbol" in c), table.columns[0])
    ncol=next((c for c in table.columns if "company" in c or "name" in c), table.columns[1])
    out=table[[tcol,ncol]].copy(); out.columns=["ticker","name"]
    out["ticker"]=out["ticker"].astype(str).str.strip()
    return out.dropna().drop_duplicates(subset=["ticker"])

@lru_cache(maxsize=8)
def members_cac40():
    df=_extract_name_ticker(_read_tables("https://en.wikipedia.org/wiki/CAC_40"))
    df["ticker"]=df["ticker"].apply(lambda x: x if "." in x else f"{x}.PA")
    df["index"]="CAC 40"
    return df

# =========================
# MAPPING LS → YAHOO (simplifié)
# =========================
def maybe_guess_yahoo(s):
    s=(s or "").strip().upper()
    if not s: return None
    if s.endswith(".PA") or s.endswith(".DE") or s.endswith(".NS") or s.endswith(".L"):
        return s
    if len(s)<=6 and s.isalpha(): return s+".PA"
    return s

# =========================
# AGGRÉGATION MARCHÉS (corrigé pour inclure LT)
# =========================
def fetch_all_markets(markets, days_hist=240):
    """
    markets: liste de tuples (Indice, source)
    Retourne les tickers + indicateurs CT/LT complets
    """
    frames=[]
    for idx, _ in markets:
        if idx=="CAC 40":
            mem=members_cac40()
        elif idx=="DAX":
            mem=_extract_name_ticker(_read_tables("https://en.wikipedia.org/wiki/DAX")).assign(index="DAX")
            mem["ticker"]=mem["ticker"].apply(lambda x: x if "." in x else f"{x}.DE")
        elif idx=="NASDAQ 100":
            mem=_extract_name_ticker(_read_tables("https://en.wikipedia.org/wiki/NASDAQ-100")).assign(index="NASDAQ 100")
        elif idx=="LS Exchange":
            ls_list=[]
            try:
                with open(os.path.join(DATA_DIR,"watchlist_ls.json"),"r",encoding="utf-8") as f:
                    ls_list=json.load(f)
            except Exception: pass
            tickers=[maybe_guess_yahoo(x) or x for x in ls_list] if ls_list else []
            mem=pd.DataFrame({"ticker":tickers,"name":ls_list})
            mem["index"]="LS Exchange"
        else:
            continue

        if mem.empty: continue
        px=fetch_prices(mem["ticker"].tolist(), days=days_hist)
        if px.empty: continue
        met=compute_metrics(px).merge(mem, left_on="Ticker", right_on="ticker", how="left")
        met["Indice"]=idx

        keep=[
            "Ticker","Date","Close","MA20","MA50","MA120","MA240",
            "ct_trend_score","lt_trend_score","Indice","name"
        ]
        frames.append(met[keep])

    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()

# =========================
# IA DECISION (simplifiée)
# =========================
def decision_label_from_row(row, vol_max=0.05):
    px=float(row.get("Close", np.nan))
    ma20=float(row.get("MA20", np.nan))
    ma50=float(row.get("MA50", np.nan))
    ma120=float(row.get("MA120", np.nan))
    ma240=float(row.get("MA240", np.nan))
    if not np.isfinite(px): return "👁️ Surveiller"
    ct = "haussier" if (px>ma20>ma50) else "baissier" if (px<ma20<ma50) else "neutre"
    lt = "haussier" if (px>ma120>ma240) else "baissier" if (px<ma120<ma240) else "neutre"
    if ct=="haussier" and lt=="haussier": return "🟢 Acheter (CT+LT)"
    if ct=="baissier" and lt=="baissier": return "🔴 Vendre (CT+LT)"
    if lt=="haussier" and ct=="neutre": return "🟠 Garder"
    return "👁️ Surveiller"
