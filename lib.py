# -*- coding: utf-8 -*-
import os, json, math, requests, numpy as np, pandas as pd, yfinance as yf
from functools import lru_cache

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
def fetch_prices_cached(tickers_tuple, period="180d"):
    tickers = list(tickers_tuple)
    if not tickers: return pd.DataFrame()
    try:
        data = yf.download(
            tickers, period=period, interval="1d",
            auto_adjust=True, group_by="ticker", threads=False, progress=False
        )
    except Exception:
        return pd.DataFrame()
    if data is None or len(data) == 0: return pd.DataFrame()
    frames=[]
    if {"Open","High","Low","Close"}.issubset(data.columns):
        df=data.copy(); df["Ticker"]=tickers[0]; frames.append(df)
    else:
        for t in tickers:
            if t in data and isinstance(data[t],pd.DataFrame):
                df=data[t].copy(); df["Ticker"]=t; frames.append(df)
    out=pd.concat(frames); out.reset_index(inplace=True)
    return out

def fetch_prices(tickers, days=180):
    return fetch_prices_cached(tuple(tickers), period=f"{days}d")

# =========================
# MÉTRIQUES TECHNIQUES (MA20 / 50 / 120 / 240)
# =========================
def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Retourne 1 ligne par ticker avec indicateurs CT+LT"""
    if df is None or df.empty: 
        return pd.DataFrame(columns=["Ticker","Date","Close","MA20","MA50","MA120","MA240","pct_1d","pct_7d","pct_30d"])
    df=df.copy()
    if "Date" not in df.columns:
        df=df.reset_index().rename(columns={df.index.name or "index":"Date"})
    df["Ticker"]=df["Ticker"].astype(str).str.upper()
    df=df.sort_values(["Ticker","Date"])
    # Moyennes mobiles
    for n in [20,50,120,240]:
        df[f"MA{n}"]=df.groupby("Ticker")["Close"].transform(lambda s: s.rolling(n,min_periods=5).mean())
    last=df.groupby("Ticker").tail(1)[["Ticker","Date","Close","MA20","MA50","MA120","MA240"]].copy()

    # Gaps CT + LT
    for n in [20,50,120,240]:
        last[f"gap{n}"]=np.where(np.isfinite(last[f"MA{n}"]) & (last[f"MA{n}"]!=0),
                                 last["Close"]/last[f"MA{n}"]-1,np.nan)
    last["ct_trend_score"]=0.6*last["gap20"]+0.4*last["gap50"]
    last["lt_trend_score"]=0.5*last["gap120"]+0.5*last["gap240"]

    # Variation calendaire approximative
    last["pct_1d"]=np.nan; last["pct_7d"]=np.nan; last["pct_30d"]=np.nan
    return last

# =========================
# TENDANCE LONG TERME (LT)
# =========================
def trend_label_LT(row):
    """Renvoie 🌱 / ⚖️ / 🌧 selon MA120/MA240"""
    ma120, ma240, px = row.get("MA120"), row.get("MA240"), row.get("Close")
    if not all(map(np.isfinite,[ma120,ma240,px])): return "⚪️"
    if px>ma120>ma240: return "🌱"
    if px<ma120<ma240: return "🌧"
    return "⚖️"
