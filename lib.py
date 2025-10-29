# -*- coding: utf-8 -*-
import os, json, math, requests, numpy as np, pandas as pd, yfinance as yf
from functools import lru_cache
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

# =========================
# FICHIERS & PRESETS
# =========================
DATA_DIR = "data"
MAPPING_PATH = os.path.join(DATA_DIR, "id_mapping.json")
WL_PATH = os.path.join(DATA_DIR, "watchlist_ls.json")
PROFILE_PATH = os.path.join(DATA_DIR, "profile.json")
LAST_SEARCH_PATH = os.path.join(DATA_DIR, "last_search.json")

os.makedirs(DATA_DIR, exist_ok=True)
_defaults = [
    (MAPPING_PATH, {}),
    (WL_PATH, []),
    (PROFILE_PATH, {"profil": "Neutre"}),
    (LAST_SEARCH_PATH, {"last": "TTE.PA"}),
]
for p, default in _defaults:
    if not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(default, f)

UA = {"User-Agent": "Mozilla/5.0"}

# =========================
# SENTIMENT (VADER)
# =========================
try:
    nltk.data.find("sentiment/vader_lexicon.zip")
except LookupError:
    try:
        nltk.download("vader_lexicon")
    except Exception:
        pass

try:
    SIA = SentimentIntensityAnalyzer()
except Exception:
    SIA = None

# =========================
# PROFILS IA
# =========================
PROFILE_PARAMS = {
    "Agressif": {"vol_max": 0.08, "target_mult": 1.10, "stop_mult": 0.92, "entry_mult": 0.990},
    "Neutre":   {"vol_max": 0.05, "target_mult": 1.07, "stop_mult": 0.95, "entry_mult": 0.990},
    "Prudent":  {"vol_max": 0.03, "target_mult": 1.05, "stop_mult": 0.97, "entry_mult": 0.995},
}

def get_profile_params(profile: str):
    return PROFILE_PARAMS.get(profile or "Neutre", PROFILE_PARAMS["Neutre"])

def load_profile():
    try:
        return json.load(open(PROFILE_PATH, "r", encoding="utf-8")).get("profil", "Neutre")
    except Exception:
        return "Neutre"

def save_profile(p):
    try:
        json.dump({"profil": p}, open(PROFILE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_last_search():
    try:
        return json.load(open(LAST_SEARCH_PATH, "r", encoding="utf-8")).get("last", "")
    except Exception:
        return ""

def save_last_search(t):
    try:
        json.dump({"last": t}, open(LAST_SEARCH_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass

# =========================
# MAPPING / WATCHLIST
# =========================
def load_mapping():
    try:
        return json.load(open(MAPPING_PATH, "r", encoding="utf-8"))
    except Exception:
        return {}

def save_mapping(m):
    json.dump(m, open(MAPPING_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def load_watchlist_ls():
    try:
        return json.load(open(WL_PATH, "r", encoding="utf-8"))
    except Exception:
        return []

def save_watchlist_ls(lst):
    json.dump(lst, open(WL_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# =========================
# LS EXCHANGE → YAHOO
# =========================
def _norm(s): return (s or "").strip().upper()

_PARIS = {"AIR","ORA","MC","TTE","BNP","SGO","ENGI","SU","DG","ACA","GLE","RI","KER","HO","EN","CAP","AI","PUB","VIE","VIV","STM"}

def guess_yahoo_from_ls(ticker: str):
    if not ticker: return None
    t = _norm(ticker)
    if "." in t and not t.endswith(".LS"):
        return t
    if t.endswith(".LS"):
        return f"{t[:-3]}.L"
    if t == "TOTB":
        return "TOTB.F"
    if t.endswith("B") and not t.endswith("AB"):
        return f"{t}.F"
    if t in _PARIS:
        return f"{t}.PA"
    if len(t) <= 6 and t.isalpha():
        return f"{t}.PA"
    return t

def maybe_guess_yahoo(s):
    s = _norm(s)
    m = load_mapping().get(s)
    return m or guess_yahoo_from_ls(s)

def resolve_identifier(id_or_ticker):
    raw = _norm(id_or_ticker)
    if not raw: return None, {}
    mapping = load_mapping()
    if raw in mapping:
        return mapping[raw], {"source": "mapping"}
    guess = maybe_guess_yahoo(raw)
    if guess:
        try:
            hist = yf.download(guess, period="5d", interval="1d", auto_adjust=False, progress=False, threads=False)
            if not hist.empty:
                mapping[raw] = guess
                save_mapping(mapping)
                return guess, {"source": "heuristic"}
        except Exception:
            pass
    return None, {}

# =========================
# PRIX & MÉTRIQUES (ajout MA120/MA240)
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
            if t in data and isinstance(data[t], pd.DataFrame):
                df=data[t].copy(); df["Ticker"]=t; frames.append(df)
    if not frames: return pd.DataFrame()
    out=pd.concat(frames); out.reset_index(inplace=True)
    return out

def fetch_prices(tickers, days=240):
    return fetch_prices_cached(tuple(tickers), period=f"{days}d")

def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute MA20, MA50, MA120, MA240, ATR14, tendances et variations."""
    cols=["Ticker","Date","Close","ATR14","MA20","MA50","MA120","MA240","trend_score","pct_1d","pct_7d","pct_30d"]
    if df is None or df.empty: return pd.DataFrame(columns=cols)
    df=df.copy()
    if "Date" not in df.columns:
        df=df.reset_index().rename(columns={df.index.name or "index":"Date"})
    need={"Ticker","Date","High","Low","Close"}
    if need - set(df.columns): return pd.DataFrame(columns=cols)

    df["Ticker"]=df["Ticker"].astype(str).str.upper()
    df=df.sort_values(["Ticker","Date"])
    df["PrevClose"]=df.groupby("Ticker")["Close"].shift(1)
    df["TR"]=np.maximum(df["High"]-df["Low"],
                        np.maximum((df["High"]-df["PrevClose"]).abs(), (df["Low"]-df["PrevClose"]).abs()))
    df["ATR14"]=df.groupby("Ticker")["TR"].transform(lambda s:s.rolling(14,min_periods=5).mean())
    for n in [20,50,120,240]:
        df[f"MA{n}"]=df.groupby("Ticker")["Close"].transform(lambda s:s.rolling(n,min_periods=5).mean())

    last=df.groupby("Ticker").tail(1)[["Ticker","Date","Close","ATR14","MA20","MA50","MA120","MA240"]].copy()

    # Gaps et score tendance
    def safe_gap(row,a,b): 
        return row[a]/row[b]-1 if pd.notna(row[a]) and pd.notna(row[b]) and row[b]!=0 else np.nan

    last["gap20"]=last.apply(lambda r:safe_gap(r,"Close","MA20"),axis=1)
    last["gap50"]=last.apply(lambda r:safe_gap(r,"Close","MA50"),axis=1)
    last["gap120"]=last.apply(lambda r:safe_gap(r,"Close","MA120"),axis=1)
    last["gap240"]=last.apply(lambda r:safe_gap(r,"Close","MA240"),axis=1)
    last["trend_score"]=(
        0.4*last["gap20"] + 0.3*last["gap50"] + 0.2*last["gap120"] + 0.1*last["gap240"]
    )
    return last.reset_index(drop=True)

# =========================
# DÉCISION IA LONG TERME
# =========================
def decision_label_from_row(row, held=False, vol_max=0.05):
    """Prend en compte MA20 / MA50 / MA120 / MA240 pour une décision IA long terme."""
    px=float(row.get("Close", math.nan))
    ma20, ma50, ma120, ma240 = [float(row.get(f"MA{n}", math.nan)) for n in [20,50,120,240]]
    atr=float(row.get("ATR14", math.nan)) if pd.notna(row.get("ATR14", math.nan)) else math.nan
    pru=float(row.get("PRU", math.nan)) if "PRU" in row else math.nan
    if not math.isfinite(px): return "👁️ Surveiller"
    vol=(atr/px) if (math.isfinite(atr) and px>0) else 0.03

    # Tendance globale : comptage du nombre de MAs sous le cours
    ma_values=[ma for ma in [ma20,ma50,ma120,ma240] if math.isfinite(ma)]
    trend_strength = sum(px>=ma for ma in ma_values)

    score=0.0
    score += 0.4*(trend_strength/len(ma_values) - 0.5)  # pondération selon tendance long terme
    if math.isfinite(pru) and pru>0:
        score += 0.2*(1 if px>pru*1.02 else -1 if px<pru*0.98 else 0)
    score += 0.4*(-1 if vol>vol_max else 1)

    if trend_strength==4 and px>ma240:
        return "🟢 Acheter LT"
    if trend_strength<=1 and px<ma240:
        return "🚫 Éviter LT"
    if held:
        if score>0.5: return "🟢 Renforcer"
        if score<-0.2: return "🔴 Alléger"
        return "🟠 Conserver"
    else:
        if score>0.3: return "🟢 Acheter"
        if score<-0.2: return "🚫 Éviter"
        return "👁️ Surveiller"

# =========================
# NIVEAUX DE PRIX
# =========================
def price_levels_from_row(row, profile="Neutre"):
    p=get_profile_params(profile)
    px=float(row.get("Close", math.nan))
    ma50=float(row.get("MA50", math.nan))
    ma120=float(row.get("MA120", math.nan))
    base = np.nanmean([v for v in [ma50, ma120, px] if pd.notna(v)])
    if not math.isfinite(base): return {"entry":math.nan,"target":math.nan,"stop":math.nan}
    return {
        "entry": round(base*p["entry_mult"],2),
        "target": round(base*p["target_mult"],2),
        "stop":   round(base*p["stop_mult"],2)
    }

# =========================
# STYLE TABLES
# =========================
def style_variations(df, cols):
    def color_var(v):
        if pd.isna(v): return ""
        if v>0: return "background-color:#e8f5e9; color:#0b8f3a"
        if v<0: return "background-color:#ffebee; color:#d5353a"
        return "background-color:#e8f0fe; color:#1e88e5"
    sty=df.style
    for c in cols:
        if c in df.columns:
            sty=sty.applymap(color_var, subset=[c])
    return sty
